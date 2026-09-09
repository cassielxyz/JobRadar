from __future__ import annotations
import json, os, re, tempfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
import httpx
from playwright.sync_api import sync_playwright
from .db import SupabaseREST

SUPPORTED_HOSTS=('greenhouse.io','lever.co','ashbyhq.com')
SENSITIVE=re.compile(r'gender|race|ethnicity|disability|veteran|sexual orientation|religion|marital|date of birth|age',re.I)
CAPTCHA=re.compile(r'captcha|recaptcha|hcaptcha',re.I)

def host_ok(url):
    h=(urlparse(url).hostname or '').lower()
    return any(h==x or h.endswith('.'+x) for x in SUPPORTED_HOSTS)

def storage_download(path:str)->bytes:
    base=os.environ['SUPABASE_URL'].rstrip('/')
    key=os.environ['SUPABASE_SERVICE_ROLE_KEY']
    r=httpx.get(f"{base}/storage/v1/object/resumes/{path}",headers={'apikey':key,'Authorization':f'Bearer {key}'},timeout=30)
    r.raise_for_status(); return r.content

def split_name(full):
    p=[x for x in str(full or '').strip().split() if x]
    return (p[0] if p else '', ' '.join(p[1:]) if len(p)>1 else '')

def _try_fill(page, labels, value):
    if not value:return False
    for label in labels:
        try:
            el=page.get_by_label(re.compile(label,re.I)).first
            if el.count(): el.fill(str(value)); return True
        except: pass
    return False

def _required_unanswered(page):
    out=[]
    try:
        els=page.locator('input[required], textarea[required], select[required]')
        for i in range(min(els.count(),80)):
            e=els.nth(i)
            try:
                if not e.is_visible():continue
                typ=(e.get_attribute('type') or '').lower()
                if typ in ('hidden','submit','button'):continue
                aria=e.get_attribute('aria-label') or ''
                name=e.get_attribute('name') or ''
                placeholder=e.get_attribute('placeholder') or ''
                label=' '.join([aria,name,placeholder])
                if typ in ('checkbox','radio'):
                    if not e.is_checked():out.append(label or typ)
                else:
                    if not (e.input_value() or '').strip():out.append(label or e.evaluate('(x)=>x.outerHTML').strip()[:120])
            except: pass
    except: pass
    return out[:20]

def run_one(db, app, prefs, resume):
    url=app.get('apply_url') or ''
    if not host_ok(url):
        db.update('applications',{'status':'review_required','details':{**(app.get('details') or {}),'reason':'unsupported application host'},'updated_at':datetime.now(timezone.utc).isoformat()},{'id':f"eq.{app['id']}"}); return
    parsed=resume.get('parsed_json') or {}; first,last=split_name(parsed.get('full_name'))
    answers=prefs.get('application_answers') or {}
    with tempfile.TemporaryDirectory() as td:
        fp=Path(td)/resume.get('original_filename','resume.pdf'); fp.write_bytes(storage_download(resume['storage_path']))
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1100})
            try:
                page.goto(url,wait_until='domcontentloaded',timeout=45000); page.wait_for_timeout(1500)
                body=page.locator('body').inner_text(timeout=5000)
                if CAPTCHA.search(body):
                    raise RuntimeError('captcha detected')
                _try_fill(page,['first name','given name'],first)
                _try_fill(page,['last name','surname','family name'],last)
                _try_fill(page,['email'],parsed.get('email') or answers.get('email'))
                _try_fill(page,['phone','mobile'],parsed.get('phone') or answers.get('phone'))
                _try_fill(page,['location','city'],answers.get('current_city'))
                _try_fill(page,['linkedin'],parsed.get('linkedin_url') or answers.get('linkedin_url'))
                _try_fill(page,['github'],parsed.get('github_url') or answers.get('github_url'))
                _try_fill(page,['website','portfolio'],answers.get('portfolio_url'))
                try:
                    up=page.locator('input[type=file]').first
                    if up.count():up.set_input_files(str(fp))
                except: pass
                if SENSITIVE.search(body):
                    pass
                unresolved=_required_unanswered(page)
                if unresolved:
                    db.update('applications',{'status':'review_required','details':{**(app.get('details') or {}),'reason':'required questions need review','unresolved':unresolved},'updated_at':datetime.now(timezone.utc).isoformat()},{'id':f"eq.{app['id']}"}); return
                if not prefs.get('auto_submit_enabled'):
                    db.update('applications',{'status':'review_required','details':{**(app.get('details') or {}),'reason':'form prefill ready; auto-submit disabled'},'updated_at':datetime.now(timezone.utc).isoformat()},{'id':f"eq.{app['id']}"}); return
                btn=page.get_by_role('button',name=re.compile(r'^(submit application|submit|apply)$',re.I)).first
                if not btn.count():
                    raise RuntimeError('submit button not recognized')
                btn.click(); page.wait_for_timeout(2500)
                txt=page.locator('body').inner_text(timeout=5000)
                success=bool(re.search(r'thank you|application (?:has been )?submitted|we received your application',txt,re.I))
                status='submitted' if success else 'review_required'
                details={**(app.get('details') or {}),'reason':'submitted by safe ATS adapter' if success else 'submission confirmation not detected'}
                db.update('applications',{'status':status,'details':details,'submitted_at':datetime.now(timezone.utc).isoformat() if success else None,'updated_at':datetime.now(timezone.utc).isoformat()},{'id':f"eq.{app['id']}"})
            except Exception as e:
                db.update('applications',{'status':'review_required','details':{**(app.get('details') or {}),'reason':str(e)[:300]},'updated_at':datetime.now(timezone.utc).isoformat()},{'id':f"eq.{app['id']}"})
            finally: browser.close()

def run():
    db=SupabaseREST(); apps=db.select('applications',{'select':'*','status':'eq.queued','order':'created_at.asc','limit':'15'})
    for app in apps:
        p=db.select('candidate_preferences',{'select':'*','user_id':f"eq.{app['user_id']}",'limit':'1'})
        r=db.select('resumes',{'select':'*','id':f"eq.{app.get('resume_id')}",'limit':'1'}) if app.get('resume_id') else []
        if not p or not r: continue
        run_one(db,app,p[0],r[0])
    print(json.dumps({'processed':len(apps)}))

if __name__=='__main__': run()
