from urllib.parse import urlparse
import httpx

UA = {"User-Agent":"JobRadarEverywhere/0.9 (+personal job research; respectful fetch)"}

def domain_matches(url, allowed):
    host = (urlparse(url).hostname or "").lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in allowed)

def verify_url(url, official_domains=None):
    try:
        with httpx.Client(timeout=20, follow_redirects=True, headers=UA) as c:
            r = c.get(url)
        active = r.status_code < 400
        final = str(r.url)
        official = active and bool(official_domains) and domain_matches(final, official_domains)
        return {"active": active, "canonical_url": final, "official": official, "status": r.status_code}
    except Exception as e:
        return {"active": False, "canonical_url": url, "official": False, "error": str(e)}
