# AG Scorer — minimal cricket scoring PWA

**Version:** 1.3.0

AG Scorer is a mobile-first cricket scoring web app that can be installed on Android, iPhone and desktop as a Progressive Web App (PWA). Its interface is designed around a fast match setup and a focused live scorer.

## Main features

- Email/password registration and login
- Teams, player directory and tournaments
- Ball-by-ball scoring for runs, wickets, wides, no-balls, byes and leg-byes
- Live match view, current over, batting and bowling scorecards, undo and WebSocket updates
- Shared player profile: one player identity can be selected from either team's player picker in the same match; career statistics remain on that one profile
- **Single-batter mode:** create a match with one batter at the crease and no non-striker; odd runs and over changes do not rotate strike; the setting continues into the second innings
- MVP rankings across saved matches, combining a shared player profile into one leaderboard entry
- Printable scorecard PDF export with an AG Scorer watermark and “Made With Love By Amber Gupta” footer
- Installable PWA with app icon and cached application shell
- Responsive mobile and desktop layouts

## Project structure

```text
AG_Scorer_Web/
├── backend/
│   ├── app/main.py
│   ├── tests/test_api.py
│   ├── requirements.txt
│   └── .env.example
├── web/
│   ├── index.html
│   ├── manifest.webmanifest
│   ├── sw.js
│   ├── icons/
│   └── assets/
├── docs/SETUP.md
├── render.yaml
├── start_web.bat
└── start_web.sh
```

## Run locally (Windows)

Open PowerShell in the project folder:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Then open `http://127.0.0.1:8000`. See `docs/SETUP.md` for macOS/Linux and test instructions.

Demo data is disabled by default. For local testing only, set `SEED_DEMO=true` before starting the server to create the sample account (`demo@agscorer.app` / `agscorer123`). Do not enable demo seeding on a public deployment.

## Shared player

Go to **Players → Add shared player**. A shared player is created once and appears in the player selector for each team owned by the same account. During match setup, the same shared identity is selectable from either side's lineup picker. It is not duplicated, so statistics are accumulated on the same player profile.

## MVP rankings

Open **MVP rankings** from the main navigation to see the account-wide player leaderboard across saved matches. The default points formula is 1 point per run, +1 bonus per four, +2 bonus per six and +20 points per bowler-credited wicket. A shared player is ranked as one identity. Fielding points are not included because catches and run-outs are not currently recorded as separate scoring events.

## Scorecard PDF

Open a match, choose **Scorecard**, then select **Export scorecard PDF**. The browser opens a print-ready scorecard; choose **Save as PDF** in the print dialog. Each PDF page carries an AG SCORER watermark and the footer “Made With Love By Amber Gupta”.

## Single-batter mode

While creating a match, enable **Single-batter mode**. Select one solo batter and an opening bowler; no non-striker is requested or displayed. Runs and over completion do not change the batter on strike. After a wicket, choose the incoming batter who occupies the solo batting position. This mode is retained for the second innings.

## PWA installation

- **Android / desktop Chrome or Edge:** open the hosted URL and use the browser's Install app option (or the install icon in the address bar).
- **iPhone / iPad:** open the hosted URL in Safari, tap Share, then choose Add to Home Screen.

The service worker caches the static app shell. **Ball-by-ball scoring and account data still require an internet connection**; offline score synchronization is not included in this release.

## API / tests

- Health: `/health`
- API docs: `/docs`
- Tests: `cd backend && python -m pytest -q`

## Deployment

The root `render.yaml` defines a Render web service and a top-level PostgreSQL database resource. Connect the repository through Render → New → Blueprint. The free database plan is for testing and has a limited lifetime; choose a durable paid database before treating match records as permanent.

Before public release, add production-grade rate limiting, account recovery, email verification, security headers, audit logs, data export/deletion and a privacy policy. Use HTTPS, a unique generated JWT secret and database backups.
