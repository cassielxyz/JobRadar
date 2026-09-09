# JobRadar South  [![Job research](https://github.com/cassielxyz/JobRadar/actions/workflows/research.yml/badge.svg)](https://github.com/cassielxyz/JobRadar/actions/workflows/research.yml)

A free-first automated South India job research dashboard for fresher cybersecurity, networking and cloud-networking opportunities.

## Included
- Four seeded categories: Government/PSU, Startup Fresher, Entry-level Companies, Paid Internships
- Unlimited dashboard-created categories
- Government/PSU + ATS/company + optional Agent Reach discovery
- direct-apply-link resolution and official-notification separation
- deterministic scoring + Gemini + GitHub Copilot review
- Supabase persistence
- GitHub Actions scheduled research
- professional responsive Next.js dashboard
- **Google sign-in with an owner email allowlist**
- free notification stack: **ntfy + Telegram + Email only**

## Dashboard access
Run locally from `apps/web` or deploy that folder to Vercel. The dashboard now opens on a Google sign-in screen and only emails listed in `AUTHORIZED_EMAILS` can enter. Full instructions are in `SETUP.md`.

## Current migrations
Run `001_init.sql`, `002_direct_apply_links.sql`, `003_ai_review.sql`, `004_notification_settings.sql`, and `005_google_auth.sql` in order.

## Security model
- Supabase service-role credentials remain server-only.
- Browser authentication uses the Supabase publishable/anon key.
- Dashboard pages and API routes require a valid Supabase Google session.
- An authenticated Google account must also be present in `AUTHORIZED_EMAILS`.
- Migration 005 removes anonymous read policies from dashboard data.
- GitHub Actions continues to use the service-role key for collector writes.

## Verification principle
Community/social sources are discovery inputs. Government alerts require official verification when configured, and high-priority alerts require a verified direct application URL. Compensation is never invented when it is not disclosed.
