# JobRadar South — Setup

## 1. Supabase database
Run these files in **Supabase → SQL Editor** in order:

1. `supabase/migrations/001_init.sql`
2. `supabase/migrations/002_direct_apply_links.sql`
3. `supabase/migrations/003_ai_review.sql`
4. `supabase/migrations/004_notification_settings.sql`
5. `supabase/migrations/005_google_auth.sql`

If you already ran 001–004, run **only `005_google_auth.sql` now**.

Migration 005 removes the old anonymous read policies. The collector still works because GitHub Actions uses the service-role key, while the dashboard requires an authenticated Google session.

### Server-only Supabase values
For GitHub Actions and the Vercel server routes:

- `SUPABASE_URL` — Supabase **Settings → Data API → Project URL / API URL**
- `SUPABASE_SERVICE_ROLE_KEY` — Supabase **Settings → API Keys → Legacy anon, service_role API keys → service_role**

Keep `SUPABASE_SERVICE_ROLE_KEY` private. Never place it in a `NEXT_PUBLIC_` variable, browser code, screenshots, or Git commits.

## 2. Enable Google login in Supabase
JobRadar now uses **Supabase Auth + Google OAuth** instead of the old dashboard admin token.

### A. Create Google OAuth credentials
In Google Cloud Console:

1. Create/select a project.
2. Configure the OAuth consent screen.
3. Create an **OAuth 2.0 Client ID** for a Web application.
4. In Supabase open **Authentication → Providers → Google**.
5. Supabase shows the callback/redirect URL that Google must allow. Add that exact Supabase callback URL to the Google OAuth client's **Authorized redirect URIs**.
6. Copy the Google Client ID and Client Secret into the Supabase Google provider and enable it.

Do not put the Google Client Secret into the JobRadar frontend. Supabase stores/uses it for the provider.

### B. Configure Supabase URL settings
Open **Supabase → Authentication → URL Configuration**.

During local development:

- Site URL: `http://localhost:3000`
- Add redirect URL: `http://localhost:3000/auth/callback`

After Vercel deployment also add:

- `https://YOUR-VERCEL-DOMAIN.vercel.app/auth/callback`

If you later add a custom domain, add its `/auth/callback` URL too.

### C. Browser-safe Supabase values
In **Supabase → Settings → API Keys**, copy the **Publishable key**. This key is designed for browser use and is not the service-role secret.

JobRadar web app needs:

```text
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
AUTHORIZED_EMAILS=your-google-account@gmail.com
```

`AUTHORIZED_EMAILS` is a comma-separated allowlist. Example:

```text
AUTHORIZED_EMAILS=you@gmail.com,second-account@gmail.com
```

Only a Google account whose email appears in this variable can enter the dashboard. Authentication alone is not enough.

For older Supabase projects you may use `NEXT_PUBLIC_SUPABASE_ANON_KEY` instead of `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. The current project checks the publishable key first.

## 3. Gemini + GitHub Copilot
Add GitHub secret:

- `GEMINI_API_KEY`

Recommended repository variables:

- `AI_MODE=auto`
- `AI_REVIEW_MIN_SCORE=45`
- `GEMINI_MODEL=gemini-2.5-flash-lite`
- `AGENT_REACH_ENABLED=true` (optional)

Copilot CLI uses the GitHub Actions token when the account/repository has the required Copilot access. If Copilot is unavailable, Gemini + deterministic rules continue.

## 4. Free notification stack
JobRadar uses only **ntfy + Telegram + Email**.

### ntfy
Install the ntfy mobile app and subscribe to a hard-to-guess topic. Add:

GitHub secret:
- `NTFY_TOPIC`

GitHub variable:
- `NTFY_SERVER=https://ntfy.sh`

Use a random topic rather than your name or phone number.

### Telegram
Create a bot with BotFather, start it once from your Telegram account, obtain your chat ID, and add GitHub secrets:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

### Email (Gmail example)
Enable 2-Step Verification on the sending Google account and create an App Password.

GitHub secrets:
- `SMTP_USERNAME`
- `SMTP_PASSWORD`
- `ALERT_EMAIL_TO`

Repository variables:
- `SMTP_HOST=smtp.gmail.com`
- `SMTP_PORT=587`
- `ALERT_EMAIL_FROM=<sender email>`

All three channels can be enabled together.

## 5. Push to GitHub
Push the complete project to a GitHub repository.

The workflow `.github/workflows/research.yml` runs the collector three times per day and can also be started manually from:

**GitHub → Actions → Job research → Run workflow**

Required GitHub Actions secrets include:

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

Notification secrets are optional individually; configure the channels you want to use.

## 6. Access the dashboard locally
From the project root:

```bash
cd apps/web
npm install
```

Create `apps/web/.env.local`:

```text
SUPABASE_URL=https://YOUR-PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY
NEXT_PUBLIC_SUPABASE_URL=https://YOUR-PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLISHABLE_KEY
AUTHORIZED_EMAILS=your-google-account@gmail.com
```

Then run:

```bash
npm run dev
```

Open:

```text
http://localhost:3000
```

You should see the **Continue with Google** page instead of the dashboard. After login:

- authorized email → dashboard
- other Google email → Access Restricted page
- Sign out → back to login

The previous `DASHBOARD_ADMIN_TOKEN` prompt has been completely removed.

## 7. Deploy the private dashboard to Vercel
1. Import the GitHub repository into Vercel.
2. Set **Root Directory** to `apps/web`.
3. Add these Vercel environment variables:

```text
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
NEXT_PUBLIC_SUPABASE_URL
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY
AUTHORIZED_EMAILS
```

4. Deploy.
5. Copy the final Vercel domain.
6. Return to **Supabase → Authentication → URL Configuration** and add:
   `https://YOUR-VERCEL-DOMAIN.vercel.app/auth/callback`
7. Set the production Site URL to your Vercel/custom domain when ready.
8. Test Google login in a private/incognito browser window.

Optional dashboard-triggered cloud runs use these additional Vercel server variables:

```text
GITHUB_REPOSITORY=owner/repository
GITHUB_DISPATCH_TOKEN=...
```

Scheduled GitHub Actions do not need them.

## 8. What is protected now
The following are protected by a valid Supabase Google session plus your email allowlist:

- dashboard home
- job results
- research categories
- category creation/updates
- notification settings
- manual cloud-run API

The API routes independently verify the session, so bypassing the UI does not grant access.

The database migration also removes anonymous read access from categories, jobs, matches, sources, research runs and notification settings.

## 9. Dashboard behavior
The interface remains professional and icon-based with no decorative emoji. It includes:

- Google account identity and Sign out
- all/current matches
- verified direct Apply button
- separate official government notification link
- match score and AI review confidence
- research category sidebar
- New Category builder
- notification overview for ntfy, Telegram and Email
- responsive phone/desktop layout

## 10. Add research categories
Dashboard → **New category**.

Configure role keywords, adjacent/hidden titles, exclusions, locations, maximum experience, salary/stipend targets, source types and alert threshold. The next scheduled research run automatically scores new discoveries against the category.
