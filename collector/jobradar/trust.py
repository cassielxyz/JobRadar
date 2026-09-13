from __future__ import annotations

import re
from urllib.parse import urlparse

TRUSTED_BOARDS = (
    'linkedin.com','naukri.com','indeed.com','foundit.in','shine.com','timesjobs.com',
    'freshersworld.com','internshala.com','cutshort.io','instahyre.com','hirist.tech',
    'iimjobs.com','apna.co','workindia.in','jobhai.com','unstop.com','wellfound.com',
    'glassdoor.co.in','jooble.org','adzuna.in','careerjet.co.in','jora.com','talent.com',
    'grabjobs.co','simplyhired.com','startup.jobs','remoteok.com','weworkremotely.com',
)
TRUSTED_ATS = (
    'greenhouse.io','lever.co','ashbyhq.com','smartrecruiters.com','myworkdayjobs.com',
    'workable.com','recruitee.com','icims.com','taleo.net','successfactors.com',
)
OFFICIAL_SUFFIXES = ('.gov.in','.nic.in','.ac.in')
SHORTENERS = ('bit.ly','tinyurl.com','t.co','cutt.ly','rb.gy','shorturl.at','rebrand.ly')
PAYMENT_SCAM = re.compile(
    r'\b(?:training fee|registration fee|security deposit|refundable deposit|processing fee|'
    r'pay(?:ment)?\s+(?:before|to\s+(?:the\s+)?recruiter)|send\s+money|gift\s*card|crypto(?:currency)?\s+payment|'
    r'upi\s+(?:payment|transfer)|bank\s+transfer\s+to\s+(?:the\s+)?recruiter)\b', re.I,
)
OFF_PLATFORM_APPLY = re.compile(
    r'\b(?:apply|send\s+(?:your\s+)?resume|contact)\b.{0,90}\b(?:whatsapp|telegram)\b|'
    r'\b(?:whatsapp|telegram)\b.{0,90}\b(?:apply|resume|job)\b', re.I | re.S,
)
TOO_GOOD = re.compile(r'\b(?:no interview|guaranteed job|guaranteed selection|earn\s+\d{5,}\s+per\s+day|instant joining without interview)\b', re.I)
PERSONAL_EMAIL = re.compile(r'\b[A-Z0-9._%+-]+@(gmail|yahoo|outlook|hotmail|protonmail)\.[A-Z]{2,}\b', re.I)


def _host(url: str) -> str:
    return (urlparse(url or '').hostname or '').lower().removeprefix('www.')


def _matches(host: str, domains) -> bool:
    return any(host == d or host.endswith('.' + d) for d in domains)


def assess_job_trust(job, category=None):
    """Conservative anti-scam gate.

    This is not a claim that a job is genuine; it blocks common scam patterns and assigns a
    source-trust score. Known boards are discovery evidence, while official/ATS destinations
    receive the strongest trust. Government application fees are not treated as scams merely
    because the word 'fee' appears in a notice.
    """
    url = job.apply_url or job.canonical_url or job.source_url or ''
    host = _host(url)
    source_host = _host(job.source_url or '')
    text = f"{job.title or ''} {job.company or ''} {job.description or ''}"
    category_type = getattr(category, 'type', '') if category is not None else ''
    reasons = []

    official = bool(job.official_verified) or any(host.endswith(s) for s in OFFICIAL_SUFFIXES)
    ats = _matches(host, TRUSTED_ATS)
    board = _matches(host, TRUSTED_BOARDS) or _matches(source_host, TRUSTED_BOARDS)

    if official:
        score = 97; reasons.append('official/public-sector domain')
    elif ats:
        score = 92; reasons.append('recognized employer ATS')
    elif job.apply_verified:
        score = 86; reasons.append('verified application destination')
    elif board:
        score = 76; reasons.append('recognized job platform')
    else:
        score = 58; reasons.append('unrecognized employer/source domain')

    if _matches(host, SHORTENERS) or _matches(source_host, SHORTENERS):
        score -= 30; reasons.append('shortened destination URL')

    # Fees are normal in some official government recruitment notices. Private-job payment
    # requests, however, are a strong scam indicator.
    if category_type != 'government' and PAYMENT_SCAM.search(text):
        return {'score': 0, 'blocked': True, 'reasons': reasons + ['requests payment/deposit from applicant']}

    if OFF_PLATFORM_APPLY.search(text) and not job.apply_verified and not official:
        return {'score': 15, 'blocked': True, 'reasons': reasons + ['application routed only through WhatsApp/Telegram']}

    if TOO_GOOD.search(text):
        score -= 35; reasons.append('guaranteed/no-interview claim')

    company = (job.company or '').strip().lower()
    if not company or company in {'unknown','unknown company','web discovery','external job-platform discovery'}:
        score -= 10; reasons.append('employer identity not established')

    if PERSONAL_EMAIL.search(text) and not (official or ats or job.apply_verified):
        score -= 15; reasons.append('personal-email recruiting contact')

    if (job.raw or {}).get('discovery_only') and not job.apply_verified:
        score -= 4; reasons.append('third-party discovery listing')

    score = max(0, min(100, int(score)))
    return {'score': score, 'blocked': score < 45, 'reasons': reasons[:6]}
