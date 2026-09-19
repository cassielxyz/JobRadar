from jobradar.verify import verify_url


def test_verify_rejects_linkedin_legal_without_fetching():
    result = verify_url('https://www.linkedin.com/legal/user-agreement')
    assert result['active'] is False
    assert result['reason'] == 'non_job_url'


def test_verify_rejects_linkedin_post_without_fetching():
    result = verify_url('https://www.linkedin.com/posts/example_network-engineer-activity-123')
    assert result['active'] is False
    assert result['reason'] == 'non_job_url'
