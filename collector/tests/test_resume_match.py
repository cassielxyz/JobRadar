from jobradar.models import Job, Category
from jobradar.resume_match import personalized_score, should_queue_auto_apply, apply_candidate_to_categories


def category(kind='entry_level'):
    return Category(id='c',name='Entry',slug='entry',type=kind,role_keywords=['network engineer','soc analyst'],hidden_keywords=[],exclude_keywords=[],locations=['Chennai'],max_experience_years=2,alert_threshold=70)


def candidate(auto=True):
    return {'preferences':{'user_id':'u','active_resume_id':'r','locations':['Chennai','Bengaluru'],'target_roles':['network engineer'],'excluded_terms':[],'max_experience_years':2,'auto_apply_enabled':auto,'auto_apply_threshold':95},'resume':{'id':'r','skills':['TCP/IP','Routing','Switching','Cisco','CCNA','Linux'],'target_roles':['Network Engineer'],'certifications':['CCNA'],'education':['BE Computer Science and Engineering'],'raw_text':'BE CSE CCNA'}}


def test_resume_personalizes_locations_and_roles():
    c=category(); apply_candidate_to_categories([c],candidate())
    assert 'Bengaluru' in c.locations
    assert 'network engineer' in [x.lower() for x in c.role_keywords]


def test_resume_score_rewards_matching_network_skills():
    j=Job(title='Network Engineer - Fresher',company='X',location='Chennai',description='BE CSE. TCP/IP routing switching Cisco CCNA Linux. Fresher role.',source_id='x',source_url='x',canonical_url='https://x.test/job',experience_max=1,apply_verified=True,apply_url='https://x.test/apply')
    final,fit,reasons,gaps=personalized_score(j,category(),95,candidate())
    assert fit >= 80
    assert final >= 88
    assert any('resume skills' in x for x in reasons)


def test_auto_apply_requires_threshold_and_verified_destination():
    j=Job(title='Network Engineer',company='X',location='Chennai',description='routing',source_id='x',source_url='x',canonical_url='x',apply_verified=True,apply_url='https://boards.greenhouse.io/x/jobs/1')
    ok,_=should_queue_auto_apply(j,category(),96,candidate())
    assert ok
    ok,_=should_queue_auto_apply(j,category(),94,candidate())
    assert not ok


def test_government_never_auto_applies():
    j=Job(title='Technical Officer Network',company='Gov',location='Chennai',description='routing',source_id='g',source_url='x',canonical_url='x',apply_verified=True,apply_url='https://gov.in/apply')
    ok,reason=should_queue_auto_apply(j,category('government'),99,candidate())
    assert not ok and 'government' in reason
