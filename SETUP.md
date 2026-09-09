# JobRadar South v0.7 — Setup

## 1. Supabase migrations

Run in **Supabase → SQL Editor** in order for a new project:

1. `001_init.sql`
2. `002_direct_apply_links.sql`
3. `003_ai_review.sql`
4. `004_notification_settings.sql`
5. `005_google_auth.sql`
6. `006_precision_discovery_notifications.sql`
7. `007_resume_preferences_auto_apply.sql`

If v0.6 is already running, run **only migration 007**.

Migration 007 creates private resume/profile/application data and the private `resumes` Storage bucket. Resume files are not public.

## 2. Vercel dashboard environment

Vercel project root directory: `apps/web`

Required:

```text
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
AUTHORIZED_EMAILS=your-google-email@gmail.com
GITHUB_REPOSITORY=owner/JobRadar
GITHUB_DISPATCH_TOKEN=github_pat_...
```

Optional but recommended for better resume extraction:

```text
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.1-flash-lite
```

Without a Gemini key in Vercel, resume upload still works using deterministic extraction.

Never expose the service-role key or dispatch token using a `NEXT_PUBLIC_` prefix.

## 3. Google login

In **Supabase → Authentication → Sign In / Providers → Google**:

- Enable Google.
- Paste Google OAuth Client ID.
- Paste Google OAuth Client Secret.
- Keep **Skip nonce checks** OFF.
- Keep **Allow users without an email** OFF.

Register the Supabase callback shown there in Google Cloud, e.g.:

`https://YOUR-PROJECT.supabase.co/auth/v1/callback`

In **Supabase → Authentication → URL Configuration**:

- Production Site URL: your Vercel domain.
- Add `https://YOUR-VERCEL-DOMAIN/auth/callback`.
- For local development also allow `http://localhost:3000/auth/callback`.

## 4. GitHub Actions secrets

**Repository → Settings → Secrets and variables → Actions → Secrets**

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
GEMINI_API_KEY
NTFY_TOPIC
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
SMTP_USERNAME
SMTP_PASSWORD
ALERT_EMAIL_TO
```

Notification secrets are optional individually. Configure all three to receive ntfy + Telegram + Email.

## 5. GitHub repository variables

Under **Actions → Variables**:

```text
AI_MODE=auto
AI_REVIEW_MIN_SCORE=45
DASHBOARD_MIN_SCORE=55
GEMINI_MODEL=gemini-3.1-flash-lite
AGENT_REACH_ENABLED=true
NTFY_SERVER=https://ntfy.sh
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
ALERT_EMAIL_FROM=yourgmail@gmail.com
AUTO_APPLY_RUNNER_ENABLED=false
```

Keep `AUTO_APPLY_RUNNER_ENABLED=false` until you have uploaded and reviewed a resume, saved your application profile, and tested the application queue. Change it to `true` only when you want the separate safe auto-apply workflow to run.

## 6. Upload the first resume

Open the Vercel dashboard and sign in with the authorized Google account.

1. **Settings → Resumes**.
2. Upload a text-based PDF, DOCX or TXT resume (max 10 MB).
3. JobRadar extracts the text and shows detected profile details.
4. Add more resumes if useful (for example `Network & NOC`, `SOC & Cybersecurity`, `Cloud Support`).
5. Click **Use this** to switch active resume.

Scanned/image-only PDFs are intentionally rejected when there is too little extractable text. Export the resume as a normal PDF/DOCX instead.

## 7. Save job preferences

Open **Settings → Job preferences**:

- select Chennai, Tamil Nadu, Bengaluru, Kerala, Kochi, Coimbatore, Thiruvananthapuram, Remote, or add custom locations;
- edit target roles and excluded terms;
- set max experience years;
- set desired salary and internship stipend bands;
- choose remote/hybrid options.

Press the global **Save changes** button. The next GitHub research run automatically uses those saved preferences and the active resume.

## 8. Auto apply

Open **Settings → Auto Apply**.

Recommended first setup:

```text
Queue applications automatically: ON
Match threshold: 95
Allow final auto-submit: OFF
```

This means JobRadar may place very strong private-sector matches in the application queue but will not submit anything yet.

Fill the application profile (phone, portfolio/GitHub/LinkedIn if desired, work authorization/sponsorship answers) and **Save changes**.

When you are satisfied with the quality of queued applications:

1. optionally enable **Allow final auto-submit** in the dashboard;
2. set GitHub repository variable `AUTO_APPLY_RUNNER_ENABLED=true`.

The runner currently supports direct form attempts only for recognized Greenhouse, Lever and Ashby pages. Government/PSU jobs, captchas, unknown required questions and required sensitive demographic questions are moved to **Review required**.

## 9. Notifications

JobRadar supports only the free-first stack:

- ntfy
- Telegram
- Email / SMTP

The Notifications settings include a minimum score and a **Send test notifications** action. Normal job alerts require a qualifying new verified match.

## 10. Run research

From the dashboard press **Run research**, or in GitHub:

**Actions → Job research → Run workflow → mode=research**.

Discovery now uses:

- official/seeded portals;
- FreeHire public API for broad company/startup discovery;
- Agent Reach/Exa when enabled;
- active-resume and saved target-role query expansion.

The collector calculates both category relevance and resume fit, then stores the personalized final score.

## 11. Automatic schedules

`research.yml` runs three times per day.

`auto-apply.yml` checks queued applications every three hours, but the job itself runs only when repository variable `AUTO_APPLY_RUNNER_ENABLED=true`.

No PC needs to remain online; both workflows use GitHub-hosted runners.
