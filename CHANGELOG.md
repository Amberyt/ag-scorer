# Changelog

## 1.2.0 — Minimal PWA + solo batter

- Added an installable Progressive Web App manifest, app icons and a service worker for static shell caching.
- Added match-level Single-batter mode with no non-striker field, no odd-run strike rotation and no end-of-over batter swap.
- Preserved shared player identity across both teams' match pickers and across innings.
- Improved scorer layout and touch targets for mobile screens.
- Corrected Render Blueprint PostgreSQL declaration to use the top-level `databases` section.
- Added integration tests for solo scoring and a shared player appearing for both sides in one match.


## 1.3.0 — MVP rankings + branded scorecard PDF

- Added account-wide MVP rankings and per-match MVP rankings based on recorded batting and bowling deliveries.
- Added a transparent MVP points formula: 1 point per run, +1 per four, +2 per six, and +20 per bowler-credited wicket.
- Shared player identities are aggregated as a single player in MVP rankings.
- Added print-ready scorecard PDF export with an AG SCORER watermark and the footer “Made With Love By Amber Gupta”.
- Added the MVP rankings destination to desktop and mobile navigation.
- Added an integration test for match and account-wide MVP rankings.
