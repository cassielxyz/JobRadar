from jobradar.models import Job,Category
from jobradar.trust import assess_job_trust
from jobradar.scoring import score_job

def job(**kw):
    base=dict(title='SOC Analyst',company='Acme',location='Chennai',description='Monitor SIEM alerts and investigate incidents.',source_id='x',source_url='https://www.linkedin.com/jobs/view/1',canonical_url='https://www.linkedin.com/jobs/view/1')
    base.update(kw);return Job(**base)

def cat(**kw):
    base=dict(id='1',name='Cyber',slug='cyber',type='startup',role_keywords=['soc analyst'],hidden_keywords=['security analyst'],exclude_keywords=[],locations=['Chennai'],max_experience_years=2,source_kinds=['job_board'])
    base.update(kw);return Category(**base)

def test_known_board_is_not_blocked():
    t=assess_job_trust(job(),cat());assert not t['blocked'];assert t['score']>=70

def test_payment_scam_is_blocked_for_private_job():
    j=job(description='SOC analyst. Pay a refundable security deposit to the recruiter before joining.')
    t=assess_job_trust(j,cat());assert t['blocked']
    assert score_job(j,cat())[2] is False

def test_government_notice_fee_not_automatically_scam():
    j=job(title='Technical Assistant - Network',description='Official application fee as stated in notification. Networking and CSE eligible.',canonical_url='https://example.gov.in/jobs/1',source_url='https://example.gov.in/jobs/1',official_verified=True)
    c=cat(type='government',role_keywords=['network'],require_official_verification=True)
    assert not assess_job_trust(j,c)['blocked']
