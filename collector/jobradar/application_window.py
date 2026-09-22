from __future__ import annotations

import re
from datetime import date
from dateutil import parser as dateparser

DATE = r"(?:\d{1,2}[./-]\d{1,2}[./-]\d{2,4}|\d{1,2}\s+(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{1,2},?\s+\d{4})"

LAST_DATE = re.compile(
    rf"(?:last\s+date(?:\s+for\s+receipt\s+of\s+(?:on[- ]?line|online)\s+applications?)?|closing\s+date|application\s+deadline|last\s+date\s+to\s+apply)\D{{0,60}}({DATE})",
    re.I,
)
REGISTRATION_RANGE = re.compile(
    rf"(?:on[- ]?line|online)?\s*(?:registration|application(?:\s+period)?)\D{{0,90}}(?:from\s*)?({DATE}).{{0,100}}?(?:to|until|through|–|—)\s*({DATE})",
    re.I,
)


def _parse(token: str) -> date | None:
    try:
        value = dateparser.parse(token, dayfirst=True, fuzzy=False)
        return value.date() if value else None
    except Exception:
        return None


def infer_closing_date(text: str) -> str | None:
    body = ' '.join(str(text or '').split())
    candidates: list[date] = []
    for match in LAST_DATE.finditer(body):
        value = _parse(match.group(1))
        if value:
            candidates.append(value)
    for match in REGISTRATION_RANGE.finditer(body):
        value = _parse(match.group(2))
        if value:
            candidates.append(value)
    return max(candidates).isoformat() if candidates else None


def application_is_expired(deadline: str | None = None, text: str = '') -> bool:
    value = deadline or infer_closing_date(text)
    if not value:
        return False
    try:
        return date.fromisoformat(str(value)[:10]) < date.today()
    except Exception:
        return False
