# AG Scorer — setup

## 1. Requirements

- Python 3.10 or newer
- A modern browser (Chrome, Edge, Firefox or Safari)

## 2. Start on Windows

Open PowerShell in the project folder:

```powershell
cd backend
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Alternatively, run `start_web.bat` from the project root.

## 3. Start on macOS / Linux

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Alternatively, run `./start_web.sh` from the project root.

## 4. Open AG Scorer

Visit **http://127.0.0.1:8000**. The web interface and API are served from the same FastAPI process. Do not open `index.html` directly from the file system.

Demo data is disabled by default. For local testing only, set `SEED_DEMO=true` before starting the server to create `demo@agscorer.app` / `agscorer123`. Never enable demo seeding on a public deployment.

## 5. Shared player

1. Open **Players → Add shared player**.
2. Select a home roster and enter the player's details.
3. The shared player appears in every team selector for the same account.
4. During match setup, select that same profile from either team's player picker.

A shared player has one database identity. Stats from the player's appearances are combined under that profile.

## 6. Single-batter mode

Enable **Single-batter mode** in match setup. The lineup asks for one solo batter and an opening bowler, with no non-striker field. Odd runs and completed overs do not rotate strike. When the solo batter is dismissed, choose the incoming batter for the only batting position. The setting also applies to the second innings.

## 7. MVP rankings and scorecard PDF

- Select **MVP rankings** in the main navigation for an account-wide player leaderboard.
- Points: 1 per run, +1 per four, +2 per six and +20 per bowler-credited wicket. Fielding points are not included.
- Open a match → **Scorecard** → **Export scorecard PDF**. In the browser print dialog, choose **Save as PDF**. The export includes an AG SCORER watermark and “Made With Love By Amber Gupta” footer.

## 8. Install as an app (PWA)

- Android / desktop: use the browser's **Install app** option.
- iPhone / iPad: open in Safari → Share → **Add to Home Screen**.

The service worker caches the static interface shell. Login, match data and ball-by-ball scoring still require internet; offline write synchronization is not included.

## 9. Verify the backend

```bash
cd backend
python -m pytest -q
```

API docs: `/docs` · Health check: `/health`.

## 10. Production checklist

Use a strong unique JWT secret, disable demo seeding, use managed PostgreSQL over HTTPS/WSS, restrict CORS, configure backups, and add rate limiting, account recovery, email verification, security headers, audit logs and privacy/data-deletion information before a public launch.
