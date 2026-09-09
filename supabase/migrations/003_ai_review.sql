alter table job_matches add column if not exists ai_review jsonb not null default '{}'::jsonb;
