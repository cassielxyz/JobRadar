-- JobRadar South v0.7
-- Resume-driven matching, synced preferences, saved/application tracking and safe auto-apply queue.

create table if not exists resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  name text not null,
  original_filename text not null,
  storage_path text not null unique,
  mime_type text not null,
  size_bytes integer not null check (size_bytes > 0),
  raw_text text not null default '',
  parsed_json jsonb not null default '{}'::jsonb,
  skills text[] not null default '{}',
  target_roles text[] not null default '{}',
  certifications text[] not null default '{}',
  education text[] not null default '{}',
  experience_years numeric,
  is_active boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create unique index if not exists one_active_resume_per_user
  on resumes(user_id) where is_active = true;
create index if not exists resumes_user_created_idx on resumes(user_id, created_at desc);

create table if not exists candidate_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  active_resume_id uuid references resumes(id) on delete set null,
  locations text[] not null default array['Chennai','Tamil Nadu','Bengaluru','Kerala'],
  target_roles text[] not null default array['network engineer','cybersecurity analyst','soc analyst','noc engineer','cloud support engineer','network security engineer'],
  excluded_terms text[] not null default array['senior','lead','principal','manager','architect'],
  max_experience_years numeric not null default 2,
  salary_min_monthly integer default 20000,
  salary_target_monthly integer default 27000,
  stipend_min_monthly integer default 10000,
  stipend_target_monthly integer default 20000,
  allow_remote boolean not null default true,
  allow_hybrid boolean not null default true,
  auto_apply_enabled boolean not null default false,
  auto_submit_enabled boolean not null default false,
  auto_apply_threshold integer not null default 95 check (auto_apply_threshold between 80 and 100),
  application_answers jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table job_matches
  add column if not exists rule_score integer check (rule_score between 0 and 100),
  add column if not exists resume_score integer check (resume_score between 0 and 100),
  add column if not exists resume_id uuid references resumes(id) on delete set null,
  add column if not exists resume_reasons text[] not null default '{}',
  add column if not exists skill_gaps text[] not null default '{}';

create table if not exists saved_jobs (
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid not null references jobs(id) on delete cascade,
  created_at timestamptz not null default now(),
  primary key (user_id, job_id)
);

create table if not exists applications (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid not null references jobs(id) on delete cascade,
  resume_id uuid references resumes(id) on delete set null,
  status text not null default 'saved' check (status in ('saved','queued','review_required','submitted','applied_manual','interview','offer','rejected','withdrawn','failed','skipped')),
  method text not null default 'manual' check (method in ('manual','assisted','auto')),
  score integer,
  apply_url text,
  details jsonb not null default '{}'::jsonb,
  submitted_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, job_id)
);
create index if not exists applications_user_status_idx on applications(user_id, status, updated_at desc);

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('resumes','resumes',false,10485760,array['application/pdf','application/vnd.openxmlformats-officedocument.wordprocessingml.document','text/plain'])
on conflict (id) do update set
  public=false,
  file_size_limit=10485760,
  allowed_mime_types=excluded.allowed_mime_types;

alter table resumes enable row level security;
alter table candidate_preferences enable row level security;
alter table saved_jobs enable row level security;
alter table applications enable row level security;

do $$ begin
  create policy "users read own resumes" on resumes for select to authenticated using (auth.uid() = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "users read own preferences" on candidate_preferences for select to authenticated using (auth.uid() = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "users read own saved jobs" on saved_jobs for select to authenticated using (auth.uid() = user_id);
exception when duplicate_object then null; end $$;
do $$ begin
  create policy "users read own applications" on applications for select to authenticated using (auth.uid() = user_id);
exception when duplicate_object then null; end $$;
