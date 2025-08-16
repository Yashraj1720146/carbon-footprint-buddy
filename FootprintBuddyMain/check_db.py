# check_db.py
import sqlite3, json, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")  # users.db next to check_db.py

print("DB path:", DB_PATH, "| exists:", os.path.exists(DB_PATH))

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

print("Tables:", cur.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall())

try:
    rows = cur.execute("SELECT id, username, password FROM users ORDER BY id;").fetchall()
    print(f"Total users: {len(rows)}")
    for user_id, username, blob in rows:
        kind = "PBKDF2"
        try:
            rec = json.loads(blob)
            if not isinstance(rec, dict) or "hash" not in rec or "salt" not in rec:
                kind = "LEGACY_SHA256"
        except Exception:
            kind = "LEGACY_SHA256"
        print(f"- {user_id}: {username} [{kind}] (password length={len(blob)})")
except sqlite3.OperationalError as e:
    print("DB error:", e)

conn.close()