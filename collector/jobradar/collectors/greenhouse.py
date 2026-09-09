import httpx
from ..models import Job

class GreenhouseCollector:
    """Requires source.config.board_token, e.g. company board token."""
    def collect(self, source):
        token=(source.get('config') or {}).get('board_token')
        if not token: return []
        url=f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        r=httpx.get(url,timeout=25); r.raise_for_status(); out=[]
        for x in r.json().get('jobs',[]):
            out.append(Job(title=x.get('title',''),company=source['name'],location=(x.get('location') or {}).get('name',''),
                description=x.get('content',''),source_id=source['id'],source_url=url,canonical_url=x.get('absolute_url',''),posted_at=x.get('updated_at'),raw=x))
        return out
