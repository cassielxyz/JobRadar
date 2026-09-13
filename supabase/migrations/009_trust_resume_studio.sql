-- JobRadar Everywhere v1.0
-- Truthful job-specific resume studio + learning plans + government discovery fallback.

create table if not exists generated_resumes (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  job_id uuid not null references jobs(id) on delete cascade,
  base_resume_id uuid not null references resumes(id) on delete cascade,
  title text not null,
  content_json jsonb not null default '{}'::jsonb,
  learning_plan jsonb not null default '[]'::jsonb,
  ats_score integer not null default 0 check (ats_score between 0 and 100),
  provider text not null default 'rules',
  status text not null default 'draft' check (status in ('draft','edited','used','archived')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, job_id, base_resume_id)
);
create index if not exists generated_resumes_user_updated_idx on generated_resumes(user_id, updated_at desc);
alter table generated_resumes enable row level security;
do $$ begin
  create policy "users read own generated resumes" on generated_resumes for select to authenticated using (auth.uid()=user_id);
exception when duplicate_object then null; end $$;

-- Government sites occasionally block GitHub-hosted runners. Allow the web-discovery fallback;
-- government categories still require official-domain verification before eligibility.
update categories
set source_kinds = case when not ('community'=any(source_kinds)) then array_append(source_kinds,'community') else source_kinds end,
    updated_at = now()
where type='government' or slug='government-psu';
