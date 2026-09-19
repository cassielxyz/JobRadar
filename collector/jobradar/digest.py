from __future__ import annotations

import argparse
import re
from collections import defaultdict
from urllib.parse import urlparse

from .db import SupabaseREST
from .integration_config import apply_dashboard_integrations
from .notifications import deliver, get_settings
from .resume_match import load_candidate
from .linkresolver import is_non_job_url

URL_RE = re.compile(r'https?://\S+', re.I)


def _clean_title(value):
    text = str(value or '').replace('\n', ' ').strip()
    text = re.sub(r'\[([^\]]+)\]\(https?://[^)]+\)', r'\1', text)
    text = URL_RE.sub('', text)
    text = re.sub(r'^\s*(?:URL\s*:|[-–—]+)\s*', '', text, flags=re.I)
    text = re.sub(r'^\s*\[[^\]]*(?:20\d{2}|liked?|reposted?)[^\]]*\]\s*', '', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip(' -–—|:[]()')
    return (text or 'Job opening')[:120]


def _safe_url(value):
    url = str(value or '').strip()
    if not url.startswith(('http://', 'https://')) or is_non_job_url(url):
        return ''
    return url


def _destination(job):
    # Never reuse a stale/broken apply URL simply because an old database row once marked it
    # verified. Validate its shape again at notification time.
    apply_url = _safe_url(job.get('apply_url'))
    if job.get('apply_verified') and apply_url:
        return apply_url
    notice = _safe_url(job.get('notification_url'))
    if notice:
        return notice
    canonical = _safe_url(job.get('canonical_url'))
    if canonical:
        return canonical
    return _safe_url(job.get('source_url'))


def _host_label(url):
    try:
        h = (urlparse(url).hostname or '').lower().removeprefix('www.')
    except Exception:
        return 'source'
    known = {
        'linkedin.com':'LinkedIn','naukri.com':'Naukri','indeed.com':'Indeed',
        'internshala.com':'Internshala','shine.com':'Shine','foundit.in':'Foundit',
        'cutshort.io':'Cutshort','instahyre.com':'Instahyre','wellfound.com':'Wellfound',
    }
    for domain, label in known.items():
        if h == domain or h.endswith('.'+domain):
            return label
    return h.split('.')[0].title() if h else 'Source'


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

    rows = db.select('job_matches', {
        'select': 'score,eligible,category:categories(id,name,slug),job:jobs(id,title,company,location,apply_url,apply_verified,notification_url,canonical_url,source_url,active,application_status)',
        'eligible': 'eq.true',
        'order': 'score.desc',
        'limit': '500',
    })

    groups = defaultdict(list)
    for row in rows:
        job = row.get('job') or {}
        cat = row.get('category') or {}
        if not job or job.get('active') is False or job.get('application_status') == 'closed':
            continue
        destination = _destination(job)
        if not destination:
            # An eligible row with no usable destination is not useful enough to notify.
            continue
        row['_destination'] = destination
        groups[cat.get('name') or 'Other'].append(row)

    sent = []
    max_items = max(1, min(10, int(limit_per_category)))
    for category, items in groups.items():
        top = items[:max_items]
        if not top:
            continue

        plain = [f"{len(top)} verified matches - {category}", ""]
        rich = [f"### {len(top)} verified matches", f"**{category}**", ""]
        actions = []
        first_url = top[0].get('_destination') or ''

        for i, row in enumerate(top, 1):
            job = row.get('job') or {}
            url = row.get('_destination') or ''
            title = _clean_title(job.get('title'))
            company = str(job.get('company') or '').strip()
            if company.lower() in {'external job-platform discovery', 'web discovery'}:
                company = _host_label(url)
            where = str(job.get('location') or 'Location not disclosed').strip()
            score = int(row.get('score') or 0)
            source = _host_label(url)

            plain.append(f"{i}. {title}")
            plain.append(f"   {company or source} | {where} | {score}%")
            plain.append(f"   {url}")

            rich.append(f"**{i}. {title}**")
            rich.append(f"{company or source} · {where} · **{score}%**")
            rich.append(f"[Open job on {source}]({url})")
            rich.append("")

            if len(actions) < 3:
                actions.append({'label': f'Open #{i}', 'url': url})

        subject = f'JobRadar - {category}'
        results = deliver(
            subject,
            '\n'.join(plain),
            first_url or None,
            settings,
            ntfy_text='\n'.join(rich),
            ntfy_actions=actions,
            ntfy_tags=['briefcase', 'heavy_check_mark', 'mag'],
            ntfy_markdown=True,
        )
        sent.append({
            'category': category,
            'count': len(top),
            'channels': results,
            'delivered': any(r.get('ok') for r in results),
        })

    summary = {'digest': 'complete', 'categories': sent}
    print(summary)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=10)
    args = p.parse_args()
    run(args.limit)
