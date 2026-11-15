import sqlite3
c = sqlite3.connect("subtitler.db")
print("integrity:", c.execute("PRAGMA integrity_check").fetchone()[0])
print("journal_mode:", c.execute("PRAGMA journal_mode").fetchone()[0])
for (name,) in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall():
    try:
        cnt = c.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
        print(f"table {name}: {cnt} rows")
    except Exception as e:
        print(f"table {name}: ERROR {e}")
c.close()
try:
    c2 = sqlite3.connect("subtitler.db.corrupt.20261110_072451.bak")
    print("bak integrity:", c2.execute("PRAGMA integrity_check").fetchone()[0])
except Exception as e:
    print("bak unreadable:", e)
