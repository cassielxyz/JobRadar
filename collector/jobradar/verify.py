from urllib.parse import urlparse
import httpx

from .linkresolver import is_non_job_url

UA = {"User-Agent":"JobRadarEverywhere/1.1 (+personal job research; respectful fetch)"}


def domain_matches(url, allowed):
    host = (urlparse(url).hostname or "").lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in allowed)


def verify_url(url, official_domains=None):
    if is_non_job_url(url):
        return {
            "active": False,
            "canonical_url": url,
            "official": False,
            "reason": "non_job_url",
        }
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=UA) as c:
            r = c.get(url)
        final = str(r.url)
        active = r.status_code < 400 and not is_non_job_url(final)
        official = active and bool(official_domains) and domain_matches(final, official_domains)
        result = {"active": active, "canonical_url": final, "official": official, "status": r.status_code}
        if r.status_code < 400 and not active:
            result["reason"] = "redirected_to_non_job_url"
        return result
    except Exception as e:
        return {"active": False, "canonical_url": url, "official": False, "error": str(e)}
