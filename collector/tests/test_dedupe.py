from jobradar.dedupe import job_identity_keys, normalized_url_key


def test_tracking_parameters_do_not_make_a_new_job():
    a = normalized_url_key('https://careers.example.com/jobs/123/?utm_source=naukri&ref=home')
    b = normalized_url_key('https://careers.example.com/jobs/123')
    assert a == b


def test_indeed_job_id_query_parameter_is_preserved():
    a = normalized_url_key('https://in.indeed.com/viewjob?jk=abc123&utm_source=google')
    b = normalized_url_key('https://in.indeed.com/viewjob?jk=def456&utm_source=google')
    assert a.endswith('viewjob?jk=abc123')
    assert b.endswith('viewjob?jk=def456')
    assert a != b


def test_same_vacancy_on_different_boards_shares_role_company_location_identity():
    naukri = {
        'title': 'Network Support Engineer',
        'company': 'Acme Networks Pvt Ltd',
        'location': 'Bengaluru, Karnataka, India',
        'canonical_url': 'https://www.naukri.com/job-listings-network-support-engineer-acme-123',
    }
    linkedin = {
        'title': 'Network Support Engineer',
        'company': 'Acme Networks Private Limited',
        'location': 'Bangalore, Karnataka',
        'canonical_url': 'https://www.linkedin.com/jobs/view/987654321',
    }
    assert job_identity_keys(naukri) & job_identity_keys(linkedin)


def test_same_title_at_different_companies_is_not_cross_source_duplicate():
    a = {
        'title': 'SOC Analyst L1', 'company': 'Alpha Security', 'location': 'Chennai',
        'canonical_url': 'https://example.com/jobs/a',
    }
    b = {
        'title': 'SOC Analyst L1', 'company': 'Beta Security', 'location': 'Chennai',
        'canonical_url': 'https://example.net/jobs/b',
    }
    assert not (job_identity_keys(a) & job_identity_keys(b))


def test_same_company_title_in_different_known_cities_is_not_merged():
    chennai = {
        'title': 'NOC Engineer', 'company': 'Example Telecom', 'location': 'Chennai',
        'canonical_url': 'https://jobs.example.com/chennai/noc-1',
    }
    kochi = {
        'title': 'NOC Engineer', 'company': 'Example Telecom', 'location': 'Kochi',
        'canonical_url': 'https://jobs.example.com/kochi/noc-2',
    }
    role_keys_a = {x for x in job_identity_keys(chennai) if x.startswith('role:')}
    role_keys_b = {x for x in job_identity_keys(kochi) if x.startswith('role:')}
    assert not (role_keys_a & role_keys_b)
