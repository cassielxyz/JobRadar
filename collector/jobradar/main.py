import os, re, json, hashlib, argparse, yaml
from datetime import datetime, timezone
from pathlib import Path
from .db import SupabaseREST
from .models import Category
from .collectors.generic import GenericCollector
from .collectors.greenhouse import GreenhouseCollector
from .collectors.lever import LeverCollector
from .collectors.agent_reach import AgentReachCollector
from .verify import verify_url
from .linkresolver import resolve_job_links
from .extract import infer_money, infer_experience
from .scoring import score_job
from .ai import review_job, merge_ai_score
from .alerts.telegram import send as telegram_send
from .alerts.ntfy import send as ntfy_send
from .alerts.email import send as email_send

ROOT=Path(__file__).resolve().parents[2]

def fp(job):
    basis='|'.join([job.title.lower().strip(),job.company.lower().strip(),job.canonical_url.split('?')[0]])
    return hashlib.sha256(basis.encode()).hexdigest()

def categories(db):
    out=[]
    for x in db.select('categories',{'select':'*','enabled':'eq.true'}):
        out.append(Category(**{k:x[k] for k in Category.__dataclass_fields__ if k in x}))
    return out

def load_and_seed_sources(db):
    cfg=yaml.safe_load((ROOT/'config/sources.yaml').read_text())
    for s in cfg['sources']:
        payload={**s,'enabled':True,'config':s.get('config',{})}
        db.upsert('sources',payload,'id')
    return db.select('sources',{'select':'*','enabled':'eq.true','order':'priority.desc'})

def relevant_discovery(job, cats):
    text=(job.title+' '+job.description).lower()
    words=set()
    for c in cats: words.update(w.lower() for w in c.role_keywords+c.hidden_keywords)
    return any(w in text for w in words)

def alert_text(job, cat, score, reasons):
    sal='Salary not disclosed'
    if job.salary_min_monthly: sal=f"₹{job.salary_min_monthly:,}/month" + (f"–₹{job.salary_max_monthly:,}" if job.salary_max_monthly and job.salary_max_monthly!=job.salary_min_monthly else '')
    if job.stipend_monthly: sal=f"Stipend ₹{job.stipend_monthly:,}/month"
    return f"🚨 {cat.name}\n{job.title}\n{job.company}\n📍 {job.location or 'Not disclosed'}\n💰 {sal}\n🎯 Match {score}%\n✅ {'; '.join(reasons[:4])}\n🔗 Apply: {job.apply_url or job.canonical_url}" + (f"\n📄 Notification: {job.notification_url}" if job.notification_url and job.notification_url != (job.apply_url or '') else '')

def run(trigger='schedule'):
    db=SupabaseREST(); runrow=db.insert('research_runs',{'trigger':trigger})[0]; runid=runrow['id']
    cats=categories(db); sources=load_and_seed_sources(db)
    discovered=verified=matched=alerted=0; errors=[]
    generic=GenericCollector(); greenhouse=GreenhouseCollector(); lever=LeverCollector()
    try:
        for source in sources:
            try:
                if source['kind']=='ats' and (source.get('config') or {}).get('provider')=='greenhouse': found=greenhouse.collect(source)
                elif source['kind']=='ats' and (source.get('config') or {}).get('provider')=='lever': found=lever.collect(source)
                else: found=generic.collect(source)
                discovered += len(found)
                for job in found:
                    if not relevant_discovery(job,cats): continue
                    v=verify_url(job.canonical_url, source.get('official_domains') or [])
                    if not v.get('active'): continue
                    verified += 1; job.canonical_url=v['canonical_url']; job.official_verified=v['official']
                    links=resolve_job_links(job.canonical_url, job.source_url, source.get('official_domains') or [])
                    job.apply_url=links.get('apply_url'); job.notification_url=links.get('notification_url')
                    job.apply_verified=bool(links.get('apply_verified')); job.link_confidence=int(links.get('link_confidence') or 0)
                    job.salary_min_monthly,job.salary_max_monthly=infer_money(job.description)
                    job.experience_min,job.experience_max=infer_experience(job.description)
                    fingerprint=fp(job)
                    rows=db.upsert('jobs',{
                      'fingerprint':fingerprint,'title':job.title,'company':job.company,'location':job.location,'description':job.description[:10000],
                      'employment_type':job.employment_type,'experience_min':job.experience_min,'experience_max':job.experience_max,
                      'salary_min_monthly':job.salary_min_monthly,'salary_max_monthly':job.salary_max_monthly,'stipend_monthly':job.stipend_monthly,
                      'source_id':job.source_id,'source_url':job.source_url,'canonical_url':job.canonical_url,'official_verified':job.official_verified,
                      'apply_url':job.apply_url,'notification_url':job.notification_url,'apply_verified':job.apply_verified,'link_confidence':job.link_confidence,
                      'active':True,'deadline':job.deadline,'posted_at':job.posted_at,'last_seen_at':datetime.now(timezone.utc).isoformat(),'raw':job.raw
                    },'fingerprint')
                    jid=rows[0]['id']
                    for cat in cats:
                        score,reasons,eligible=score_job(job,cat)
                        if score < 45: continue
                        ai_review=review_job(job,cat,score)
                        score,reasons,eligible=merge_ai_score(score,reasons,eligible,ai_review)
                        matched += 1
                        existing=db.select('job_matches',{'select':'alerted_at','job_id':f'eq.{jid}','category_id':f'eq.{cat.id}'})
                        already=bool(existing and existing[0].get('alerted_at'))
                        should_alert=eligible and score>=cat.alert_threshold and job.apply_verified and bool(job.apply_url) and not already
                        payload={'job_id':jid,'category_id':cat.id,'score':score,'reasons':reasons,'eligible':eligible,'ai_review':ai_review}
                        if should_alert:
                            text=alert_text(job,cat,score,reasons)
                            tg=telegram_send(text)
                            nt=ntfy_send(text, job.apply_url)
                            em=email_send(f'JobRadar: {job.title} — {score}% match', text)
                            if tg or nt or em:
                                payload['alerted_at']=datetime.now(timezone.utc).isoformat(); alerted += 1
                        db.upsert('job_matches',payload,'job_id,category_id')
            except Exception as e:
                errors.append({'source':source['id'],'error':str(e)[:500]})
                db.update('sources',{'last_error':str(e)[:1000]},{'id':f"eq.{source['id']}"})
        db.update('research_runs',{'finished_at':datetime.now(timezone.utc).isoformat(),'status':'completed','discovered':discovered,'verified':verified,'matched':matched,'alerted':alerted,'errors':errors},{'id':f'eq.{runid}'})
    except Exception as e:
        db.update('research_runs',{'finished_at':datetime.now(timezone.utc).isoformat(),'status':'failed','errors':errors+[{'fatal':str(e)}]},{'id':f'eq.{runid}'})
        raise
    print(json.dumps({'discovered':discovered,'verified':verified,'matched':matched,'alerted':alerted,'errors':errors},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--trigger',default='schedule'); args=p.parse_args(); run(args.trigger)
