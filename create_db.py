"""Create or upgrade rms.db.  main.py does this automatically on every start,
so running this file by hand is optional."""
from db import init_db

if __name__ == "__main__":
    result = init_db()
    if result.get("migrated"):
        print("Upgraded the existing database. A backup was saved as rms.db.bak-v1.")
        print(result)
    else:
        print("Database is ready.")
