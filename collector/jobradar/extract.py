from __future__ import annotations

import re
from datetime import date, datetime
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from urllib.parse import urljoin

MONEY = re.compile(r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.\d+)?)\s*(k|lpa|lakh)?", re.I)
EXP_RANGE = re.compile(r"(?:(\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\+?)\s*(?:years?|yrs?)", re.I)
FRESHER = re.compile(r"\b(fresher(?:s)?|fresh graduate|entry[- ]level|no experience|required experience\s*[:\-]?\s*nil|0\s*(?:-|to|–|—)\s*[12]\s*(?:years?|yrs?)|0\+?\s*(?:years?|yrs?))\b", re.I)
DATE_TOKEN = re.compile(
    r"(?:\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b|"
    r"\b\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}\b|"
    r"\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4}\b)",
    re.I,
)
DEADLINE_CONTEXT = re.compile(r"\b(last\s+date|closing\s+date|application\s+deadline|deadline|last\s+date\s+to\s+apply|online\s+application\s+closes?)\b", re.I)
UPDATE_HINT = re.compile(r"\b(admit\s*card|hall\s*ticket|exam(?:ination)?\s+date|schedule\s+of\s+(?:exam|interview)|interview\s+schedule|shortlist|shortlisted|answer\s+key|result(?:s)?|document\s+verification)\b", re.I)
CLOSED_HINT = re.compile(r"\b(application|registration|online\s+application)\s+(?:is\s+)?closed\b|\bapplications?\s+closed\b|\bexpired\b", re.I)

LOCATION_PATTERNS = [
    ("Chennai", re.compile(r"\bchennai\b", re.I)),
    ("Tamil Nadu", re.compile(r"\btamil\s*nadu\b", re.I)),
    ("Bengaluru", re.compile(r"\b(?:bengaluru|bangalore)\b", re.I)),
    ("Kerala", re.compile(r"\bkerala\b", re.I)),
    ("Kochi, Kerala", re.compile(r"\b(?:kochi|cochin|ernakulam)\b", re.I)),
    ("Thiruvananthapuram, Kerala", re.compile(r"\b(?:thiruvananthapuram|trivandrum)\b", re.I)),
    ("Hyderabad, Telangana", re.compile(r"\bhyderabad\b", re.I)),
    ("Andhra Pradesh", re.compile(r"\bandhra\s*pradesh\b", re.I)),
    ("Puducherry", re.compile(r"\b(?:puducherry|pondicherry)\b", re.I)),
]


def money_to_monthly(value, unit):
    n = float(value.replace(',', ''))
    u = (unit or '').lower()
    if u == 'k':
        return int(n * 1000)
    if u in ('lpa', 'lakh'):
        return int(n * 100000 / 12)
    return int(n)


def infer_money(text):
    vals = []
    for m in MONEY.finditer(text or ''):
        try:
            vals.append(money_to_monthly(m.group(1), m.group(2)))
        except Exception:
            pass
    vals = [v for v in vals if 1000 <= v <= 1000000]
    return (min(vals), max(vals)) if vals else (None, None)


def infer_experience(text):
    text = text or ''
    m = EXP_RANGE.search(text)
    if m:
        if m.group(1):
            return float(m.group(1)), float(m.group(2))
        v = float(m.group(3))
        return v, v
    if FRESHER.search(text):
        return 0.0, 0.0
    return None, None


def has_explicit_fresher_evidence(text: str) -> bool:
    return bool(FRESHER.search(text or ''))


def infer_location(text: str, fallback: str = '') -> str:
    if fallback and fallback.strip():
        return fallback.strip()
    body = text or ''
    for label, pattern in LOCATION_PATTERNS:
        if pattern.search(body):
            return label
    return ''


def _parse_date_token(token: str) -> date | None:
    try:
        dt = dateparser.parse(token, dayfirst=True, fuzzy=False)
        return dt.date() if dt else None
    except Exception:
        return None


def infer_deadline(text: str) -> str | None:
    text = ' '.join((text or '').split())
    for ctx in DEADLINE_CONTEXT.finditer(text):
        window = text[ctx.end():ctx.end() + 140]
        token = DATE_TOKEN.search(window)
        if not token:
            continue
        parsed = _parse_date_token(token.group(0))
        if parsed:
            return parsed.isoformat()
    return None


def infer_event_type(title: str, text: str) -> str:
    combined = f"{title} {text[:2000]}"
    return 'exam_update' if UPDATE_HINT.search(combined) else 'vacancy'


def infer_application_status(title: str, text: str, deadline: str | None = None) -> str:
    event_type = infer_event_type(title, text)
    if event_type == 'exam_update':
        return 'update'
    if deadline:
        try:
            if date.fromisoformat(deadline) < date.today():
                return 'closed'
            return 'open'
        except Exception:
            pass
    if CLOSED_HINT.search(text or ''):
        return 'closed'
    return 'unknown'


def is_stale_title(title: str, now_year: int | None = None) -> bool:
    now_year = now_year or datetime.now().year
    years = [int(x) for x in re.findall(r"\b20\d{2}\b", title or '')]
    return bool(years and max(years) < now_year)


def visible_text(html: str) -> str:
    soup = BeautifulSoup(html or '', 'html.parser')
    for tag in soup(['script', 'style', 'noscript', 'svg']):
        tag.decompose()
    return ' '.join(soup.stripped_strings)


def best_heading(html: str, fallback: str) -> str:
    soup = BeautifulSoup(html or '', 'html.parser')
    for selector in ('h1', 'h2', 'title'):
        node = soup.find(selector)
        if node:
            value = ' '.join(node.stripped_strings).strip()
            if 4 <= len(value) <= 240:
                return value
    return fallback


def links_from_html(html, base_url):
    soup = BeautifulSoup(html, 'html.parser')
    out = []
    for a in soup.find_all('a', href=True):
        title = ' '.join(a.stripped_strings)
        href = urljoin(base_url, a['href'])
        if title and href.startswith(('http://', 'https://')):
            out.append((title, href))
    return out
