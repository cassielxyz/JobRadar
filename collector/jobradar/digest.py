from __future__ import annotations

import argparse
import html
import re
from collections import defaultdict
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
    if job.get('event_type') == 'vacancy':
        apply_url = _safe_url(job.get('apply_url'))
        return apply_url if job.get('apply_verified') and apply_url else ''
    if job.get('official_verified'):
        return _safe_url(job.get('notification_url')) or _safe_url(job.get('canonical_url'))
    return ''


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
        'select': 'job_id,category_id,score,eligible,alerted_at,reasons,resume_reasons,category:categories(id,name,slug,alert_threshold),job:jobs(id,title,company,location,description,raw,source_id,apply_url,apply_verified,notification_url,canonical_url,source_url,active,application_status,event_type,official_verified)',
        'eligible': 'eq.true',
        'order': 'score.desc',
        'limit': '800',
    })

    sent = []
    category_counts = defaultdict(int)
    seen_jobs = set()
    seen_destinations = set()
    max_items = max(1, min(10, int(limit_per_category)))

    for row in rows:
        if row.get('alerted_at'):
            continue
        job = row.get('job') or {}
        cat = row.get('category') or {}
        jid = str(job.get('id') or row.get('job_id') or '')
        if not jid or jid in applied_ids or jid in seen_jobs:
            continue
        if not job or job.get('active') is False or job.get('application_status') == 'closed':
            continue

        category = cat.get('name') or 'Other'
        if category_counts[category] >= max_items:
            continue
        score = int(row.get('score') or 0)
        floor = max(int(cat.get('alert_threshold') or 70), int(settings.get('minimum_score') or 70))
        if score < floor:
            continue

        destination = _destination(job)
        if not destination:
            continue
        destination_key = destination.split('?', 1)[0].rstrip('/').casefold()
        if destination_key in seen_destinations:
            continue

        title = _meaningful_title(job.get('title'))
        if not title:
            # Generic search-result labels such as "URL" and "Job opening" are not useful alerts.
            continue
        company = _company(job, destination)
        where = str(job.get('location') or 'Location not disclosed').strip()
        source = _host_label(job.get('source_url') or destination)
        summary = _summary(job.get('description'))
        reasons = [str(x).strip() for x in ((row.get('resume_reasons') or []) + (row.get('reasons') or [])) if str(x).strip()]

        plain = [
            f'{title} — {score}% match',
            f'Company: {company}',
            f'Location: {where}',
            f'Category: {category}',
            f'Source: {source}',
        ]
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
            '✅ **New verified match**',
        ]
        if summary:
            rich += ['', '**Role summary**', summary]
        if reasons:
            rich += ['', '**Why it matched**'] + [f'• {x}' for x in reasons[:4]]

        actions = [{'action':'view', 'label':'🟢 Apply / Open', 'url':destination, 'clear':False}]
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
            db.update('job_matches', {'alerted_at':stamp}, {
                'job_id':f'eq.{jid}', 'category_id':f"eq.{row.get('category_id')}"
            })
            category_counts[category] += 1
            seen_jobs.add(jid)
            seen_destinations.add(destination_key)

        sent.append({
            'category': category,
            'job_id': jid,
            'title': title,
            'score': score,
            'delivered': delivered,
            'channels': results,
        })

    summary = {'digest': 'complete', 'sent': sent, 'delivered': sum(1 for x in sent if x['delivered'])}
    print(summary)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=10)
    args = p.parse_args()
    run(args.limit)
