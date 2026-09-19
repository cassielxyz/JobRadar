from jobradar.linkresolver import _candidate_score, _same_or_trusted, _matches_domain, is_non_job_url


def test_ats_is_trusted():
    assert _matches_domain('https://jobs.lever.co/acme/123', ('lever.co',))


def test_social_is_not_trusted_for_company_source():
    assert not _same_or_trusted('https://linkedin.com/jobs/view/1', ['acme.com'], 'https://careers.acme.com/jobs')


def test_apply_anchor_scores_high():
    score=_candidate_score('Apply Now','https://careers.acme.com/apply/123',['acme.com'],'https://careers.acme.com/jobs/123')
    assert score >= 65


def test_pdf_not_apply():
    score=_candidate_score('Notification','https://acme.gov.in/jobs/notice.pdf',['acme.gov.in'],'https://acme.gov.in/jobs')
    assert score < 65


def test_linkedin_legal_page_is_rejected():
    assert is_non_job_url('https://www.linkedin.com/legal/user-agreement?trk=linkedin-tc_auth-button_user-agreement')


def test_linkedin_job_detail_is_allowed():
    assert not is_non_job_url('https://www.linkedin.com/jobs/view/1234567890?trk=public_jobs_topcard-title')


def test_linkedin_search_page_is_not_a_job_card_source():
    assert is_non_job_url('https://www.linkedin.com/jobs/search/?keywords=network%20engineer')
