import os
import httpx

def send_result(text,url=None):
    topic=os.getenv('NTFY_TOPIC');server=os.getenv('NTFY_SERVER','https://ntfy.sh').rstrip('/')
    if not topic:return {'channel':'ntfy','configured':False,'ok':False,'error':'not configured'}
    headers={'Title':'JobRadar South','Priority':'high'}
    if url:headers['Click']=url;headers['Actions']=f'view, Apply now, {url}'
    try:
        r=httpx.post(f"{server}/{topic}",content=text.encode('utf-8'),headers=headers,timeout=20)
        return {'channel':'ntfy','configured':True,'ok':r.is_success,'status':r.status_code,'error':None if r.is_success else r.text[:180]}
    except Exception as e:return {'channel':'ntfy','configured':True,'ok':False,'error':str(e)[:180]}

def send(text,url=None):return bool(send_result(text,url).get('ok'))
