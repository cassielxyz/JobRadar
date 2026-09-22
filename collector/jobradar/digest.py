from __future__ import annotations

import argparse
import html
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from .db import SupabaseREST
from .dedupe import job_identity_keys, normalized_url_key
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
DAILY_ALERT_TARGET = max(1, min(25, int(os.getenv('JOBRADAR_DAILY_ALERT_TARGET', '10') or 10)))
HISTORY_LIMIT = max(1000, min(10000, int(os.getenv('JOBRADAR_ALERT_HISTORY_LIMIT', '5000') or 5000)))
LOCAL_TZ = ZoneInfo(os.getenv('JOBRADAR_TIMEZONE', 'Asia/Kolkata'))


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
    """Prefer a verified direct apply URL, then a verified-safe live job page."""
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
    """Relax the normal threshold only enough to fill the daily new-job target."""
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
        'freshersworld.com':'Freshersworld','hirist.tech':'Hirist','apna.co':'Apna',
        'unstop.com':'Unstop','jobs.weekday.works':'Weekday','cuvette.tech':'Cuvette',
        'joinsuperset.com':'Superset','geektrust.com':'Geektrust','talent500.co':'Talent500',
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
        for key in ('company_name', 'companyName', 'company', 'employer_name', 'employerName', 'employer', 'organization'):
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


def _parse_ts(value):
    try:
        return datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
    except Exception:
        return None


def _primary_identity(keys, fallback):
    keys = set(keys or set())
    for prefix in ('role:', 'req:', 'url:'):
        values = sorted(k for k in keys if k.startswith(prefix))
        if values:
            return values[0]
    return str(fallback or '')


def _historical_alert_state(db):
    """Load every recent alerted identity, not merely the current job ID.

    The old code only remembered `job_id`. The same vacancy found later on Naukri, LinkedIn,
    Indeed or an employer ATS therefore received a different ID and was notified again. This
    history uses normalized URL and role/company/location identities across sources.
    """
    try:
        rows = db.select('job_matches', {
            'select': 'job_id,alerted_at,job:jobs(id,title,company,location,raw,apply_url,canonical_url,source_url,notification_url)',
            'alerted_at': 'not.is.null',
            'order': 'alerted_at.desc',
            'limit': str(HISTORY_LIMIT),
        })
    except Exception:
        rows = []

    historical_keys = set()
    today_items = set()
    today = datetime.now(LOCAL_TZ).date()
    for row in rows:
        job = row.get('job') or {}
        jid = str(job.get('id') or row.get('job_id') or '')
        keys = job_identity_keys(job)
        historical_keys.update(keys)
        ts = _parse_ts(row.get('alerted_at'))
        if ts:
            try:
                local_date = ts.astimezone(LOCAL_TZ).date() if ts.tzinfo else ts.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ).date()
            except Exception:
                local_date = None
            if local_date == today:
                today_items.add(_primary_identity(keys, jid))
    return historical_keys, len(today_items)


def _prepare_candidates(rows, applied_ids, settings, historical_keys=None):
    diagnostics = Counter()
    historical_keys = set(historical_keys or set())
    globally_alerted = {
        str((row.get('job') or {}).get('id') or row.get('job_id') or '')
        for row in rows if row.get('alerted_at')
    }
    candidates = []
    seen_jobs = set()
    seen_destinations = set()
    seen_identity_keys = set()

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
        destination_key = normalized_url_key(destination)
        if destination_key and destination_key in seen_destinations:
            diagnostics['duplicate_destination'] += 1
            continue

        title = _meaningful_title(job.get('title'))
        if not title:
            diagnostics['generic_title'] += 1
            continue

        identity_keys = job_identity_keys(job)
        if identity_keys & historical_keys:
            diagnostics['already_alerted_equivalent'] += 1
            continue
        if identity_keys and identity_keys & seen_identity_keys:
            diagnostics['duplicate_cross_source'] += 1
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
            'identity_keys': identity_keys,
            'title': title,
            'score': score,
            'normal_floor': normal_floor,
        })
        seen_jobs.add(jid)
        if destination_key:
            seen_destinations.add(destination_key)
        seen_identity_keys.update(identity_keys)

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
    historical_keys, alerted_today = _historical_alert_state(db)
    rows = db.select('job_matches', {
        'select': 'job_id,category_id,score,eligible,alerted_at,reasons,resume_reasons,category:categories(id,name,slug,alert_threshold),job:jobs(id,title,company,location,description,raw,source_id,apply_url,apply_verified,notification_url,canonical_url,source_url,active,application_status,event_type,official_verified,link_confidence)',
        'eligible': 'eq.true',
        'order': 'score.desc',
        'limit': '1500',
    })

    candidates, diagnostics = _prepare_candidates(rows, applied_ids, settings, historical_keys)
    primary = [x for x in candidates if x['score'] >= x['normal_floor']]
    fallback = [
        x for x in candidates
        if x['score'] < x['normal_floor'] and x['score'] >= _fallback_floor(x['normal_floor'])
    ]
    remaining_today = max(0, DAILY_ALERT_TARGET - alerted_today)
    ordered = primary + fallback

    sent = []
    category_counts = defaultdict(int)
    max_items = max(1, min(10, int(limit_per_category)))
    delivered_this_run = 0

    for item in ordered:
        if delivered_this_run >= remaining_today:
            break

        row = item['row']
        job = item['job']
        cat = item['cat']
        jid = item['job_id']
        destination = item['destination']
        title = item['title']
        score = item['score']
        mode = 'primary' if score >= item['normal_floor'] else 'fallback'
        category = cat.get('name') or 'Other'
        if category_counts[category] >= max_items:
            diagnostics['category_cap'] += 1
            continue

        # Re-check the live history set because an earlier item in this same run may be an
        # equivalent listing from another source.
        identity_keys = item.get('identity_keys') or set()
        if identity_keys & historical_keys:
            diagnostics['duplicate_after_selection'] += 1
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
        if mode == 'fallback':
            plain.append('Alert level: good verified match used to fill today’s new-job target')
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
        if mode == 'fallback':
            rich += ['', '🟡 **Good verified match**', 'Included because today has not yet reached the new-job target.']
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
        if source_url and normalized_url_key(source_url) != normalized_url_key(destination):
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
            db.update('job_matches', {'alerted_at':stamp}, {'job_id':f'eq.{jid}'})
            category_counts[category] += 1
            delivered_this_run += 1
            historical_keys.update(identity_keys)
            diagnostics['delivered_' + mode] += 1
        else:
            diagnostics['delivery_failed'] += 1

        sent.append({
            'category': category,
            'job_id': jid,
            'title': title,
            'score': score,
            'mode': mode,
            'delivered': delivered,
            'channels': results,
        })

    diagnostics['below_normal_floor'] = sum(1 for x in candidates if x['score'] < x['normal_floor'])
    diagnostics['below_fallback_floor'] = sum(1 for x in candidates if x['score'] < _fallback_floor(x['normal_floor']))
    if remaining_today == 0:
        diagnostics['daily_target_already_reached'] += 1

    summary = {
        'digest': 'complete',
        'mode': 'daily-target-reached' if remaining_today == 0 else ('mixed' if primary and fallback else ('primary' if primary else 'fallback')),
        'daily_target': DAILY_ALERT_TARGET,
        'alerted_today_before_run': alerted_today,
        'remaining_daily_target_before_run': remaining_today,
        'candidates': len(candidates),
        'primary_candidates': len(primary),
        'fallback_candidates': len(fallback),
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
