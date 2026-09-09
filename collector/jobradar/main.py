from __future__ import annotations

import os
import json
import hashlib
import argparse
import yaml
from datetime import datetime, timezone
from pathlib import Path

from .db import SupabaseREST
from .models import Category
from .collectors.generic import GenericCollector
from .collectors.greenhouse import GreenhouseCollector
from .collectors.lever import LeverCollector
from .collectors.freehire import FreeHireCollector
from .collectors.agent_reach import AgentReachCollector
from .verify import verify_url
from .linkresolver import resolve_job_links
from .extract import (
    infer_money, infer_experience, infer_deadline, infer_event_type,
    infer_application_status, infer_location, is_stale_title,
)
from .scoring import score_job, source_allowed
from .ai import review_job, merge_ai_score
from .notifications import get_settings, deliver, any_success
from .resume_match import load_candidate, apply_candidate_to_categories, personalized_score, should_queue_auto_apply

ROOT = Path(__file__).resolve().parents[2]
DISPLAY_MIN_SCORE = int(os.getenv('DASHBOARD_MIN_SCORE', '55') or 55)


def fp(job):
    basis = '|'.join([
        job.title.lower().strip(), job.company.lower().strip(),
        job.canonical_url.split('?')[0], job.event_type,
    ])
    return hashlib.sha256(basis.encode()).hexdigest()


def categories(db):
    out = []
    for x in db.select('categories', {'select':'*','enabled':'eq.true'}):
        out.append(Category(**{k:x[k] for k in Category.__dataclass_fields__ if k in x}))
    return out


def load_and_seed_sources(db):
    cfg = yaml.safe_load((ROOT/'config/sources.yaml').read_text())
    for s in cfg['sources']:
        payload = {
            **s,
            'enabled': bool(s.get('enabled', True)),
            'config': s.get('config', {}),
        }
        db.upsert('sources', payload, 'id')
    return db.select('sources', {'select':'*','enabled':'eq.true','order':'priority.desc'})


def alert_text(job, cat, score, reasons):
    compensation = 'Salary not disclosed'
    if job.salary_min_monthly:
        compensation = f"₹{job.salary_min_monthly:,}/month"
        if job.salary_max_monthly and job.salary_max_monthly != job.salary_min_monthly:
            compensation += f"–₹{job.salary_max_monthly:,}/month"
    if job.stipend_monthly:
        compensation = f"Stipend ₹{job.stipend_monthly:,}/month"
    destination = job.apply_url if job.event_type == 'vacancy' else (job.notification_url or job.canonical_url)
    lines = [
        f"JobRadar South — {score}% match",
        job.title,
        job.company,
        f"Location: {job.location or 'Not disclosed'}",
        f"Compensation: {compensation}",
        f"Category: {cat.name}",
        f"Why: {'; '.join(reasons[:4])}",
    ]
    if job.deadline:
        lines.append(f"Deadline: {job.deadline}")
    if destination:
        lines.append(f"Open: {destination}")
    if job.notification_url and job.notification_url != destination:
        lines.append(f"Official notification: {job.notification_url}")
    return '\n'.join(lines)


def _enrich(job, source):
    text = job.description or ''
    if not job.location:
        job.location = infer_location(text, ((source.get('config') or {}).get('default_location') or ''))
    if job.salary_min_monthly is None:
        job.salary_min_monthly, job.salary_max_monthly = infer_money(text)
    if job.experience_min is None and job.experience_max is None:
        job.experience_min, job.experience_max = infer_experience(text)
    job.deadline = job.deadline or infer_deadline(text)
    job.event_type = infer_event_type(job.title, text)
    job.application_status = infer_application_status(job.title, text, job.deadline)
    return job


def _process_job(db, job, source, target_categories, run_errors, notification_settings, stats, candidate=None):
    if is_stale_title(job.title):
        return
    source_kind = source.get('kind') or (job.raw or {}).get('source_kind') or ''
    target_categories = [c for c in target_categories if source_allowed(c, source_kind)]
    if not target_categories:
        return

    v = verify_url(job.canonical_url, source.get('official_domains') or [])
    if not v.get('active'):
        return
    stats['verified'] += 1
    job.canonical_url = v['canonical_url']
    job.official_verified = v['official']
    job = _enrich(job, source)
    if job.application_status == 'closed':
        return

    links = resolve_job_links(
        job.canonical_url, job.source_url, source.get('official_domains') or [],
        trusted_listing=(source.get('id') == 'freehire'),
    )
    job.apply_url = links.get('apply_url')
    job.notification_url = links.get('notification_url')
    job.apply_verified = bool(links.get('apply_verified'))
    job.link_confidence = int(links.get('link_confidence') or 0)
    if job.event_type == 'exam_update' and job.official_verified and not job.notification_url:
        job.notification_url = job.canonical_url

    fingerprint = fp(job)
    rows = db.upsert('jobs', {
        'fingerprint':fingerprint,
        'title':job.title,
        'company':job.company,
        'location':job.location,
        'description':job.description[:10000],
        'employment_type':job.employment_type,
        'experience_min':job.experience_min,
        'experience_max':job.experience_max,
        'salary_min_monthly':job.salary_min_monthly,
        'salary_max_monthly':job.salary_max_monthly,
        'stipend_monthly':job.stipend_monthly,
        'source_id':job.source_id,
        'source_url':job.source_url,
        'canonical_url':job.canonical_url,
        'official_verified':job.official_verified,
        'apply_url':job.apply_url,
        'notification_url':job.notification_url,
        'apply_verified':job.apply_verified,
        'link_confidence':job.link_confidence,
        'event_type':job.event_type,
        'application_status':job.application_status,
        'active':True,
        'deadline':job.deadline,
        'posted_at':job.posted_at,
        'last_seen_at':datetime.now(timezone.utc).isoformat(),
        'raw':job.raw,
    }, 'fingerprint')
    if not rows:
        return
    jid = rows[0]['id']

    for cat in target_categories:
        score, reasons, eligible = score_job(job, cat)
        ai_review = {'mode':os.getenv('AI_MODE','auto'),'results':[],'consensus':None}
        if eligible or score >= 45:
            ai_review = review_job(job, cat, score)
            score, reasons, eligible = merge_ai_score(score, reasons, eligible, ai_review)
        rule_score = score
        score, resume_score, resume_reasons, skill_gaps = personalized_score(job, cat, rule_score, candidate)
        if score < DISPLAY_MIN_SCORE:
            eligible = False

        stats['matched'] += 1 if eligible else 0
        existing = db.select('job_matches', {
            'select':'alerted_at', 'job_id':f'eq.{jid}', 'category_id':f'eq.{cat.id}'
        })
        already = bool(existing and existing[0].get('alerted_at'))
        notify_floor = max(int(cat.alert_threshold), int(notification_settings.get('minimum_score') or 70))
        destination_ok = (
            (job.event_type == 'vacancy' and job.apply_verified and bool(job.apply_url)) or
            (job.event_type == 'exam_update' and job.official_verified and bool(job.notification_url or job.canonical_url))
        )
        should_alert = eligible and score >= notify_floor and destination_ok and not already
        active_resume_id = (candidate or {}).get('preferences', {}).get('active_resume_id') if candidate else None
        payload = {
            'job_id':jid, 'category_id':cat.id, 'score':score, 'rule_score':rule_score, 'reasons':reasons,
            'eligible':eligible, 'ai_review':ai_review, 'resume_id':active_resume_id,
            'resume_score':resume_score, 'resume_reasons':resume_reasons, 'skill_gaps':skill_gaps,
        }
        if should_alert:
            text = alert_text(job, cat, score, reasons)
            dest = job.apply_url if job.event_type == 'vacancy' else (job.notification_url or job.canonical_url)
            results = deliver(f'JobRadar: {job.title} — {score}% match', text, dest, notification_settings)
            stats['notification_attempts'] += 1
            for result in results:
                if result.get('ok'):
                    stats['notification_successes'][result['channel']] = stats['notification_successes'].get(result['channel'], 0) + 1
                elif result.get('configured'):
                    run_errors.append({'notification':result.get('channel'),'error':result.get('error') or f"HTTP {result.get('status')}"})
            if any_success(results):
                payload['alerted_at'] = datetime.now(timezone.utc).isoformat()
                stats['alerted'] += 1

        queue, queue_reason = should_queue_auto_apply(job, cat, score, candidate)
        if queue and eligible and candidate:
            pref=(candidate.get('preferences') or {})
            uid=pref.get('user_id')
            rid=pref.get('active_resume_id')
            if uid and rid:
                try:
                    db.upsert('applications', {
                        'user_id':uid, 'job_id':jid, 'resume_id':rid, 'status':'queued', 'method':'auto',
                        'score':score, 'apply_url':job.apply_url,
                        'details':{'queue_reason':queue_reason,'category':cat.name,'auto_submit_enabled':bool(pref.get('auto_submit_enabled'))},
                        'updated_at':datetime.now(timezone.utc).isoformat(),
                    }, 'user_id,job_id')
                    stats['auto_apply_queued']=stats.get('auto_apply_queued',0)+1
                except Exception as e:
                    run_errors.append({'auto_apply_queue':jid,'error':str(e)[:300]})
        db.upsert('job_matches', payload, 'job_id,category_id')


def run(trigger='schedule'):
    db = SupabaseREST()
    runrow = db.insert('research_runs', {'trigger':trigger})[0]
    runid = runrow['id']
    candidate = load_candidate(db)
    cats = apply_candidate_to_categories(categories(db), candidate)
    sources = load_and_seed_sources(db)
    notification_settings = get_settings(db)
    errors = []
    stats = {
        'discovered':0, 'verified':0, 'matched':0, 'alerted':0,
        'notification_attempts':0, 'notification_successes':{}, 'auto_apply_queued':0,
    }

    generic = GenericCollector()
    greenhouse = GreenhouseCollector()
    lever = LeverCollector()
    freehire = FreeHireCollector()
    agent_reach = AgentReachCollector()

    source_by_id = {s['id']:s for s in sources}
    try:
        for source in sources:
            provider = (source.get('config') or {}).get('provider')
            if provider in {'freehire','agent_reach'}:
                continue
            try:
                source_cats = [c for c in cats if source_allowed(c, source.get('kind') or '')]
                if not source_cats:
                    continue
                if source['kind'] == 'ats' and provider == 'greenhouse':
                    found = greenhouse.collect(source)
                elif source['kind'] == 'ats' and provider == 'lever':
                    found = lever.collect(source)
                else:
                    found = generic.collect(source)
                stats['discovered'] += len(found)
                for job in found:
                    _process_job(db, job, source, source_cats, errors, notification_settings, stats, candidate)
                db.update('sources', {'last_ok_at':datetime.now(timezone.utc).isoformat(),'last_error':None}, {'id':f"eq.{source['id']}"})
            except Exception as e:
                errors.append({'source':source['id'],'error':str(e)[:500]})
                db.update('sources', {'last_error':str(e)[:1000]}, {'id':f"eq.{source['id']}"})

        fh_source = source_by_id.get('freehire')
        if fh_source:
            for cat in [c for c in cats if source_allowed(c, 'job_board')]:
                try:
                    found = freehire.collect(cat, fh_source['id'])
                    stats['discovered'] += len(found)
                    for job in found:
                        _process_job(db, job, fh_source, [cat], errors, notification_settings, stats, candidate)
                except Exception as e:
                    errors.append({'source':'freehire','category':cat.slug,'error':str(e)[:500]})

        ar_source = source_by_id.get('agent-reach')
        if ar_source and agent_reach.enabled():
            for cat in [c for c in cats if source_allowed(c, 'community')]:
                try:
                    found = agent_reach.collect(cat, ar_source['id'])
                    stats['discovered'] += len(found)
                    for job in found:
                        _process_job(db, job, ar_source, [cat], errors, notification_settings, stats, candidate)
                except Exception as e:
                    errors.append({'source':'agent-reach','category':cat.slug,'error':str(e)[:500]})

        db.update('research_runs', {
            'finished_at':datetime.now(timezone.utc).isoformat(), 'status':'completed',
            'discovered':stats['discovered'], 'verified':stats['verified'],
            'matched':stats['matched'], 'alerted':stats['alerted'], 'errors':errors,
            'notification_status':{
                'attempts':stats['notification_attempts'],
                'successes':stats['notification_successes'],
                'auto_apply_queued':stats.get('auto_apply_queued',0),
            },
        }, {'id':f'eq.{runid}'})
    except Exception as e:
        db.update('research_runs', {
            'finished_at':datetime.now(timezone.utc).isoformat(), 'status':'failed',
            'errors':errors+[{'fatal':str(e)}],
        }, {'id':f'eq.{runid}'})
        raise

    print(json.dumps({**stats, 'errors':errors}, indent=2))


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--trigger', default='schedule')
    args = p.parse_args()
    run(args.trigger)
