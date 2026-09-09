create table if not exists notification_settings (
  id text primary key default 'default',
  ntfy_enabled boolean not null default true,
  telegram_enabled boolean not null default true,
  email_enabled boolean not null default true,
  minimum_score integer not null default 70 check (minimum_score between 0 and 100),
  quiet_hours_enabled boolean not null default false,
  quiet_start time default '23:00',
  quiet_end time default '07:00',
  updated_at timestamptz not null default now()
);
insert into notification_settings(id) values ('default') on conflict (id) do nothing;
alter table notification_settings enable row level security;
create policy "public read notification settings" on notification_settings for select using (true);
