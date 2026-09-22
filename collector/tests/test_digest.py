from jobradar.digest import _company, _destination, _fallback_floor, _meaningful_title
from jobradar.collectors.freehire import _rotate


def test_digest_rejects_generic_search_titles():
    assert _meaningful_title('URL') == ''
    assert _meaningful_title('Job opening') == ''
    assert _meaningful_title('Network Support Engineer') == 'Network Support Engineer'


def test_digest_uses_raw_company_when_discovery_label_is_generic():
    job = {
        'company': 'External job-platform discovery',
        'raw': {'result': {'company_name': 'Example Networks Pvt Ltd'}},
    }
    assert _company(job, 'https://internshala.com/job/123') == 'Example Networks Pvt Ltd'


def test_digest_prefers_verified_direct_apply_destination():
    job = {
        'event_type': 'vacancy',
        'active': True,
        'apply_verified': True,
        'apply_url': 'https://careers.example.com/jobs/1/apply',
        'canonical_url': 'https://careers.example.com/jobs/1',
    }
    assert _destination(job) == 'https://careers.example.com/jobs/1/apply'


def test_digest_uses_safe_live_job_page_when_apply_button_cannot_be_verified():
    job = {
        'event_type': 'vacancy',
        'active': True,
        'apply_verified': False,
        'apply_url': None,
        'canonical_url': 'https://www.linkedin.com/jobs/view/123456789',
    }
    assert _destination(job) == 'https://www.linkedin.com/jobs/view/123456789'


def test_digest_does_not_fallback_to_login_or_legal_pages():
    job = {
        'event_type': 'vacancy',
        'active': True,
        'apply_verified': False,
        'apply_url': None,
        'canonical_url': 'https://www.linkedin.com/legal/user-agreement',
        'source_url': 'https://www.linkedin.com/login',
    }
    assert _destination(job) == ''


def test_fallback_floor_relaxes_silence_without_dropping_below_quality_floor():
    assert _fallback_floor(70) == 55
    assert _fallback_floor(80) == 55
    assert _fallback_floor(50) == 50


def test_freehire_query_rotation_changes_leading_role_without_losing_queries():
    values = ['network engineer', 'noc engineer', 'network admin', 'support engineer']
    rotated = _rotate(values, 2)
    assert rotated[0] == 'network admin'
    assert sorted(rotated) == sorted(values)
