# Ushiri Pharmacy

Flask + SQLite app for pharmacy stock, sales, batches and reports.

## Features

- Stock In with medicines, batches, bonus boxes and expiry tracking
- Stock overview with expired, expiring-soon, low-stock and out-of-stock badges
- Batches page to edit or delete stock entries
- Sale page with box/strip modes and FEFO (earliest-expiry-first) deduction
- Printable bills linked from the report
- Daily/monthly sales and profit report
- CSRF protection, secure session cookies, validation and error pages
- Automated tests with GitHub Actions CI

## Files

- `app.py` — entry point
- `config.py` — settings from environment variables
- `pharmacy/` — app factory, database helpers, security and route blueprints
- `templates/` — HTML pages
- `pharmacy.db` — local database (not in Git)
- `requirements.txt` — pinned dependencies
- `tests/` — 15 automated tests
- `backup_db.py` — database backup tool
- `.github/workflows/tests.yml` — CI

## Setup

1. `git clone https://github.com/Usama3231/Pharmacy.git`
2. `cd Pharmacy`
3. `python -m venv .venv`
4. Windows: `.venv\Scripts\activate`
5. `pip install -r requirements.txt`
6. `set SECRET_KEY=your-long-random-string`
7. `python app.py`
8. Open `http://127.0.0.1:5000`

Generate a key: `python -c "import secrets; print(secrets.token_hex(32))"`

Environment variables:
- `SECRET_KEY` — session signing key
- `FLASK_DEBUG=1` — enable debug mode locally
- `CSRF_ENABLED=0` — disable CSRF (tests only)
- `SESSION_COOKIE_SECURE=1` — require HTTPS cookies

## Tests

`python -m unittest discover -s tests -v`

The tests use a temporary database, so `pharmacy.db` is never changed. The same command runs automatically on every push/PR via GitHub Actions.

## Backup

`python backup_db.py` writes `backups/pharmacy_<date>.db` (ignored by Git).

## Collaboration (Sam and Azan)

- Work on separate branches (`sam-...`, `azan-...`), not directly on `main`.
- Commit, push, then open a Pull Request for review before merging.
- Pull/Sync before starting work.
- Never commit `pharmacy.db`.
