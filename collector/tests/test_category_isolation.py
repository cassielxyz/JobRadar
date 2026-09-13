from jobradar.models import Category
from jobradar.resume_match import apply_candidate_to_categories

def category(name,slug,keywords):
    return Category(id=slug,name=name,slug=slug,type='custom',role_keywords=keywords,hidden_keywords=[],exclude_keywords=[],locations=['Chennai'])

def test_profile_roles_do_not_contaminate_existing_categories():
    cats=[category('Software developer','software',['software developer','frontend developer']),category('SOC','soc',['soc analyst'])]
    candidate={'preferences':{'locations':['Chennai'],'target_roles':['SOC Analyst'],'excluded_terms':[]},'resume':{'target_roles':['Network Engineer'],'skills':['SIEM','CCNA'],'parsed_json':{}}}
    out=apply_candidate_to_categories(cats,candidate)
    assert 'SOC Analyst' not in out[0].role_keywords
    assert 'Network Engineer' not in out[0].role_keywords
    assert out[0].role_keywords==['software developer','frontend developer']
    assert out[1].role_keywords==['soc analyst']

def test_empty_custom_category_can_fallback_to_profile_roles():
    cats=[category('My jobs','mine',[])]
    candidate={'preferences':{'locations':['Kerala'],'target_roles':['Cloud Support Engineer'],'excluded_terms':[]},'resume':{'target_roles':[],'skills':[],'parsed_json':{}}}
    out=apply_candidate_to_categories(cats,candidate)
    assert 'Cloud Support Engineer' in out[0].role_keywords
