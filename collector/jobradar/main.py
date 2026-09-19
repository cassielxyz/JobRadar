from __future__ import annotations

import os
import json
import hashlib
import argparse
import html
import re
import yaml
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

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
from .scoring import score_job, source_allowed, semantic_gate, location_plausible
from .ai import review_job, merge_ai_score
from .notifications import get_settings, deliver, any_success
from .resume_match import load_candidate, apply_candidate_to_categories, personalized_score, should_queue_auto_apply
from .integration_config import apply_dashboard_integrations

ROOT = Path(__file__).resolve().parents[2]
DISPLAY_MIN_SCORE = int(os.getenv('DASHBOARD_MIN_SCORE', '40') or 40)
SUPPRESS_APPLICATION_STATUSES = {
    'queued', 'review_required', 'submitted', 'applied_manual', 'interview',
    'offer', 'rejected', 'withdrawn', 'skipped',
}


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


def _summary(value, limit=420):
    text = html.unescape(str(value or ''))
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'https?://\S+', '', text)
    text = re.sub(r'\s+', ' ', text).strip(' -–—|')
    if len(text) <= limit:
        return text
    clipped = text[:limit].rsplit(' ', 1)[0].rstrip(' ,;:-')
    return clipped + '…'


def _source_label(job):
    raw = job.raw or {}
    explicit = str(raw.get('source_platform') or raw.get('source_name') or '').strip()
    if explicit:
        return explicit[:80]
    for value in (job.apply_url, job.canonical_url, job.source_url):
        try:
            host = (urlparse(value or '').hostname or '').lower().removeprefix('www.')
        except Exception:
            host = ''
        if host:
            known = {
                'linkedin.com':'LinkedIn', 'internshala.com':'Internshala', 'shine.com':'Shine',
                'naukri.com':'Naukri', 'indeed.com':'Indeed', 'foundit.in':'Foundit',
                'cutshort.io':'Cutshort', 'wellfound.com':'Wellfound',
            }
            for domain, name in known.items():
                if host == domain or host.endswith('.' + domain):
                    return name
            return host
    return 'Verified source'


def _already_tracked_application(db, candidate, job_id):
    uid = ((candidate or {}).get('preferences') or {}).get('user_id')
    if not uid:
        return False
    try:
        rows = db.select('applications', {
            'select':'status', 'user_id':f'eq.{uid}', 'job_id':f'eq.{job_id}', 'limit':'1'
        })
        return bool(rows and str(rows[0].get('status') or '') in SUPPRESS_APPLICATION_STATUSES)
    except Exception:
        return False


def alert_text(job, cat, score, reasons):
    compensation = 'Salary not disclosed'
    if job.salary_min_monthly:
        compensation = f"₹{job.salary_min_monthly:,}/month"
        if job.salary_max_monthly and job.salary_max_monthly != job.salary_min_monthly:
            compensation += f"–₹{job.salary_max_monthly:,}/month"
    if job.stipend_monthly:
        compensation = f"Stipend ₹{job.stipend_monthly:,}/month"
    destination = job.apply_url if job.event_type == 'vacancy' else (job.notification_url or job.canonical_url)
    summary = _summary(job.description)
    source = _source_label(job)
    lines = [
        f"JobRadar Everywhere — {score}% match",
        job.title,
        job.company,
        f"Location: {job.location or 'Not disclosed'}",
        f"Compensation: {compensation}",
        f"Category: {cat.name}",
        f"Source: {source}",
    ]
    if summary:
        lines.append(f"Summary: {summary}")
    lines.append(f"Why: {'; '.join(reasons[:4])}")
    if job.deadline:
        lines.append(f"Deadline: {job.deadline}")
    if destination:
        lines.append(f"Open: {destination}")
    if job.source_url and job.source_url != destination:
        lines.append(f"Source URL: {job.source_url}")
    if job.notification_url and job.notification_url != destination:
        lines.append(f"Official notification: {job.notification_url}")
    return '\n'.join(lines)


def _enrich(job, source):
    # Prefer parsed values from structured sources, fill only missing values.
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

    # Cheap enrichment + semantic/location gates happen before network verification.
    # Country-wide/multi-location listings are retained because many boards only expose
    # the exact city after the job detail page is opened.
    job = _enrich(job, source)
    if job.application_status == 'closed':
        return
    gated = []
    for cat in target_categories:
        ok, _ = semantic_gate(job, cat)
        if not ok:
            continue
        if not location_plausible(job.location, cat.locations):
            continue
        gated.append(cat)
    target_categories = gated
    if not target_categories:
        return

    official_domains = list(source.get('official_domains') or [])
    for domain in ((job.raw or {}).get('official_domains') or []):
        if domain and domain not in official_domains:
            official_domains.append(domain)
    v = verify_url(job.canonical_url, official_domains)
    if not v.get('active'):
        return
    stats['verified'] += 1
    job.canonical_url = v['canonical_url']
    job.official_verified = v['official']

    links = resolve_job_links(
        job.canonical_url, job.source_url, official_domains,
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
        # Do not spend AI on jobs already blocked by the hard semantic/experience gates.
        ai_review = {'mode':os.getenv('AI_MODE','auto'),'results':[],'consensus':None}
        if eligible or score >= 45:
            ai_review = review_job(job, cat, score)
            score, reasons, eligible = merge_ai_score(score, reasons, eligible, ai_review, cat)
        rule_score = score
        score, resume_score, resume_reasons, skill_gaps = personalized_score(job, cat, rule_score, candidate)
        if score < DISPLAY_MIN_SCORE:
            eligible = False

        stats['matched'] += 1 if eligible else 0
        # A job is a single notification item even if it matches multiple categories.
        # Once any category has successfully alerted it, later categories/runs stay quiet.
        existing = db.select('job_matches', {'select':'alerted_at', 'job_id':f'eq.{jid}'})
        already = any(bool(x.get('alerted_at')) for x in existing)
        notify_floor = max(int(cat.alert_threshold), int(notification_settings.get('minimum_score') or 70))
        destination_ok = (
            (job.event_type == 'vacancy' and job.apply_verified and bool(job.apply_url)) or
            (job.event_type == 'exam_update' and job.official_verified and bool(job.notification_url or job.canonical_url))
        )
        tracked_application = _already_tracked_application(db, candidate, jid)
        should_alert = eligible and score >= notify_floor and destination_ok and not already and not tracked_application
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
    integration_state = apply_dashboard_integrations(db, (candidate or {}).get('preferences', {}).get('user_id') if candidate else None)
    cats = apply_candidate_to_categories(categories(db), candidate)
    sources = load_and_seed_sources(db)
    notification_settings = get_settings(db)
    errors = []
    stats = {
        'discovered':0, 'verified':0, 'matched':0, 'alerted':0,
        'notification_attempts':0, 'notification_successes':{}, 'auto_apply_queued':0,
        'dashboard_integrations': integration_state.get('keys', []),
    }

    generic = GenericCollector()
    greenhouse = GreenhouseCollector()
    lever = LeverCollector()
    freehire = FreeHireCollector()
    agent_reach = AgentReachCollector()

    source_by_id = {s['id']:s for s in sources}
    try:
        # 1) Authoritative/static sources. Special dynamic providers are handled below.
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

        # 2) FreeHire: dynamic, keyless coverage for every category that allows job boards.
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

        # 3) Agent Reach / Exa: category-aware public-web discovery for categories that allow community sources.
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
