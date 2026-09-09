<p align="center"><img src="assets/readme-hero.svg" alt="JobRadar" width="100%"></p>

# JobRadar

JobRadar is a private, resume-driven job discovery and verification workspace for fresher networking, cybersecurity, cloud networking, NOC/SOC, network support and closely related infrastructure opportunities, with South India as the primary search region.

[![Job research](https://github.com/cassielxyz/JobRadar/actions/workflows/research.yml/badge.svg)](https://github.com/cassielxyz/JobRadar/actions/workflows/research.yml)

## v0.7 — Resume-driven matching

- Upload PDF, DOCX or TXT resumes from the dashboard.
- Extract resume text, skills, education, certifications and target roles server-side.
- Save multiple resumes and switch the active resume at any time.
- Select preferred locations, target roles, exclusions, experience and salary/stipend targets.
- Sync settings to Supabase with a single Save changes action.
- Use the active resume and saved preferences to expand discovery and calculate personalized match scores.
- Show resume-fit evidence and skill gaps on verified job cards.
- Save jobs and track applications.
- Queue private-sector applications above a configurable high-confidence threshold (default 95%).
- Optional safe auto-submit is limited to recognized Greenhouse, Lever and Ashby forms and stops for CAPTCHA, unknown required fields, or sensitive questions.
- Government/PSU applications are always manual.
- Notifications use ntfy, Telegram and email.
- Google sign-in plus an authorized-email allowlist protects the dashboard.

## Discovery pipeline

```text
Official portals + ATS/company sources + FreeHire + optional Agent Reach/Exa
                              |
                              v
                   Verify liveness/direct links
                              |
                              v
                  Deterministic relevance rules
                              |
                              v
                   Gemini / Copilot review
                              |
                              v
                 Active-resume personalized score
                              |
                              v
                         Supabase
                    /       |       \
                   v        v        v
             Web dashboard ntfy  Telegram/Email
```

## Starter categories

1. Government / PSU
2. Startup Fresher Jobs
3. Entry-level Companies
4. Paid Internships

Custom categories can also be created from the dashboard.

## Repository layout

| Path | Responsibility |
| --- | --- |
| `apps/web/` | Next.js dashboard, Google-authenticated API routes, resume management and settings |
| `collector/` | Discovery, verification, scoring, AI review, notifications and safe auto-apply runner |
| `config/sources.yaml` | Official and discovery source registry |
| `supabase/migrations/` | Database, auth, precision, resume/preferences and application tracking schema |
| `.github/workflows/research.yml` | Scheduled research and notification test workflow |
| `.github/workflows/auto-apply.yml` | Optional safe application queue processor |
| `.github/workflows/test.yml` | CI tests |
| `SETUP.md` | Full deployment and configuration instructions |

## Upgrade from v0.6

If migrations 001–006 are already applied, run only:

```text
supabase/migrations/007_resume_preferences_auto_apply.sql
```

If migration 006 has not been applied yet, run 006 first and then 007.

Keep the GitHub repository variable `AUTO_APPLY_RUNNER_ENABLED=false` until the active resume and match quality have been reviewed. Final auto-submit is also separately opt-in from the dashboard.

## Security

- Store secrets only in Supabase, Vercel or GitHub protected secret stores.
- Keep `.env` files local; commit only examples with placeholders.
- Never expose the Supabase service-role key or GitHub dispatch token to browser code.
- Enforce authorization server-side, not only in the UI.
- Treat job descriptions and external HTML as untrusted input.
- Community/social sources are discovery inputs, not trusted final application destinations.
- Verify application URLs before presenting or alerting them.
- Auto-apply never attempts to bypass CAPTCHA or invent answers to unknown/sensitive questions.
- Rotate any credential that has ever been committed, even if the current file is later deleted.

## Local development

```bash
cd apps/web
npm install
npm run dev
```

See `SETUP.md` for Supabase migrations, Google OAuth, Vercel variables, GitHub Actions secrets/variables, resume setup, notification tests and the first resume-driven research run.
