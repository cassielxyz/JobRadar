from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from urllib.parse import urlparse
from ..models import Job, Category
from ..scoring import semantic_gate

URL_RE = re.compile(r'https?://[^\s\]\)\}"\']+')
SOCIAL = ('linkedin.com','reddit.com','x.com','twitter.com','instagram.com','facebook.com','indeed.com','naukri.com','wellfound.com','cutshort.io','instahyre.com','foundit.in')


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


class AgentReachCollector:
    """Optional Exa/web discovery through Agent Reach's configured upstream tools.

    Agent Reach is a router/installer, so JobRadar calls mcporter/Exa directly when that
    backend is actually available. Failure is non-fatal because FreeHire and direct sources
    remain active.
    """
    def enabled(self):
        return os.getenv('AGENT_REACH_ENABLED','false').lower() == 'true'

    def available(self):
        return self.enabled() and bool(shutil.which('mcporter'))

    def _queries(self, category: Category):
        loc = ' '.join(category.locations[:8]) or 'India remote'
        roles = [str(x).strip() for x in category.role_keywords[:4] if str(x).strip()]
        if not roles:
            return []
        queries = []
        for role in roles[:3]:
            base = f'"{role}" {loc}'
            if getattr(category, 'fresher_only', False):
                base += ' fresher OR "entry level" OR junior OR graduate'
            if category.type == 'internship':
                base = f'"{role}" internship stipend {loc}'
            elif category.type == 'startup':
                base += ' startup'
            queries.extend([
                f'{base} careers apply',
                f'{base} site:linkedin.com/jobs/view',
                f'{base} site:in.indeed.com/viewjob',
                f'{base} site:naukri.com/job-listings',
                f'{base} (site:wellfound.com/jobs OR site:cutshort.io OR site:instahyre.com)',
                f'{base} (site:jobs.lever.co OR site:boards.greenhouse.io OR site:jobs.ashbyhq.com OR site:careers.smartrecruiters.com)',
            ])
        # Startup/company discovery catches roles that never make it to the large boards.
        if category.type in {'startup','entry_level','custom'}:
            queries.append(f'India startup careers {loc} networking cybersecurity cloud infrastructure jobs')
            queries.append(f'"careers" "security" startup {loc} "apply"')
        out=[]
        seen=set()
        for q in queries:
            key=q.casefold()
            if key not in seen:
                seen.add(key);out.append(q)
            if len(out)>=18:
                break
        return out

    def _call_exa(self, query: str):
        if not self.available():
            return []
        cmd = ['mcporter','call','exa.web_search_exa',f'query={query}','numResults=4']
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=35, check=False)
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

    def collect(self, category: Category, source_id='agent-reach'):
        out, seen = [], set()
        for query in self._queries(category):
            for title, url, snippet, raw in self._call_exa(query):
                if not url or url in seen:
                    continue
                seen.add(url)
                # Social links are valid discovery evidence but intentionally cannot become a
                # verified final Apply button unless another resolver later finds an official page.
                company = 'Web discovery'
                if any(_host(url).endswith(d) for d in SOCIAL):
                    company = 'External job-platform discovery'
                job=Job(
                    title=(title or snippet or url)[:240], company=company, location='',
                    description=(snippet or title)[:6000], source_id=source_id,
                    source_url=url, canonical_url=url,
                    raw={'discovered_via':'agent-reach-exa','query':query,'result':raw,'source_kind':'community'}
                )
                relevant, _ = semantic_gate(job, category)
                if not relevant:
                    continue
                out.append(job)
                if len(out) >= 18:
                    return out
        return out
