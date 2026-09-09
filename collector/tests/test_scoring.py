from jobradar.models import Job,Category
from jobradar.scoring import score_job

def test_network_fresher_match():
    c=Category(id='1',name='Entry',slug='entry',type='entry_level',role_keywords=['network engineer'],hidden_keywords=['technical support'],exclude_keywords=['senior'],locations=['Chennai'],max_experience_years=2,salary_min_monthly=20000)
    j=Job(title='Network Engineer - Fresher',company='X',location='Chennai',description='TCP/IP routing switching. ₹25000 per month',source_id='x',source_url='x',canonical_url='https://x.test/job',experience_max=1,salary_min_monthly=25000,official_verified=True)
    s,r,e=score_job(j,c); assert s>=70 and e
