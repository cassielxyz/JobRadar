import os
import httpx

def send_result(text):
    token=os.getenv('TELEGRAM_BOT_TOKEN');chat=os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat:return {'channel':'telegram','configured':False,'ok':False,'error':'not configured'}
    try:
        r=httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",json={'chat_id':chat,'text':text,'disable_web_page_preview':False},timeout=20)
        if r.is_success:return {'channel':'telegram','configured':True,'ok':True,'status':r.status_code}
        try:detail=str(r.json().get('description') or '')[:180]
        except Exception:detail=r.text[:180]
        return {'channel':'telegram','configured':True,'ok':False,'status':r.status_code,'error':detail or 'request failed'}
    except Exception as e:return {'channel':'telegram','configured':True,'ok':False,'error':str(e)[:180]}

def send(text):return bool(send_result(text).get('ok'))
