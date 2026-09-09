from __future__ import annotations

import httpx
from ..models import Job
from ..extract import links_from_html, visible_text, best_heading, infer_location, is_stale_title

ROLE_HINTS = (
    'job','career','recruit','vacan','notification','apprent','engineer','scientist','technical',
    'cyber','network','security','intern','officer','signal','telecom','computer','information',
    'assistant','administrator','exam','admit','result','interview'
)

class GenericCollector:
    def __init__(self):
        self.client = httpx.Client(
            timeout=25,
            follow_redirects=True,
            headers={"User-Agent":"Mozilla/5.0 JobRadarEverywhere/0.9 (+personal job research)"},
        )

    def _detail(self, url: str, fallback_title: str):
        try:
            r = self.client.get(url)
            if r.status_code >= 400:
                return fallback_title, fallback_title, str(r.url)
            content_type = r.headers.get('content-type', '').lower()
            if 'html' not in content_type:
                return fallback_title, fallback_title, str(r.url)
            text = visible_text(r.text)[:20000]
            title = best_heading(r.text, fallback_title)
            return title, text or fallback_title, str(r.url)
        except Exception:
            return fallback_title, fallback_title, url

    def collect(self, source):
        r = self.client.get(source['url'])
        r.raise_for_status()
        default_location = ((source.get('config') or {}).get('default_location') or '').strip()
        jobs = []
        seen = set()
        for title, url in links_from_html(r.text, str(r.url))[:500]:
            low = f"{title} {url}".lower()
            if not any(k in low for k in ROLE_HINTS):
                continue
            # Do not resurrect clearly historical links from prior years.
            if is_stale_title(title):
                continue
            key = url.split('#')[0]
            if key in seen:
                continue
            seen.add(key)
            detail_title, description, final_url = self._detail(url, title[:240])
            location = infer_location(description, default_location)
            jobs.append(Job(
                title=(detail_title or title)[:240],
                company=source['name'],
                location=location,
                description=description,
                source_id=source['id'],
                source_url=source['url'],
                canonical_url=final_url,
                raw={'discovery_title': title, 'source_kind': source.get('kind')},
            ))
            # Respectful cap per government index page; next run will revisit the source.
            if len(jobs) >= 80:
                break
        return jobs
