from __future__ import annotations

import re
from .models import Category, Job
from .extract import has_explicit_fresher_evidence
from .trust import assess_job_trust
from .category_research import category_search_terms, related_title_match

LOCATION_ALIASES = {
    "bangalore":"bengaluru", "bengaluru":"bengaluru", "tn":"tamil nadu",
    "pondicherry":"puducherry", "trivandrum":"thiruvananthapuram",
}

CORE_TECH = re.compile(
    r"\b(network(?:ing)?|network\s+(?:engineer|administrator|support|security|operations)|noc|soc|"
    r"routing|switching|router|switch|tcp/?ip|wan|lan|vlan|vpn|firewall|ids/?ips|siem|"
    r"cyber(?:security|\s+security)?|information\s+security|infosec|vapt|penetration\s+test|"
    r"vulnerability|incident\s+response|digital\s+forensic|iam|identity\s+and\s+access|"
    r"cloud\s+(?:network|networking|support|security|infrastructure)|aws\s+(?:vpc|network)|"
    r"azure\s+(?:network|vnet)|vpc|bgp|ospf|mpls|sd-?wan|cisco|ccna|juniper|fortinet|palo\s+alto)\b",
    re.I,
)
CSE_EVIDENCE = re.compile(r"\b(computer\s+science(?:\s+(?:and|&)\s+engineering)?|cse|information\s+technology|\bit\b|computer\s+engineering)\b", re.I)
UNRELATED_DISCIPLINE_TITLE = re.compile(r"\b(mechanical|civil|chemical|metallurgy|metallurgical|automobile|aerospace|architecture|agriculture|textile)\b", re.I)
SENIOR_TITLE = re.compile(r"\b(senior|sr\.?|lead|principal|staff|manager|architect|head|director)\b", re.I)
INTERNSHIP_TITLE = re.compile(r"\b(intern(?:ship)?|trainee)\b", re.I)
OPEN_ENDED_EXPERIENCE = re.compile(r"\b(?:(?:at\s+least|minimum(?:\s+of)?|min\.?|more\s+than)\s*)?(\d+(?:\.\d+)?)\s*(?:\+|or\s+more)?\s*(?:years?|yrs?)\b", re.I)
HANDS_ON_EXPERIENCE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:\+)?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:hands[- ]on|professional|relevant|work|industry|soc|security|network|cloud)?\s*experience\b", re.I)
EXPLICIT_MINIMUM = re.compile(r"\b(?:at\s+least|minimum(?:\s+of)?|min\.?)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b", re.I)
PLUS_YEARS = re.compile(r"\b(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)\b", re.I)
BROAD_INDIA_LOCATION = re.compile(r"\b(india|pan[- ]?india|nationwide|multiple locations?|various locations?)\b", re.I)


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()


def contains_any(text, words):
    t = norm(text)
    return [w for w in words if norm(w) and norm(w) in t]


def _loc(v: str) -> str:
    n = norm(v)
    for a, b in LOCATION_ALIASES.items():
        n = re.sub(rf"\b{re.escape(a)}\b", b, n)
    return n


def location_matches(job_location: str, locations: list[str]) -> list[str]:
    jl = _loc(job_location)
    if not jl:
        return []
    hits = []
    for x in locations:
        target = _loc(x)
        if target and (target in jl or jl in target):
            hits.append(x)
    return hits


def location_plausible(job_location: str, locations: list[str]) -> bool:
    """Discovery-stage location gate that avoids false negatives.

    Exact city/state matches are preferred, but country-wide or multi-location listings are
    kept for later scoring because many job boards only expose "India" before the detail page
    is opened. Remote remains opt-in unless no locations were configured.
    """
    if not locations or not job_location:
        return True
    if location_matches(job_location, locations):
        return True
    jl = _loc(job_location)
    if BROAD_INDIA_LOCATION.search(jl):
        return True
    if 'remote' in jl:
        return any('remote' in _loc(str(x)) for x in locations)
    return False


def source_allowed(category: Category, source_kind: str) -> bool:
    return not category.source_kinds or source_kind in category.source_kinds


def semantic_gate(job: Job, category: Category):
    """Hard category relevance gate before ranking.

    New/custom categories are adaptive: their name, slug, configured role terms and safe
    role-family expansions all participate in matching. This prevents a newly-created category
    from returning zero results merely because a job board uses an adjacent title.
    """
    title = norm(job.title)
    body = norm(job.description)
    text = f"{title} {body}"
    role_terms = category_search_terms(category, limit=40)
    category_text = norm(' '.join(role_terms))
    category_is_network_family = bool(CORE_TECH.search(category_text))

    if UNRELATED_DISCIPLINE_TITLE.search(title) and not CORE_TECH.search(title):
        return False, ["unrelated engineering discipline"]

    role_hits_title = contains_any(title, role_terms)
    role_hits_body = contains_any(text, role_terms)
    related_title_hits = related_title_match(title, category)
    hidden_hits = contains_any(title, category.hidden_keywords) or contains_any(text, category.hidden_keywords)
    core = bool(CORE_TECH.search(text))
    cse = bool(CSE_EVIDENCE.search(text))

    if category.type == 'government':
        relevant = bool(role_hits_title or role_hits_body or related_title_hits or (category_is_network_family and core) or (hidden_hits and cse))
        if not relevant:
            return False, ["no category-specific role/CSE/IT evidence"]
    else:
        relevant = bool(role_hits_title or role_hits_body or related_title_hits or hidden_hits)
        if not relevant and category_is_network_family and core:
            relevant = True
        if not relevant:
            return False, ["job does not match this category's role family"]
        if category.type == 'internship' and not INTERNSHIP_TITLE.search(text):
            return False, ["listing is not clearly an internship/trainee role"]

    if getattr(category, 'fresher_only', False) and SENIOR_TITLE.search(title):
        return False, ["fresher-only category: senior-level title"]
    return True, []


def fresher_gate(job: Job, category: Category):
    """Apply strict experience rejection only when the category explicitly opts in."""
    if not getattr(category, 'fresher_only', False):
        return True, []
    title = norm(job.title)
    text = norm(f"{job.title} {job.description}")
    if SENIOR_TITLE.search(title):
        return False, ["fresher-only category: senior-level title"]

    range_matches = list(re.finditer(r"\b(\d+(?:\.\d+)?)\s*(?:-|to|–|—)\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b", text, re.I))
    for m in range_matches:
        lo, hi = float(m.group(1)), float(m.group(2))
        if lo <= 1 and hi <= float(category.max_experience_years):
            return True, [f"fresher experience range {lo:g}-{hi:g} years"]

    hard = []
    for rx, label in ((PLUS_YEARS, 'open-ended'), (EXPLICIT_MINIMUM, 'minimum'), (HANDS_ON_EXPERIENCE, 'hands-on')):
        for m in rx.finditer(text):
            years = float(m.group(1))
            if years >= 2 or years > float(category.max_experience_years):
                hard.append(f"{label} {years:g}+ years requirement")
    if hard:
        return False, ["fresher-only category: " + hard[0]]

    if job.experience_min is not None and float(job.experience_min) > float(category.max_experience_years):
        return False, ["fresher-only category: experience minimum exceeds target"]
    if job.experience_max is not None and float(job.experience_max) > float(category.max_experience_years):
        return False, ["fresher-only category: experience maximum exceeds target"]
    return True, []


def score_job(job: Job, category: Category):
    gate, gate_reasons = semantic_gate(job, category)
    if not gate:
        return 0, gate_reasons, False
    fresh_ok, fresh_reasons = fresher_gate(job, category)
    if not fresh_ok:
        return 0, fresh_reasons, False

    trust = assess_job_trust(job, category)
    if trust.get('blocked'):
        return 0, ["trust/scam gate: " + str((trust.get('reasons') or ['blocked'])[-1])], False

    text = " ".join([job.title, job.description, job.company])
    role_terms = category_search_terms(category, limit=40)
    title_hits = contains_any(job.title, role_terms)
    body_hits = contains_any(text, role_terms)
    related_hits = related_title_match(job.title, category)
    hidden_hits = contains_any(text, category.hidden_keywords)
    excludes = contains_any(text, category.exclude_keywords)
    location_hits = location_matches(job.location, category.locations)

    score = 0
    reasons = []
    trust_score = int(trust.get('score') or 0)
    if trust_score >= 90:
        score += 8; reasons.append("high-trust source")
    elif trust_score >= 70:
        score += 4; reasons.append("recognized source")
    if title_hits:
        score += 32
        reasons.append("target role title")
    elif related_hits:
        score += 27
        reasons.append("related role-title wording")
    elif body_hits:
        score += 22
        reasons.append("target role duties")
    elif CORE_TECH.search(text):
        score += 20
        reasons.append("network/cyber/cloud technical evidence")

    if hidden_hits:
        score += min(12, 4 * len(hidden_hits))
        reasons.append("adjacent/hidden title")

    if location_hits:
        score += 15
        reasons.append("preferred location")
    elif job.location and BROAD_INDIA_LOCATION.search(job.location):
        score += 5
        reasons.append("India/multi-location listing; exact city not disclosed")
    elif job.location:
        reasons.append("outside or unclear preferred location")
    else:
        reasons.append("location not disclosed")

    if job.experience_max is not None:
        if job.experience_max <= category.max_experience_years:
            score += 15
            reasons.append("experience within category target")
        elif getattr(category, 'fresher_only', False):
            return max(0, min(100, score - 30)), reasons + ["fresher-only category: experience exceeds target"], False
        else:
            score -= 8
            reasons.append("experience above preferred target")
    elif job.experience_min is not None:
        if job.experience_min <= category.max_experience_years:
            score += 8
            reasons.append("experience minimum within category target")
        elif getattr(category, 'fresher_only', False):
            return max(0, min(100, score - 30)), reasons + ["fresher-only category: experience minimum exceeds target"], False
        else:
            score -= 8
            reasons.append("experience minimum above preferred target")
    elif has_explicit_fresher_evidence(text):
        score += 15
        reasons.append("explicit fresher/entry-level wording")
    else:
        reasons.append("experience not stated")

    if category.type == "internship":
        if job.stipend_monthly is not None:
            if category.stipend_min_monthly is None or job.stipend_monthly >= category.stipend_min_monthly:
                score += 12
                reasons.append("stipend meets target")
            elif category.require_paid:
                return max(0, min(100, score - 20)), reasons + ["stipend below target"], False
        elif category.require_paid:
            reasons.append("stipend not disclosed")
    else:
        if job.salary_min_monthly is not None and category.salary_min_monthly and job.salary_min_monthly >= category.salary_min_monthly:
            score += 10
            reasons.append("salary meets target")
        elif job.salary_min_monthly is None:
            reasons.append("salary not disclosed")

    if job.official_verified:
        score += 10
        reasons.append("official source verified")

    if job.application_status == 'closed':
        return max(0, min(100, score - 40)), reasons + ["application closed"], False

    if excludes:
        score -= 35
        reasons.append("excluded/senior requirement detected")
        return max(0, min(100, score)), reasons, False

    if category.require_official_verification and not job.official_verified:
        return max(0, min(100, score)), reasons + ["official verification required"], False

    eligible = score >= 40
    return max(0, min(100, score)), reasons, eligible
