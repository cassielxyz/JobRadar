from __future__ import annotations

import html
import re
from urllib.parse import parse_qsl, urlencode, urlsplit

GENERIC_COMPANIES = {
    '', 'unknown', 'unknown company', 'web discovery', 'external job-platform discovery',
    'company not disclosed', 'not disclosed', 'confidential',
}

# These query parameters identify an individual job on boards whose detail page is query-based.
JOB_ID_QUERY_KEYS = {
    'id', 'jobid', 'job_id', 'jid', 'jk', 'gh_jid', 'positionid', 'position_id',
    'reqid', 'req_id', 'requisitionid', 'requisition_id', 'job', 'jobkey', 'job_key',
}

TRACKING_QUERY_PREFIXES = ('utm_', 'ref_', 'source_', 'trk_', 'tracking_')
TRACKING_QUERY_KEYS = {
    'ref', 'source', 'src', 'campaign', 'medium', 'from', 'origin', 'trackingid',
    'tracking_id', 'clickid', 'gclid', 'fbclid', 'mc_cid', 'mc_eid',
}

COMPANY_SUFFIX_RE = re.compile(
    r'\b(?:private\s+limited|pvt\.?\s*ltd\.?|pvt\.?|ltd\.?|limited|inc\.?|incorporated|'
    r'llc|llp|plc|corp\.?|corporation|company|co\.?)\b', re.I,
)
GENERIC_LOCATION_RE = re.compile(
    r'\b(?:india|remote|hybrid|work\s+from\s+home|wfh|on[- ]?site|multiple\s+locations?|'
    r'pan\s+india|anywhere\s+in\s+india|not\s+disclosed|location\s+not\s+disclosed)\b', re.I,
)

LOCATION_ALIASES = {
    'bengaluru': 'bangalore',
    'bangaluru': 'bangalore',
    'new delhi': 'delhi',
    'gurugram': 'gurgaon',
    'trivandrum': 'thiruvananthapuram',
    'cochin': 'kochi',
}

REQ_KEYS = {
    'job_id', 'jobid', 'jobId', 'requisition_id', 'requisitionId', 'req_id', 'reqId',
    'position_id', 'positionId', 'external_id', 'externalId', 'posting_id', 'postingId',
}


def _value(job, name, default=''):
    if isinstance(job, dict):
        return job.get(name, default)
    return getattr(job, name, default)


def _plain(value) -> str:
    text = html.unescape(str(value or '')).lower()
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'[^a-z0-9+#.]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def normalized_url_key(url: str) -> str:
    """Return a stable job URL key while preserving query-based job IDs.

    Tracking parameters are intentionally discarded, but identifiers such as Indeed's `jk`
    remain. This prevents both false duplicates (all Indeed /viewjob URLs collapsing together)
    and trivial duplicates caused by UTM/referral parameters or trailing slashes.
    """
    try:
        p = urlsplit(str(url or '').strip())
    except Exception:
        return ''
    host = (p.hostname or '').lower().removeprefix('www.')
    if not host:
        return ''
    path = re.sub(r'/+', '/', p.path or '/').rstrip('/') or '/'
    kept = []
    for key, value in parse_qsl(p.query, keep_blank_values=False):
        k = key.lower()
        if k in JOB_ID_QUERY_KEYS:
            kept.append((k, value.strip()))
            continue
        if k in TRACKING_QUERY_KEYS or any(k.startswith(prefix) for prefix in TRACKING_QUERY_PREFIXES):
            continue
    kept.sort()
    query = urlencode(kept)
    return f'{host}{path}' + (f'?{query}' if query else '')


def normalize_title(value) -> str:
    text = str(value or '')
    text = re.sub(r'\s*[|·-]\s*(?:linkedin(?: jobs)?|naukri|indeed|foundit|shine|internshala)\s*$', '', text, flags=re.I)
    return _plain(text)


def normalize_company(value) -> str:
    text = _plain(value)
    if text in GENERIC_COMPANIES:
        return ''
    text = COMPANY_SUFFIX_RE.sub(' ', text)
    text = re.sub(r'\s+', ' ', text).strip(' .,-')
    return '' if text in GENERIC_COMPANIES else text


def normalize_location(value) -> str:
    text = _plain(value)
    if not text:
        return ''
    for old, new in LOCATION_ALIASES.items():
        text = re.sub(rf'\b{re.escape(old)}\b', new, text)
    text = GENERIC_LOCATION_RE.sub(' ', text)
    # State/country suffixes vary a lot across boards; keep the first useful city/region phrase.
    parts = [re.sub(r'\s+', ' ', x).strip() for x in re.split(r'[,;/|]', text) if x.strip()]
    return (parts[0] if parts else re.sub(r'\s+', ' ', text).strip())[:80]


def _walk_company(value, depth=0) -> str:
    if depth > 4:
        return ''
    if isinstance(value, dict):
        for key in ('company_name', 'companyName', 'company', 'employer_name', 'employerName', 'employer', 'organization'):
            item = value.get(key)
            if isinstance(item, str) and normalize_company(item):
                return item.strip()
            if isinstance(item, dict):
                name = item.get('name')
                if isinstance(name, str) and normalize_company(name):
                    return name.strip()
        hiring = value.get('hiringOrganization') or value.get('hiring_organization')
        if isinstance(hiring, dict) and isinstance(hiring.get('name'), str) and normalize_company(hiring.get('name')):
            return hiring['name'].strip()
        for nested in value.values():
            found = _walk_company(nested, depth + 1)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value[:12]:
            found = _walk_company(nested, depth + 1)
            if found:
                return found
    return ''


def resolved_company(job) -> str:
    direct = str(_value(job, 'company', '') or '').strip()
    if normalize_company(direct):
        return direct
    raw = _value(job, 'raw', {}) or {}
    return _walk_company(raw)


def _walk_req_ids(value, depth=0):
    if depth > 4:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if key in REQ_KEYS and isinstance(item, (str, int)):
                text = str(item).strip()
                if 2 <= len(text) <= 100:
                    yield text.lower()
            if isinstance(item, (dict, list)):
                yield from _walk_req_ids(item, depth + 1)
    elif isinstance(value, list):
        for item in value[:12]:
            yield from _walk_req_ids(item, depth + 1)


def job_identity_keys(job) -> set[str]:
    """Build conservative cross-source identities for notification de-duplication.

    URL identities catch the same listing with different tracking parameters. A title/company/
    location identity catches the same vacancy mirrored on multiple boards. We intentionally do
    not make a title-only key because two different employers can legitimately use the same role.
    """
    keys: set[str] = set()
    for name in ('apply_url', 'canonical_url', 'source_url', 'notification_url'):
        key = normalized_url_key(str(_value(job, name, '') or ''))
        if key:
            keys.add('url:' + key)

    title = normalize_title(_value(job, 'title', ''))
    company = normalize_company(resolved_company(job))
    location = normalize_location(_value(job, 'location', ''))
    if title and company:
        if location:
            keys.add(f'role:{title}|company:{company}|location:{location}')
        else:
            keys.add(f'role:{title}|company:{company}')

        for req_id in _walk_req_ids(_value(job, 'raw', {}) or {}):
            keys.add(f'req:{company}|{req_id}')

    return keys


def is_equivalent_to_history(job, historical_keys: set[str]) -> bool:
    return bool(job_identity_keys(job) & set(historical_keys or set()))
