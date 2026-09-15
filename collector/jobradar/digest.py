from __future__ import annotations

import argparse
from collections import defaultdict

from .db import SupabaseREST
from .integration_config import apply_dashboard_integrations
from .notifications import get_settings
from .resume_match import load_candidate
from .alerts.ntfy import send_result


def _destination(job):
    return (
        job.get('apply_url')
        or job.get('notification_url')
        or job.get('canonical_url')
        or job.get('source_url')
        or ''
    )


def run(limit_per_category=10):
    db = SupabaseREST()
    candidate = load_candidate(db)
    user_id = ((candidate or {}).get('preferences') or {}).get('user_id')
    apply_dashboard_integrations(db, user_id)
    settings = get_settings(db)
    if not settings.get('ntfy_enabled'):
        result = {'digest': 'skipped', 'reason': 'ntfy disabled'}
        print(result)
        return result

    rows = db.select('job_matches', {
        'select': 'score,eligible,category:categories(id,name,slug),job:jobs(id,title,company,location,apply_url,notification_url,canonical_url,source_url,active,application_status)',
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
        groups[cat.get('name') or 'Other'].append(row)

    sent = []
    max_items = max(1, min(10, int(limit_per_category)))
    for category, items in groups.items():
        top = items[:max_items]
        if not top:
            continue

        lines = [f"Top {len(top)} verified matches — {category}"]
        first_url = ''
        for i, row in enumerate(top, 1):
            job = row.get('job') or {}
            url = _destination(job)
            if not first_url and url:
                first_url = url
            where = job.get('location') or 'location not disclosed'
            lines.append(
                f"{i}. {job.get('title', 'Job')} — {job.get('company', '')} — {where} — {row.get('score', 0)}%"
            )
            if url:
                lines.append(url)

        result = send_result(
            '\n'.join(lines),
            url=first_url or None,
            title=f'JobRadar Everywhere · {category}',
        )
        sent.append({'category': category, 'count': len(top), **result})

    summary = {'digest': 'complete', 'categories': sent}
    print(summary)
    return summary


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--limit', type=int, default=10)
    args = p.parse_args()
    run(args.limit)
