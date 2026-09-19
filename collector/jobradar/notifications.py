from __future__ import annotations

from .alerts.telegram import send_result as telegram_send
from .alerts.ntfy import send_result as ntfy_send
from .alerts.email import send_result as email_send

DEFAULTS = {
    'ntfy_enabled': True,
    'telegram_enabled': True,
    'email_enabled': True,
    'minimum_score': 70,
}


def get_settings(db):
    try:
        rows = db.select('notification_settings', {'select':'*','id':'eq.default'})
        return {**DEFAULTS, **(rows[0] if rows else {})}
    except Exception:
        return dict(DEFAULTS)


def deliver(
    subject: str,
    text: str,
    url: str | None,
    settings: dict,
    *,
    ntfy_text: str | None = None,
    ntfy_actions: list[dict] | None = None,
    ntfy_tags: list[str] | None = None,
    ntfy_markdown: bool = False,
):
    results = []
    if settings.get('ntfy_enabled', True):
        results.append(ntfy_send(
            ntfy_text if ntfy_text is not None else text,
            url,
            title=subject,
            actions=ntfy_actions,
            tags=ntfy_tags,
            markdown=ntfy_markdown,
        ))
    if settings.get('telegram_enabled', True):
        results.append(telegram_send(text))
    if settings.get('email_enabled', True):
        results.append(email_send(subject, text))
    return results


def any_success(results):
    return any(x.get('ok') for x in results)
