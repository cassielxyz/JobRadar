from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import yaml

from ..models import Job, Category
from ..scoring import semantic_gate
from ..linkresolver import is_non_job_url
from ..category_research import category_search_terms
from ..dedupe import normalized_url_key

URL_RE = re.compile(r'https?://[^\s\]\)\}"\']+')
ROOT = Path(__file__).resolve().parents[3]
PLATFORM_FILE = ROOT / 'config' / 'discovery_platforms.yaml'

GOVERNMENT_DOMAINS = (
    'tnpsc.gov.in','tamilnaducareerservices.tn.gov.in','keralapsc.gov.in','cmd.kerala.gov.in',
    'careers-itmission.kerala.gov.in','itmission.kerala.gov.in','tanfinet.tn.gov.in','drdo.gov.in',
    'isro.gov.in','bel-india.in','cdac.in','careers.cdac.in','nielit.gov.in','recruit-delhi.nielit.gov.in',
    'rrbchennai.gov.in','bsnl.co.in','ecil.co.in','ncs.gov.in',
)

# Search these individually instead of only in large OR batches. Exa/search engines tend to
# over-return one dominant domain from a mixed query; individual passes materially improve Naukri
# and fresher-board coverage.
INDIA_CORE_DOMAINS = (
    'naukri.com','linkedin.com','indeed.com','foundit.in','shine.com','freshersworld.com',
    'internshala.com','cutshort.io','instahyre.com','hirist.tech','apna.co','unstop.com',
    'jobs.weekday.works','cuvette.tech','joinsuperset.com','geektrust.com','talent500.co',
)

ATS_SEARCH_GROUPS = (
    ('boards.greenhouse.io','job-boards.greenhouse.io','jobs.lever.co','jobs.ashbyhq.com'),
    ('jobs.smartrecruiters.com','myworkdayjobs.com','workdayjobs.com','apply.workable.com'),
    ('recruitee.com','teamtailor.com','jobs.jobvite.com','breezy.hr','applytojob.com'),
    ('icims.com','oraclecloud.com','successfactors.com','jobs.dayforcehcm.com','eightfold.ai'),
)

DISCOVERY_ONLY_HINTS = (
    'linkedin.com','naukri.com','indeed.com','foundit.in','shine.com','timesjobs.com',
    'freshersworld.com','internshala.com','cutshort.io','instahyre.com','hirist.tech',
    'iimjobs.com','apna.co','workindia.in','jobhai.com','unstop.com','wellfound.com',
    'hirect.in','herkey.com','quikr.com','jooble.org','adzuna.in','careerjet.co.in',
    'jora.com','talent.com','grabjobs.co','simplyhired.com','jobsora.com','glassdoor.co.in',
    'jobs.weekday.works','cuvette.tech','joinsuperset.com','geektrust.com','talent500.co',
    'placementindia.com','freshersnow.com','timesascent.com',
    'ziprecruiter.com','dice.com','builtin.com','startup.jobs','remoteok.com',
    'weworkremotely.com','remotive.com','himalayas.app','jobspresso.co',
    'workingnomads.com','remote.co','nodesk.co','jobicy.com','dynamitejobs.com',
    'arc.dev','turing.com','contra.com','upwork.com','peopleperhour.com','freelancer.com',
)


def _host(url: str) -> str:
    return (urlparse(url).hostname or '').lower().removeprefix('www.')


def _clean_title(value: str, fallback: str = '') -> str:
    text = str(value or '').replace('\n', ' ').strip()
    text = re.sub(r'\[([^\]]{2,160})\]\(https?://[^)]+\)', r'\1', text)
    text = URL_RE.sub('', text)
    text = re.sub(r'^\s*(?:URL\s*:|[-–—]+)\s*', '', text, flags=re.I)
    text = re.sub(r'^\s*\[[^\]]*(?:20\d{2}|liked?|reposted?)[^\]]*\]\s*', '', text, flags=re.I)
    text = re.sub(r'\s*[·|]\s*(?:LinkedIn|Indeed|Naukri|Internshala|Shine|Foundit)\s*$', '', text, flags=re.I)
    text = re.sub(r'\s+', ' ', text).strip(' -–—|:[]()')
    if not text or len(text) < 3 or text.lower().startswith(('http', 'www.')):
        text = str(fallback or '').split('\n', 1)[0].strip()
        text = URL_RE.sub('', text)
        text = re.sub(r'\s+', ' ', text).strip(' -–—|:[]()')
    return (text or 'Job opening')[:180]


def _walk(obj):
    if isinstance(obj, dict):
        if obj.get('url'):
            yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


def _walk_text(obj, keys, depth=0):
    if depth > 4:
        return ''
    if isinstance(obj, dict):
        for key in keys:
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                name = value.get('name')
                if isinstance(name, str) and name.strip():
                    return name.strip()
        for value in obj.values():
            if isinstance(value, (dict, list)):
                found = _walk_text(value, keys, depth + 1)
                if found:
                    return found
    elif isinstance(obj, list):
        for value in obj[:12]:
            found = _walk_text(value, keys, depth + 1)
            if found:
                return found
    return ''


def _extract_company(raw):
    return _walk_text(raw, (
        'company_name','companyName','company','employer_name','employerName','employer',
        'organization','hiringOrganization',
    ))


def _extract_location(raw):
    return _walk_text(raw, (
        'location','job_location','jobLocation','city','region','formattedLocation','locationName',
    ))


def _load_platforms():
    try:
        data = yaml.safe_load(PLATFORM_FILE.read_text(encoding='utf-8')) or {}
        rows = data.get('platforms') or []
        return [x for x in rows if isinstance(x, dict) and x.get('domain')]
    except Exception:
        return []


PLATFORMS = _load_platforms()


def _platform_for(url: str):
    host = _host(url)
    best = None
    for row in PLATFORMS:
        domain = str(row.get('domain') or '').lower().lstrip('.')
        if host == domain or host.endswith('.' + domain) or domain.endswith('.' + host):
            if best is None or len(domain) > len(str(best.get('domain') or '')):
                best = row
    return best


class AgentReachCollector:
    """Parallel category-aware discovery across public boards and employer ATS pages."""

    def enabled(self):
        return os.getenv('AGENT_REACH_ENABLED','false').lower() == 'true'

    def available(self):
        return self.enabled() and bool(shutil.which('mcporter'))

    def _platform_priority(self, category: Category):
        preferred = ['india','general','tech','ats']
        if getattr(category, 'fresher_only', False):
            preferred = ['india','fresher','tech','ats','general']
        if category.type == 'internship':
            preferred = ['india','internship','fresher','tech','ats']
        elif category.type == 'startup':
            preferred = ['india','startup','tech','ats','remote']
        elif any('remote' in str(x).lower() for x in category.locations):
            preferred = ['india','remote','tech','ats','general']

        def rank(row):
            tags = {str(x).lower() for x in (row.get('tags') or [])}
            score = 0
            for i, tag in enumerate(reversed(preferred), 1):
                if tag in tags:
                    score += i * 10
            if 'india' in tags: score += 25
            if 'ats' in tags: score += 18
            if 'fresher' in tags and getattr(category, 'fresher_only', False): score += 20
            if 'freelance' in tags: score -= 30
            return -score, str(row.get('name') or '')

        return sorted(PLATFORMS, key=rank)

    def _queries(self, category: Category):
        loc_values = [' '.join(str(x).split()).strip() for x in category.locations[:8] if str(x).strip()]
        loc = '(' + ' OR '.join(f'"{x}"' for x in loc_values) + ')' if loc_values else '(India OR remote)'

        roles = category_search_terms(category, limit=20)
        if not roles:
            return []

        qualifier_terms = []
        if getattr(category, 'fresher_only', False):
            qualifier_terms += ['fresher','"entry level"','junior','graduate','trainee','L1','"0-1 years"','"0-2 years"']
        if category.type == 'internship':
            qualifier_terms += ['internship','intern','stipend']
        elif category.type == 'startup':
            qualifier_terms += ['startup','scaleup']
        qualifier = '(' + ' OR '.join(qualifier_terms) + ')' if qualifier_terms else ''

        role_expr = ' OR '.join(f'"{r}"' for r in roles[:6])
        queries = []
        if category.type == 'government':
            for i in range(0, len(GOVERNMENT_DOMAINS), 4):
                domains = ' OR '.join(f'site:{d}' for d in GOVERNMENT_DOMAINS[i:i+4])
                queries.append(f'({role_expr}) {loc} {qualifier} ({domains}) recruitment careers apply')
            return [' '.join(q.split()) for q in queries][:16]

        # Search more adjacent titles directly. These are high-yield for employer career pages
        # that are not indexed under a known job-board domain.
        for role in roles[:8]:
            queries.append(f'"{role}" {loc} {qualifier} (careers OR jobs OR hiring OR apply)')

        # Give major Indian boards their own query so Naukri/Indeed/etc. cannot be crowded out by
        # LinkedIn or one dominant domain in a multi-site search.
        for domain in INDIA_CORE_DOMAINS[:12]:
            queries.append(f'({role_expr}) {loc} {qualifier} site:{domain}')

        # Cover the rest of the discovery catalog in small batches.
        core = set(INDIA_CORE_DOMAINS)
        platforms = [p for p in self._platform_priority(category) if str(p.get('domain') or '') not in core]
        for i in range(0, min(len(platforms), 36), 6):
            batch = platforms[i:i+6]
            domains = ' OR '.join(f'site:{p["domain"]}' for p in batch)
            queries.append(f'({role_expr}) {loc} {qualifier} ({domains})')

        for group in ATS_SEARCH_GROUPS:
            domains = ' OR '.join(f'site:{domain}' for domain in group)
            queries.append(f'({role_expr}) {loc} {qualifier} ({domains})')

        queries.extend([
            f'({role_expr}) {loc} {qualifier} ("company careers" OR "career portal") apply',
            f'({role_expr}) {loc} {qualifier} ("graduate program" OR "graduate engineer trainee" OR "associate engineer")',
        ])

        out, seen = [], set()
        for q in queries:
            q = ' '.join(q.split())
            key = q.casefold()
            if key not in seen:
                seen.add(key)
                out.append(q)
        return out[:36]

    def _call_exa(self, query: str):
        if not self.available():
            return []
        cmd = ['mcporter','call','exa.web_search_exa',f'query={query}','numResults=10']
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)
        except Exception:
            return []
        if p.returncode != 0 or not p.stdout.strip():
            return []
        text = p.stdout.strip()
        rows = []
        try:
            obj = json.loads(text)
            for x in _walk(obj):
                url = str(x.get('url') or '').strip()
                title = str(x.get('title') or x.get('name') or '').strip()
                snippet = str(x.get('text') or x.get('snippet') or x.get('description') or '')
                if url and not is_non_job_url(url):
                    rows.append((_clean_title(title, snippet), url, snippet, x))
        except Exception:
            for line in text.splitlines():
                for url in URL_RE.findall(line):
                    if not is_non_job_url(url):
                        rows.append((_clean_title(line[:180], line), url, line[:1000], {'raw_line': line}))
        return rows

    def collect(self, category: Category, source_id='agent-reach', target_candidates=110):
        queries = self._queries(category)
        if not queries or not self.available():
            return []

        out, seen = [], set()
        max_workers = max(2, min(8, int(os.getenv('AGENT_REACH_WORKERS','6') or 6)))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {pool.submit(self._call_exa, q): q for q in queries}
            for future in as_completed(future_map):
                query = future_map[future]
                try:
                    rows = future.result()
                except Exception:
                    rows = []
                for title, url, snippet, raw in rows:
                    url_key = normalized_url_key(url)
                    if not url or not url_key or url_key in seen or is_non_job_url(url):
                        continue
                    seen.add(url_key)
                    platform = _platform_for(url)
                    host = _host(url)
                    official_domain = next((d for d in GOVERNMENT_DOMAINS if host == d or host.endswith('.'+d)), '')
                    platform_name = str((platform or {}).get('name') or host or 'Web discovery')
                    discovery_only = any(host == d or host.endswith('.'+d) for d in DISCOVERY_ONLY_HINTS)
                    extracted_company = _extract_company(raw)
                    extracted_location = _extract_location(raw)
                    company = extracted_company or ('External job-platform discovery' if discovery_only else 'Web discovery')
                    job = Job(
                        title=_clean_title(title, snippet), company=company, location=extracted_location,
                        description=(snippet or title)[:6000], source_id=source_id,
                        source_url=url, canonical_url=url,
                        raw={
                            'discovered_via':'agent-reach-exa',
                            'source_platform':platform_name,
                            'source_domain':host,
                            'discovery_only':discovery_only,
                            'query':query,
                            'result':raw,
                            'source_kind':'government' if official_domain else 'community',
                            'official_domains':[official_domain] if official_domain else [],
                        },
                    )
                    relevant, _ = semantic_gate(job, category)
                    if not relevant:
                        continue
                    out.append(job)
                    if len(out) >= target_candidates:
                        for f in future_map:
                            f.cancel()
                        return out
        return out
