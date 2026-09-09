from __future__ import annotations

import base64
import hashlib
import json
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ENV_MAP = {
    'ntfy_server':'NTFY_SERVER','ntfy_topic':'NTFY_TOPIC',
    'telegram_bot_token':'TELEGRAM_BOT_TOKEN','telegram_chat_id':'TELEGRAM_CHAT_ID',
    'smtp_host':'SMTP_HOST','smtp_port':'SMTP_PORT','smtp_username':'SMTP_USERNAME','smtp_password':'SMTP_PASSWORD',
    'alert_email_from':'ALERT_EMAIL_FROM','alert_email_to':'ALERT_EMAIL_TO',
    'gemini_api_key':'GEMINI_API_KEY','gemini_model':'GEMINI_MODEL',
}

def _b64(s: str) -> bytes:
    pad='='*((4-len(s)%4)%4)
    return base64.urlsafe_b64decode((s+pad).encode())

def decrypt_payload(envelope: str) -> dict:
    parts=(envelope or '').split('.')
    if len(parts)!=4 or parts[0]!='v1':
        return {}
    seed=os.getenv('SUPABASE_SERVICE_ROLE_KEY','')
    if not seed:
        return {}
    key=hashlib.sha256(seed.encode()).digest()
    iv,body,tag=_b64(parts[1]),_b64(parts[2]),_b64(parts[3])
    raw=AESGCM(key).decrypt(iv,body+tag,None)
    obj=json.loads(raw.decode('utf-8'))
    return obj if isinstance(obj,dict) else {}

def resolve_user_id(db, user_id=None):
    if user_id:return user_id
    try:
        rows=db.select('candidate_preferences',{'select':'user_id','order':'updated_at.desc','limit':'1'})
        if rows and rows[0].get('user_id'):return rows[0].get('user_id')
    except Exception:pass
    try:
        rows=db.select('integration_settings',{'select':'user_id','order':'updated_at.desc','limit':'1'})
        if rows and rows[0].get('user_id'):return rows[0].get('user_id')
    except Exception:pass
    return None

def apply_dashboard_integrations(db, user_id=None):
    uid=resolve_user_id(db,user_id)
    if not uid:return {'loaded':False,'user_id':None,'keys':[]}
    try:
        rows=db.select('integration_settings',{'select':'encrypted_payload','user_id':f'eq.{uid}','limit':'1'})
        payload=decrypt_payload(rows[0].get('encrypted_payload','')) if rows else {}
    except Exception:
        payload={}
    loaded=[]
    for key,env in ENV_MAP.items():
        value=str(payload.get(key) or '').strip()
        if value:
            os.environ[env]=value
            loaded.append(key)
    return {'loaded':bool(loaded),'user_id':uid,'keys':loaded}
