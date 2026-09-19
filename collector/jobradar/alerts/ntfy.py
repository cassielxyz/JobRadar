import os
import httpx


def _clean(value):
    return str(value or '').replace('\r', ' ').replace('\n', ' ').strip()


def _action_list(actions):
    out = []
    for item in actions or []:
        if not isinstance(item, dict):
            continue
        url = str(item.get('url') or '').strip()
        label = _clean(item.get('label') or 'Open')[:40]
        if not url.startswith(('http://', 'https://')):
            continue
        out.append({'action': 'view', 'label': label, 'url': url, 'clear': bool(item.get('clear', False))})
        if len(out) >= 3:
            break
    return out


def send_result(text, url=None, title=None, *, actions=None, tags=None, markdown=False, priority=4):
    topic = os.getenv('NTFY_TOPIC')
    server = os.getenv('NTFY_SERVER', 'https://ntfy.sh').rstrip('/')
    if not topic:
        return {'channel': 'ntfy', 'configured': False, 'ok': False, 'error': 'not configured'}

    payload = {
        'topic': topic,
        'title': _clean(title or 'JobRadar Everywhere')[:200],
        'message': str(text or ''),
        'priority': max(1, min(5, int(priority or 4))),
        'markdown': bool(markdown),
        'tags': list(tags or ['briefcase', 'heavy_check_mark'])[:5],
    }
    if url and str(url).startswith(('http://', 'https://')):
        payload['click'] = str(url)
    action_rows = _action_list(actions)
    if not action_rows and url and str(url).startswith(('http://', 'https://')):
        action_rows = [{'action': 'view', 'label': 'Open job', 'url': str(url), 'clear': False}]
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
