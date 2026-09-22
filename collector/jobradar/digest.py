from __future__ import annotations

import argparse
import html
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

from .db import SupabaseREST
from .integration_config import apply_dashboard_integrations
from .notifications import deliver, get_settings, any_success
from .resume_match import load_candidate
from .linkresolver import is_non_job_url

URL_RE = re.compile(r'https?://\S+', re.I)
GENERIC_TITLES = {'url', 'job', 'jobs', 'job opening', 'opening', 'vacancy', 'job opportunity', 'career opportunity'}
SUPPRESS_APPLICATION_STATUSES = {
    'queued', 'review_required', 'submitted', 'applied_manual', 'interview',
    'offer', 'rejected', 'withdrawn', 'skipped',
}
FALLBACK_MIN_SCORE = max(40, min(69, int(os.getenv('NTFY_FALLBACK_MIN_SCORE', '55') or 55)))
FALLBACK_MAX_TOTAL = max(1, min(6, int(os.getenv('NTFY_FALLBACK_MAX_TOTAL', '3') or 3)))


def _clean_title(value):
    text = str(value or '').replace('\n', ' ').strip()
    text = re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', r'\1', text)
    text = URL_RE.sub('', text)
    text = re.sub(r'^\s*(?:URL\s*:|[-–—]+)\s*', '', text, flags=re.I)
    text = re.sub(r'^\s*\[[^\]]*(?:20\d{2}|liked?|reposted?)[^\]]*\]\s*', '', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip(' -–—|:[]()')
    return text[:140]


def _meaningful_title(value):
    title = _clean_title(value)
    return title if title and title.casefold() not in GENERIC_TITLES else ''


def _safe_url(value):
    url = str(value or '').strip()
    if not url.startswith(('http://', 'https://')) or is_non_job_url(url):
        return ''
    return url


def _destination(job):
    """Prefer a verified direct apply URL, then a verified-safe live job page.

    Every row in `jobs` reached this table only after the collector's URL verifier accepted its
    canonical URL. Requiring `apply_verified` as the *only* possible destination starved ntfy
    whenever a job board hid its apply button from server-side HTML. The canonical fallback is
    still passed through the strict non-job/login/legal filter.
    """
    if job.get('event_type') == 'vacancy':
        apply_url = _safe_url(job.get('apply_url'))
        if job.get('apply_verified') and apply_url:
            return apply_url
        canonical = _safe_url(job.get('canonical_url'))
        if canonical and job.get('active') is not False:
            return canonical
        return _safe_url(job.get('source_url')) if job.get('active') is not False else ''
    if job.get('official_verified'):
        return _safe_url(job.get('notification_url')) or _safe_url(job.get('canonical_url'))
    return ''


def _fallback_floor(normal_floor):
    """Never let a 70+ preference turn a healthy research run into permanent silence.

    The user's normal/category threshold remains the primary alert gate. Only when a run has no
    new primary candidates does the digest expose a tiny set of otherwise-eligible verified jobs.
    """
    return min(max(40, int(normal_floor or 70)), FALLBACK_MIN_SCORE)


def _host_label(url):
    try:
        h = (urlparse(url).hostname or '').lower().removeprefix('www.')
    except Exception:
        return 'Source'
    known = {
        'linkedin.com':'LinkedIn','naukri.com':'Naukri','indeed.com':'Indeed',
        'internshala.com':'Internshala','shine.com':'Shine','foundit.in':'Foundit',
        'cutshort.io':'Cutshort','instahyre.com':'Instahyre','wellfound.com':'Wellfound',
    }
    for domain, label in known.items():
        if h == domain or h.endswith('.'+domain):
            return label
    return h.split('.')[0].title() if h else 'Source'


def _summary(value, limit=420):
    text = html.unescape(str(value or ''))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = URL_RE.sub('', text)
    text = re.sub(r'\s+', ' ', text).strip(' -–—|')
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(' ', 1)[0].rstrip(' ,;:-') + '…'


def _walk_company(value, depth=0):
    if depth > 3:
        return ''
    if isinstance(value, dict):
        for key in ('company_name', 'company', 'employer_name', 'employer', 'organization'):
            item = value.get(key)
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                name = item.get('name')
                if isinstance(name, str) and name.strip():
                    return name.strip()
        hiring = value.get('hiringOrganization') or value.get('hiring_organization')
        if isinstance(hiring, dict) and isinstance(hiring.get('name'), str):
            return hiring['name'].strip()
        for nested in value.values():
            result = _walk_company(nested, depth + 1)
            if result:
                return result
    elif isinstance(value, list):
        for nested in value[:8]:
            result = _walk_company(nested, depth + 1)
            if result:
                return result
    return ''


def _company(job, destination):
    company = str(job.get('company') or '').strip()
    if company.casefold() not in {'', 'unknown', 'unknown company', 'web discovery', 'external job-platform discovery'}:
        return company[:120]
    raw_company = _walk_company(job.get('raw') or {})
    if raw_company and raw_company.casefold() not in {'web discovery', 'external job-platform discovery'}:
        return raw_company[:120]
    source = _host_label(destination)
    return f'Company not disclosed · {source}'


def _applied_job_ids(db, user_id):
    if not user_id:
        return set()
    try:
        rows = db.select('applications', {'select':'job_id,status', 'user_id':f'eq.{user_id}', 'limit':'1000'})
    except Exception:
        return set()
    return {
        str(x.get('job_id')) for x in rows
        if x.get('job_id') and str(x.get('status') or '') in SUPPRESS_APPLICATION_STATUSES
    }


def _prepare_candidates(rows, applied_ids, settings):
    diagnostics = Counter()
    globally_alerted = {
        str((row.get('job') or {}).get('id') or row.get('job_id') or '')
        for row in rows if row.get('alerted_at')
    }
    candidates = []
    seen_jobs = set()
    seen_destinations = set()

    for row in rows:
        job = row.get('job') or {}
        cat = row.get('category') or {}
        jid = str(job.get('id') or row.get('job_id') or '')
        if not jid:
            diagnostics['missing_job_id'] += 1
            continue
        if jid in globally_alerted:
            diagnostics['already_alerted'] += 1
            continue
        if jid in applied_ids:
            diagnostics['already_applied'] += 1
            continue
        if jid in seen_jobs:
            diagnostics['duplicate_job'] += 1
            continue
        if job.get('active') is False or job.get('application_status') == 'closed':
            diagnostics['inactive_or_closed'] += 1
            continue

        destination = _destination(job)
        if not destination:
            diagnostics['no_safe_destination'] += 1
            continue
        destination_key = destination.split('?', 1)[0].rstrip('/').casefold()
        if destination_key in seen_destinations:
            diagnostics['duplicate_destination'] += 1
            continue

        title = _meaningful_title(job.get('title'))
        if not title:
            diagnostics['generic_title'] += 1
            continue

        score = int(row.get('score') or 0)
        normal_floor = max(int(cat.get('alert_threshold') or 70), int(settings.get('minimum_score') or 70))
        candidates.append({
            'row': row,
            'job': job,
            'cat': cat,
            'job_id': jid,
            'destination': destination,
            'destination_key': destination_key,
            'title': title,
            'score': score,
            'normal_floor': normal_floor,
        })
        seen_jobs.add(jid)
        seen_destinations.add(destination_key)

    return candidates, diagnostics


def run(limit_per_category=10):
    db = SupabaseREST()
    candidate = load_candidate(db)
    user_id = ((candidate or {}).get('preferences') or {}).get('user_id')
    apply_dashboard_integrations(db, user_id)
    settings = get_settings(db)

    if not any(settings.get(k, True) for k in ('ntfy_enabled', 'telegram_enabled', 'email_enabled')):
        result = {'digest': 'skipped', 'reason': 'all notification channels disabled'}
        print(result)
        return result

    applied_ids = _applied_job_ids(db, user_id)
    rows = db.select('job_matches', {
        'select': 'job_id,category_id,score,eligible,alerted_at,reasons,resume_reasons,category:categories(id,name,slug,alert_threshold),job:jobs(id,title,company,location,description,raw,source_id,apply_url,apply_verified,notification_url,canonical_url,source_url,active,application_status,event_type,official_verified,link_confidence)',
        'eligible': 'eq.true',
        'order': 'score.desc',
        'limit': '1000',
    })

    candidates, diagnostics = _prepare_candidates(rows, applied_ids, settings)
    primary = [x for x in candidates if x['score'] >= x['normal_floor']]
    fallback_mode = not bool(primary)
    if fallback_mode:
        chosen = [x for x in candidates if x['score'] >= _fallback_floor(x['normal_floor'])][:FALLBACK_MAX_TOTAL]
    else:
        chosen = primary

    sent = []
    category_counts = defaultdict(int)
    max_items = max(1, min(10, int(limit_per_category)))

    for item in chosen:
        row = item['row']
        job = item['job']
        cat = item['cat']
        jid = item['job_id']
        destination = item['destination']
        title = item['title']
        score = item['score']
        category = cat.get('name') or 'Other'
        if category_counts[category] >= max_items:
            diagnostics['category_cap'] += 1
            continue

        company = _company(job, destination)
        where = str(job.get('location') or 'Location not disclosed').strip()
        source = _host_label(job.get('source_url') or destination)
        summary = _summary(job.get('description'))
        reasons = [str(x).strip() for x in ((row.get('resume_reasons') or []) + (row.get('reasons') or [])) if str(x).strip()]
        direct_apply = bool(job.get('apply_verified') and _safe_url(job.get('apply_url')) == destination)

        plain = [
            f'{title} — {score}% match',
            f'Company: {company}',
            f'Location: {where}',
            f'Category: {category}',
            f'Source: {source}',
        ]
        if fallback_mode:
            plain.append('Alert level: good verified fallback (no stronger new jobs this run)')
        if summary:
            plain.append(f'Summary: {summary}')
        if reasons:
            plain.append('Why: ' + '; '.join(reasons[:4]))
        plain.append(f'Open: {destination}')

        rich = [
            f'🏢 **Company:** {company}',
            f'📍 **Location:** {where}',
            f'🧭 **Track:** {category}',
            f'🎯 **Match:** **{score}%**',
            f'🌐 **Source:** {source}',
            '✅ **Direct application verified**' if direct_apply else '✅ **Live job page verified**',
        ]
        if fallback_mode:
            rich += ['', '🟡 **Good verified match**', 'No stronger new job passed your normal alert score in this run.']
        if summary:
            rich += ['', '**Role summary**', summary]
        if reasons:
            rich += ['', '**Why it matched**'] + [f'• {x}' for x in reasons[:4]]

        actions = [{
            'action':'view',
            'label':'🟢 Apply now' if direct_apply else '🔵 View job',
            'url':destination,
            'clear':False,
        }]
        source_url = _safe_url(job.get('source_url'))
        if source_url and source_url != destination:
            actions.append({'action':'view', 'label':'🌐 View source', 'url':source_url, 'clear':False})
        if len(actions) < 3:
            actions.append({'action':'copy', 'label':'📋 Copy title', 'value':title, 'clear':False})

        results = deliver(
            f'JobRadar · {title} · {score}%',
            '\n'.join(plain),
            destination,
            settings,
            ntfy_text='\n'.join(rich),
            ntfy_actions=actions,
            ntfy_tags=['briefcase', 'heavy_check_mark', 'mag'],
            ntfy_markdown=True,
        )
        delivered = any_success(results)
        if delivered:
            stamp = datetime.now(timezone.utc).isoformat()
            # Mark every category match for this job so the same vacancy cannot reappear under
            # another category on the next run.
            db.update('job_matches', {'alerted_at':stamp}, {'job_id':f'eq.{jid}'})
            category_counts[category] += 1
            diagnostics['delivered_fallback' if fallback_mode else 'delivered_primary'] += 1
        else:
            diagnostics['delivery_failed'] += 1

        sent.append({
            'category': category,
            'job_id': jid,
            'title': title,
            'score': score,
            'mode': 'fallback' if fallback_mode else 'primary',
            'delivered': delivered,
            'channels': results,
        })

    if not primary:
        diagnostics['below_normal_floor'] = sum(1 for x in candidates if x['score'] < x['normal_floor'])
        diagnostics['below_fallback_floor'] = sum(1 for x in candidates if x['score'] < _fallback_floor(x['normal_floor']))

    summary = {
        'digest': 'complete',
        'mode': 'fallback' if fallback_mode else 'primary',
        'candidates': len(candidates),
        'primary_candidates': len(primary),
        'sent': sent,
        'delivered': sum(1 for x in sent if x['delivered']),
        'diagnostics': dict(diagnostics),
    }
    print(summary)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=10)
    args = p.parse_args()
    run(args.limit)
