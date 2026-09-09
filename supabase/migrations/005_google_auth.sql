-- Lock dashboard data behind Supabase Auth.
-- GitHub Actions/collector continues to use the service-role key and bypasses RLS.

drop policy if exists "public read categories" on categories;
drop policy if exists "public read jobs" on jobs;
drop policy if exists "public read matches" on job_matches;
drop policy if exists "public read sources" on sources;
drop policy if exists "public read runs" on research_runs;
drop policy if exists "public read notification settings" on notification_settings;

create policy "authenticated read categories" on categories for select to authenticated using (true);
create policy "authenticated read jobs" on jobs for select to authenticated using (true);
create policy "authenticated read matches" on job_matches for select to authenticated using (true);
create policy "authenticated read sources" on sources for select to authenticated using (true);
create policy "authenticated read runs" on research_runs for select to authenticated using (true);
create policy "authenticated read notification settings" on notification_settings for select to authenticated using (true);
