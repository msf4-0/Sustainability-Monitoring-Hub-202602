"""
One-command database bootstrap.

Waits for the database to accept connections, then initialises the schema,
seeds GHG reference data, and repairs any polluted JSON persistence rows.

Works with both the bundled Docker database (``docker compose up -d``) and a
native MySQL/MariaDB server configured via ``.env``.

Usage:
    python scripts/bootstrap.py
    python scripts/bootstrap.py --wait 60     # wait up to 60s for the DB
    python scripts/bootstrap.py --skip-factors
"""

import sys
import os
import time
import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from config.settings import config

try:
    import mysql.connector
    from mysql.connector import Error
except ImportError:
    print("❌ mysql-connector-python is not installed. Run: pip install -r requirements.txt")
    sys.exit(1)


def wait_for_database(timeout: int = 60, interval: int = 3) -> bool:
    """Poll the server until it accepts a connection or timeout elapses."""
    db_config = config.database_config.copy()
    db_config.pop('database', None)  # connect to server, not a specific schema

    deadline = time.time() + timeout
    attempt = 0
    while True:
        attempt += 1
        try:
            conn = mysql.connector.connect(**db_config)
            conn.close()
            print(f"✅ Database is reachable at {db_config.get('host')}:{db_config.get('port')}")
            return True
        except Error as e:
            remaining = int(deadline - time.time())
            if remaining <= 0:
                print(f"❌ Database not reachable after {timeout}s: {e}")
                print("   Start it with: docker compose up -d")
                return False
            print(f"⏳ Waiting for database... ({remaining}s left)")
            time.sleep(interval)


def run_script(name: str, extra_args=None) -> bool:
    """Run a sibling script with the current interpreter."""
    script = ROOT / "scripts" / name
    if not script.exists():
        print(f"❌ Script not found: {script}")
        return False

    print("\n" + "=" * 64)
    print(f"▶️  {name}")
    print("=" * 64)
    cmd = [sys.executable, str(script)] + (extra_args or [])
    result = subprocess.run(cmd)
    return result.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="Bootstrap the Sustainability Monitoring Hub database")
    parser.add_argument('--wait', type=int, default=60, help="Seconds to wait for the database")
    parser.add_argument('--skip-factors', action='store_true', help="Skip GHG factor seeding")
    parser.add_argument('--skip-repair', action='store_true', help="Skip JSON persistence repair")
    args = parser.parse_args()

    print("=" * 64)
    print("🚀 Sustainability Monitoring Hub - Bootstrap")
    print("=" * 64)

    if not wait_for_database(timeout=args.wait):
        return 1

    steps = [("setup_db.py", None)]
    if not args.skip_factors:
        steps.append(("setup_ghg_factors.py", None))
    if not args.skip_repair:
        steps.append(("repair_json_persistence.py", None))

    for name, extra in steps:
        if not run_script(name, extra):
            print(f"\n❌ Bootstrap failed while running {name}")
            return 1

    print("\n" + "=" * 64)
    print("🎉 Bootstrap complete!")
    print("=" * 64)
    print("\n📝 Next steps:")
    print("  1. Run: python -m streamlit run app/main.py")
    print("  2. Login with: admin / admin123")
    print("  3. Change the admin password immediately!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
