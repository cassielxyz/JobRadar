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


def test_linkedin_post_is_rejected():
    assert is_non_job_url('https://www.linkedin.com/posts/some-user_network-engineer-fresher-activity-123456')


def test_linkedin_job_detail_is_allowed():
    assert not is_non_job_url('https://www.linkedin.com/jobs/view/1234567890?trk=public_jobs_topcard-title')


def test_linkedin_search_page_is_not_a_job_card_source():
    assert is_non_job_url('https://www.linkedin.com/jobs/search/?keywords=network%20engineer')


def test_internshala_registration_is_rejected():
    assert is_non_job_url('https://internshala.com/registration/student')


def test_internshala_job_detail_is_allowed():
    assert not is_non_job_url('https://internshala.com/job/detail/fresher-network-engineering-role-job-in-bangalore-at-example123')


def test_shine_login_is_rejected():
    assert is_non_job_url('https://www.shine.com/pages/myshine/login')


def test_dayforce_job_url_is_allowed_as_direct_ats_destination():
    assert not is_non_job_url('https://jobs.dayforcehcm.com/en-US/acme/CANDIDATEPORTAL/jobs/12345')


def test_workday_site_job_url_is_allowed_as_direct_ats_destination():
    assert not is_non_job_url('https://acme.wd5.myworkdaysite.com/recruiting/acme/jobs/job/Network-Engineer_R123')


def test_adp_job_url_is_allowed_as_direct_ats_destination():
    assert not is_non_job_url('https://recruiting.adp.com/srccar/public/RTI.home?c=123&d=ExternalCareerSite')
