# JobRadar Everywhere — Setup

The canonical installation guide now lives in [`README.md`](README.md).

For an existing v0.7/v0.8 installation upgrading to v0.9:

1. Pull the latest `main` branch.
2. Run `supabase/migrations/008_everywhere_categories_integrations.sql` in Supabase SQL Editor.
3. Let Vercel redeploy the latest commit.
4. Open **Settings → Integrations** and optionally move ntfy, Telegram, SMTP, and Gemini credentials into the encrypted dashboard store.
5. Review every category and enable **Fresher-only** only where strict fresher rejection is intended.
6. Run **Notification test**.
7. Run **Job research**.
8. Keep `AUTO_APPLY_RUNNER_ENABLED=false` until you have reviewed the new results.

See the README for full first-time setup, key acquisition links, Google OAuth, GitHub Actions, Vercel, troubleshooting, and security guidance.
