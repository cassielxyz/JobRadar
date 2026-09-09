alter table jobs add column if not exists apply_url text;
alter table jobs add column if not exists notification_url text;
alter table jobs add column if not exists apply_verified boolean not null default false;
alter table jobs add column if not exists link_confidence integer not null default 0 check (link_confidence between 0 and 100);
create index if not exists jobs_apply_verified_idx on jobs (apply_verified, active);
