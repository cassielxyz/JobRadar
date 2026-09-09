from __future__ import annotations
import re
from .extract import has_explicit_fresher_evidence
from .scoring import location_matches

NORMALIZE = {
    'tcp/ip':'tcp/ip','tcpip':'tcp/ip','active directory':'active directory','ad':'active directory',
    'cyber security':'cybersecurity','information security':'information security','network security':'network security',
    'cloud networking':'cloud networking','aws vpc':'vpc','azure vnet':'vnet',
}
JOB_SKILLS = [
    'tcp/ip','routing','switching','vlan','vpn','firewall','cisco','ccna','ospf','bgp','eigrp','dhcp','dns','nat','acl',
    'wireshark','linux','windows server','active directory','siem','soc','noc','ids/ips','vapt','penetration testing',
    'cybersecurity','information security','network security','incident response','digital forensics','iam','zero trust',
    'aws','azure','gcp','vpc','vnet','cloud networking','cloud security','docker','kubernetes','python','bash','powershell',
]

def norm(v):
    return re.sub(r'\s+',' ',str(v or '').lower()).strip()

def _contains(text, term):
    t=norm(term); s=norm(text)
    if not t:return False
    if len(t)<=3:return bool(re.search(rf'\b{re.escape(t)}\b',s))
    return t in s

def load_candidate(db):
    prefs_rows=db.select('candidate_preferences', {'select':'*','order':'updated_at.desc','limit':'1'})
    if not prefs_rows:return None
    prefs=prefs_rows[0]
    rid=prefs.get('active_resume_id')
    resume=None
    if rid:
        rows=db.select('resumes', {'select':'*','id':f'eq.{rid}','limit':'1'})
        resume=rows[0] if rows else None
    return {'preferences':prefs,'resume':resume}

def apply_candidate_to_categories(categories, candidate):
    if not candidate:return categories
    p=candidate.get('preferences') or {}; r=candidate.get('resume') or {}; parsed=r.get('parsed_json') or {}
    locs=[x for x in (p.get('locations') or []) if str(x).strip()]
    roles=[x for x in (p.get('target_roles') or []) if str(x).strip()]
    resume_roles=[x for x in [*(r.get('target_roles') or []),*(parsed.get('target_roles') or [])] if str(x).strip()]
    excluded=[x for x in (p.get('excluded_terms') or []) if str(x).strip()]
    discovery_skill_allow={'ccna','ccnp','cisco','routing','switching','tcp/ip','vlan','network security','cybersecurity','information security','soc','noc','cloud networking','cloud security','aws','azure','vpc','vnet','linux','firewall','siem','vapt','wireshark','active directory'}
    evidence=' '.join([str(r.get('raw_text') or ''),str(parsed.get('professional_summary') or ''),' '.join(parsed.get('projects') or []),' '.join(r.get('certifications') or [])])
    inferred=[x for x in JOB_SKILLS if _contains(evidence,x)]
    resume_skills=[x for x in [*(r.get('skills') or []),*inferred] if norm(x) in discovery_skill_allow]
    for c in categories:
        if locs:c.locations=list(dict.fromkeys(locs))
        # Global role preferences personalize discovery but preserve each category's specialist seeds.
        c.role_keywords=list(dict.fromkeys([*roles,*resume_roles,*c.role_keywords]))[:40]
        c.hidden_keywords=list(dict.fromkeys([*c.hidden_keywords,*resume_skills]))[:40]
        c.exclude_keywords=list(dict.fromkeys([*excluded,*c.exclude_keywords]))[:30]
        if p.get('max_experience_years') is not None:
            c.max_experience_years=float(p['max_experience_years'])
        if c.type!='internship':
            if p.get('salary_min_monthly') is not None:c.salary_min_monthly=int(p['salary_min_monthly'])
            if p.get('salary_target_monthly') is not None:c.salary_max_monthly=int(p['salary_target_monthly'])
        else:
            if p.get('stipend_min_monthly') is not None:c.stipend_min_monthly=int(p['stipend_min_monthly'])
            if p.get('stipend_target_monthly') is not None:c.stipend_max_monthly=int(p['stipend_target_monthly'])
    return categories

def personalized_score(job, category, base_score, candidate):
    if not candidate or not candidate.get('resume'):
        return base_score, None, [], []
    p=candidate.get('preferences') or {}; r=candidate.get('resume') or {}; parsed=r.get('parsed_json') or {}; text=f"{job.title} {job.description}".lower()
    reasons=[]; fit=0
    roles=list(dict.fromkeys([*(p.get('target_roles') or []),*(r.get('target_roles') or []),*(parsed.get('target_roles') or []),*category.role_keywords]))
    role_hits=[x for x in roles if _contains(job.title,x)]
    if role_hits:
        fit+=30; reasons.append('resume target role aligns with title')
    elif any(_contains(text,x) for x in roles):
        fit+=20; reasons.append('resume target role aligns with duties')

    resume_evidence=' '.join([str(r.get('raw_text') or ''),str(parsed.get('professional_summary') or ''),' '.join(parsed.get('projects') or []),' '.join(r.get('certifications') or [])]).lower()
    inferred_skills=[s for s in JOB_SKILLS if _contains(resume_evidence,s)]
    skills=list(dict.fromkeys([norm(x) for x in [*(r.get('skills') or []),*inferred_skills] if norm(x)]))
    matched=[s for s in skills if _contains(text,s)]
    if skills:
        # Reward up to eight concrete matching skills, not sheer resume keyword volume.
        fit+=round(35*min(1,len(matched)/max(3,min(8,len(skills)))))
        if matched:reasons.append('resume skills: '+', '.join(matched[:5]))

    certs=[norm(x) for x in [*(r.get('certifications') or []),*(parsed.get('certifications') or [])] if norm(x)]
    cert_hits=[x for x in certs if _contains(text,x)]
    if cert_hits:
        fit+=10; reasons.append('relevant certification: '+', '.join(cert_hits[:2]))

    educ=' '.join([*(r.get('education') or []),*(parsed.get('education') or [])]).lower()
    if re.search(r'computer science|\bcse\b|information technology|\bit\b',educ+' '+str(r.get('raw_text') or '')[:6000].lower()):
        if re.search(r'computer science|\bcse\b|information technology|\bit\b|b\.?e|b\.?tech',text):
            fit+=8; reasons.append('education aligns with eligibility')

    locs=p.get('locations') or category.locations
    if location_matches(job.location or '',locs):
        fit+=10; reasons.append('selected location')
    elif not job.location and (p.get('allow_remote') or False) and re.search(r'\bremote\b',text):
        fit+=10; reasons.append('remote preference')

    maxexp=float(p.get('max_experience_years') or category.max_experience_years or 2)
    if job.experience_max is not None and float(job.experience_max)<=maxexp:
        fit+=7; reasons.append('experience requirement fits')
    elif has_explicit_fresher_evidence(text):
        fit+=7; reasons.append('fresher-friendly')

    if job.apply_verified and job.apply_url:
        fit+=5

    fit=max(0,min(100,fit))
    final=round((base_score*0.5)+(fit*0.5))
    # A strong rules/AI score should never be hidden solely because a sparse resume omitted keywords.
    final=max(min(base_score,88),final)

    job_required=[s for s in JOB_SKILLS if _contains(text,s)]
    gaps=[s for s in job_required if not any(norm(s)==x or _contains(x,s) or _contains(s,x) for x in skills)]
    return max(0,min(100,final)),fit,reasons[:6],gaps[:8]

def should_queue_auto_apply(job, category, final_score, candidate):
    if not candidate or not candidate.get('resume'):return False,'no active resume'
    if getattr(category,'type',None)=='government':return False,'government applications require manual review'
    p=candidate.get('preferences') or {}
    if not p.get('auto_apply_enabled'):return False,'auto apply disabled'
    threshold=int(p.get('auto_apply_threshold') or 95)
    if final_score<threshold:return False,'below auto-apply threshold'
    if job.event_type!='vacancy' or job.application_status=='closed':return False,'not an open vacancy'
    if not job.apply_verified or not job.apply_url:return False,'apply link is not verified'
    return True,'high-confidence verified match'
