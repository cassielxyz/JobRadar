import httpx
from ..models import Job

class LeverCollector:
    def collect(self, source):
        company=(source.get('config') or {}).get('company')
        if not company: return []
        url=f"https://api.lever.co/v0/postings/{company}?mode=json"
        r=httpx.get(url,timeout=25); r.raise_for_status(); out=[]
        for x in r.json():
            cats=x.get('categories') or {}
            desc=' '.join([x.get('descriptionPlain',''), x.get('additionalPlain','')])
            out.append(Job(title=x.get('text',''),company=source['name'],location=cats.get('location',''),description=desc,
                employment_type=cats.get('commitment','unknown'),source_id=source['id'],source_url=url,canonical_url=x.get('hostedUrl',''),raw=x))
        return out
