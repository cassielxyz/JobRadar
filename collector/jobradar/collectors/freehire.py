from __future__ import annotations

import html
import re
import httpx
from bs4 import BeautifulSoup
from ..models import Job, Category
from ..scoring import semantic_gate, location_matches

API = 'https://freehire.me/api/v1/agent/jobs/search'


def _plain(value) -> str:
    if value is None:
        return ''
    text = str(value)
    if '<' in text and '>' in text:
        text = BeautifulSoup(text, 'html.parser').get_text(' ', strip=True)
    return html.unescape(text)


def _money_monthly(x: dict, key: str):
    value = x.get(key)
    if value in (None, ''):
        return None
    try:
        n = float(value)
    except Exception:
        return None
    period = str(x.get('salary_period') or '').lower()
    currency = str(x.get('salary_currency') or '').upper()
    if currency not in ('INR', ''):
        return None
    if period == 'year':
        n /= 12
    elif period == 'day':
        n *= 22
    elif period == 'hour':
        n *= 176
    return int(n) if 1000 <= n <= 1000000 else None


class FreeHireCollector:
    """Keyless discovery across many ATS/company/job-board sources via FreeHire.

    FreeHire results still pass JobRadar's own role/location/experience verification and
    direct-link resolver before they can appear or alert.
    """
    def __init__(self):
        self.client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent":"JobRadarEverywhere/0.9"})

    def _queries(self, category: Category):
        seeds = []
        # Prefer role phrases over very broad adjacent titles.
        for term in category.role_keywords + category.hidden_keywords:
            t = ' '.join(str(term).split()).strip()
            if len(t) < 4:
                continue
            if t.lower() not in [s.lower() for s in seeds]:
                seeds.append(t)
            if len(seeds) >= 4:
                break
        return seeds

    def _params(self, category: Category, query: str):
        params = {
            'q': query,
            'countries': 'IN',
            'posted_within_days': '30',
            'description_format': 'text',
            'limit': '25',
            'sort': 'posted_at',
            'order': 'desc',
        }
        if category.type == 'startup':
            params['company_type'] = 'startup'
        elif category.type == 'internship':
            params['seniority'] = 'intern'
            params['employment_type'] = 'internship'
        elif getattr(category, 'fresher_only', False):
            params['seniority'] = 'junior,intern'
        return params

    def collect(self, category: Category, source_id='freehire'):
        out = []
        seen = set()
        for query in self._queries(category):
            try:
                r = self.client.get(API, params=self._params(category, query))
                r.raise_for_status()
                data = r.json().get('data') or []
            except Exception:
                continue
            for x in data:
                url = str(x.get('url') or '').strip()
                if not url or url in seen:
                    continue
                seen.add(url)
                title = _plain(x.get('title'))[:240]
                description = _plain(x.get('description') or x.get('summary') or x.get('description_preview'))[:20000]
                company = _plain(x.get('company') or x.get('company_name') or 'Unknown company')[:240]
                location = _plain(x.get('location') or ', '.join(x.get('cities') or []) or ', '.join(x.get('countries') or []))[:240]
                employment = str(x.get('employment_type') or x.get('employment') or 'unknown')
                seniority = str(x.get('seniority') or '')
                if seniority:
                    description = f"Seniority: {seniority}. {description}"
                job = Job(
                    title=title,
                    company=company,
                    location=location,
                    description=description,
                    employment_type=employment,
                    source_id=source_id,
                    # Treat the actual posting as the source for direct-link trust checks.
                    source_url=url,
                    canonical_url=url,
                    salary_min_monthly=_money_monthly(x, 'salary_min'),
                    salary_max_monthly=_money_monthly(x, 'salary_max'),
                    posted_at=x.get('posted_at') or x.get('created_at') or x.get('updated_at'),
                    raw={**x, 'discovered_via': 'freehire', 'query': query, 'source_kind': 'job_board'},
                )
                relevant, _ = semantic_gate(job, category)
                if not relevant:
                    continue
                if job.location and not location_matches(job.location, category.locations):
                    if 'remote' not in job.location.lower():
                        continue
                out.append(job)
                if len(out) >= 30:
                    return out
        return out
