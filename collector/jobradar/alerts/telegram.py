import os, httpx

def send(text):
    token=os.getenv('TELEGRAM_BOT_TOKEN'); chat=os.getenv('TELEGRAM_CHAT_ID')
    if not token or not chat: return False
    r=httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",json={'chat_id':chat,'text':text,'disable_web_page_preview':False},timeout=20)
    return r.is_success
