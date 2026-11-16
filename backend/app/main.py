from __future__ import annotations

import base64
from contextlib import asynccontextmanager
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from dotenv import load_dotenv
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, create_engine, inspect, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

load_dotenv()

APP_NAME = "AG Scorer API"
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ag_scorer.db")
JWT_SECRET = os.getenv("JWT_SECRET", "CHANGE_ME_BEFORE_DEPLOYING_AG_SCORER")
TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "72"))

engine_kwargs = {"connect_args": {"check_same_thread": False}} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, future=True, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Team(Base):
    __tablename__ = "teams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    short_name: Mapped[str] = mapped_column(String(12))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    players: Mapped[list[Player]] = relationship(back_populates="team", cascade="all, delete-orphan")


class Player(Base):
    __tablename__ = "players"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(30), default="All-rounder")
    jersey_number: Mapped[int] = mapped_column(Integer, default=0)
    is_common: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    team: Mapped[Team] = relationship(back_populates="players")


class Tournament(Base):
    __tablename__ = "tournaments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(140))
    format: Mapped[str] = mapped_column(String(30), default="League")
    venue: Mapped[str] = mapped_column(String(140), default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class Match(Base):
    __tablename__ = "matches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(160))
    venue: Mapped[str] = mapped_column(String(160), default="")
    match_format: Mapped[str] = mapped_column(String(30), default="T20")
    total_overs: Mapped[int] = mapped_column(Integer, default=20)
    team_a_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    team_b_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    batting_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    bowling_team_id: Mapped[int] = mapped_column(ForeignKey("teams.id"))
    striker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id"), nullable=True)
    non_striker_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id"), nullable=True)
    bowler_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id"), nullable=True)
    innings: Mapped[int] = mapped_column(Integer, default=1)
    single_batter_mode: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="live")
    toss_winner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    toss_decision: Mapped[str] = mapped_column(String(20), default="bat")
    tournament_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tournaments.id"), nullable=True)
    winner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("teams.id"), nullable=True)
    result_text: Mapped[str] = mapped_column(String(240), default="")
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    deliveries: Mapped[list[Delivery]] = relationship(back_populates="match", cascade="all, delete-orphan")


class Delivery(Base):
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), index=True)
    innings: Mapped[int] = mapped_column(Integer)
    sequence: Mapped[int] = mapped_column(Integer)
    over_number: Mapped[int] = mapped_column(Integer)
    ball_number: Mapped[int] = mapped_column(Integer)
    striker_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    non_striker_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    bowler_id: Mapped[int] = mapped_column(ForeignKey("players.id"))
    runs_bat: Mapped[int] = mapped_column(Integer, default=0)
    extra_type: Mapped[str] = mapped_column(String(20), default="")
    extra_runs: Mapped[int] = mapped_column(Integer, default=0)
    running_runs: Mapped[int] = mapped_column(Integer, default=0)
    wicket_type: Mapped[str] = mapped_column(String(30), default="")
    dismissed_player_id: Mapped[Optional[int]] = mapped_column(ForeignKey("players.id"), nullable=True)
    is_legal: Mapped[bool] = mapped_column(Boolean, default=True)
    previous_striker_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    previous_non_striker_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    previous_bowler_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    previous_status: Mapped[str] = mapped_column(String(30), default="live")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    match: Mapped[Match] = relationship(back_populates="deliveries")


Base.metadata.create_all(bind=engine)

# Lightweight forward migration for databases created by earlier AG Scorer versions.
# SQLite and PostgreSQL both accept FALSE as a boolean default.
if "is_common" not in {column["name"] for column in inspect(engine).get_columns("players")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE players ADD COLUMN is_common BOOLEAN NOT NULL DEFAULT FALSE"))

# Add the match-level solo-batter setting without disturbing existing matches.
if "single_batter_mode" not in {column["name"] for column in inspect(engine).get_columns("matches")}:
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE matches ADD COLUMN single_batter_mode BOOLEAN NOT NULL DEFAULT FALSE"))


# ---------- Schemas ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TeamIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    short_name: str = Field(min_length=2, max_length=12)


class PlayerIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    role: str = "All-rounder"
    jersey_number: int = Field(default=0, ge=0, le=999)


class CommonPlayerIn(PlayerIn):
    home_team_id: int


class TournamentIn(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    format: str = "League"
    venue: str = ""


class MatchIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    venue: str = ""
    match_format: str = "T20"
    total_overs: int = Field(default=20, ge=1, le=90)
    team_a_id: int
    team_b_id: int
    toss_winner_id: int
    toss_decision: str = "bat"
    striker_id: int
    non_striker_id: Optional[int] = None
    bowler_id: int
    single_batter_mode: bool = False
    tournament_id: Optional[int] = None


class BallIn(BaseModel):
    runs_bat: int = Field(default=0, ge=0, le=6)
    extra_type: Optional[str] = None
    extra_runs: int = Field(default=0, ge=0, le=10)
    running_runs: int = Field(default=0, ge=0, le=6)
    wicket_type: Optional[str] = None
    dismissed_player_id: Optional[int] = None
    new_batter_id: Optional[int] = None


class BattersIn(BaseModel):
    striker_id: int
    non_striker_id: Optional[int] = None


class BowlerIn(BaseModel):
    bowler_id: int


class NextInningsIn(BaseModel):
    striker_id: int
    non_striker_id: Optional[int] = None
    bowler_id: int


class CompleteIn(BaseModel):
    winner_id: Optional[int] = None
    result_text: str = "Match completed"


# ---------- Helpers ----------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str, salt: Optional[str] = None) -> str:
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 240_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, digest = stored.split("$", 2)
        return hmac.compare_digest(hash_password(password, salt).split("$", 2)[2], digest)
    except (ValueError, AttributeError):
        return False


def b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def issue_token(user_id: int) -> str:
    now = datetime.now(timezone.utc)
    header = b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = {"sub": str(user_id), "iat": int(now.timestamp()), "exp": int((now + timedelta(hours=TOKEN_TTL_HOURS)).timestamp())}
    body = b64(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header}.{body}"
    signature = b64(hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
    return f"{signing_input}.{signature}"


def decode_token(token: str) -> int:
    try:
        header, body, signature = token.split(".", 2)
        signing_input = f"{header}.{body}"
        expected = b64(hmac.new(JWT_SECRET.encode(), signing_input.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("Bad signature")
        header_data = json.loads(base64.urlsafe_b64decode(header + "=" * (-len(header) % 4)))
        if header_data.get("alg") != "HS256":
            raise ValueError("Unsupported algorithm")
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(payload["exp"]) < int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("Expired token")
        return int(payload["sub"])
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)) -> User:
    if not credentials:
        raise HTTPException(status_code=401, detail="Sign in required")
    user_id = decode_token(credentials.credentials)
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    return user


def player_in_team(db: Session, player_id: int, team_id: int, owner_id: int | None = None) -> bool:
    """A common player has one identity and may be selected for any team owned by the same user."""
    player = db.get(Player, player_id)
    if not player:
        return False
    if player.team_id == team_id:
        return True
    if not player.is_common or owner_id is None:
        return False
    home_team = db.get(Team, player.team_id)
    selected_team = db.get(Team, team_id)
    return bool(home_team and selected_team and home_team.owner_id == owner_id == selected_team.owner_id)


def team_for_user(db: Session, team_id: int, user_id: int) -> Team:
    team = db.get(Team, team_id)
    if not team or team.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Team not found")
    return team


def match_for_user(db: Session, match_id: int, user_id: int) -> Match:
    match = db.get(Match, match_id)
    if not match or match.owner_id != user_id:
        raise HTTPException(status_code=404, detail="Match not found")
    return match


def deliveries_for(db: Session, match_id: int, innings: int) -> list[Delivery]:
    return list(db.scalars(select(Delivery).where(Delivery.match_id == match_id, Delivery.innings == innings).order_by(Delivery.sequence)))


def innings_score(db: Session, match: Match, innings: int) -> dict:
    deliveries = deliveries_for(db, match.id, innings)
    runs = sum(d.runs_bat + d.extra_runs for d in deliveries)
    wickets = sum(1 for d in deliveries if d.wicket_type)
    legal_balls = sum(1 for d in deliveries if d.is_legal)
    overs = f"{legal_balls // 6}.{legal_balls % 6}"
    extras = sum(d.extra_runs for d in deliveries)
    batting: dict[int, dict] = {}
    bowling: dict[int, dict] = {}
    for d in deliveries:
        bat = batting.setdefault(d.striker_id, {"player_id": d.striker_id, "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissal": "not out"})
        bat["runs"] += d.runs_bat
        if d.extra_type != "wide":
            bat["balls"] += 1
        if d.runs_bat == 4:
            bat["fours"] += 1
        if d.runs_bat == 6:
            bat["sixes"] += 1
        if d.dismissed_player_id is not None:
            dismissed_row = batting.setdefault(d.dismissed_player_id, {"player_id": d.dismissed_player_id, "runs": 0, "balls": 0, "fours": 0, "sixes": 0, "dismissal": "not out"})
            dismissed_row["dismissal"] = d.wicket_type
        bowl = bowling.setdefault(d.bowler_id, {"player_id": d.bowler_id, "runs": 0, "balls": 0, "wickets": 0, "maidens": 0})
        bowl["runs"] += d.runs_bat + d.extra_runs - (d.extra_runs if d.extra_type in ("bye", "leg_bye", "penalty") else 0)
        if d.is_legal:
            bowl["balls"] += 1
        if d.wicket_type and d.wicket_type not in ("run_out", "retired_hurt", "obstructing_field"):
            bowl["wickets"] += 1
    team_batting_rows = []
    for player_id, row in batting.items():
        p = db.get(Player, player_id)
        row["name"] = p.name if p else f"Player {player_id}"
        row["strike_rate"] = round(row["runs"] * 100 / row["balls"], 2) if row["balls"] else 0
        team_batting_rows.append(row)
    team_bowling_rows = []
    for player_id, row in bowling.items():
        p = db.get(Player, player_id)
        row["name"] = p.name if p else f"Player {player_id}"
        row["overs"] = f"{row['balls'] // 6}.{row['balls'] % 6}"
        row["economy"] = round(row["runs"] * 6 / row["balls"], 2) if row["balls"] else 0
        team_bowling_rows.append(row)
    return {
        "innings": innings, "runs": runs, "wickets": wickets, "overs": overs,
        "legal_balls": legal_balls, "extras": extras, "batting": team_batting_rows,
        "bowling": team_bowling_rows,
    }


def match_payload(db: Session, match: Match) -> dict:
    team_a, team_b = db.get(Team, match.team_a_id), db.get(Team, match.team_b_id)
    batting_team, bowling_team = db.get(Team, match.batting_team_id), db.get(Team, match.bowling_team_id)
    all_deliveries = list(db.scalars(select(Delivery).where(Delivery.match_id == match.id).order_by(Delivery.sequence)))
    current = innings_score(db, match, match.innings)
    first = innings_score(db, match, 1)
    second = innings_score(db, match, 2) if match.innings >= 2 else None
    striker = db.get(Player, match.striker_id) if match.striker_id else None
    non_striker = db.get(Player, match.non_striker_id) if match.non_striker_id else None
    bowler = db.get(Player, match.bowler_id) if match.bowler_id else None
    last_over = []
    current_innings_deliveries = deliveries_for(db, match.id, match.innings)
    if current_innings_deliveries:
        last_over_no = current_innings_deliveries[-1].over_number
        last_over = [f"W" if d.wicket_type else (f"Wd+{d.extra_runs}" if d.extra_type == "wide" else f"Nb+{d.runs_bat + d.extra_runs}" if d.extra_type == "no_ball" else str(d.runs_bat + d.extra_runs)) for d in current_innings_deliveries if d.over_number == last_over_no][-6:]
    target = first["runs"] + 1 if match.innings == 2 else None
    required = max(0, target - current["runs"]) if target is not None else None
    return {
        "id": match.id, "title": match.title, "venue": match.venue, "format": match.match_format,
        "total_overs": match.total_overs, "status": match.status, "innings": match.innings,
        "team_a": {"id": team_a.id, "name": team_a.name, "short_name": team_a.short_name},
        "team_b": {"id": team_b.id, "name": team_b.name, "short_name": team_b.short_name},
        "batting_team": {"id": batting_team.id, "name": batting_team.name, "short_name": batting_team.short_name},
        "bowling_team": {"id": bowling_team.id, "name": bowling_team.name, "short_name": bowling_team.short_name},
        "striker": {"id": striker.id, "name": striker.name} if striker else None,
        "non_striker": {"id": non_striker.id, "name": non_striker.name} if non_striker and not match.single_batter_mode else None,
        "single_batter_mode": bool(match.single_batter_mode),
        "bowler": {"id": bowler.id, "name": bowler.name} if bowler else None,
        "score": current, "first_innings": first, "second_innings": second,
        "target": target, "runs_required": required, "last_over": last_over,
        "winner_id": match.winner_id, "result_text": match.result_text,
        "tournament_id": match.tournament_id, "created_at": match.created_at.isoformat(),
        "deliveries_count": len(all_deliveries),
        "dismissed_player_ids": [d.dismissed_player_id for d in current_innings_deliveries if d.dismissed_player_id is not None],
    }


# ---------- WebSocket fan-out ----------
class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, set[WebSocket]] = {}

    async def connect(self, match_id: int, websocket: WebSocket):
        await websocket.accept()
        self.connections.setdefault(match_id, set()).add(websocket)

    def disconnect(self, match_id: int, websocket: WebSocket):
        self.connections.get(match_id, set()).discard(websocket)

    async def broadcast(self, match_id: int, payload: dict):
        dead = []
        for socket in self.connections.get(match_id, set()):
            try:
                await socket.send_json(payload)
            except Exception:
                dead.append(socket)
        for socket in dead:
            self.disconnect(match_id, socket)


manager = ConnectionManager()


def startup_seed_demo():
    if os.getenv("SEED_DEMO", "false").lower() not in ("1", "true", "yes"):
        return
    db = SessionLocal()
    try:
        demo = db.scalar(select(User).where(User.email == "demo@agscorer.app"))
        if not demo:
            demo = User(name="AG Scorer Demo", email="demo@agscorer.app", password_hash=hash_password("agscorer123"))
            db.add(demo)
            db.flush()
            t1 = Team(name="Delhi Strikers", short_name="DLS", owner_id=demo.id)
            t2 = Team(name="Mandoli Warriors", short_name="MDW", owner_id=demo.id)
            db.add_all([t1, t2])
            db.flush()
            names_a = ["Arjun Mehta", "Kabir Singh", "Rohan Verma", "Aman Khan", "Dev Sharma", "Ishaan Roy", "Yash Malik", "Kunal Das", "Harsh Batra", "Nikhil Rao", "Aditya Jain"]
            names_b = ["Vivaan Gupta", "Rehan Ali", "Samar Kapoor", "Ritik Saini", "Manav Khanna", "Dhruv Joshi", "Aryan Bose", "Sahil Arora", "Pranav Gill", "Kartik Sen", "Om Prakash"]
            db.add_all([Player(team_id=t1.id, name=n, role="All-rounder", jersey_number=i + 1) for i, n in enumerate(names_a)])
            db.add_all([Player(team_id=t2.id, name=n, role="All-rounder", jersey_number=i + 1) for i, n in enumerate(names_b)])
            db.flush()
            players_a = list(db.scalars(select(Player).where(Player.team_id == t1.id).order_by(Player.id)))
            players_b = list(db.scalars(select(Player).where(Player.team_id == t2.id).order_by(Player.id)))
            demo_tournament = Tournament(name="AG Premier League", format="League", venue="Delhi", owner_id=demo.id)
            db.add(demo_tournament)
            db.flush()
            db.add(Match(
                title="Delhi Strikers vs Mandoli Warriors", venue="Mandoli Cricket Ground", match_format="T20", total_overs=20,
                team_a_id=t1.id, team_b_id=t2.id, batting_team_id=t1.id, bowling_team_id=t2.id,
                striker_id=players_a[0].id, non_striker_id=players_a[1].id, bowler_id=players_b[0].id,
                toss_winner_id=t1.id, toss_decision="bat", tournament_id=demo_tournament.id, owner_id=demo.id,
            ))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(application: FastAPI):
    startup_seed_demo()
    yield


app = FastAPI(title=APP_NAME, version="1.2.0", description="AG Scorer web app API: cricket scoring, teams, shared players, tournaments and statistics.", lifespan=lifespan)
allowed_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_DIR = PROJECT_ROOT / "web"
ASSETS_DIR = WEB_DIR / "assets"
if ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
ICONS_DIR = WEB_DIR / "icons"
if ICONS_DIR.exists():
    app.mount("/icons", StaticFiles(directory=ICONS_DIR), name="icons")


@app.get("/manifest.webmanifest")
def pwa_manifest():
    return FileResponse(WEB_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/sw.js")
def pwa_service_worker():
    return FileResponse(WEB_DIR / "sw.js", media_type="application/javascript", headers={"Cache-Control": "no-cache"})


@app.get("/")
def root():
    index_file = WEB_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"app": APP_NAME, "status": "ok", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy", "service": APP_NAME}


# ---------- Authentication ----------
@app.post("/auth/register")
def register(data: RegisterIn, db: Session = Depends(get_db)):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")
    user = User(name=data.name.strip(), email=email, password_hash=hash_password(data.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"access_token": issue_token(user.id), "token_type": "bearer", "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.post("/auth/login")
def login(data: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return {"access_token": issue_token(user.id), "token_type": "bearer", "user": {"id": user.id, "name": user.name, "email": user.email}}


@app.get("/auth/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "name": user.name, "email": user.email}


# ---------- Teams and players ----------
@app.get("/teams")
def list_teams(db: Session = Depends(get_db), user: User = Depends(current_user)):
    teams = list(db.scalars(select(Team).where(Team.owner_id == user.id).order_by(Team.name)))
    return [{"id": t.id, "name": t.name, "short_name": t.short_name, "players_count": len(t.players)} for t in teams]


@app.post("/teams", status_code=201)
def create_team(data: TeamIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    team = Team(name=data.name.strip(), short_name=data.short_name.upper().strip(), owner_id=user.id)
    db.add(team)
    db.commit()
    db.refresh(team)
    return {"id": team.id, "name": team.name, "short_name": team.short_name, "players_count": 0}


@app.get("/teams/{team_id}/players")
def list_players(team_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    team = team_for_user(db, team_id, user.id)
    roster = list(team.players)
    common = list(db.scalars(select(Player).join(Team, Player.team_id == Team.id).where(
        Team.owner_id == user.id, Player.is_common.is_(True)
    ).order_by(Player.name)))
    unique = {p.id: p for p in [*roster, *common]}
    return [{"id": p.id, "team_id": p.team_id, "name": p.name, "role": p.role,
             "jersey_number": p.jersey_number, "is_common": bool(p.is_common)}
            for p in sorted(unique.values(), key=lambda player: (player.name.lower(), player.id))]


@app.post("/teams/{team_id}/players", status_code=201)
def create_player(team_id: int, data: PlayerIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    team_for_user(db, team_id, user.id)
    player = Player(team_id=team_id, name=data.name.strip(), role=data.role, jersey_number=data.jersey_number)
    db.add(player)
    db.commit()
    db.refresh(player)
    return {"id": player.id, "team_id": player.team_id, "name": player.name, "role": player.role,
            "jersey_number": player.jersey_number, "is_common": False}


@app.get("/players/common")
def list_common_players(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = list(db.scalars(select(Player).join(Team, Player.team_id == Team.id).where(
        Team.owner_id == user.id, Player.is_common.is_(True)
    ).order_by(Player.name)))
    return [{"id": p.id, "team_id": p.team_id, "home_team": db.get(Team, p.team_id).name,
             "name": p.name, "role": p.role, "jersey_number": p.jersey_number, "is_common": True}
            for p in rows]


@app.post("/players/common", status_code=201)
def create_common_player(data: CommonPlayerIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    team_for_user(db, data.home_team_id, user.id)
    player = Player(team_id=data.home_team_id, name=data.name.strip(), role=data.role,
                    jersey_number=data.jersey_number, is_common=True)
    db.add(player)
    db.commit()
    db.refresh(player)
    home_team = db.get(Team, player.team_id)
    return {"id": player.id, "team_id": player.team_id, "home_team": home_team.name,
            "name": player.name, "role": player.role, "jersey_number": player.jersey_number, "is_common": True}


# ---------- Tournaments ----------
@app.get("/tournaments")
def list_tournaments(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = list(db.scalars(select(Tournament).where(Tournament.owner_id == user.id).order_by(Tournament.created_at.desc())))
    output = []
    for t in rows:
        match_count = len(list(db.scalars(select(Match).where(Match.tournament_id == t.id))))
        output.append({"id": t.id, "name": t.name, "format": t.format, "venue": t.venue, "matches_count": match_count})
    return output


@app.post("/tournaments", status_code=201)
def create_tournament(data: TournamentIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    tournament = Tournament(name=data.name.strip(), format=data.format, venue=data.venue, owner_id=user.id)
    db.add(tournament)
    db.commit()
    db.refresh(tournament)
    return {"id": tournament.id, "name": tournament.name, "format": tournament.format, "venue": tournament.venue, "matches_count": 0}


@app.get("/tournaments/{tournament_id}/standings")
def tournament_standings(tournament_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    tournament = db.get(Tournament, tournament_id)
    if not tournament or tournament.owner_id != user.id:
        raise HTTPException(status_code=404, detail="Tournament not found")
    matches = list(db.scalars(select(Match).where(Match.tournament_id == tournament_id)))
    table: dict[int, dict] = {}
    for match in matches:
        for team_id in (match.team_a_id, match.team_b_id):
            table.setdefault(team_id, {"team_id": team_id, "played": 0, "won": 0, "lost": 0, "tied": 0, "points": 0})
        if match.status == "completed":
            for team_id in (match.team_a_id, match.team_b_id):
                table[team_id]["played"] += 1
            if match.winner_id:
                table[match.winner_id]["won"] += 1
                table[match.winner_id]["points"] += 2
                loser_id = match.team_b_id if match.winner_id == match.team_a_id else match.team_a_id
                table[loser_id]["lost"] += 1
            else:
                for team_id in (match.team_a_id, match.team_b_id):
                    table[team_id]["tied"] += 1
                    table[team_id]["points"] += 1
    result = []
    for row in table.values():
        team = db.get(Team, row["team_id"])
        row["team"] = team.name if team else "Unknown"
        result.append(row)
    return sorted(result, key=lambda r: (r["points"], r["won"]), reverse=True)


# ---------- Matches and scorecards ----------
@app.get("/matches")
def list_matches(db: Session = Depends(get_db), user: User = Depends(current_user)):
    matches = list(db.scalars(select(Match).where(Match.owner_id == user.id).order_by(Match.created_at.desc())))
    return [match_payload(db, m) for m in matches]


@app.post("/matches", status_code=201)
def create_match(data: MatchIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    team_a, team_b = team_for_user(db, data.team_a_id, user.id), team_for_user(db, data.team_b_id, user.id)
    if team_a.id == team_b.id:
        raise HTTPException(status_code=400, detail="Choose two different teams")
    if data.toss_winner_id not in (team_a.id, team_b.id):
        raise HTTPException(status_code=400, detail="Toss winner must be one of the match teams")
    if data.toss_decision not in ("bat", "bowl"):
        raise HTTPException(status_code=400, detail="Toss decision must be bat or bowl")
    batting_first_id = data.toss_winner_id if data.toss_decision == "bat" else (team_b.id if data.toss_winner_id == team_a.id else team_a.id)
    bowling_first_id = team_b.id if batting_first_id == team_a.id else team_a.id
    if not player_in_team(db, data.striker_id, batting_first_id, user.id):
        raise HTTPException(status_code=400, detail="Opening striker must belong to the team batting first")
    if data.single_batter_mode:
        # Internally keep a valid player reference in the legacy non-striker slot;
        # the API and UI expose no non-striker in solo mode.
        effective_non_striker_id = data.striker_id
    else:
        if not data.non_striker_id or not player_in_team(db, data.non_striker_id, batting_first_id, user.id):
            raise HTTPException(status_code=400, detail="Opening non-striker must belong to the team batting first")
        if data.striker_id == data.non_striker_id:
            raise HTTPException(status_code=400, detail="Opening batters must be different players")
        effective_non_striker_id = data.non_striker_id
    if not player_in_team(db, data.bowler_id, bowling_first_id, user.id):
        raise HTTPException(status_code=400, detail="Opening bowler must belong to the bowling team")
    if data.tournament_id:
        tournament = db.get(Tournament, data.tournament_id)
        if not tournament or tournament.owner_id != user.id:
            raise HTTPException(status_code=404, detail="Tournament not found")
    match = Match(
        title=data.title.strip(), venue=data.venue, match_format=data.match_format, total_overs=data.total_overs,
        team_a_id=team_a.id, team_b_id=team_b.id, batting_team_id=batting_first_id, bowling_team_id=bowling_first_id,
        striker_id=data.striker_id, non_striker_id=effective_non_striker_id, bowler_id=data.bowler_id,
        single_batter_mode=data.single_batter_mode,
        toss_winner_id=data.toss_winner_id, toss_decision=data.toss_decision, tournament_id=data.tournament_id, owner_id=user.id,
    )
    db.add(match)
    db.commit()
    db.refresh(match)
    return match_payload(db, match)


@app.get("/matches/{match_id}")
def get_match(match_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return match_payload(db, match_for_user(db, match_id, user.id))


@app.get("/matches/{match_id}/scorecard")
def scorecard(match_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    match = match_for_user(db, match_id, user.id)
    first = innings_score(db, match, 1)
    second = innings_score(db, match, 2) if match.innings >= 2 else None
    return {"match_id": match.id, "innings": [first] + ([second] if second else [])}


# MVP points are intentionally simple and transparent. Fielding points are not
# included because catches/run-outs are not separately captured by the scorer.
MVP_BOWLER_CREDITED_WICKETS = {"bowled", "caught", "lbw", "stumped", "hit_wicket"}


def build_mvp_rankings(db: Session, deliveries: list[Delivery]) -> list[dict]:
    totals: dict[int, dict] = {}

    def row_for(player_id: int) -> dict:
        return totals.setdefault(player_id, {
            "player_id": player_id, "runs": 0, "balls_faced": 0, "fours": 0,
            "sixes": 0, "wickets": 0, "matches_seen": set(),
        })

    for delivery in deliveries:
        batter = row_for(delivery.striker_id)
        batter["runs"] += delivery.runs_bat
        if delivery.extra_type != "wide":
            batter["balls_faced"] += 1
        if delivery.runs_bat == 4:
            batter["fours"] += 1
        elif delivery.runs_bat == 6:
            batter["sixes"] += 1
        batter["matches_seen"].add(delivery.match_id)

        bowler = row_for(delivery.bowler_id)
        bowler["matches_seen"].add(delivery.match_id)
        if delivery.wicket_type in MVP_BOWLER_CREDITED_WICKETS:
            bowler["wickets"] += 1

    ranked = []
    for player_id, totals_row in totals.items():
        player = db.get(Player, player_id)
        if not player:
            continue
        points = totals_row["runs"] + totals_row["fours"] + (2 * totals_row["sixes"]) + (20 * totals_row["wickets"])
        ranked.append({
            "player_id": player_id,
            "name": player.name,
            "role": player.role,
            "is_common": bool(player.is_common),
            "matches": len(totals_row["matches_seen"]),
            "runs": totals_row["runs"],
            "balls_faced": totals_row["balls_faced"],
            "fours": totals_row["fours"],
            "sixes": totals_row["sixes"],
            "wickets": totals_row["wickets"],
            "points": points,
        })

    ranked.sort(key=lambda item: (item["points"], item["wickets"], item["runs"], item["sixes"]), reverse=True)
    for rank, item in enumerate(ranked, start=1):
        item["rank"] = rank
    return ranked


@app.get("/mvp-rankings")
def mvp_rankings(db: Session = Depends(get_db), user: User = Depends(current_user)):
    deliveries = list(db.scalars(
        select(Delivery)
        .join(Match, Delivery.match_id == Match.id)
        .where(Match.owner_id == user.id)
        .order_by(Delivery.match_id, Delivery.sequence)
    ))
    return {
        "rankings": build_mvp_rankings(db, deliveries),
        "points_formula": "1 point per run + 1 bonus per four + 2 bonus per six + 20 points per bowler-credited wicket",
        "fielding_points_included": False,
    }


@app.get("/matches/{match_id}/mvp")
def match_mvp_rankings(match_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    match_for_user(db, match_id, user.id)
    deliveries = list(db.scalars(
        select(Delivery).where(Delivery.match_id == match_id).order_by(Delivery.sequence)
    ))
    return {
        "rankings": build_mvp_rankings(db, deliveries),
        "points_formula": "1 point per run + 1 bonus per four + 2 bonus per six + 20 points per bowler-credited wicket",
        "fielding_points_included": False,
    }


@app.post("/matches/{match_id}/balls", status_code=201)
async def add_ball(match_id: int, data: BallIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    match = match_for_user(db, match_id, user.id)
    if match.status != "live":
        raise HTTPException(status_code=409, detail=f"Match is {match.status}; scoring is locked")
    if not match.striker_id or (not match.single_batter_mode and not match.non_striker_id) or not match.bowler_id:
        raise HTTPException(status_code=409, detail="Select the active batter(s) and bowler before scoring")
    allowed_extras = (None, "wide", "no_ball", "bye", "leg_bye", "penalty")
    if data.extra_type not in allowed_extras:
        raise HTTPException(status_code=400, detail="Unsupported extra type")
    if data.extra_type in ("wide", "no_ball") and data.extra_runs < 1:
        raise HTTPException(status_code=400, detail="Wide and no-ball must include at least one extra run")
    if data.wicket_type and data.wicket_type not in ("bowled", "caught", "lbw", "run_out", "stumped", "hit_wicket", "retired_hurt", "obstructing_field", "hit_twice"):
        raise HTTPException(status_code=400, detail="Unsupported dismissal type")
    valid_dismissed_ids = (match.striker_id,) if match.single_batter_mode else (match.striker_id, match.non_striker_id)
    if data.wicket_type and data.dismissed_player_id not in valid_dismissed_ids:
        raise HTTPException(status_code=400, detail="Select the dismissed batter")
    if data.wicket_type and data.new_batter_id and not player_in_team(db, data.new_batter_id, match.batting_team_id, user.id):
        raise HTTPException(status_code=400, detail="Incoming batter must belong to the batting team")
    if data.wicket_type:
        if not data.new_batter_id:
            raise HTTPException(status_code=400, detail="Select an incoming batter")
        if data.new_batter_id in (match.striker_id, match.non_striker_id):
            raise HTTPException(status_code=400, detail="Incoming batter is already at the crease")
        dismissed_before = {d.dismissed_player_id for d in deliveries_for(db, match.id, match.innings) if d.dismissed_player_id is not None}
        if data.new_batter_id in dismissed_before:
            raise HTTPException(status_code=400, detail="A dismissed batter cannot return to the crease")
    current_deliveries = deliveries_for(db, match.id, match.innings)
    legal_before = sum(1 for d in current_deliveries if d.is_legal)
    sequence = (max((d.sequence for d in match.deliveries), default=0) + 1)
    is_legal = data.extra_type not in ("wide", "no_ball")
    over_number = legal_before // 6 + 1
    ball_number = legal_before % 6 + 1
    delivery = Delivery(
        match_id=match.id, innings=match.innings, sequence=sequence, over_number=over_number, ball_number=ball_number,
        striker_id=match.striker_id, non_striker_id=(match.striker_id if match.single_batter_mode else match.non_striker_id), bowler_id=match.bowler_id,
        runs_bat=data.runs_bat, extra_type=data.extra_type or "", extra_runs=data.extra_runs,
        running_runs=data.running_runs, wicket_type=data.wicket_type or "", dismissed_player_id=data.dismissed_player_id,
        is_legal=is_legal, previous_striker_id=match.striker_id, previous_non_striker_id=(match.striker_id if match.single_batter_mode else match.non_striker_id),
        previous_bowler_id=match.bowler_id, previous_status=match.status,
    )
    db.add(delivery)
    # Strike changes for completed runs, then at the end of every completed over.
    if not match.single_batter_mode and (data.runs_bat + data.running_runs) % 2 == 1:
        match.striker_id, match.non_striker_id = match.non_striker_id, match.striker_id
    if is_legal and (legal_before + 1) % 6 == 0:
        if not match.single_batter_mode:
            match.striker_id, match.non_striker_id = match.non_striker_id, match.striker_id
        match.bowler_id = None  # scorer must choose the next over's bowler
    if data.wicket_type:
        dismissed = data.dismissed_player_id
        if match.single_batter_mode:
            match.striker_id = data.new_batter_id
            match.non_striker_id = data.new_batter_id
        elif dismissed == match.striker_id:
            match.striker_id = data.new_batter_id
        elif dismissed == match.non_striker_id:
            match.non_striker_id = data.new_batter_id
    db.flush()
    score = innings_score(db, match, match.innings)
    if score["wickets"] >= 10 or score["legal_balls"] >= match.total_overs * 6:
        if match.innings == 2:
            first_score = innings_score(db, match, 1)["runs"]
            if score["runs"] > first_score:
                match.status = "completed"
                match.winner_id = match.batting_team_id
                match.result_text = f"{match.winner_id and db.get(Team, match.winner_id).name} won by {10 - score['wickets']} wickets"
            elif score["runs"] == first_score:
                match.status = "completed"
                match.winner_id = None
                match.result_text = "Match tied"
            else:
                match.status = "completed"
                match.winner_id = match.bowling_team_id
                match.result_text = f"{db.get(Team, match.winner_id).name} won by {first_score - score['runs']} runs"
        else:
            match.status = "innings_break"
    elif match.innings == 2 and score["runs"] > innings_score(db, match, 1)["runs"]:
        match.status = "completed"
        match.winner_id = match.batting_team_id
        match.result_text = f"{db.get(Team, match.winner_id).name} won by {10 - score['wickets']} wickets"
    db.commit()
    db.refresh(match)
    payload = match_payload(db, match)
    await manager.broadcast(match.id, {"type": "score_update", "match": payload})
    return payload


@app.put("/matches/{match_id}/batters")
async def set_batters(match_id: int, data: BattersIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    match = match_for_user(db, match_id, user.id)
    if match.status != "live":
        raise HTTPException(status_code=409, detail=f"Match is {match.status}; batters cannot be changed")
    if not player_in_team(db, data.striker_id, match.batting_team_id, user.id):
        raise HTTPException(status_code=400, detail="Striker must belong to the batting team")
    dismissed_ids = {d.dismissed_player_id for d in deliveries_for(db, match.id, match.innings) if d.dismissed_player_id is not None}
    if data.striker_id in dismissed_ids:
        raise HTTPException(status_code=400, detail="A dismissed batter cannot return to the crease")
    if match.single_batter_mode:
        match.striker_id = data.striker_id
        match.non_striker_id = data.striker_id
    else:
        if not data.non_striker_id or not player_in_team(db, data.non_striker_id, match.batting_team_id, user.id):
            raise HTTPException(status_code=400, detail="Non-striker must belong to the batting team")
        if data.non_striker_id in dismissed_ids:
            raise HTTPException(status_code=400, detail="A dismissed batter cannot return to the crease")
        if data.striker_id == data.non_striker_id:
            raise HTTPException(status_code=400, detail="Batters must be different players")
        match.striker_id, match.non_striker_id = data.striker_id, data.non_striker_id
    db.commit()
    payload = match_payload(db, match)
    await manager.broadcast(match.id, {"type": "score_update", "match": payload})
    return payload


@app.put("/matches/{match_id}/bowler")
async def set_bowler(match_id: int, data: BowlerIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    match = match_for_user(db, match_id, user.id)
    if match.status != "live":
        raise HTTPException(status_code=409, detail=f"Match is {match.status}; bowler cannot be changed")
    if not player_in_team(db, data.bowler_id, match.bowling_team_id, user.id):
        raise HTTPException(status_code=400, detail="Bowler must belong to the bowling team")
    match.bowler_id = data.bowler_id
    db.commit()
    payload = match_payload(db, match)
    await manager.broadcast(match.id, {"type": "score_update", "match": payload})
    return payload


@app.post("/matches/{match_id}/next-innings")
async def next_innings(match_id: int, data: NextInningsIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    match = match_for_user(db, match_id, user.id)
    if match.innings != 1 or match.status != "innings_break":
        raise HTTPException(status_code=409, detail="The first innings must finish before starting the next innings")
    if not player_in_team(db, data.striker_id, match.bowling_team_id, user.id):
        raise HTTPException(status_code=400, detail="Second-innings striker must belong to the team batting second")
    if not player_in_team(db, data.bowler_id, match.batting_team_id, user.id):
        raise HTTPException(status_code=400, detail="Second-innings bowler must belong to the team bowling second")
    if match.single_batter_mode:
        effective_non_striker_id = data.striker_id
    else:
        if not data.non_striker_id or not player_in_team(db, data.non_striker_id, match.bowling_team_id, user.id):
            raise HTTPException(status_code=400, detail="Second-innings non-striker must belong to the team batting second")
        if data.striker_id == data.non_striker_id:
            raise HTTPException(status_code=400, detail="Batters must be different players")
        effective_non_striker_id = data.non_striker_id
    match.batting_team_id, match.bowling_team_id = match.bowling_team_id, match.batting_team_id
    match.striker_id, match.non_striker_id, match.bowler_id = data.striker_id, effective_non_striker_id, data.bowler_id
    match.innings = 2
    match.status = "live"
    db.commit()
    payload = match_payload(db, match)
    await manager.broadcast(match.id, {"type": "score_update", "match": payload})
    return payload


@app.post("/matches/{match_id}/undo")
async def undo_last_ball(match_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    match = match_for_user(db, match_id, user.id)
    last = db.scalar(select(Delivery).where(Delivery.match_id == match_id, Delivery.innings == match.innings).order_by(Delivery.sequence.desc()).limit(1))
    if not last:
        raise HTTPException(status_code=404, detail="There is no ball to undo")
    match.striker_id = last.previous_striker_id
    match.non_striker_id = last.previous_non_striker_id
    match.bowler_id = last.previous_bowler_id
    match.status = last.previous_status
    match.winner_id = None
    match.result_text = ""
    db.delete(last)
    db.commit()
    payload = match_payload(db, match)
    await manager.broadcast(match.id, {"type": "score_update", "match": payload})
    return payload


@app.post("/matches/{match_id}/complete")
async def complete_match(match_id: int, data: CompleteIn, db: Session = Depends(get_db), user: User = Depends(current_user)):
    match = match_for_user(db, match_id, user.id)
    if data.winner_id and data.winner_id not in (match.team_a_id, match.team_b_id):
        raise HTTPException(status_code=400, detail="Winner must be one of the match teams")
    match.status = "completed"
    match.winner_id = data.winner_id
    match.result_text = data.result_text or "Match completed"
    db.commit()
    payload = match_payload(db, match)
    await manager.broadcast(match.id, {"type": "score_update", "match": payload})
    return payload


@app.get("/players/{player_id}/stats")
def player_stats(player_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    player = db.get(Player, player_id)
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")
    team_for_user(db, player.team_id, user.id)
    batting_balls = list(db.scalars(select(Delivery).where(Delivery.striker_id == player_id)))
    bowling_balls = list(db.scalars(select(Delivery).where(Delivery.bowler_id == player_id)))
    runs = sum(d.runs_bat for d in batting_balls)
    faced = sum(1 for d in batting_balls if d.extra_type != "wide")
    wickets = sum(1 for d in bowling_balls if d.wicket_type and d.wicket_type not in ("run_out", "retired_hurt", "obstructing_field"))
    dismissals = sum(1 for d in db.scalars(select(Delivery).where(Delivery.dismissed_player_id == player_id)))
    conceded = sum(d.runs_bat + d.extra_runs - (d.extra_runs if d.extra_type in ("bye", "leg_bye", "penalty") else 0) for d in bowling_balls)
    legal_balls = sum(1 for d in bowling_balls if d.is_legal)
    return {
        "id": player.id, "name": player.name, "role": player.role, "team_id": player.team_id,
        "is_common": bool(player.is_common),
        "runs": runs, "balls_faced": faced, "batting_average": round(runs / dismissals, 2) if dismissals else float(runs),
        "strike_rate": round(runs * 100 / faced, 2) if faced else 0, "fours": sum(1 for d in batting_balls if d.runs_bat == 4),
        "sixes": sum(1 for d in batting_balls if d.runs_bat == 6), "wickets": wickets,
        "bowling_overs": f"{legal_balls // 6}.{legal_balls % 6}", "runs_conceded": conceded,
        "economy": round(conceded * 6 / legal_balls, 2) if legal_balls else 0,
    }


@app.websocket("/ws/matches/{match_id}")
async def match_socket(websocket: WebSocket, match_id: int, token: str):
    # WebSocket clients pass their bearer token as ?token=... because browser-style
    # WebSocket APIs do not consistently expose custom authorization headers.
    try:
        user_id = decode_token(token)
        db = SessionLocal()
        try:
            match = db.get(Match, match_id)
            if not match or match.owner_id != user_id:
                await websocket.close(code=1008)
                return
        finally:
            db.close()
    except HTTPException:
        await websocket.close(code=1008)
        return
    await manager.connect(match_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(match_id, websocket)

