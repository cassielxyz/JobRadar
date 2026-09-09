import json
from datetime import datetime, timezone

from .db import SupabaseREST
from .notifications import get_settings, deliver


def main():
    db = SupabaseREST()
    run = db.insert('research_runs', {'trigger': 'notification-test', 'status': 'running'})[0]
    run_id = run['id']
    settings = get_settings(db)
    text = (
        'JobRadar South notification test\n'
        'If you received this message, this delivery channel is configured correctly.\n'
        'This is a test only; no job application is required.'
    )
    results = deliver('JobRadar South — notification test', text, None, settings)
    safe = [{k: v for k, v in r.items() if k not in {'token', 'password'}} for r in results]
    failed = [r for r in safe if not r.get('ok')]
    status = 'completed' if results and not failed else 'failed'
    errors = [{'notification': r.get('channel'), 'error': r.get('error') or f"HTTP {r.get('status')}"} for r in failed]
    db.update('research_runs', {
        'finished_at': datetime.now(timezone.utc).isoformat(),
        'status': status,
        'discovered': 0,
        'verified': 0,
        'matched': 0,
        'alerted': 0,
        'errors': errors,
        'notification_status': {
            'test': True,
            'channels': safe,
            'enabled': {
                'ntfy': bool(settings.get('ntfy_enabled', True)),
                'telegram': bool(settings.get('telegram_enabled', True)),
                'email': bool(settings.get('email_enabled', True)),
            },
        },
    }, {'id': f'eq.{run_id}'})
    print(json.dumps({'notification_test': safe, 'settings': settings}, indent=2))
    if not results:
        raise SystemExit('All notification channels are disabled in dashboard settings.')
    if failed:
        names = ', '.join(str(r.get('channel')) for r in failed)
        raise SystemExit(f'Notification test failed for: {names}. See channel diagnostics above.')


if __name__ == '__main__':
    main()
