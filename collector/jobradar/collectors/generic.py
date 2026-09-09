import httpx
from bs4 import BeautifulSoup
from ..models import Job
from ..extract import links_from_html

ROLE_HINTS = ('job','career','recruit','vacan','notification','apprent','engineer','scientist','technical','cyber','network','security','intern','officer','signal','telecom','computer','information')

class GenericCollector:
    def collect(self, source):
        with httpx.Client(timeout=25, follow_redirects=True, headers={"User-Agent":"Mozilla/5.0 JobRadarSouth"}) as c:
            r=c.get(source['url']); r.raise_for_status()
        jobs=[]
        for title,url in links_from_html(r.text, str(r.url))[:400]:
            if any(k in title.lower() or k in url.lower() for k in ROLE_HINTS):
                jobs.append(Job(title=title[:240], company=source['name'], location='', description=title,
                    source_id=source['id'], source_url=source['url'], canonical_url=url, raw={'discovery_title':title}))
        return jobs
