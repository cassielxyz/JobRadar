from __future__ import annotations

import re
from .models import Category

# Generic role words are useful as a second signal, but are too broad to define a
# category on their own. Domain words + one of these generic words form a safe
# fuzzy title match when an exact synonym is not present.
GENERIC_ROLE_WORDS = {
    'engineer', 'engineering', 'analyst', 'specialist', 'administrator', 'admin',
    'developer', 'consultant', 'associate', 'executive', 'technician', 'support',
    'architect', 'manager', 'intern', 'internship', 'trainee', 'officer', 'lead',
    'operations', 'operation', 'monitoring', 'helpdesk', 'desk',
}
STOPWORDS = {
    'job', 'jobs', 'role', 'roles', 'opening', 'openings', 'career', 'careers',
    'fresher', 'freshers', 'entry', 'level', 'junior', 'senior', 'remote', 'india',
    'and', 'or', 'the', 'for', 'with', 'in', 'of', 'to', 'a', 'an',
}

ROLE_FAMILIES: tuple[tuple[re.Pattern[str], tuple[str, ...]], ...] = (
    (re.compile(r'\b(network|networking|ccna|noc|routing|switching|cisco|infrastructure)\b', re.I), (
        'network engineer', 'junior network engineer', 'network support engineer',
        'network support associate', 'network administrator', 'network admin',
        'network operations engineer', 'network operations center engineer', 'noc engineer',
        'noc analyst', 'noc support engineer', 'noc monitoring engineer', 'network analyst',
        'network technician', 'network operations associate', 'infrastructure engineer',
        'infrastructure support engineer', 'it infrastructure engineer', 'it operations engineer',
        'it operations associate', 'technical support engineer', 'technical support associate',
        'system engineer', 'systems engineer', 'system administrator', 'systems administrator',
        'desktop support engineer', 'service desk analyst', 'it support engineer',
        'graduate engineer trainee network', 'network trainee', 'network intern',
    )),
    (re.compile(r'\b(cybersecurity|cyber security|infosec|information security|soc analyst|siem|vapt|penetration test|security operations)\b', re.I), (
        'cybersecurity analyst', 'cyber security analyst', 'junior cybersecurity analyst',
        'security analyst', 'junior security analyst', 'soc analyst', 'soc analyst l1',
        'soc engineer', 'security operations analyst', 'security operations center analyst',
        'information security analyst', 'information security associate', 'security engineer',
        'network security analyst', 'network security engineer', 'vulnerability analyst',
        'vulnerability management analyst', 'incident response analyst', 'siem analyst',
        'security monitoring analyst', 'cybersecurity associate', 'cybersecurity trainee',
        'cybersecurity intern', 'information security intern', 'vapt analyst',
    )),
    (re.compile(r'\b(cloud|aws|azure|gcp)\b', re.I), (
        'cloud engineer', 'junior cloud engineer', 'cloud support engineer', 'cloud support associate',
        'cloud operations engineer', 'cloud operations associate', 'cloud infrastructure engineer',
        'cloud administrator', 'cloud support analyst', 'platform engineer', 'cloud trainee',
        'cloud intern',
    )),
    (re.compile(r'\b(devops|site reliability|sre|platform engineer)\b', re.I), (
        'devops engineer', 'junior devops engineer', 'devops associate', 'devops trainee',
        'site reliability engineer', 'sre engineer', 'platform engineer',
        'cloud devops engineer', 'build and release engineer',
    )),
    (re.compile(r'\b(data analyst|data analytics|business intelligence|\bbi analyst\b)\b', re.I), (
        'data analyst', 'data analytics analyst', 'business intelligence analyst',
        'bi analyst', 'reporting analyst', 'analytics analyst',
    )),
    (re.compile(r'\b(data engineer|etl|data pipeline)\b', re.I), (
        'data engineer', 'etl developer', 'etl engineer', 'data pipeline engineer',
        'analytics engineer',
    )),
    (re.compile(r'\b(software|developer|frontend|front end|backend|back end|full stack|fullstack)\b', re.I), (
        'software engineer', 'software developer', 'application developer', 'backend developer',
        'frontend developer', 'full stack developer', 'fullstack developer',
    )),
    (re.compile(r'\b(quality assurance|\bqa\b|software test|tester|test engineer)\b', re.I), (
        'qa engineer', 'quality assurance engineer', 'software tester', 'test engineer',
        'automation test engineer', 'qa analyst',
    )),
    (re.compile(r'\b(help ?desk|service desk|desktop support|it support|technical support|system admin|it operations)\b', re.I), (
        'it support engineer', 'it support associate', 'technical support engineer',
        'technical support associate', 'desktop support engineer', 'desktop support technician',
        'service desk analyst', 'service desk associate', 'help desk analyst', 'helpdesk engineer',
        'system administrator', 'systems administrator', 'system engineer', 'it operations engineer',
        'it operations analyst', 'infrastructure support engineer',
    )),
    (re.compile(r'\b(ui|ux|user experience|product design|web design)\b', re.I), (
        'ui designer', 'ux designer', 'ui ux designer', 'product designer', 'web designer',
    )),
    (re.compile(r'\b(digital marketing|seo|social media|performance marketing|content marketing)\b', re.I), (
        'digital marketing executive', 'digital marketing specialist', 'seo analyst',
        'seo executive', 'social media executive', 'performance marketing analyst',
    )),
)

ALIASES = {
    'administrator': {'administrator', 'admin'},
    'admin': {'administrator', 'admin'},
    'engineering': {'engineering', 'engineer'},
    'engineer': {'engineer', 'engineering'},
    'analytics': {'analytics', 'analyst'},
    'analyst': {'analyst', 'analytics'},
    'developer': {'developer', 'development'},
    'development': {'developer', 'development'},
    'cybersecurity': {'cybersecurity', 'cyber', 'security'},
    'frontend': {'frontend', 'front-end', 'front end'},
    'backend': {'backend', 'back-end', 'back end'},
    'fullstack': {'fullstack', 'full-stack', 'full stack'},
    'operations': {'operations', 'operation', 'ops'},
    'support': {'support', 'helpdesk', 'help desk', 'service desk'},
}


def _norm(value: str) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip().lower())


def _dedupe(values):
    out, seen = [], set()
    for value in values:
        value = ' '.join(str(value or '').split()).strip(' -–—,;/')
        key = value.casefold()
        if len(value) < 3 or key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def category_search_terms(category: Category, limit: int = 24) -> list[str]:
    """Build robust search terms for any newly-created category.

    The category name and slug are always usable fallbacks, so a new category is not
    dependent on a hand-maintained global source list. Known role families add common
    adjacent titles, while user-entered role/hidden keywords remain highest priority.
    """
    base = _dedupe([
        *(category.role_keywords or []),
        *(category.hidden_keywords or []),
        category.name,
        str(category.slug or '').replace('-', ' '),
    ])
    haystack = _norm(' '.join(base))
    expanded = list(base)
    for trigger, terms in ROLE_FAMILIES:
        if trigger.search(haystack):
            expanded.extend(terms)
    return _dedupe(expanded)[:max(1, limit)]


def _token_present(text: str, token: str) -> bool:
    text = _norm(text)
    variants = ALIASES.get(token, {token})
    for variant in variants:
        variant = _norm(variant)
        if ' ' in variant:
            if variant in text:
                return True
        elif re.search(rf'\b{re.escape(variant)}\w*\b', text, re.I):
            return True
    return False


def related_title_match(title: str, category: Category) -> list[str]:
    """Return derived category terms that plausibly match a title.

    This is intentionally title-only. It prevents a generic mention in a long job
    description from turning an unrelated vacancy into a category match.
    """
    title_norm = _norm(title)
    if not title_norm:
        return []
    hits = []
    for term in category_search_terms(category, limit=60):
        term_norm = _norm(term)
        if term_norm in title_norm:
            hits.append(term)
            continue
        tokens = re.findall(r'[a-z0-9+#.]+', term_norm)
        useful = [t for t in tokens if t not in STOPWORDS and len(t) >= 3]
        if not useful:
            continue
        domain = [t for t in useful if t not in GENERIC_ROLE_WORDS]
        generic = [t for t in useful if t in GENERIC_ROLE_WORDS]
        if not domain:
            continue
        domain_hits = sum(1 for t in domain if _token_present(title_norm, t))
        generic_hits = sum(1 for t in generic if _token_present(title_norm, t))
        if len(domain) == 1:
            ok = domain_hits == 1 and (not generic or generic_hits >= 1)
        else:
            needed = max(2, (len(domain) * 2 + 2) // 3)
            ok = domain_hits >= needed and (not generic or generic_hits >= 1)
        if ok:
            hits.append(term)
    return _dedupe(hits)
