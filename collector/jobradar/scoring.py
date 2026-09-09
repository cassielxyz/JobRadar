import re
from .models import Category, Job

LOCATION_ALIASES = {"bangalore":"bengaluru", "bengaluru":"bengaluru", "tn":"tamil nadu"}

def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").lower()).strip()

def contains_any(text, words):
    t = norm(text)
    return [w for w in words if norm(w) and norm(w) in t]

def score_job(job: Job, category: Category):
    text = " ".join([job.title, job.description, job.company])
    title_hits = contains_any(job.title, category.role_keywords)
    body_hits = contains_any(text, category.role_keywords)
    hidden_hits = contains_any(text, category.hidden_keywords)
    excludes = contains_any(text, category.exclude_keywords)
    location_text = LOCATION_ALIASES.get(norm(job.location), norm(job.location))
    location_hits = [x for x in category.locations if LOCATION_ALIASES.get(norm(x), norm(x)) in location_text or location_text in LOCATION_ALIASES.get(norm(x), norm(x))]

    score = 0; reasons = []
    if title_hits: score += 30; reasons.append("role title match")
    elif body_hits: score += 22; reasons.append("role keyword match")
    if hidden_hits: score += min(18, 6 * len(hidden_hits)); reasons.append("hidden/adjacent title match")
    if location_hits: score += 15; reasons.append("preferred South India location")
    if job.experience_max is None or job.experience_max <= category.max_experience_years:
        score += 15; reasons.append("fresher/entry-level compatible")
    if category.type == "internship":
        if job.stipend_monthly is not None:
            if category.stipend_min_monthly is None or job.stipend_monthly >= category.stipend_min_monthly:
                score += 12; reasons.append("stipend meets target")
        elif category.require_paid:
            reasons.append("stipend not disclosed")
    else:
        if job.salary_min_monthly is not None and category.salary_min_monthly and job.salary_min_monthly >= category.salary_min_monthly:
            score += 10; reasons.append("salary meets target")
        elif job.salary_min_monthly is None:
            reasons.append("salary not disclosed")
    if job.official_verified:
        score += 10; reasons.append("official source verified")
    if excludes:
        score -= 35; reasons.append("excluded/senior requirement detected")
    if category.require_official_verification and not job.official_verified:
        return max(0, min(100, score)), reasons + ["official verification required"], False
    eligible = score >= 45 and not (category.require_paid and job.stipend_monthly == 0)
    return max(0, min(100, score)), reasons, eligible
