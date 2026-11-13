import os
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# ---------------------------------------------------------------------------
# Database configuration
#
# Priority:
#   1. DATABASE_URL environment variable (or .env file)   -> use it as-is
#   2. PostgreSQL on localhost                              -> use it if reachable
#   3. SQLite file (./audienceiq.db)                        -> development fallback
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv():
    """Minimal .env loader so we do not depend on python-dotenv being present."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

ECHO_SQL = os.getenv("SQL_ECHO", "false").lower() == "true"

POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://localhost/audienceiq")
SQLITE_URL = f"sqlite:///{(BASE_DIR / 'audienceiq.db').as_posix()}"


def _postgres_works(url: str) -> bool:
    """Return True only if we can actually open a connection."""
    try:
        test_engine = create_engine(url, pool_pre_ping=True)
        with test_engine.connect():
            pass
        test_engine.dispose()
        return True
    except Exception as exc:  # noqa: BLE001 - any failure means "fall back"
        print(f"[database] PostgreSQL not available ({exc.__class__.__name__}), using SQLite.")
        return False


def _create_engine():
    env_url = os.getenv("DATABASE_URL")

    if env_url:
        if env_url.startswith("sqlite"):
            print(f"[database] Using DATABASE_URL from environment: {env_url}")
            return create_engine(
                env_url,
                connect_args={"check_same_thread": False},
                echo=ECHO_SQL,
            )
        if _postgres_works(env_url):
            print("[database] Using PostgreSQL from DATABASE_URL.")
            return create_engine(env_url, pool_pre_ping=True, echo=ECHO_SQL)

    if _postgres_works(POSTGRES_URL):
        print(f"[database] Using PostgreSQL at {POSTGRES_URL}")
        return create_engine(POSTGRES_URL, pool_pre_ping=True, echo=ECHO_SQL)

    print(f"[database] Falling back to SQLite at {SQLITE_URL}")
    return create_engine(
        SQLITE_URL,
        connect_args={"check_same_thread": False},
        echo=ECHO_SQL,
    )


engine = _create_engine()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def init_db():
    """Create any missing tables. Safe to call on every startup."""
    from models import Base as ModelsBase  # noqa: F401  (ensures models are registered)

    Base.metadata.create_all(bind=engine)
    print("[database] Tables ready.")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
