import os, httpx

def send(text, url=None):
    topic=os.getenv('NTFY_TOPIC'); server=os.getenv('NTFY_SERVER','https://ntfy.sh').rstrip('/')
    if not topic: return False
    headers={'Title':'JobRadar South','Priority':'high','Tags':'briefcase'}
    if url:
        headers['Click']=url
        headers['Actions']=f'view, Apply now, {url}'
    try:
        r=httpx.post(f"{server}/{topic}",content=text.encode('utf-8'),headers=headers,timeout=20)
        return r.is_success
    except Exception:
        return False
