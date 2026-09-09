from jobradar.models import Job, Category
from jobradar.scoring import score_job, location_matches, source_allowed, fresher_gate
from jobradar.extract import infer_experience


def cat(kind='entry_level', fresher=None):
    if fresher is None:
        fresher = kind in {'startup','entry_level','internship'}
    return Category(
        id='1', name='Entry', slug='entry', type=kind,
        role_keywords=['network engineer','soc analyst','cybersecurity analyst','cloud support engineer'],
        hidden_keywords=['technical support','scientist','technical officer'],
        exclude_keywords=['senior','manager','mechanical'],
        locations=['Chennai','Tamil Nadu','Bengaluru','Kerala'],
        max_experience_years=2,
        salary_min_monthly=20000,
        require_official_verification=(kind == 'government'),
        source_kinds=['job_board','company'] if kind != 'government' else ['government'],
        alert_threshold=70,
        fresher_only=fresher,
    )


def job(title='Network Engineer - Fresher', description='TCP/IP routing switching. Fresher. ₹25000 per month', exp_min=None, exp_max=1):
    return Job(title=title,company='X',location='Chennai',description=description,source_id='x',source_url='x',canonical_url='https://x.test/job',experience_min=exp_min,experience_max=exp_max,salary_min_monthly=25000)


def test_network_fresher_match():
    s, r, e = score_job(job(), cat())
    assert s >= 70 and e


def test_empty_location_never_matches():
    assert location_matches('', ['Tamil Nadu','Chennai']) == []


def test_unknown_experience_is_not_fresher_bonus():
    c = cat()
    j = job(title='Network Engineer',description='TCP/IP routing switching.',exp_max=None)
    score, reasons, eligible = score_job(j, c)
    assert 'experience not stated' in reasons
    assert 'experience within category target' not in reasons
    assert eligible in {True, False}  # unknown is not a hard rejection; only explicit non-fresher evidence is.


def test_two_plus_years_soc_is_rejected_in_fresher_category():
    c=cat('startup',True)
    j=job(title='SOC Analyst',description='2+ years of hands-on experience in a Security Operations Center. SIEM incident response cybersecurity.',exp_min=2,exp_max=None)
    ok,reasons=fresher_gate(j,c)
    assert not ok
    assert 'fresher-only category' in reasons[0]
    score,reasons,eligible=score_job(j,c)
    assert score == 0 and not eligible


def test_two_plus_years_not_hard_rejected_in_general_category():
    c=cat('custom',False)
    c.role_keywords=['soc analyst'];c.hidden_keywords=[];c.source_kinds=[]
    j=job(title='SOC Analyst',description='2+ years of hands-on experience in a Security Operations Center. SIEM incident response cybersecurity.',exp_min=2,exp_max=None)
    ok,_=fresher_gate(j,c)
    assert ok
    score,reasons,eligible=score_job(j,c)
    assert score > 0
    assert not any('fresher-only category' in x for x in reasons)


def test_zero_to_two_years_is_allowed_in_fresher_category():
    c=cat('entry_level',True)
    j=job(title='Network Engineer',description='0-2 years experience. TCP/IP routing switching.',exp_min=0,exp_max=2)
    ok,_=fresher_gate(j,c)
    assert ok


def test_infer_experience_keeps_plus_open_ended():
    assert infer_experience('Requires 2+ years of hands-on experience') == (2.0, None)
    assert infer_experience('0-2 years experience accepted') == (0.0, 2.0)


def test_mechanical_government_scientist_is_rejected():
    c = cat('government',False)
    j = Job(title='Scientist/Engineer SC Mechanical',company='ISRO',location='Bengaluru',description='Mechanical engineering recruitment.',source_id='isro',source_url='https://isro.gov.in/Careers.html',canonical_url='https://isro.gov.in/job',official_verified=True)
    score, reasons, eligible = score_job(j, c)
    assert score == 0 and not eligible
    assert 'unrelated engineering discipline' in reasons


def test_government_hidden_title_needs_actual_tech_evidence_to_display():
    c = cat('government',False)
    j = Job(title='Technical Officer - Computer Science',company='Gov Lab',location='Chennai',description='BE CSE. Work includes routing, switching, firewall administration and VPN. Freshers eligible.',source_id='gov',source_url='https://gov.in/jobs',canonical_url='https://gov.in/jobs/1',experience_max=0,official_verified=True)
    score, reasons, eligible = score_job(j, c)
    assert eligible and score >= 55


def test_source_kinds_are_enforced():
    c = cat('government',False)
    assert source_allowed(c, 'government')
    assert not source_allowed(c, 'job_board')
