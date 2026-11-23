# Ushiri Pharmacy

Flask + SQLite app for pharmacy stock, sales and reports.

## Files

- `app.py` — Flask routes and database logic
- `templates/` — HTML pages
- `pharmacy.db` — local database (not in Git)
- `requirements.txt` — pinned dependencies
- `tests/` — automated tests
- `backup_db.py` — database backup tool

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

Set `FLASK_DEBUG=1` only for local debugging; leave it unset otherwise.

## Tests

`python -m unittest discover -s tests -v`

## Backup

`python backup_db.py` writes `backups/pharmacy_<date>.db` (ignored by Git).

## Collaboration (Sam and Azan)

- Work on separate branches (`sam-...`, `azan-...`), not directly on `main`.
- Commit, push, then open a Pull Request for review before merging.
- Pull/Sync before starting work.
- Never commit `pharmacy.db`.
