from __future__ import annotations

import html
import re
import httpx
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from ..models import Job, Category
from ..scoring import semantic_gate, location_plausible
from ..category_research import category_search_terms

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


def _platform_name(x: dict, url: str):
    explicit = _plain(x.get('source_name') or x.get('source') or x.get('provider') or x.get('board'))
    if explicit:
        return explicit[:80]
    host = (urlparse(url).hostname or '').lower().replace('www.','')
    known = {
        'linkedin.com':'LinkedIn Jobs','naukri.com':'Naukri','indeed.com':'Indeed',
        'foundit.in':'Foundit','shine.com':'Shine','timesjobs.com':'TimesJobs',
        'freshersworld.com':'Freshersworld','internshala.com':'Internshala',
        'cutshort.io':'Cutshort','instahyre.com':'Instahyre','wellfound.com':'Wellfound',
        'boards.greenhouse.io':'Greenhouse','job-boards.greenhouse.io':'Greenhouse',
        'jobs.lever.co':'Lever','jobs.ashbyhq.com':'Ashby','jobs.smartrecruiters.com':'SmartRecruiters',
    }
    for domain, name in known.items():
        if host == domain or host.endswith('.'+domain):
            return name
    return host or 'FreeHire discovery'


class FreeHireCollector:
    """Keyless dynamic discovery for every enabled category.

    Search terms are generated from the category itself, so newly-created/custom categories
    do not depend on a static list of hard-coded roles. A wider date window is used only when
    the recent passes cannot fill a useful candidate pool.
    """
    def __init__(self):
        self.client = httpx.Client(timeout=30, follow_redirects=True, headers={"User-Agent":"JobRadarEverywhere/1.2"})

    def _queries(self, category: Category):
        return category_search_terms(category, limit=14)

    def _params(self, category: Category, query: str, days=60):
        params = {
            'q': query,
            'countries': 'IN',
            'posted_within_days': str(days),
            'description_format': 'text',
            'limit': '50',
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

    def collect(self, category: Category, source_id='freehire', target_candidates=70):
        out = []
        seen = set()
        queries = self._queries(category)
        if not queries:
            return out

        # 30/90 days prioritizes freshness; 180 days is a resilience pass for niche/new
        # categories. Old entries are still rejected later if the listing is closed/stale.
        for days in (30, 90, 180):
            for query in queries:
                try:
                    r = self.client.get(API, params=self._params(category, query, days=days))
                    r.raise_for_status()
                    payload = r.json()
                    data = payload.get('data') or payload.get('jobs') or []
                except Exception:
                    continue
                for x in data:
                    url = str(x.get('url') or x.get('apply_url') or '').strip()
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
                    platform = _platform_name(x, url)
                    job = Job(
                        title=title,
                        company=company,
                        location=location,
                        description=description,
                        employment_type=employment,
                        source_id=source_id,
                        source_url=url,
                        canonical_url=url,
                        salary_min_monthly=_money_monthly(x, 'salary_min'),
                        salary_max_monthly=_money_monthly(x, 'salary_max'),
                        posted_at=x.get('posted_at') or x.get('created_at') or x.get('updated_at'),
                        raw={
                            **x,
                            'discovered_via':'freehire',
                            'source_platform':platform,
                            'query':query,
                            'query_window_days':days,
                            'source_kind':'job_board',
                        },
                    )
                    relevant, _ = semantic_gate(job, category)
                    if not relevant:
                        continue
                    if not location_plausible(job.location, category.locations):
                        continue
                    out.append(job)
                    if len(out) >= target_candidates:
                        return out
            if len(out) >= max(25, target_candidates // 2):
                break
        return out
