## Quick orientation

- This is a single-repository Flask monolith. The main application lives in `app.py` (models, routes, forms, and helpers are colocated). Treat `app.py` as the canonical source of truth.
- Persistent schema migration code is in `migrations/` (Alembic via `flask-migrate`). The default DB is SQLite (`sqlite:///marketplace.db`) unless `DATABASE_URL` env var is set.

## What to look at first (fast path)

- `app.py` — core app: configuration, extension init (SQLAlchemy, Migrate, LoginManager, Mail, SocketIO, Limiter), models (`User`, `Service`, `Message`), and all HTTP + SocketIO handlers.
- `templates/` and `static/` — UI and upload destinations. Upload folders: `static/uploads/ids`, `static/uploads/avatars`, `static/uploads/chat` (see `app.config['ID_FOLDER']`, `AVATAR_FOLDER`, `CHAT_UPLOAD_FOLDER`).
- `migrations/` — Alembic migration history; use `flask db upgrade` to apply.
- Utility scripts: `create_user.py`, `check_users.py`, `reset_password.py`, `add_test_user.py` — these import `app` and run inside Flask app context.

## Architecture & patterns (concise)

- Monolith: one Flask app object (`app = Flask(__name__)`) and single DB instance `db = SQLAlchemy(app)` in `app.py`.
- Models and business logic are colocated with routes. When changing models, update `migrations/` via Flask-Migrate (`flask db migrate`) then `flask db upgrade`.
- Real-time features use `flask_socketio` (Socket.IO event handlers at bottom of `app.py`). When running locally use `python app.py` (it calls `socketio.run(app, ...)`).
- ID verification integrates Google Cloud Vision — look for `GOOGLE_CLOUD_VISION_API_KEY` and `GOOGLE_APPLICATION_CREDENTIALS` usage in `app.py` and the helper functions `verify_id_document` / `analyze_id_image`.
- Rate limiting is applied per-route with `@limiter.limit(...)` (see `register`, `login`, `forgot_password`, `post_service`).

## Developer workflows (commands & examples)

- Run locally (dev):

  - Set environment (Windows PowerShell):
    $env:FLASK_APP = 'app.py'; $env:FLASK_ENV = 'development'
    (or just run) `python app.py` — the file creates DB tables on start and runs SocketIO server.

- DB migrations (recommended):

  - Set FLASK_APP and use flask-migrate commands (PowerShell):
    $env:FLASK_APP='app.py'
    flask db migrate -m "describe change"
    flask db upgrade

  - Note: `migrations/` already contains history; prefer `flask db upgrade` to bring a local DB up-to-date.

- Creating test/admin users: use `create_user.py` or `add_test_user.py`. These scripts call `app.app_context()` and interact with models directly (no HTTP required).

## Important environment variables (found in `app.py`)

- `SECRET_KEY` — fallback to `dev-secret-key` if not set; set for production.
- `DATABASE_URL` — defaults to `sqlite:///marketplace.db`.
- `ADMIN_EMAIL`, `ADMIN_PWD` — used by `app.py` main to create a default admin on first run.
- Mail: `MAIL_SERVER`, `MAIL_PORT`, `MAIL_USE_TLS`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_DEFAULT_SENDER`.
- Google Vision: `GOOGLE_CLOUD_VISION_API_KEY` and `GOOGLE_APPLICATION_CREDENTIALS` (path to credentials JSON). The code also contains hard-coded KEY_PATH examples — validate these before running.

## Project-specific conventions & gotchas

- Single-file app: many behaviors are implemented inline in `app.py`. When editing, search that file first — form classes, models, and route logic are all in the same file.
- Duplicate form definitions: there is a small `forms.py` with `LoginForm`/`RegisterForm`, but `app.py` defines and uses its own `FlaskForm` classes too — treat `app.py` forms as authoritative unless migrating to a refactor.
- File uploads: the app writes user-uploaded files into `static/uploads/...` and stores filenames in model columns (e.g., `User.id_image`, `User.avatar`). Use `secure_filename()` and the configured folders.
- Google Vision usage: the repository sets environment variables and also loads a local KEY_PATH — be careful not to leak credentials. Tests or local runs may need a service account JSON available at `GOOGLE_APPLICATION_CREDENTIALS`.
- Rate-limits: endpoints critical for auth are limited; tests hitting them rapidly can trigger 429 responses.

## Integration points

- Database: SQLAlchemy models in `app.py` + Alembic migrations in `migrations/`.
- Email: Flask-Mail — `send_reset_email` uses `ts.dumps(...)` and `url_for(..., _external=True)` to build reset links; if `MAIL_SERVER` is missing the app prints the reset URL to the Flask flash messages (dev fallback).
- Vision API: `google.cloud.vision` client used in `verify_id_document` and `analyze_id_image`.
- SocketIO: `socketio.emit` used to notify new messages; server started via `socketio.run(app, ...)` in `__main__`.

## Examples to copy when coding

- Check unread message count: use `unread_count_for_user(user_id)` helper in `app.py` (used in `inject_globals`).
- Marking messages read: see `chat()` route where `is_read` is toggled and `db.session.commit()` is called.
- Protecting admin routes: use `@require_role("admin")` wrapper defined in `app.py`.

## When changing models or files

- Add migration after model change: set `FLASK_APP=app.py` and run `flask db migrate` then `flask db upgrade`.
- If you change file upload paths or names, also update templates that reference `/static/uploads/...` (search `uploads/` in `templates/`).

## Minimal testing & verification steps

- Start app: `python app.py` and visit `http://127.0.0.1:5000/`.
- Use `create_user.py` to add a seller/test user quickly.
- If email isn't configured, use the flashed reset link printed to the UI for password reset flows.

## Contact points for follow-up

- If you need to refactor into a package structure, move models and forms out of `app.py` into `models.py`/`forms.py` and update `FLASK_APP` to the package module.

---

If any of these sections are unclear or you want me to expand an example (migrations, SocketIO, or Vision integration), tell me which area and I'll iterate.
