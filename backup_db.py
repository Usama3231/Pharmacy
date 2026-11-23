import os
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(BASE_DIR, "pharmacy.db")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")


def backup():
    if not os.path.exists(SOURCE):
        print("No pharmacy.db found; nothing to back up.")
        return None
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = "pharmacy_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
    target = os.path.join(BACKUP_DIR, name)
    source_conn = sqlite3.connect(SOURCE)
    target_conn = sqlite3.connect(target)
    try:
        source_conn.backup(target_conn)
    finally:
        target_conn.close()
        source_conn.close()
    print(f"Backup saved: {target}")
    return target


if __name__ == "__main__":
    backup()
