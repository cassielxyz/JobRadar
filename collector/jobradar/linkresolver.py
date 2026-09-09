from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urljoin, urlparse
import re
import httpx
from bs4 import BeautifulSoup

UA = {"User-Agent": "Mozilla/5.0 JobRadarEverywhere/0.9 (+personal job research)"}

APPLY_TEXT = re.compile(r"\b(apply(?:\s+now|\s+online)?|online\s+application|register(?:\s+now)?|application\s+portal|candidate\s+login|click\s+here\s+to\s+apply)\b", re.I)
NOTICE_TEXT = re.compile(r"\b(notification|advertisement|detailed\s+advertisement|official\s+notice|recruitment\s+notice)\b", re.I)
APPLY_URL = re.compile(r"(apply|application|register|registration|recruit|career|job|candidate|login)", re.I)
NOTICE_URL = re.compile(r"(notification|advert|notice|vacanc|recruit).*(\.pdf(?:$|\?))|\.pdf(?:$|\?)", re.I)
ATS_DOMAINS = (
    "greenhouse.io", "boards.greenhouse.io", "job-boards.greenhouse.io",
    "lever.co", "jobs.lever.co", "ashbyhq.com", "jobs.ashbyhq.com",
    "workdayjobs.com", "myworkdayjobs.com", "smartrecruiters.com",
    "icims.com", "oraclecloud.com", "successfactors.com",
)
SOCIAL_DOMAINS = ("linkedin.com", "reddit.com", "x.com", "twitter.com", "instagram.com", "facebook.com")


def _host(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def _matches_domain(url: str, domains: list[str] | tuple[str, ...]) -> bool:
    h = _host(url)
    return any(h == d.lower() or h.endswith("." + d.lower()) for d in domains)


def _is_pdf(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def _clean(url: str) -> str:
    # Keep query strings because many recruitment portals encode post IDs there.
    return url.strip().replace("&amp;", "&")


def _same_or_trusted(url: str, official_domains: list[str], source_url: str) -> bool:
    if _matches_domain(url, ATS_DOMAINS):
        return True
    if official_domains and _matches_domain(url, official_domains):
        return True
    sh, uh = _host(source_url), _host(url)
    return bool(sh and uh and (sh == uh or uh.endswith("." + sh) or sh.endswith("." + uh)))


def _candidate_score(text: str, href: str, official_domains: list[str], source_url: str) -> int:
    score = 0
    if APPLY_TEXT.search(text): score += 70
    if APPLY_URL.search(href): score += 20
    if _matches_domain(href, ATS_DOMAINS): score += 35
    if official_domains and _matches_domain(href, official_domains): score += 25
    if _same_or_trusted(href, official_domains, source_url): score += 10
    if _is_pdf(href): score -= 90
    if href.lower().startswith(("mailto:", "javascript:", "tel:")): score -= 100
    if _matches_domain(href, SOCIAL_DOMAINS): score -= 60
    return score


def _notice_score(text: str, href: str, official_domains: list[str], source_url: str) -> int:
    score = 0
    if NOTICE_TEXT.search(text): score += 45
    if _is_pdf(href): score += 45
    if NOTICE_URL.search(href): score += 20
    if official_domains and _matches_domain(href, official_domains): score += 25
    if _same_or_trusted(href, official_domains, source_url): score += 10
    return score


def _fetch(url: str):
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
    return r.status_code < 400, str(r.url)


def resolve_job_links(canonical_url: str, source_url: str, official_domains: list[str] | None = None, trusted_listing: bool = False) -> dict:
    """Resolve a discovery URL into a verified apply destination and optional notification.

    Conservative by design: secondary/social domains are never accepted as the final apply URL.
    Known ATS URLs and explicitly trusted original-posting feeds can be verified destinations.
    A generic government careers/notice page is never promoted to a verified direct-apply URL
    merely because it is alive.
    """
    official_domains = official_domains or []
    canonical_url = _clean(canonical_url)
    source_url = _clean(source_url or canonical_url)
    notification_url = canonical_url if _is_pdf(canonical_url) and _same_or_trusted(canonical_url, official_domains, source_url) else None
    apply_url = None
    apply_verified = False
    confidence = 0

    # A known ATS URL is already a strong direct application destination.
    if _matches_domain(canonical_url, ATS_DOMAINS):
        ok, final = _active(canonical_url)
        if ok:
            return {"apply_url": final, "notification_url": notification_url, "apply_verified": True, "link_confidence": 100}

    # Inspect the concrete vacancy/listing page first, then its source page as fallback.
    pages = []
    if not _is_pdf(canonical_url): pages.append(canonical_url)
    if source_url != canonical_url and not _is_pdf(source_url): pages.append(source_url)

    best_apply = (0, None)
    best_notice = (0, notification_url)
    for page in pages[:2]:
        r = _fetch(page)
        if not r or r.status_code >= 400 or "html" not in r.headers.get("content-type", "").lower():
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            text = " ".join(a.stripped_strings)[:300]
            href = urljoin(str(r.url), a.get("href"))
            if not href.startswith(("http://", "https://")):
                continue
            a_score = _candidate_score(text, href, official_domains, source_url)
            if a_score > best_apply[0] and _same_or_trusted(href, official_domains, source_url):
                best_apply = (a_score, href)
            n_score = _notice_score(text, href, official_domains, source_url)
            if n_score > best_notice[0] and _same_or_trusted(href, official_domains, source_url):
                best_notice = (n_score, href)

    if best_apply[1] and best_apply[0] >= 65:
        ok, final = _active(best_apply[1])
        if ok and not _matches_domain(final, SOCIAL_DOMAINS):
            apply_url, confidence = final, min(100, best_apply[0])
            apply_verified = True

    if best_notice[1]:
        ok, final = _active(best_notice[1])
        if ok: notification_url = final

    # Fallback pages may still be useful to the user, but they are NOT considered a
    # verified direct-apply destination unless we observed an explicit apply link above.
    # This is especially important for government career/notice pages, where an active
    # page can describe recruitment without accepting applications.
    if not apply_url and not _is_pdf(canonical_url) and not _matches_domain(canonical_url, SOCIAL_DOMAINS):
        trusted = _same_or_trusted(canonical_url, official_domains, source_url)
        if trusted:
            ok, final = _active(canonical_url)
            if ok:
                apply_url = final
                confidence = 80 if trusted_listing else 45
                apply_verified = bool(trusted_listing)

    return {
        "apply_url": apply_url,
        "notification_url": notification_url,
        "apply_verified": apply_verified,
        "link_confidence": confidence,
    }
