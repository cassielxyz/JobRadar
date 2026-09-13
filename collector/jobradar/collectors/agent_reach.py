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

URL_RE = re.compile(r'https?://[^\s\]\)\}"\']+')
ROOT = Path(__file__).resolve().parents[3]
PLATFORM_FILE = ROOT / 'config' / 'discovery_platforms.yaml'

# Public job boards/aggregators are useful discovery evidence, but they are not treated as
# trusted final Apply destinations. JobRadar still resolves/verifies the employer/ATS URL.
DISCOVERY_ONLY_HINTS = (
    'linkedin.com','naukri.com','indeed.com','foundit.in','shine.com','timesjobs.com',
    'freshersworld.com','internshala.com','cutshort.io','instahyre.com','hirist.tech',
    'iimjobs.com','apna.co','workindia.in','jobhai.com','unstop.com','wellfound.com',
    'hirect.in','herkey.com','quikr.com','jooble.org','adzuna.in','careerjet.co.in',
    'jora.com','talent.com','grabjobs.co','simplyhired.com','jobsora.com','glassdoor.co.in',
    'ziprecruiter.com','dice.com','builtin.com','startup.jobs','remoteok.com',
    'weworkremotely.com','remotive.com','himalayas.app','jobspresso.co',
    'workingnomads.com','remote.co','nodesk.co','jobicy.com','dynamitejobs.com',
    'arc.dev','turing.com','contra.com','upwork.com','peopleperhour.com','freelancer.com',
)


def _host(url: str) -> str:
    return (urlparse(url).hostname or '').lower()


def _walk(obj):
    if isinstance(obj, dict):
        if obj.get('url'):
            yield obj
        for v in obj.values():
            yield from _walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v)


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
            # Prefer the most specific domain when multiple catalog entries match.
            if best is None or len(domain) > len(str(best.get('domain') or '')):
                best = row
    return best


class AgentReachCollector:
    """Parallel web discovery across 70+ job platforms through Agent Reach / Exa.

    The platform catalog is intentionally broader than the trusted-link list. Results from
    Naukri, LinkedIn, Indeed and other job boards are discovery leads only; the rest of the
    JobRadar pipeline still enforces role/location/experience rules and verifies the final
    application destination.
    """

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
            # India and ATS sources should generally be exhausted before global freelance boards.
            if 'india' in tags: score += 25
            if 'ats' in tags: score += 18
            if 'freelance' in tags: score -= 20
            return -score, str(row.get('name') or '')

        return sorted(PLATFORMS, key=rank)

    def _queries(self, category: Category):
        loc = ' '.join(category.locations[:8]) or 'India remote'
        roles = []
        for value in list(category.role_keywords) + list(category.hidden_keywords):
            role = ' '.join(str(value).split()).strip()
            if len(role) >= 4 and role.casefold() not in {r.casefold() for r in roles}:
                roles.append(role)
            if len(roles) >= 6:
                break
        if not roles:
            return []

        qualifier = ''
        if getattr(category, 'fresher_only', False):
            qualifier += ' fresher OR "entry level" OR junior OR graduate OR trainee OR L1'
        if category.type == 'internship':
            qualifier += ' internship OR intern OR trainee stipend'
        elif category.type == 'startup':
            qualifier += ' startup OR scaleup'

        queries = []
        # Broad company-career discovery catches roles that never reach the large boards.
        for role in roles[:4]:
            queries.append(f'"{role}" {loc} {qualifier} careers apply')

        # Search the entire 70+ catalog in small domain batches. Smaller batches produce much
        # better search relevance than one huge OR expression while remaining fast in parallel.
        platforms = self._platform_priority(category)
        role_expr = ' OR '.join(f'"{r}"' for r in roles[:3])
        for i in range(0, len(platforms), 5):
            batch = platforms[i:i+5]
            domains = ' OR '.join(f'site:{p["domain"]}' for p in batch)
            queries.append(f'({role_expr}) {loc} {qualifier} ({domains})')

        # Direct ATS/company searches are especially valuable because the application URL can
        # often be verified without depending on a third-party board.
        queries.extend([
            f'({role_expr}) {loc} (site:boards.greenhouse.io OR site:job-boards.greenhouse.io OR site:jobs.lever.co OR site:jobs.ashbyhq.com)',
            f'({role_expr}) {loc} (site:jobs.smartrecruiters.com OR site:myworkdayjobs.com OR site:apply.workable.com OR site:recruitee.com)',
            f'({role_expr}) {loc} careers "apply" cybersecurity networking cloud infrastructure',
        ])

        out, seen = [], set()
        for q in queries:
            q = ' '.join(q.split())
            key = q.casefold()
            if key not in seen:
                seen.add(key)
                out.append(q)
        return out[:28]

    def _call_exa(self, query: str):
        if not self.available():
            return []
        cmd = ['mcporter','call','exa.web_search_exa',f'query={query}','numResults=6']
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
                if url:
                    rows.append((title, url, snippet, x))
        except Exception:
            for line in text.splitlines():
                for url in URL_RE.findall(line):
                    rows.append((line[:180], url, line[:1000], {'raw_line': line}))
        return rows

    def collect(self, category: Category, source_id='agent-reach', target_candidates=70):
        queries = self._queries(category)
        if not queries or not self.available():
            return []

        out, seen = [], set()
        max_workers = max(2, min(6, int(os.getenv('AGENT_REACH_WORKERS','6') or 6)))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            future_map = {pool.submit(self._call_exa, q): q for q in queries}
            for future in as_completed(future_map):
                query = future_map[future]
                try:
                    rows = future.result()
                except Exception:
                    rows = []
                for title, url, snippet, raw in rows:
                    if not url or url in seen:
                        continue
                    seen.add(url)
                    platform = _platform_for(url)
                    host = _host(url)
                    platform_name = str((platform or {}).get('name') or host or 'Web discovery')
                    discovery_only = any(host == d or host.endswith('.'+d) for d in DISCOVERY_ONLY_HINTS)
                    company = 'External job-platform discovery' if discovery_only else 'Web discovery'
                    job = Job(
                        title=(title or snippet or url)[:240], company=company, location='',
                        description=(snippet or title)[:6000], source_id=source_id,
                        source_url=url, canonical_url=url,
                        raw={
                            'discovered_via':'agent-reach-exa',
                            'source_platform':platform_name,
                            'source_domain':host,
                            'discovery_only':discovery_only,
                            'query':query,
                            'result':raw,
                            'source_kind':'community',
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
