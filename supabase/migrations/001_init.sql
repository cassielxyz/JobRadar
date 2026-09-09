create extension if not exists pgcrypto;

create table if not exists categories (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  slug text not null unique,
  enabled boolean not null default true,
  type text not null check (type in ('government','startup','entry_level','internship','custom')),
  role_keywords text[] not null default '{}',
  hidden_keywords text[] not null default '{}',
  exclude_keywords text[] not null default '{}',
  locations text[] not null default '{}',
  max_experience_years numeric not null default 2,
  salary_min_monthly integer,
  salary_max_monthly integer,
  stipend_min_monthly integer,
  stipend_max_monthly integer,
  require_paid boolean not null default false,
  require_official_verification boolean not null default false,
  source_kinds text[] not null default '{}',
  alert_threshold integer not null default 70 check (alert_threshold between 0 and 100),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists sources (
  id text primary key,
  name text not null,
  kind text not null,
  url text not null,
  enabled boolean not null default true,
  priority integer not null default 50,
  official_domains text[] not null default '{}',
  config jsonb not null default '{}'::jsonb,
  last_ok_at timestamptz,
  last_error text,
  created_at timestamptz not null default now()
);

create table if not exists jobs (
  id uuid primary key default gen_random_uuid(),
  fingerprint text not null unique,
  title text not null,
  company text not null,
  location text,
  description text,
  employment_type text,
  experience_min numeric,
  experience_max numeric,
  salary_min_monthly integer,
  salary_max_monthly integer,
  stipend_monthly integer,
  currency text default 'INR',
  source_id text references sources(id) on delete set null,
  source_url text not null,
  canonical_url text not null,
  official_verified boolean not null default false,
  active boolean not null default true,
  deadline date,
  posted_at timestamptz,
  first_seen_at timestamptz not null default now(),
  last_seen_at timestamptz not null default now(),
  raw jsonb not null default '{}'::jsonb
);

create table if not exists job_matches (
  job_id uuid references jobs(id) on delete cascade,
  category_id uuid references categories(id) on delete cascade,
  score integer not null check (score between 0 and 100),
  reasons text[] not null default '{}',
  eligible boolean not null default true,
  alerted_at timestamptz,
  primary key (job_id, category_id)
);

create table if not exists research_runs (
  id uuid primary key default gen_random_uuid(),
  trigger text not null default 'schedule',
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  status text not null default 'running',
  discovered integer not null default 0,
  verified integer not null default 0,
  matched integer not null default 0,
  alerted integer not null default 0,
  errors jsonb not null default '[]'::jsonb
);

insert into categories (name,slug,type,role_keywords,hidden_keywords,exclude_keywords,locations,max_experience_years,salary_min_monthly,salary_max_monthly,require_official_verification,source_kinds,alert_threshold)
values
('Government / PSU','government-psu','government',
 array['network engineer','network administrator','noc','soc','cyber security','cybersecurity','information security','network security','cloud networking','system administrator','it infrastructure','computer science','information technology'],
 array['scientist','scientific assistant','technical assistant','technical officer','project engineer','signal','telecom','it officer','computer','informatics','digital forensics'],
 array['diploma only','iti only'],
 array['Chennai','Tamil Nadu','Bengaluru','Bangalore','Kerala'],2,20000,27000,true,
 array['government','psu','railway','defence','research','telecom'],70),
('Startup Fresher Jobs','startup-fresher','startup',
 array['network engineer','network support','noc','soc analyst','cybersecurity analyst','security analyst','cloud support','cloud network','infrastructure engineer','network security'],
 array['technical support engineer','security operations','it infrastructure','systems engineer','support engineer'],
 array['senior','lead','manager','5+ years','4+ years','3+ years'],
 array['Chennai','Tamil Nadu','Bengaluru','Bangalore','Kerala'],2,20000,27000,false,
 array['ats','company','community'],72),
('Entry-level Companies','entry-level-companies','entry_level',
 array['network engineer','network administrator','network support','noc engineer','soc analyst','cyber security analyst','cloud support associate','infrastructure engineer','system administrator'],
 array['graduate engineer trainee','associate engineer','technical support','operations engineer','security operations'],
 array['senior','lead','manager','5+ years','4+ years','3+ years'],
 array['Chennai','Tamil Nadu','Bengaluru','Bangalore','Kerala'],2,20000,27000,false,
 array['ats','company','job_board'],70),
('Paid Internships','paid-internships','internship',
 array['cyber security intern','cybersecurity intern','network intern','networking intern','soc intern','cloud intern','cloud networking intern','information security intern'],
 array['security trainee','network trainee','infrastructure intern','it intern'],
 array['unpaid'],
 array['Chennai','Tamil Nadu','Bengaluru','Bangalore','Kerala'],1,null,null,false,
 array['ats','company','job_board','community'],65)
on conflict (slug) do nothing;

update categories set stipend_min_monthly=10000, stipend_max_monthly=20000, require_paid=true where slug='paid-internships';

alter table categories enable row level security;
alter table jobs enable row level security;
alter table job_matches enable row level security;
alter table sources enable row level security;
alter table research_runs enable row level security;

-- Public read-only dashboard policies. All writes use service-role key server-side.
create policy "public read categories" on categories for select using (true);
create policy "public read jobs" on jobs for select using (true);
create policy "public read matches" on job_matches for select using (true);
create policy "public read sources" on sources for select using (true);
create policy "public read runs" on research_runs for select using (true);
