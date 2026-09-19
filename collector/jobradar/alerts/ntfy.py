import os
import re
from urllib.parse import urlparse

import httpx


def _clean(value):
    return str(value or '').replace('\r', ' ').replace('\n', ' ').strip()


def _http_url(value):
    url = str(value or '').strip()
    if not url.startswith(('http://', 'https://')):
        return None
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    return url if parsed.hostname else None


def _md(value):
    value = _clean(value)
    for ch in ('\\', '`', '*', '_', '[', ']'):
        value = value.replace(ch, '\\' + ch)
    return value


def _category_accent(category):
    value = (category or '').lower()
    if any(x in value for x in ('cyber', 'security', 'soc')):
        return '🟣', 'shield'
    if any(x in value for x in ('network', 'noc', 'infrastructure')):
        return '🔵', 'computer'
    if any(x in value for x in ('government', 'govt', 'public sector')):
        return '🟠', 'office'
    if any(x in value for x in ('startup', 'private')):
        return '🟢', 'rocket'
    if any(x in value for x in ('intern', 'student')):
        return '🟡', 'mortar_board'
    return '🟦', 'briefcase'


def _parse_jobradar_alert(text):
    """Turn the collector's plain-text alert into a compact ntfy card.

    URLs are intentionally removed from the message body and exposed only as native
    action buttons, so Android's ntfy feed stays readable instead of becoming a wall
    of raw links.
    """
    raw_lines = [line.strip() for line in str(text or '').splitlines() if line.strip()]
    if len(raw_lines) < 3 or not raw_lines[0].lower().startswith('jobradar everywhere'):
        return None

    score_match = re.search(r'(\d{1,3})\s*%\s*match', raw_lines[0], re.I)
    score = min(100, int(score_match.group(1))) if score_match else None
    job_title = _clean(raw_lines[1])
    company = _clean(raw_lines[2])
    fields = {}
    open_url = None
    notice_url = None

    for line in raw_lines[3:]:
        if line.lower().startswith('open:'):
            open_url = _http_url(line.split(':', 1)[1].strip())
            continue
        if line.lower().startswith('official notification:'):
            notice_url = _http_url(line.split(':', 1)[1].strip())
            continue
        if ':' in line:
            key, value = line.split(':', 1)
            fields[_clean(key).lower()] = _clean(value)

    category = fields.get('category', '')
    accent, category_tag = _category_accent(category)
    title_parts = [f'{accent} {job_title}']
    if score is not None:
        title_parts.append(f'{score}% match')

    body = []
    if company:
        body.append(f'🏢 **Company:** {_md(company)}')
    body.append(f"📍 **Location:** {_md(fields.get('location') or 'Not disclosed')}")
    body.append(f"💰 **Pay:** {_md(fields.get('compensation') or 'Not disclosed')}")
    if category:
        body.append(f'🧭 **Track:** {_md(category)}')
    if score is not None:
        body.append(f'🎯 **Match:** **{score}%**')
    if fields.get('deadline'):
        body.append(f"⏳ **Deadline:** {_md(fields['deadline'])}")
    body.append('✅ **Application link verified**')

    reasons = [x.strip() for x in (fields.get('why') or '').split(';') if x.strip()]
    if reasons:
        body.extend(['', '**Why it matched**'])
        for reason in reasons[:4]:
            reason = re.sub(r'https?://\S+', '', reason).strip(' -')
            if reason:
                body.append(f'• {_md(reason)}')

    actions = []
    primary = open_url or notice_url
    if primary:
        actions.append({
            'action': 'view',
            'label': '🟢 Open job' if open_url else '📄 Open notice',
            'url': primary,
            'clear': False,
        })
    if notice_url and notice_url != primary:
        actions.append({'action': 'view', 'label': '📄 Official notice', 'url': notice_url, 'clear': False})
    if job_title:
        actions.append({'action': 'copy', 'label': '📋 Copy title', 'value': job_title, 'clear': False})

    return {
        'title': ' · '.join(title_parts),
        'message': '\n'.join(body),
        'actions': actions[:3],
        'tags': ['briefcase', category_tag, 'heavy_check_mark'][:3],
        'url': primary,
    }


def _action_list(actions):
    out = []
    for item in actions or []:
        if not isinstance(item, dict):
            continue
        action = str(item.get('action') or 'view').strip().lower()
        label = _clean(item.get('label') or 'Open')[:40]
        clear = bool(item.get('clear', False))

        if action == 'copy':
            value = _clean(item.get('value'))
            if not value:
                continue
            out.append({'action': 'copy', 'label': label, 'value': value[:1000], 'clear': clear})
        else:
            url = _http_url(item.get('url'))
            if not url:
                continue
            out.append({'action': 'view', 'label': label, 'url': url, 'clear': clear})

        if len(out) >= 3:
            break
    return out


def send_result(text, url=None, title=None, *, actions=None, tags=None, markdown=False, priority=4):
    topic = os.getenv('NTFY_TOPIC')
    server = os.getenv('NTFY_SERVER', 'https://ntfy.sh').rstrip('/')
    if not topic:
        return {'channel': 'ntfy', 'configured': False, 'ok': False, 'error': 'not configured'}

    parsed = _parse_jobradar_alert(text)
    if parsed:
        text = parsed['message']
        title = parsed['title']
        markdown = True
        if actions is None:
            actions = parsed['actions']
        if tags is None:
            tags = parsed['tags']
        if not _http_url(url):
            url = parsed['url']

    payload = {
        'topic': topic,
        'title': _clean(title or 'JobRadar Everywhere')[:200],
        'message': str(text or ''),
        'priority': max(1, min(5, int(priority or 4))),
        'markdown': bool(markdown),
        'tags': list(tags or ['briefcase', 'heavy_check_mark'])[:5],
    }
    safe_url = _http_url(url)
    if safe_url:
        payload['click'] = safe_url
    action_rows = _action_list(actions)
    if not action_rows and safe_url:
        action_rows = [{'action': 'view', 'label': '🟢 Open job', 'url': safe_url, 'clear': False}]
    if action_rows:
        payload['actions'] = action_rows

    try:
        # JSON publishing avoids fragile non-ASCII HTTP header handling and lets ntfy render
        # Markdown plus up to three native action buttons in Android/web clients.
        r = httpx.post(server, json=payload, timeout=20)
        return {
            'channel': 'ntfy',
            'configured': True,
            'ok': r.is_success,
            'status': r.status_code,
            'error': None if r.is_success else r.text[:180],
        }
    except Exception as e:
        return {
            'channel': 'ntfy',
            'configured': True,
            'ok': False,
            'error': str(e)[:180],
        }


def send(text, url=None, title=None, **kwargs):
    return bool(send_result(text, url=url, title=title, **kwargs).get('ok'))
