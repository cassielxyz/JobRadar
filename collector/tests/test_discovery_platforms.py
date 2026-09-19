from jobradar.collectors.agent_reach import AgentReachCollector, PLATFORMS, _platform_for, _clean_title
from jobradar.models import Category


def test_platform_catalog_has_at_least_fifty_sources():
    assert len(PLATFORMS) >= 50
    domains = {str(x.get('domain')) for x in PLATFORMS}
    for required in {
        'linkedin.com', 'naukri.com', 'indeed.com', 'internshala.com',
        'cutshort.io', 'instahyre.com', 'wellfound.com',
        'boards.greenhouse.io', 'jobs.lever.co', 'jobs.ashbyhq.com',
        'myworkdayjobs.com',
    }:
        assert required in domains


def test_platform_detection_prefers_specific_domain():
    assert _platform_for('https://jobs.lever.co/example/123')['name'] == 'Lever'
    assert _platform_for('https://boards.greenhouse.io/example/jobs/1')['name'] == 'Greenhouse'


def test_fresher_queries_include_major_india_boards_and_ats():
    cat = Category(
        id='x', name='Fresher Cyber', slug='fresher-cyber', type='startup',
        role_keywords=['SOC Analyst', 'Network Engineer'], hidden_keywords=['Security Analyst'],
        exclude_keywords=[], locations=['Chennai', 'Bengaluru'], fresher_only=True,
        source_kinds=['community','job_board','ats'],
    )
    queries = ' '.join(AgentReachCollector()._queries(cat)).lower()
    assert 'site:naukri.com' in queries
    assert 'site:indeed.com' in queries
    assert 'site:linkedin.com' in queries
    assert 'site:jobs.lever.co' in queries
    assert 'fresher' in queries


def test_search_result_title_is_cleaned():
    dirty='URL: [Network Engineer Fresher](https://example.com/jobs/1) https://example.com/jobs/1'
    assert _clean_title(dirty) == 'Network Engineer Fresher'
