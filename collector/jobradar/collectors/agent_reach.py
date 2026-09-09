import os, subprocess, shlex, json
from ..models import Job

class AgentReachCollector:
    """Optional discovery adapter. It executes explicitly configured commands.
    Agent Reach itself configures upstream platform tools; it is not assumed to expose a universal search API.
    """
    def collect_command(self, command_template, query, source_id='agent-reach'):
        if os.getenv('AGENT_REACH_ENABLED','false').lower() != 'true': return []
        args=[part.replace('{query}', query) for part in command_template]
        p=subprocess.run(args, capture_output=True, text=True, timeout=90, check=False)
        if p.returncode != 0: return []
        text=p.stdout.strip(); out=[]
        try:
            data=json.loads(text)
            if isinstance(data,list):
                for x in data:
                    url=x.get('url') or x.get('html_url') or ''
                    title=x.get('title') or x.get('name') or str(x)[:120]
                    if url: out.append(Job(title=title,company='Community discovery',location='',description=str(x),source_id=source_id,source_url=url,canonical_url=url,raw=x))
        except Exception:
            for line in text.splitlines():
                if 'http' in line:
                    url=line[line.find('http'):].split()[0]
                    out.append(Job(title=line[:160],company='Community discovery',location='',description=line,source_id=source_id,source_url=url,canonical_url=url))
        return out
