import json
from .alerts.telegram import send_result as telegram_send
from .alerts.ntfy import send_result as ntfy_send
from .alerts.email import send_result as email_send


def main():
    text = (
        'JobRadar South notification test\n'
        'If you received this message, this delivery channel is configured correctly.\n'
        'This is a test only; no job application is required.'
    )
    results = [
        ntfy_send(text, None),
        telegram_send(text),
        email_send('JobRadar South — notification test', text),
    ]
    safe = [{k:v for k,v in r.items() if k not in {'token','password'}} for r in results]
    print(json.dumps({'notification_test': safe}, indent=2))
    configured = [r for r in results if r.get('configured')]
    if not configured:
        raise SystemExit('No notification channels are configured in this workflow.')
    if not any(r.get('ok') for r in configured):
        raise SystemExit('All configured notification channels failed. See results above.')


if __name__ == '__main__':
    main()
