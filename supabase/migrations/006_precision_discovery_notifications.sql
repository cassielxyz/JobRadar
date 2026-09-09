-- JobRadar South v0.6
-- Precision fixes, dynamic discovery support, and notification diagnostics.

alter table jobs
  add column if not exists event_type text not null default 'vacancy',
  add column if not exists application_status text not null default 'unknown';

alter table research_runs
  add column if not exists notification_status jsonb not null default '{}'::jsonb;

update categories
set
  role_keywords = array['network engineer','network administrator','network support','noc engineer','noc','soc analyst','cyber security','cybersecurity','security analyst','information security','network security','cloud networking','cloud network','system administrator','it infrastructure'],
  hidden_keywords = array['scientist','scientific assistant','technical assistant','technical officer','project engineer','signal','telecom','it officer','computer','informatics','digital forensics','security operations'],
  exclude_keywords = array['diploma only','iti only','mechanical','civil','chemical','metallurgy','automobile','aerospace'],
  locations = array['Chennai','Tamil Nadu','Bengaluru','Bangalore','Kerala'],
  max_experience_years = 2,
  salary_min_monthly = 20000,
  salary_max_monthly = 27000,
  require_official_verification = true,
  source_kinds = array['government','psu','railway','defence','research','telecom'],
  alert_threshold = 70,
  updated_at = now()
where slug = 'government-psu';

update categories
set
  role_keywords = array['network engineer','network support engineer','noc engineer','soc analyst','cybersecurity analyst','security analyst','cloud support engineer','cloud network engineer','network security engineer','infrastructure engineer'],
  hidden_keywords = array['technical support engineer','security operations','it infrastructure','systems engineer','support engineer'],
  exclude_keywords = array['senior','lead','principal','staff','manager','architect','5+ years','4+ years','3+ years'],
  locations = array['Chennai','Tamil Nadu','Bengaluru','Bangalore','Kerala'],
  max_experience_years = 2,
  salary_min_monthly = 20000,
  salary_max_monthly = 27000,
  source_kinds = array['job_board','ats','company','community'],
  alert_threshold = 72,
  updated_at = now()
where slug = 'startup-fresher';

update categories
set
  role_keywords = array['network engineer','network administrator','network support','noc engineer','soc analyst','cyber security analyst','cybersecurity analyst','cloud support associate','cloud support engineer','infrastructure engineer','system administrator','network security'],
  hidden_keywords = array['graduate engineer trainee','associate engineer','technical support','operations engineer','security operations'],
  exclude_keywords = array['senior','lead','principal','staff','manager','architect','5+ years','4+ years','3+ years'],
  locations = array['Chennai','Tamil Nadu','Bengaluru','Bangalore','Kerala'],
  max_experience_years = 2,
  salary_min_monthly = 20000,
  salary_max_monthly = 27000,
  source_kinds = array['job_board','ats','company','community'],
  alert_threshold = 70,
  updated_at = now()
where slug = 'entry-level-companies';

update categories
set
  role_keywords = array['cyber security intern','cybersecurity intern','network intern','networking intern','soc intern','cloud intern','cloud networking intern','information security intern','network security intern'],
  hidden_keywords = array['security trainee','network trainee','infrastructure intern','it security intern'],
  exclude_keywords = array['unpaid','senior','lead','manager'],
  locations = array['Chennai','Tamil Nadu','Bengaluru','Bangalore','Kerala'],
  max_experience_years = 1,
  stipend_min_monthly = 10000,
  stipend_max_monthly = 20000,
  require_paid = true,
  source_kinds = array['job_board','ats','company','community'],
  alert_threshold = 65,
  updated_at = now()
where slug = 'paid-internships';

update notification_settings
set minimum_score = 65, updated_at = now()
where id = 'default' and minimum_score = 70;

update job_matches set eligible = false;

create index if not exists jobs_event_status_idx on jobs(event_type, application_status, active);
create index if not exists research_runs_started_idx on research_runs(started_at desc);
