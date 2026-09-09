<p align="center"><img src="assets/readme-hero.svg" alt="JobRadar" width="100%"></p>

# JobRadar

JobRadar is an automated job-discovery and verification workspace designed to collect opportunities, classify them into useful dashboards, and present them through a web application instead of relying on manual daily searches.

The repository combines a Next.js frontend, Supabase-backed application data, scheduled GitHub Actions research, and server routes for jobs, categories, settings, authentication, and controlled research execution.

## Product goals

- Discover relevant openings on a recurring schedule.
- Separate opportunities into focused dashboards rather than one unfiltered feed.
- Preserve source/application links and enough metadata for verification.
- Support authenticated access and user settings.
- Make the research workflow reproducible through automation.

## Architecture

```text
GitHub Actions research workflow
            |
            v
      Research / ingestion
            |
            v
         Supabase
            |
      +-----+------+
      |            |
      v            v
 Next.js API    Auth/session
      |            |
      +-----+------+
            v
       Web dashboard
```

## Repository layout

| Path | Responsibility |
| --- | --- |
| `apps/web/app/` | Next.js routes and UI |
| `apps/web/app/api/jobs/` | Job API surface |
| `apps/web/app/api/categories/` | Dashboard/category API |
| `apps/web/app/api/settings/` | User settings API |
| `apps/web/app/api/run/` | Controlled research execution endpoint |
| `apps/web/lib/` | Authentication and Supabase helpers |
| `.github/workflows/research.yml` | Scheduled/automated research workflow |
| `.github/workflows/test.yml` | CI checks |
| `.env.example` | Safe configuration template |
| `SETUP.md` | Expanded setup instructions |

## Configuration

Copy the example environment file into a local ignored environment file and provide your own development values. Never commit service-role credentials, database passwords, private API tokens, or production authentication secrets.

```bash
cp .env.example .env.local
```

Use GitHub Actions secrets for workflow credentials and the deployment provider's protected environment settings for production values.

## Local development

The web application lives under `apps/web`.

```bash
cd apps/web
npm install
npm run dev
```

Before deployment, run the project's available tests and production build. See `SETUP.md` for the full environment and service configuration.

## Automation

`research.yml` is responsible for recurring research. A healthy automation pipeline should:

1. fetch only from allowed/expected sources;
2. validate and normalize incoming records;
3. deduplicate jobs deterministically;
4. retain official or trustworthy application links;
5. write data using least-privilege credentials;
6. fail visibly when a source changes rather than silently ingesting malformed data.

## Security

- Store secrets only in Supabase, deployment, or GitHub protected secret stores.
- Keep `.env` files local; commit only examples with placeholders.
- Enforce authorization server-side, not only in the UI.
- Treat job descriptions and external HTML as untrusted input.
- Validate URLs before presenting them as application destinations.
- Never expose Supabase service-role keys to browser code.
- Rotate any credential that has ever been committed, even if the current file is later deleted.

## Reliability and data quality

Automation is only useful when stale and duplicate jobs are controlled. Prefer source timestamps, deterministic identifiers, explicit verification status, and scheduled cleanup over heuristic deletion. A failed source should not invalidate unrelated sources in the same research run.

## Project state

The repository already includes web routes, authentication helpers, Supabase integration, GitHub Actions automation, and setup documentation. Future work should continue strengthening verification quality, source coverage, observability, and safe autonomous research rather than replacing the existing architecture with mock data.
