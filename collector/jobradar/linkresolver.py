from __future__ import annotations

from urllib.parse import urljoin, urlparse
import re
import httpx
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 JobRadarEverywhere/1.2 (+personal job research)"}

APPLY_TEXT = re.compile(r"\b(apply(?:\s+now|\s+online)?|online\s+application|register(?:\s+now)?|application\s+portal|candidate\s+login|click\s+here\s+to\s+apply|submit\s+application)\b", re.I)
NOTICE_TEXT = re.compile(r"\b(notification|advertisement|detailed\s+advertisement|official\s+notice|recruitment\s+notice)\b", re.I)
APPLY_URL = re.compile(r"(apply|application|register|registration|recruit|career|job|candidate|position|vacanc)", re.I)
NOTICE_URL = re.compile(r"(notification|advert|notice|vacanc|recruit).*(\.pdf(?:$|\?))|\.pdf(?:$|\?)", re.I)

# Direct employer/application systems. If a live URL is on one of these domains, JobRadar can
# treat it as a verified application destination instead of only showing the discovery board.
ATS_DOMAINS = (
    "greenhouse.io", "boards.greenhouse.io", "job-boards.greenhouse.io",
    "lever.co", "jobs.lever.co", "ashbyhq.com", "jobs.ashbyhq.com",
    "workdayjobs.com", "myworkdayjobs.com", "myworkdaysite.com",
    "smartrecruiters.com", "jobs.smartrecruiters.com",
    "workable.com", "apply.workable.com", "jobs.workable.com",
    "recruitee.com", "personio.de", "jobs.personio.de", "personio.com",
    "teamtailor.com", "bamboohr.com", "jobvite.com", "jobs.jobvite.com",
    "breezy.hr", "icims.com", "taleo.net", "oraclecloud.com", "successfactors.com",
    "rippling.com", "ats.rippling.com", "comeet.com", "applytojob.com",
    "pinpointhq.com", "careers-page.com", "jobscore.com", "jobs.jobscore.com",
    "dayforcehcm.com", "jobs.dayforcehcm.com", "eightfold.ai", "phenompeople.com",
    "adp.com", "recruiting.adp.com", "workforcenow.adp.com", "hireology.com",
)
SOCIAL_DOMAINS = ("linkedin.com", "reddit.com", "x.com", "twitter.com", "instagram.com", "facebook.com")
JOB_BOARD_DOMAINS = (
    "linkedin.com", "naukri.com", "indeed.com", "internshala.com", "shine.com",
    "foundit.in", "timesjobs.com", "freshersworld.com", "cutshort.io", "instahyre.com",
    "hirist.tech", "iimjobs.com", "apna.co", "workindia.in", "jobhai.com", "unstop.com",
    "wellfound.com", "hirect.in", "herkey.com", "quikr.com", "glassdoor.co.in",
    "jooble.org", "adzuna.in", "careerjet.co.in", "jora.com", "talent.com", "grabjobs.co",
    "jobs.weekday.works", "cuvette.tech", "joinsuperset.com", "geektrust.com", "talent500.co",
    "placementindia.com", "freshersnow.com", "timesascent.com",
)

# Search engines regularly return footer/legal/auth/account pages from job boards. Those are
# never valid per-job destinations and must be dropped before scoring, saving or notifying.
NON_JOB_PATH = re.compile(
    r"(?:^|/)(?:legal(?:/|$)|help(?:/|$)|privacy(?:/|$)|accessibility(?:/|$)|"
    r"cookie(?:s|/|$)|terms(?:/|$)|user-agreement(?:/|$)|authwall(?:/|$)|"
    r"checkpoint(?:/|$)|signup(?:/|$)|sign-up(?:/|$)|signin(?:/|$)|sign-in(?:/|$)|"
    r"login(?:/|$)|registration(?:/|$)|register(?:/|$)|account(?:/|$)|profile(?:/|$)|"
    r"feed(?:/|$)|about(?:/|$)|contact(?:/|$)|support(?:/|$))",
    re.I,
)
JOBISH_PATH = re.compile(r"(?:job|jobs|job-listing|job-listings|viewjob|position|opening|vacanc|career|internship|intern|apply|opportunit)", re.I)


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def _matches_domain(url: str, domains: list[str] | tuple[str, ...]) -> bool:
    h = _host(url)
    return any(h == d.lower() or h.endswith("." + d.lower()) for d in domains)


def is_non_job_url(url: str) -> bool:
    """Return True for navigation/auth/legal/search pages that are not concrete job listings."""
    try:
        p = urlparse(url or "")
    except Exception:
        return True
    host = (p.hostname or "").lower().removeprefix("www.")
    path = p.path or "/"
    query = (p.query or "").lower()
    if not host:
        return True
    if NON_JOB_PATH.search(path):
        return True
    if any(token in query for token in (
        "user-agreement", "privacy-policy", "terms-of-service", "auth-button_user-agreement",
        "login", "signup", "registration",
    )):
        return True

    # LinkedIn is especially noisy in search indexes. Only the canonical job detail form is
    # allowed. /posts/, /company/, /jobs/search/, authwall, legal pages etc. are rejected.
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        return not bool(re.match(r"^/jobs/view/[^/?#]+/?$", path, re.I))

    # ATS hosts are application systems; their paths vary widely by vendor and tenant. Generic
    # account/legal paths above are still rejected, but we do not force a single URL pattern.
    if _matches_domain(url, ATS_DOMAINS):
        return False

    if any(host == d or host.endswith("." + d) for d in JOB_BOARD_DOMAINS):
        combined = f"{path}?{query}"
        if not JOBISH_PATH.search(combined):
            return True
        if re.search(r"/(?:jobs?|internships?)/(?:search|browse)(?:/|$)", path, re.I):
            return True

    return False


def _is_pdf(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def _clean(url: str) -> str:
    return (url or "").strip().replace("&amp;", "&")


def _same_or_trusted(url: str, official_domains: list[str], source_url: str) -> bool:
    if _matches_domain(url, ATS_DOMAINS):
        return True
    if official_domains and _matches_domain(url, official_domains):
        return True
    sh, uh = _host(source_url), _host(url)
    return bool(sh and uh and (sh == uh or uh.endswith("." + sh) or sh.endswith("." + uh)))


def _candidate_score(text: str, href: str, official_domains: list[str], source_url: str) -> int:
    if is_non_job_url(href):
        return -200
    score = 0
    if APPLY_TEXT.search(text): score += 70
    if APPLY_URL.search(href): score += 20
    if _matches_domain(href, ATS_DOMAINS): score += 40
    if official_domains and _matches_domain(href, official_domains): score += 25
    if _same_or_trusted(href, official_domains, source_url): score += 10
    if _is_pdf(href): score -= 90
    if href.lower().startswith(("mailto:", "javascript:", "tel:")): score -= 100
    if _matches_domain(href, SOCIAL_DOMAINS): score -= 60
    return score


def _notice_score(text: str, href: str, official_domains: list[str], source_url: str) -> int:
    if is_non_job_url(href):
        return -200
    score = 0
    if NOTICE_TEXT.search(text): score += 45
    if _is_pdf(href): score += 45
    if NOTICE_URL.search(href): score += 20
    if official_domains and _matches_domain(href, official_domains): score += 25
    if _same_or_trusted(href, official_domains, source_url): score += 10
    return score


def _fetch(url: str):
    if is_non_job_url(url):
        return None
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=UA) as c:
            r = c.get(url)
        return r
    except Exception:
        return None


def _active(url: str) -> tuple[bool, str]:
    r = _fetch(url)
    if not r:
        return False, url
    final = str(r.url)
    if is_non_job_url(final):
        return False, final
    return r.status_code < 400, final


def resolve_job_links(canonical_url: str, source_url: str, official_domains: list[str] | None = None, trusted_listing: bool = False) -> dict:
    """Resolve discovery URLs into verified application/notice destinations conservatively."""
    official_domains = official_domains or []
    canonical_url = _clean(canonical_url)
    source_url = _clean(source_url or canonical_url)
    notification_url = canonical_url if _is_pdf(canonical_url) and _same_or_trusted(canonical_url, official_domains, source_url) else None
    apply_url = None
    apply_verified = False
    confidence = 0

    if is_non_job_url(canonical_url):
        return {"apply_url": None, "notification_url": None, "apply_verified": False, "link_confidence": 0}

    if _matches_domain(canonical_url, ATS_DOMAINS):
        ok, final = _active(canonical_url)
        if ok:
            return {"apply_url": final, "notification_url": notification_url, "apply_verified": True, "link_confidence": 100}

    pages = []
    if not _is_pdf(canonical_url):
        pages.append(canonical_url)
    if source_url != canonical_url and not _is_pdf(source_url) and not is_non_job_url(source_url):
        pages.append(source_url)

    best_apply = (0, None)
    best_notice = (0, notification_url)
    for page in pages[:2]:
        r = _fetch(page)
        if not r or r.status_code >= 400 or "html" not in r.headers.get("content-type", "").lower():
            continue
        if is_non_job_url(str(r.url)):
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            text = " ".join(a.stripped_strings)[:300]
            href = urljoin(str(r.url), a.get("href"))
            if not href.startswith(("http://", "https://")) or is_non_job_url(href):
                continue
            a_score = _candidate_score(text, href, official_domains, source_url)
            if a_score > best_apply[0] and _same_or_trusted(href, official_domains, source_url):
                best_apply = (a_score, href)
            n_score = _notice_score(text, href, official_domains, source_url)
            if n_score > best_notice[0] and _same_or_trusted(href, official_domains, source_url):
                best_notice = (n_score, href)

    if best_apply[1] and best_apply[0] >= 65:
        ok, final = _active(best_apply[1])
        if ok and not _matches_domain(final, SOCIAL_DOMAINS) and not is_non_job_url(final):
            apply_url, confidence = final, min(100, best_apply[0])
            apply_verified = True

    if best_notice[1]:
        ok, final = _active(best_notice[1])
        if ok:
            notification_url = final

    if not apply_url and not _is_pdf(canonical_url) and not _matches_domain(canonical_url, SOCIAL_DOMAINS):
        trusted = _same_or_trusted(canonical_url, official_domains, source_url)
        if trusted:
            ok, final = _active(canonical_url)
            if ok and not is_non_job_url(final):
                apply_url = final
                confidence = 80 if trusted_listing else 45
                apply_verified = bool(trusted_listing)

    return {
        "apply_url": apply_url,
        "notification_url": notification_url,
        "apply_verified": apply_verified,
        "link_confidence": confidence,
    }
