from __future__ import annotations

import re
from .models import Category, Job
from .extract import has_explicit_fresher_evidence

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


def source_allowed(category: Category, source_kind: str) -> bool:
    return not category.source_kinds or source_kind in category.source_kinds


def semantic_gate(job: Job, category: Category):
    title = norm(job.title)
    body = norm(job.description)
    text = f"{title} {body}"

    if UNRELATED_DISCIPLINE_TITLE.search(title) and not CORE_TECH.search(title):
        return False, ["unrelated engineering discipline"]

    role_hits_title = contains_any(title, category.role_keywords)
    role_hits_body = contains_any(text, category.role_keywords)
    hidden_hits = contains_any(title, category.hidden_keywords) or contains_any(text, category.hidden_keywords)
    core = bool(CORE_TECH.search(text))
    cse = bool(CSE_EVIDENCE.search(text))

    if category.type == 'government':
        relevant = bool(role_hits_title or core or (hidden_hits and cse))
        if not relevant:
            return False, ["no networking/cyber/cloud or CSE/IT evidence"]
    elif category.type == 'internship':
        relevant = bool((role_hits_title or role_hits_body or hidden_hits) and core)
        if CORE_TECH.search(title) and INTERNSHIP_TITLE.search(title):
            relevant = True
        if not relevant:
            return False, ["internship is not clearly networking/cyber/cloud related"]
    else:
        relevant = bool(role_hits_title or core)
        if not relevant and hidden_hits and core:
            relevant = True
        if not relevant:
            return False, ["role is not clearly networking/cyber/cloud related"]

    if category.type in {'startup','entry_level'} and SENIOR_TITLE.search(title):
        return False, ["senior-level title"]

    return True, []


def score_job(job: Job, category: Category):
    gate, gate_reasons = semantic_gate(job, category)
    if not gate:
        return 0, gate_reasons, False

    text = " ".join([job.title, job.description, job.company])
    title_hits = contains_any(job.title, category.role_keywords)
    body_hits = contains_any(text, category.role_keywords)
    hidden_hits = contains_any(text, category.hidden_keywords)
    excludes = contains_any(text, category.exclude_keywords)
    location_hits = location_matches(job.location, category.locations)

    score = 0
    reasons = []
    if title_hits:
        score += 32
        reasons.append("target role title")
    elif body_hits:
        score += 22
        reasons.append("target role duties")
    elif CORE_TECH.search(text):
        score += 20
        reasons.append("network/cyber/cloud technical evidence")

    if hidden_hits:
        score += min(12, 4 * len(hidden_hits))
        reasons.append("adjacent government/technical title")

    if location_hits:
        score += 15
        reasons.append("preferred location")
    elif job.location:
        reasons.append("outside or unclear preferred location")
    else:
        reasons.append("location not disclosed")

    if job.experience_max is not None:
        if job.experience_max <= category.max_experience_years:
            score += 15
            reasons.append("experience within fresher/entry-level limit")
        else:
            return max(0, min(100, score - 30)), reasons + ["experience exceeds target"], False
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

    eligible = score >= 55
    return max(0, min(100, score)), reasons, eligible
