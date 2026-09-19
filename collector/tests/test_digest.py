from jobradar.digest import _company, _destination, _meaningful_title


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


def test_digest_requires_verified_apply_destination_for_vacancy():
    job = {
        'event_type': 'vacancy',
        'apply_verified': False,
        'apply_url': 'https://example.com/job/1',
        'canonical_url': 'https://example.com/job/1',
    }
    assert _destination(job) == ''
    job['apply_verified'] = True
    assert _destination(job) == 'https://example.com/job/1'
