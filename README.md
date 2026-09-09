<p align="center"><img src="assets/readme-hero.svg" alt="JobRadar" width="100%"></p>

# JobRadar

**A personal job-finding workspace that searches for fresher opportunities, checks whether the opening is still real, compares it with your resume, and brings the best matches into one dashboard instead of making you search dozens of portals every day.**

## Why this is useful

Entry-level job hunting is repetitive: the same role can appear under different titles, many listings become stale, official links are hard to find, and a generic job portal rarely understands that roles such as NOC Engineer, Network Support, Infrastructure Support, SOC Analyst, Cloud Support, Network Administrator and Security Operations may all fit the same fresher profile.

JobRadar is designed to reduce that manual work. It is useful for:

- fresh graduates looking for networking, cybersecurity, NOC/SOC, infrastructure and cloud-support roles;
- candidates who want South India opportunities prioritized while still allowing broader discovery;
- tracking government/PSU, startup, entry-level company and paid internship openings in one place;
- comparing job requirements with an active resume instead of relying only on job-title keywords;
- receiving alerts only after a listing is checked for a usable application destination;
- saving interesting jobs and tracking application progress.

## What the user gets

```text
Your resume + preferences
          |
          v
Job discovery from official/company/ATS sources
          |
          v
Check whether the role and application link are still usable
          |
          v
Role relevance + resume-fit scoring
          |
          v
One dashboard
   |        |        |
   v        v        v
save     apply     notify
```

## Resume-driven matching

- Upload PDF, DOCX or TXT resumes from the dashboard.
- Extract resume text, skills, education, certifications and target roles server-side.
- Save multiple resumes and switch the active resume at any time.
- Select preferred locations, target roles, exclusions, experience and salary/stipend targets.
- Sync settings to Supabase.
- Use the active resume and saved preferences to calculate personalized match scores.
- Show resume-fit evidence and skill gaps on verified job cards.
- Save jobs and track applications.
- Queue selected private-sector applications above a configurable confidence threshold.
- Optional auto-submit is limited to recognized Greenhouse, Lever and Ashby forms and stops for CAPTCHA, unknown required fields, or sensitive questions.
- Government/PSU applications remain manual.
- Notifications can use ntfy, Telegram and email.
- Google sign-in plus an authorized-email allowlist protects the dashboard.

## Discovery pipeline

```text
Official portals + ATS/company sources + discovery sources
                              |
                              v
                   Verify liveness/direct links
                              |
                              v
                  Deterministic relevance rules
                              |
                              v
                  Optional AI-assisted review
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

## Starter dashboards

1. Government / PSU
2. Startup Fresher Jobs
3. Entry-level Companies
4. Paid Internships

Custom categories can also be created from the dashboard.

## Repository layout

| Path | Responsibility |
| --- | --- |
| `apps/web/` | Next.js dashboard, authenticated API routes, resume management and settings |
| `collector/` | Discovery, verification, scoring, review, notifications and safe auto-apply runner |
| `config/sources.yaml` | Official and discovery source registry |
| `supabase/migrations/` | Database, auth, precision, resume/preferences and application tracking schema |
| `.github/workflows/research.yml` | Scheduled research and notification workflow |
| `.github/workflows/auto-apply.yml` | Optional application queue processor |
| `.github/workflows/test.yml` | CI tests |
| `SETUP.md` | Full deployment and configuration instructions |

## Safety rules around applications

JobRadar should assist with repetitive steps without pretending to know answers the applicant must personally provide.

- CAPTCHA is never bypassed.
- Unknown required fields stop automation.
- Sensitive questions should require the user.
- Government/PSU applications remain manual.
- The system should not fabricate qualifications, experience or eligibility answers.
- A discovered community/social link is not treated as the final trusted application destination without verification.

## Security

- Store secrets only in Supabase, Vercel or GitHub protected secret stores.
- Keep `.env` files local; commit only examples with placeholders.
- Never expose the Supabase service-role key or GitHub dispatch token to browser code.
- Enforce authorization server-side, not only in the UI.
- Treat job descriptions and external HTML as untrusted input.
- Verify application URLs before presenting or alerting them.
- Rotate any credential that has ever been committed.

## Local development

```bash
cd apps/web
npm install
npm run dev
```

See `SETUP.md` for Supabase migrations, Google OAuth, Vercel variables, GitHub Actions secrets/variables, resume setup, notification tests and the first research run.

## Topics and tags

`job-search` · `job-aggregator` · `career-tools` · `fresher-jobs` · `cybersecurity-jobs` · `network-engineering-jobs` · `south-india-jobs` · `job-matching` · `resume-matching` · `nextjs` · `supabase` · `github-actions` · `job-alerts` · `ats`

## Suggested GitHub About description

> Resume-aware fresher job dashboard that discovers, verifies and ranks networking, cybersecurity, NOC/SOC, infrastructure and related opportunities, with South India as the primary focus.

<p align="center"><sub>Built to reduce repeated job searching and surface opportunities that are actually worth opening.</sub></p>
