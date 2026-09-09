-- JobRadar Everywhere v0.9
-- Category-level fresher enforcement and encrypted dashboard-managed integrations.

alter table categories
  add column if not exists fresher_only boolean not null default false;

update categories
set fresher_only = true,
    updated_at = now()
where slug in ('startup-fresher','entry-level-companies','paid-internships');

update categories
set fresher_only = false,
    updated_at = now()
where slug = 'government-psu';

create table if not exists integration_settings (
  user_id uuid primary key references auth.users(id) on delete cascade,
  encrypted_payload text not null,
  masked_json jsonb not null default '{}'::jsonb,
  updated_at timestamptz not null default now()
);

alter table integration_settings enable row level security;

-- Intentionally no browser RLS policies: this table contains encrypted secrets and is
-- accessed only by authenticated server routes / service-role collectors.
create index if not exists integration_settings_updated_idx
  on integration_settings(updated_at desc);
