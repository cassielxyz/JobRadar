from __future__ import annotations

import re
from typing import Any


def _norm(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").lower()).strip()


DEGREE_PATTERNS = {
    "me_mtech": re.compile(r"\b(?:m\.?\s*e\.?|m\.?\s*tech\.?|master(?:'s)?\s+of\s+(?:engineering|technology))\b", re.I),
    "msc": re.compile(r"\b(?:m\.?\s*sc\.?|master(?:'s)?\s+of\s+science)\b", re.I),
    "mca": re.compile(r"\b(?:m\.?\s*c\.?\s*a\.?|master(?:'s)?\s+of\s+computer\s+applications?)\b", re.I),
    "be_btech": re.compile(r"\b(?:b\.?\s*e\.?|b\.?\s*tech\.?|bachelor(?:'s)?\s+of\s+(?:engineering|technology))\b", re.I),
    "bsc": re.compile(r"\b(?:b\.?\s*sc\.?|bachelor(?:'s)?\s+of\s+science)\b", re.I),
    "bca": re.compile(r"\b(?:b\.?\s*c\.?\s*a\.?|bachelor(?:'s)?\s+of\s+computer\s+applications?)\b", re.I),
    "diploma": re.compile(r"\b(?:diploma|polytechnic)\b", re.I),
    "iti": re.compile(r"\b(?:i\.?\s*t\.?\s*i\.?|ntc|nac|national\s+trade\s+certificate|national\s+apprenticeship\s+certificate)\b", re.I),
}

GENERIC_BACHELOR = re.compile(r"\bbachelor(?:'s)?\s+degree\b|\bgraduate\s+degree\b", re.I)
GENERIC_MASTER = re.compile(r"\bmaster(?:'s)?\s+degree\b|\bpost[- ]?graduate\s+degree\b", re.I)
EQUIVALENT = re.compile(r"\bor\s+equivalent\b|\bequivalent\s+qualification\b|\bequivalent\s+degree\b", re.I)
ANY_DISCIPLINE = re.compile(r"\bany\s+(?:engineering\s+)?discipline\b|\bany\s+branch\b|\bany\s+degree\b", re.I)

FIELD_PATTERNS = {
    "cse_it": re.compile(r"\b(?:computer\s+science(?:\s+(?:and|&)\s+engineering)?|cse|information\s+technology|computer\s+engineering|software\s+engineering)\b", re.I),
    "electronics": re.compile(r"\b(?:electronics(?:\s+(?:and|&)\s+communication)?|ece|electronic\s+engineering|communication\s+engineering)\b", re.I),
    "electrical": re.compile(r"\b(?:electrical(?:\s+(?:and|&)\s+electronics)?|eee|electrical\s+engineering)\b", re.I),
    "mechanical": re.compile(r"\bmechanical(?:\s+engineering)?\b", re.I),
    "civil": re.compile(r"\bcivil(?:\s+engineering)?\b", re.I),
    "telecom": re.compile(r"\b(?:telecommunications?|telecom(?:munication)?\s+engineering)\b", re.I),
}

BACHELOR_FAMILIES = {"be_btech", "bsc", "bca"}
MASTER_FAMILIES = {"me_mtech", "msc", "mca"}
DISPLAY_DEGREE = {
    "me_mtech": "M.E/M.Tech",
    "msc": "M.Sc",
    "mca": "MCA",
    "be_btech": "B.E/B.Tech",
    "bsc": "B.Sc",
    "bca": "BCA",
    "diploma": "Diploma",
    "iti": "ITI/NTC/NAC",
    "bachelor_generic": "Bachelor's degree",
    "master_generic": "Master's degree",
}
DISPLAY_FIELD = {
    "cse_it": "Computer Science/IT",
    "electronics": "Electronics/ECE",
    "electrical": "Electrical/EEE",
    "mechanical": "Mechanical",
    "civil": "Civil",
    "telecom": "Telecommunications",
}


def _families(text: str) -> set[str]:
    out = {name for name, rx in DEGREE_PATTERNS.items() if rx.search(text or "")}
    if GENERIC_BACHELOR.search(text or ""):
        out.add("bachelor_generic")
    if GENERIC_MASTER.search(text or ""):
        out.add("master_generic")
    return out


def _fields(text: str) -> set[str]:
    return {name for name, rx in FIELD_PATTERNS.items() if rx.search(text or "")}


def _candidate_text(candidate) -> str:
    resume = (candidate or {}).get("resume") or {}
    parsed = resume.get("parsed_json") or {}
    education = [*(resume.get("education") or []), *(parsed.get("education") or [])]
    text = " ".join(str(x) for x in education if x)
    if not text.strip():
        text = str(resume.get("raw_text") or "")[:8000]
    return _norm(text)


def _job_scope(job) -> str:
    text = _norm(f"{getattr(job, 'title', '')} {getattr(job, 'description', '')}")
    title = _norm(getattr(job, "title", ""))
    if not text:
        return ""

    anchors: list[str] = []
    for rx in FIELD_PATTERNS.values():
        m = rx.search(title)
        if m:
            anchors.append(m.group(0))
    role_rx = re.compile(r"\b(?:scientist|scientific\s+assistant|technical\s+assistant|engineer|officer|technician|analyst|administrator)\b", re.I)
    for m in role_rx.finditer(title):
        anchors.append(m.group(0))

    windows: list[str] = []
    for anchor in dict.fromkeys(anchors):
        m = re.search(re.escape(anchor), text, re.I)
        if m:
            windows.append(text[max(0, m.start() - 700): min(len(text), m.end() + 1400)])
    return " ".join(windows) if windows else text


def _degree_match(required: set[str], candidate: set[str]) -> bool:
    exact = {x for x in required if x not in {"bachelor_generic", "master_generic"}}
    if exact & candidate:
        return True
    if "bachelor_generic" in required and candidate & BACHELOR_FAMILIES:
        return True
    if "master_generic" in required and candidate & MASTER_FAMILIES:
        return True
    return False


def qualification_gate(job, candidate, strict: bool = False) -> dict:
    """Compare formal education separately from skill/role relevance.

    Government recruitment is intentionally conservative: an explicitly named B.Sc,
    Diploma or ITI requirement is not treated as satisfied by B.E/B.Tech merely because
    the field is related or the candidate has a higher qualification. If a notice says
    "or equivalent" but the exact equivalence is not explicit, the result is unknown so
    the dashboard can require manual verification instead of claiming eligibility.
    """
    candidate_text = _candidate_text(candidate)
    if not candidate_text:
        return {"status": "unknown", "reasons": ["formal education not available in active resume"], "candidate_degrees": [], "required_degrees": [], "candidate_fields": [], "required_fields": []}

    scope = _job_scope(job)
    candidate_degrees = _families(candidate_text)
    required_degrees = _families(scope)
    candidate_fields = _fields(candidate_text)
    required_fields = _fields(scope)

    if not required_degrees:
        return {"status": "unknown", "reasons": ["formal qualification requirement was not explicit in the listing"], "candidate_degrees": sorted(candidate_degrees), "required_degrees": [], "candidate_fields": sorted(candidate_fields), "required_fields": sorted(required_fields)}

    degree_ok = _degree_match(required_degrees, candidate_degrees)
    if not degree_ok:
        req = ", ".join(DISPLAY_DEGREE.get(x, x) for x in sorted(required_degrees))
        have = ", ".join(DISPLAY_DEGREE.get(x, x) for x in sorted(candidate_degrees)) or "unrecognized degree"
        if EQUIVALENT.search(scope):
            return {"status": "unknown", "reasons": [f"qualification equivalence needs manual verification: listing asks for {req}; resume shows {have}"], "candidate_degrees": sorted(candidate_degrees), "required_degrees": sorted(required_degrees), "candidate_fields": sorted(candidate_fields), "required_fields": sorted(required_fields)}
        return {"status": "ineligible", "reasons": [f"formal qualification mismatch: listing requires {req}; resume shows {have}"], "candidate_degrees": sorted(candidate_degrees), "required_degrees": sorted(required_degrees), "candidate_fields": sorted(candidate_fields), "required_fields": sorted(required_fields)}

    if required_fields and candidate_fields and not ANY_DISCIPLINE.search(scope) and not (required_fields & candidate_fields):
        req = ", ".join(DISPLAY_FIELD.get(x, x) for x in sorted(required_fields))
        have = ", ".join(DISPLAY_FIELD.get(x, x) for x in sorted(candidate_fields))
        return {"status": "ineligible", "reasons": [f"discipline mismatch: listing requires {req}; resume shows {have}"], "candidate_degrees": sorted(candidate_degrees), "required_degrees": sorted(required_degrees), "candidate_fields": sorted(candidate_fields), "required_fields": sorted(required_fields)}

    reason = "formal education requirement matched"
    if strict:
        reason += " exactly enough for government eligibility screening"
    return {"status": "eligible", "reasons": [reason], "candidate_degrees": sorted(candidate_degrees), "required_degrees": sorted(required_degrees), "candidate_fields": sorted(candidate_fields), "required_fields": sorted(required_fields)}
