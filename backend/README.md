# AG Scorer backend

FastAPI backend serving the PWA from `../web`. API docs are at `/docs`; health check at `/health`.

Run locally from this directory:

```bash
python -m venv .venv
# Activate the environment, then:
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API supports shared player identities across both teams, live ball-by-ball scoring, scorecards, and match-level single-batter mode. In single-batter mode, the API exposes `non_striker: null` and keeps the active striker unchanged after runs and over completion.

Run tests with `python -m pytest -q`.
