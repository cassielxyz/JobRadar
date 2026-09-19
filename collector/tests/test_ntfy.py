from jobradar.alerts.ntfy import _action_list, _parse_jobradar_alert


def test_jobradar_alert_becomes_clean_ntfy_card():
    text = '''JobRadar Everywhere — 87% match
Network Engineer
Example Networks
Location: Chennai
Compensation: ₹25,000/month
Category: Startup Fresher Jobs
Why: CCNA match; routing and switching; fresher friendly
Open: https://careers.example.com/jobs/123
Official notification: https://careers.example.com/jobs/123/notice.pdf
'''
    parsed = _parse_jobradar_alert(text)
    assert parsed is not None
    assert parsed['title'].startswith('🟢 Network Engineer')
    assert '87% match' in parsed['title']
    assert 'https://' not in parsed['message']
    assert '**Company:** Example Networks' in parsed['message']
    assert '📍 **Location:** Chennai' in parsed['message']
    assert parsed['actions'][0]['url'] == 'https://careers.example.com/jobs/123'
    assert parsed['actions'][1]['url'].endswith('/notice.pdf')
    assert parsed['actions'][2]['action'] == 'copy'


def test_action_list_supports_safe_view_and_copy_only():
    actions = _action_list([
        {'action': 'view', 'label': 'Apply', 'url': 'https://example.com/job'},
        {'action': 'copy', 'label': 'Copy title', 'value': 'Network Engineer'},
        {'action': 'view', 'label': 'Bad', 'url': 'javascript:alert(1)'},
    ])
    assert len(actions) == 2
    assert actions[0]['action'] == 'view'
    assert actions[1]['action'] == 'copy'
