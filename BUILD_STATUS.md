# JobRadar South v0.7 — Build status

## Implemented

- Multiple saved resumes, active-resume switcher and private Supabase Storage bucket.
- PDF/DOCX/TXT server-side text extraction with deterministic profile parsing.
- Optional Gemini enrichment during resume upload.
- Resume skills, certifications, education and target-role extraction.
- Synced candidate preferences: locations, target roles, exclusions, experience, salary/stipend and remote/hybrid preferences.
- Resume-aware research query expansion.
- Personalized resume-fit score + skill-gap display.
- Saved jobs and application tracker.
- Safe auto-apply queue at configurable threshold (default 95%).
- Optional Playwright ATS runner with captcha/unknown-question/sensitive-question review gates.
- Government/PSU auto-submit disabled by design.
- Unified Settings UI with Resumes, Job Preferences, Auto Apply and Notifications tabs.
- Single Save changes action for synced settings.
- Custom radar SVG favicon, product metadata and web-app manifest.
- Existing Google OAuth, verified direct Apply links, FreeHire, Agent Reach, Gemini/Copilot and ntfy/Telegram/Email retained.

## Validation

- Python source compilation: PASS.
- Python collector tests: **20 passed**.
- TypeScript syntax pass: no syntax errors detected with the globally available TypeScript compiler; unresolved-module errors are expected without installed npm dependencies.
- Full `npm install`/Next.js production build could not be completed in this container because dependency installation timed out. Vercel remains the authoritative production build after push.

## Important beta limitation

Generic job-site auto-submit cannot be guaranteed across arbitrary career portals. v0.7 only attempts final submission on recognized ATS hosts and moves anything ambiguous to Review required rather than guessing answers or bypassing anti-bot controls.
