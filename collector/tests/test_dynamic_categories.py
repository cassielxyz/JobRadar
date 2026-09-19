from jobradar.category_research import category_search_terms, related_title_match
from jobradar.models import Category, Job
from jobradar.scoring import semantic_gate, location_plausible


def _category(name, keywords, hidden=None, kind='custom'):
    return Category(
        id='test', name=name, slug=name.lower().replace(' ', '-'), type=kind,
        role_keywords=keywords, hidden_keywords=hidden or [], exclude_keywords=[],
        locations=['Chennai', 'Tamil Nadu'], source_kinds=['job_board', 'community'],
    )


def _job(title, description=''):
    return Job(
        title=title, company='Example', location='Chennai, Tamil Nadu',
        description=description, source_id='test', source_url='https://example.com/jobs/1',
        canonical_url='https://example.com/jobs/1',
    )


def test_new_category_uses_name_as_search_fallback():
    cat = _category('Data Analyst', ['SQL'])
    terms = [x.lower() for x in category_search_terms(cat)]
    assert 'data analyst' in terms
    assert 'business intelligence analyst' in terms


def test_adjacent_title_is_relevant_for_new_category():
    cat = _category('Data Analyst', ['data analyst', 'sql', 'power bi'])
    job = _job('Business Intelligence Analyst', 'SQL dashboards and Power BI reporting')
    ok, _ = semantic_gate(job, cat)
    assert ok


def test_network_category_expands_to_noc_title():
    cat = _category('Networking', ['network engineer', 'ccna'])
    hits = related_title_match('NOC Engineer - L1', cat)
    assert hits
    ok, _ = semantic_gate(_job('NOC Engineer - L1', 'Monitor WAN links and Cisco routers'), cat)
    assert ok


def test_unrelated_custom_job_stays_rejected():
    cat = _category('Data Analyst', ['data analyst', 'sql'])
    ok, _ = semantic_gate(_job('Mechanical Design Engineer', 'AutoCAD and machine design'), cat)
    assert not ok


def test_country_only_location_is_kept_for_detail_verification():
    assert location_plausible('India', ['Chennai', 'Tamil Nadu'])
    assert not location_plausible('Delhi', ['Chennai', 'Tamil Nadu'])
