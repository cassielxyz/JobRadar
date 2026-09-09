# Build status

## Implemented
- Config-driven research categories
- Four seeded job categories
- Government/PSU source registry
- Greenhouse + Lever collectors
- Optional Agent Reach installation
- URL verification and direct-apply resolver
- Separate government notification URL
- Salary/experience extraction without guessing
- Deduplication and scoring
- ntfy + Telegram + Email alert adapters
- Supabase-backed dashboard
- Dual AI review: Gemini + GitHub Copilot CLI
- AI modes: auto / both / gemini / copilot / rules
- Prompt-injection-resistant classification prompt (job text treated as untrusted data)
- Bounded AI score adjustments; hard source/eligibility checks remain authoritative
- Dashboard AI provider/confidence badge
- **Google OAuth sign-in through Supabase Auth**
- **Email allowlist authorization via `AUTHORIZED_EMAILS`**
- **Protected dashboard pages and protected API routes**
- **Anonymous database read policies removed by migration 005**
- Logout and unauthorized-account screen

## Validation
Python unit tests cover scoring, apply-link resolution and AI JSON/consensus behavior.

The web app uses Next.js 14 + `@supabase/ssr`. Validate a production build with `npm install && npm run build` in `apps/web` or via Vercel. Google OAuth also requires the Supabase/Google redirect URLs described in `SETUP.md`.
