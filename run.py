from app import create_app
from dotenv import load_dotenv
import os

load_dotenv()

app = create_app()


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}

if __name__ == "__main__":
    # Demo stability note:
    # SSE notifications use a process-local broker. Run with a single worker/process.
    # Example: `flask run` or `gunicorn -w 1 run:app`
    app.run(debug=_env_flag("FLASK_DEBUG", default=False))
