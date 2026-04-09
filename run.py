from app import create_app
from dotenv import load_dotenv

load_dotenv()

app = create_app()

if __name__ == "__main__":
    # Demo stability note:
    # SSE notifications use a process-local broker. Run with a single worker/process.
    # Example: `flask run` or `gunicorn -w 1 run:app`
    app.run(debug=True)
