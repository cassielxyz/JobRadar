# JobRadar Everywhere — Source Coverage

JobRadar Everywhere uses a **70+ platform discovery catalog** plus direct government/PSU sources and FreeHire aggregation.

The target is **up to 10 live, verified, eligible jobs per category on the dashboard**. The system searches a much larger candidate pool (normally dozens per category) because most candidates are rejected later for experience, location, stale links, closed applications, poor role fit, or an unverifiable destination.

> JobRadar does not invent jobs to fill a quota. If fewer than ten genuinely eligible live jobs exist after all configured searches, the dashboard may temporarily show fewer than ten. Later scheduled runs keep accumulating fresh verified matches until the category is replenished.

## How the source system works

1. **Direct authoritative sources** — government, PSU, research and recruitment portals.
2. **FreeHire discovery** — keyless aggregation across ATS, company career sites and job boards.
3. **Agent Reach / Exa discovery** — public web discovery across the catalog below.
4. **Direct ATS discovery** — Greenhouse, Lever, Ashby, SmartRecruiters, Workday, Workable and others.
5. **Verification** — JobRadar applies category rules, fresher rules, location checks, liveness checks and Apply-link resolution.
6. **Balanced dashboard** — the home feed keeps the best ten live matches from each category rather than allowing one high-volume category to dominate.

Large public job boards such as LinkedIn, Naukri and Indeed are treated as **discovery evidence**, not automatically trusted final Apply destinations. JobRadar prefers resolving the employer or ATS application page before marking a result verified.

## India-first job boards

LinkedIn Jobs, Naukri, Indeed, Foundit, Shine, TimesJobs, Freshersworld, Internshala, Cutshort, Instahyre, Hirist, IIMJobs, Apna, WorkIndia, JobHai, Unstop, Wellfound, Hirect, HerKey, Quikr Jobs, Jooble, Adzuna India, Careerjet India, Jora, Talent.com, GrabJobs, SimplyHired, Jobsora, National Career Service and Glassdoor.

## Startup / global / remote discovery

ZipRecruiter, Dice, Built In, YC Work at a Startup, Startup Jobs, Remote OK, We Work Remotely, Remotive, Himalayas, Jobspresso, Working Nomads, Remote.co, NoDesk, Jobicy, Dynamite Jobs, Arc, Turing, Contra, Upwork, PeoplePerHour and Freelancer.

## Applicant-tracking systems

Greenhouse, Greenhouse Job Boards, Lever, Ashby, SmartRecruiters, Workday, Workable, Recruitee, Personio, Teamtailor, BambooHR, Jobvite, Breezy HR, iCIMS, Taleo, SAP SuccessFactors, Oracle Recruiting, Rippling ATS, Comeet, JazzHR, Pinpoint, Zoho Recruit Career Sites and JobScore.

The machine-readable catalog lives in [`config/discovery_platforms.yaml`](../config/discovery_platforms.yaml), so new discovery targets can be added without rewriting the collector.

## Category target behavior

The landing dashboard requests the best **10 live eligible matches per category**. Research intentionally collects far more than ten candidates per category:

- FreeHire: up to ~70 plausible candidates per category, with a recent pass and a 90-day fallback.
- Agent Reach / Exa: parallel searches across the 70+ platform catalog, up to ~70 plausible candidates per category.
- Direct sources: all currently discoverable relevant postings.

Every candidate still passes the existing strict rules. In a **Fresher-only** category, an explicit requirement such as `2+ years`, `minimum 2 years`, or a senior title remains a hard rejection; the quota never overrides that safety rule.
