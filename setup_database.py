"""Creates the 'suwar' database, tables and sample data in MySQL.

Usage:  python setup_database.py
(Edit the user/password in suwar/config.py first if needed.)
"""
import os
import sys

from suwar import config

try:
    import mysql.connector
except ImportError:
    sys.exit("Please install the driver first:  pip install mysql-connector-python")


def split_statements(sql: str):
    lines = [ln for ln in sql.splitlines() if not ln.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def main():
    cfg = dict(config.DB_CONFIG)
    cfg.pop("database")                      # the script creates it
    path = os.path.join(os.path.dirname(__file__), "database", "schema.sql")
    with open(path, encoding="utf-8") as f:
        statements = split_statements(f.read())
    try:
        conn = mysql.connector.connect(**cfg)
    except mysql.connector.Error as exc:
        sys.exit(f"Could not connect to MySQL: {exc}")
    cur = conn.cursor()
    for stmt in statements:
        cur.execute(stmt)
    conn.commit()
    cur.close()
    conn.close()
    print(f"Done: executed {len(statements)} statements. Database ready - now run: python main.py")


if __name__ == "__main__":
    main()
