from __future__ import annotations

import json
import re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(path):return (ROOT/path).read_text(encoding='utf-8')
def write(path,text):(ROOT/path).write_text(text,encoding='utf-8')
def replace_once(text,old,new,label):
    if old not in text:raise SystemExit(f'patch target missing: {label}')
    return text.replace(old,new,1)

# 1. Keep category discovery isolated. Resume/profile roles personalize scoring; they do not
# overwrite every category's own semantic definition.
p=Path('collector/jobradar/resume_match.py');t=read(p)
t=replace_once(t,
"        # Global role preferences personalize discovery but preserve each category's specialist seeds.\n        c.role_keywords=list(dict.fromkeys([*roles,*resume_roles,*c.role_keywords]))[:40]\n        c.hidden_keywords=list(dict.fromkeys([*c.hidden_keywords,*resume_skills]))[:40]\n",
"        # Category isolation: a SOC/network profile must not turn a Software Developer or other\n        # custom category into a SOC category. Profile roles are only a fallback for categories\n        # that intentionally have no role definition. Resume details still affect personalized_score.\n        if not c.role_keywords:\n            c.role_keywords=list(dict.fromkeys([*roles,*resume_roles]))[:40]\n        c.hidden_keywords=list(dict.fromkeys(c.hidden_keywords))[:40]\n",
'category isolation')
write(p,t)

# 2. Category-specific relevance + trust/scam gate + broader display floor.
p=Path('collector/jobradar/scoring.py');t=read(p)
t=replace_once(t,'from .extract import has_explicit_fresher_evidence\n','from .extract import has_explicit_fresher_evidence\nfrom .trust import assess_job_trust\n','trust import')
start=t.index('def semantic_gate(job: Job, category: Category):')
end=t.index('\ndef fresher_gate(job: Job, category: Category):',start)
semantic='''def semantic_gate(job: Job, category: Category):
    """Hard category relevance gate before ranking.

    Each category keeps its own role family. A networking/cyber resume therefore cannot make a
    SOC vacancy relevant to a Software Developer category. Government hidden titles remain a
    special case and need explicit CSE/IT or networking/security/cloud evidence.
    """
    title = norm(job.title)
    body = norm(job.description)
    text = f"{title} {body}"
    category_text = norm(' '.join([*(category.role_keywords or []), *(category.hidden_keywords or [])]))
    category_is_network_family = bool(CORE_TECH.search(category_text))

    if UNRELATED_DISCIPLINE_TITLE.search(title) and not CORE_TECH.search(title):
        return False, ["unrelated engineering discipline"]

    role_hits_title = contains_any(title, category.role_keywords)
    role_hits_body = contains_any(text, category.role_keywords)
    hidden_hits = contains_any(title, category.hidden_keywords) or contains_any(text, category.hidden_keywords)
    core = bool(CORE_TECH.search(text))
    cse = bool(CSE_EVIDENCE.search(text))

    if category.type == 'government':
        relevant = bool(role_hits_title or role_hits_body or (category_is_network_family and core) or (hidden_hits and cse))
        if not relevant:
            return False, ["no category-specific networking/cyber/cloud or CSE/IT evidence"]
    else:
        # Direct role/hidden-title evidence works for any category, including software/custom.
        relevant = bool(role_hits_title or role_hits_body or hidden_hits)
        # Only networking/cyber/cloud categories may use generic CORE_TECH as a fallback.
        if not relevant and category_is_network_family and core:
            relevant = True
        if not relevant:
            return False, ["job does not match this category's role family"]
        if category.type == 'internship' and not INTERNSHIP_TITLE.search(text):
            # An internship category must still have internship/trainee evidence.
            return False, ["listing is not clearly an internship/trainee role"]

    if getattr(category, 'fresher_only', False) and SENIOR_TITLE.search(title):
        return False, ["fresher-only category: senior-level title"]
    return True, []

'''
t=t[:start]+semantic+t[end+1:]
needle='''    fresh_ok, fresh_reasons = fresher_gate(job, category)\n    if not fresh_ok:\n        return 0, fresh_reasons, False\n\n    text = " ".join([job.title, job.description, job.company])\n'''
replacement='''    fresh_ok, fresh_reasons = fresher_gate(job, category)\n    if not fresh_ok:\n        return 0, fresh_reasons, False\n\n    trust = assess_job_trust(job, category)\n    if trust.get('blocked'):\n        return 0, ["trust/scam gate: " + str((trust.get('reasons') or ['blocked'])[-1])], False\n\n    text = " ".join([job.title, job.description, job.company])\n'''
t=replace_once(t,needle,replacement,'trust gate insertion')
t=replace_once(t,'    score = 0\n    reasons = []\n','''    score = 0\n    reasons = []\n    trust_score = int(trust.get('score') or 0)\n    if trust_score >= 90:\n        score += 8; reasons.append("high-trust source")\n    elif trust_score >= 70:\n        score += 4; reasons.append("recognized source")\n''','trust score bonus')
t=t.replace('    eligible = score >= 55\n','    eligible = score >= 40\n')
write(p,t)

# 3. Collector: lower dashboard-only floor and allow per-result official-domain verification.
p=Path('collector/jobradar/main.py');t=read(p)
t=t.replace("DISPLAY_MIN_SCORE = int(os.getenv('DASHBOARD_MIN_SCORE', '55') or 55)","DISPLAY_MIN_SCORE = int(os.getenv('DASHBOARD_MIN_SCORE', '40') or 40)")
old="""    v = verify_url(job.canonical_url, source.get('official_domains') or [])\n    if not v.get('active'):\n        return\n"""
new="""    official_domains = list(source.get('official_domains') or [])\n    for domain in ((job.raw or {}).get('official_domains') or []):\n        if domain and domain not in official_domains:\n            official_domains.append(domain)\n    v = verify_url(job.canonical_url, official_domains)\n    if not v.get('active'):\n        return\n"""
t=replace_once(t,old,new,'merged official domains')
t=replace_once(t,"""        job.canonical_url, job.source_url, source.get('official_domains') or [],\n        trusted_listing=(source.get('id') == 'freehire'),\n""","""        job.canonical_url, job.source_url, official_domains,\n        trusted_listing=(source.get('id') == 'freehire'),\n""",'resolver official domains')
write(p,t)

# 4. Agent Reach fallback for government sources blocked from GitHub runners.
p=Path('collector/jobradar/collectors/agent_reach.py');t=read(p)
marker="""DISCOVERY_ONLY_HINTS = (\n"""
if 'GOVERNMENT_DOMAINS = (' not in t:
    idx=t.index(marker)
    const="""GOVERNMENT_DOMAINS = (\n    'tnpsc.gov.in','tamilnaducareerservices.tn.gov.in','keralapsc.gov.in','cmd.kerala.gov.in',\n    'careers-itmission.kerala.gov.in','itmission.kerala.gov.in','tanfinet.tn.gov.in','drdo.gov.in',\n    'isro.gov.in','bel-india.in','cdac.in','careers.cdac.in','nielit.gov.in','recruit-delhi.nielit.gov.in',\n    'rrbchennai.gov.in','bsnl.co.in','ecil.co.in',\n)\n\n"""
    t=t[:idx]+const+t[idx:]
old="""        queries = []\n        for role in roles[:4]:\n            queries.append(f'\"{role}\" {loc} {qualifier} careers apply')\n\n        platforms = self._platform_priority(category)\n        role_expr = ' OR '.join(f'\"{r}\"' for r in roles[:3])\n"""
new="""        role_expr = ' OR '.join(f'\"{r}\"' for r in roles[:3])\n        queries = []\n        if category.type == 'government':\n            # Many official portals rate-limit or block GitHub runner IPs. Exa can still discover\n            # their indexed official vacancies; JobRadar verifies the returned official domain.\n            for i in range(0, len(GOVERNMENT_DOMAINS), 5):\n                domains = ' OR '.join(f'site:{d}' for d in GOVERNMENT_DOMAINS[i:i+5])\n                queries.append(f'({role_expr}) {loc} {qualifier} ({domains}) recruitment careers apply')\n            return [' '.join(q.split()) for q in queries][:12]\n\n        for role in roles[:4]:\n            queries.append(f'\"{role}\" {loc} {qualifier} careers apply')\n\n        platforms = self._platform_priority(category)\n"""
t=replace_once(t,old,new,'government exa queries')
old="""                    platform = _platform_for(url)\n                    host = _host(url)\n                    platform_name = str((platform or {}).get('name') or host or 'Web discovery')\n"""
new="""                    platform = _platform_for(url)\n                    host = _host(url)\n                    official_domain = next((d for d in GOVERNMENT_DOMAINS if host == d or host.endswith('.'+d)), '')\n                    platform_name = str((platform or {}).get('name') or host or 'Web discovery')\n"""
t=replace_once(t,old,new,'official domain detection')
t=replace_once(t,"""                            'source_kind':'community',\n""","""                            'source_kind':'government' if official_domain else 'community',\n                            'official_domains':[official_domain] if official_domain else [],\n""",'official domain metadata')
write(p,t)

# 5. Web API independently filters previously stored scam-like rows and keeps up to ten/category.
p=Path('apps/web/app/api/jobs/route.ts')
write(p,"""import {NextResponse} from 'next/server';\nimport {admin} from '@/lib/supabase';\nimport {getAuthorizedUser} from '@/lib/auth';\nimport {assessJobTrust} from '@/lib/job-trust';\n\nconst PER_CATEGORY_TARGET=10;\nexport async function GET(req:Request){\n  const auth=await getAuthorizedUser();if(auth.status!==200)return NextResponse.json({error:'Unauthorized'},{status:auth.status});\n  const u=new URL(req.url);const cat=u.searchParams.get('category_id');\n  let q=admin().from('job_matches').select('*,category:categories(id,name,slug,type,alert_threshold,fresher_only),job:jobs(*)').eq('eligible',true).order('score',{ascending:false}).limit(cat?200:1200);\n  if(cat)q=q.eq('category_id',cat);\n  const {data,error}=await q;if(error)return NextResponse.json({error:error.message},{status:500});\n  const live=(data||[]).flatMap((m:any)=>{\n    if(m.job?.active===false||m.job?.application_status==='closed')return [];\n    const trust=assessJobTrust(m.job,m.category?.type||'');\n    if(trust.blocked||trust.score<55)return [];\n    return [{...m,job:{...m.job,trust_score:trust.score,trust_reasons:trust.reasons}}];\n  });\n  if(cat)return NextResponse.json(live.slice(0,50));\n  const grouped=new Map<string,any[]>();\n  for(const row of live){const key=String(row.category_id||row.category?.id||'uncategorized');const bucket=grouped.get(key)||[];if(bucket.length<PER_CATEGORY_TARGET)bucket.push(row);grouped.set(key,bucket)}\n  const balanced=Array.from(grouped.values()).flat();balanced.sort((a:any,b:any)=>Number(b.score||0)-Number(a.score||0));return NextResponse.json(balanced);\n}\n""")

# 6. Mount Resume Studio globally.
p=Path('apps/web/app/layout.tsx');t=read(p)
t=replace_once(t,"import './mobile-v10.css';\n","import './mobile-v10.css';\nimport './resume-studio-v10.css';\n",'resume studio css')
t=replace_once(t,"import DashboardUX from './dashboard-ux';\n","import DashboardUX from './dashboard-ux';\nimport ResumeStudioEnhancer from './resume-studio-enhancer';\n",'resume studio component')
t=replace_once(t,'<body>{children}<DashboardUX/></body>','<body>{children}<DashboardUX/><ResumeStudioEnhancer/></body>','resume studio mount')
write(p,t)

# 7. Add DOCX generator dependency.
p=Path('apps/web/package.json');pkg=json.loads(read(p));pkg.setdefault('dependencies',{})['docx']='^9.7.1';write(p,json.dumps(pkg,indent=2)+'\n')

# 8. Research workflow: broader dashboard floor + actual ntfy digest after research.
p=Path('.github/workflows/research.yml');t=read(p)
t=t.replace("DASHBOARD_MIN_SCORE: ${{ vars.DASHBOARD_MIN_SCORE }}","DASHBOARD_MIN_SCORE: ${{ vars.DASHBOARD_MIN_SCORE || '40' }}")
if 'Send real-job ntfy digest' not in t:
    t += """\n      - name: Send real-job ntfy digest\n        working-directory: collector\n        env:\n          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}\n          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}\n          NTFY_SERVER: ${{ vars.NTFY_SERVER }}\n          NTFY_TOPIC: ${{ secrets.NTFY_TOPIC }}\n        run: python -m jobradar.digest --limit 10\n"""
write(p,t)

# 9. Regression tests for category isolation.
p=Path('collector/tests/test_category_isolation.py')
write(p,"""from jobradar.models import Category\nfrom jobradar.resume_match import apply_candidate_to_categories\n\ndef category(name,slug,keywords):\n    return Category(id=slug,name=name,slug=slug,type='custom',role_keywords=keywords,hidden_keywords=[],exclude_keywords=[],locations=['Chennai'])\n\ndef test_profile_roles_do_not_contaminate_existing_categories():\n    cats=[category('Software developer','software',['software developer','frontend developer']),category('SOC','soc',['soc analyst'])]\n    candidate={'preferences':{'locations':['Chennai'],'target_roles':['SOC Analyst'],'excluded_terms':[]},'resume':{'target_roles':['Network Engineer'],'skills':['SIEM','CCNA'],'parsed_json':{}}}\n    out=apply_candidate_to_categories(cats,candidate)\n    assert 'SOC Analyst' not in out[0].role_keywords\n    assert 'Network Engineer' not in out[0].role_keywords\n    assert out[0].role_keywords==['software developer','frontend developer']\n    assert out[1].role_keywords==['soc analyst']\n\ndef test_empty_custom_category_can_fallback_to_profile_roles():\n    cats=[category('My jobs','mine',[])]\n    candidate={'preferences':{'locations':['Kerala'],'target_roles':['Cloud Support Engineer'],'excluded_terms':[]},'resume':{'target_roles':[],'skills':[],'parsed_json':{}}}\n    out=apply_candidate_to_categories(cats,candidate)\n    assert 'Cloud Support Engineer' in out[0].role_keywords\n""")

# 10. Documentation.
p=Path('README.md');t=read(p)
marker='## JobRadar Everywhere v1.0 — Trust + Resume Studio'
if marker not in t:
    t += r'''\n\n---\n\n## JobRadar Everywhere v1.0 — Trust + Resume Studio\n\n### Safer job quality\n\nResearch now separates **discovery** from **trust**. LinkedIn, Naukri, Indeed and dozens of other platforms can surface leads, but JobRadar independently checks role/category relevance, experience, live destinations and common scam indicators before a listing appears. Private listings that ask applicants for deposits/payments or route applications only through WhatsApp/Telegram are blocked. Government application fees on official portals are not treated as scams.\n\n### Category isolation\n\nYour active resume personalizes scoring, but it does **not** rewrite every category. For example, a SOC-heavy resume will no longer cause SOC roles to appear inside a Software Developer category. Categories keep their own target-role definitions.\n\n### Ten-job coverage target\n\nThe dashboard targets the best **10 live, relevant, trustworthy jobs per category** and research scans 70+ discovery/ATS sources. JobRadar will not fabricate a tenth result when trustworthy matching jobs are unavailable; later scheduled runs continue replenishing the category.\n\n### Real-job ntfy digest\n\nAfter each successful research run, ntfy receives a category digest of the current eligible jobs (up to 10/category). High-priority ntfy/Telegram/email alerts still use the stricter configured alert threshold.\n\n### ATS Resume Studio\n\nEvery job can expose:\n\n- **ATS resume** — creates a job-specific draft from the active master resume + job description\n- **What to learn** — identifies JD skills that are not verified in the active resume and links to free learning resources\n- **View source** — opens the original discovery/source page even when a separate Apply button exists\n\nThe **Created resumes** section keeps every generated draft with ATS estimate, edit/preview, DOCX download and job application link. DOCX files use a conservative single-column ATS layout.\n\n### Resume integrity rule\n\nJobRadar never silently claims a skill, employer, certification, project, metric or experience that is missing from the uploaded resume. AI may rewrite/reorder existing evidence for clarity. Missing JD requirements are kept in the learning plan. After learning a skill, add truthful evidence to the master resume and regenerate the job-specific version.\n\n### Open-source design references\n\nThe studio design is inspired by established open-source patterns from **Resume Matcher** (job-description tailoring/ATS feedback) and **Reactive Resume** (multiple-resume editing/export UX). JobRadar uses the MIT-licensed `docx` package for server-side Word export. The code in this repository remains JobRadar-specific rather than embedding an entire external resume platform.\n\n### Migration\n\nRun `supabase/migrations/009_trust_resume_studio.sql` before using Generated Resumes.\n'''
write(p,t)

# Remove staging placeholder.
placeholder=ROOT/'apps/web/app/jobs-api-v10.ts.txt'
if placeholder.exists():placeholder.unlink()

print('JobRadar Everywhere v1.0 patch applied')
