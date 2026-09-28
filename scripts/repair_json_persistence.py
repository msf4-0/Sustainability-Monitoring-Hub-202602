"""
Repair polluted JSON persistence rows.

Older versions of the SEDG disclosure and ESG Ready Questionnaire forms stored
their own change-tracking/control keys inside the JSON payload, e.g.::

    {"q8_maturity": null, "last_snapshot": "{...previous save...}", ...}

Because the snapshot was re-serialised on every save, the embedded string grew
exponentially (a few KB -> several MB) and, when loaded back, corrupted session
state. This script removes those control keys from existing rows.

It is idempotent: running it repeatedly is safe and only rewrites rows that
actually contain the offending keys.

Usage:
    python scripts/repair_json_persistence.py          # repair
    python scripts/repair_json_persistence.py --dry-run
"""

import sys
import os
import argparse
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from mysql.connector import Error
from config.settings import config

# Keys that must never appear inside the persisted payload.
IESG_BLOCKED = {'last_snapshot', 'loaded_context', 'responses_loaded', 'form_status',
                'unsaved_changes', 'last_save', 'auto_save_status', 'score',
                'max_score', 'percentage', 'force_refresh', 'initialized'}
SEDG_BLOCKED = {'last_snapshot', 'has_changes', 'last_save_time', 'save_status',
                'initialized', 'form_loaded', 'loaded_context', 'force_refresh'}


class PayloadRepair:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.connection = None
        self.db_config = config.database_config.copy()
        self.db_name = self.db_config['database']

    def connect(self):
        try:
            self.connection = mysql.connector.connect(**self.db_config)
            return True
        except Error as e:
            print(f"❌ Connection failed: {e}")
            return False

    def disconnect(self):
        if self.connection and self.connection.is_connected():
            self.connection.close()

    def _table_exists(self, table: str) -> bool:
        cur = self.connection.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = %s AND table_name = %s",
            (self.db_name, table),
        )
        exists = cur.fetchone()[0] > 0
        cur.close()
        return exists

    def _repair_table(self, table: str, json_col: str, key_cols, blocked: set) -> int:
        """Remove blocked keys from the JSON column of one table."""
        if not self._table_exists(table):
            print(f"  ⏭️  {table}: table not found, skipping")
            return 0

        cur = self.connection.cursor(dictionary=True)
        select_cols = ", ".join([f"`{c}`" for c in key_cols] + [f"`{json_col}`"])
        cur.execute(f"SELECT {select_cols} FROM `{table}`")
        rows = cur.fetchall()
        cur.close()

        repaired = 0
        for row in rows:
            raw = row[json_col]
            if not raw:
                continue

            import json
            try:
                data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            except (ValueError, TypeError):
                print(f"    ⚠️  Row {row.get(key_cols[0])}: invalid JSON, skipping")
                continue

            if not isinstance(data, dict):
                continue

            # Detect blocked keys and any legacy prefix-based control keys.
            offending = [
                k for k in data.keys()
                if k in blocked or k.startswith(('responses_', 'unsaved_', 'form_'))
            ]
            if not offending:
                continue

            cleaned = {k: v for k, v in data.items() if k not in offending}
            new_raw = json.dumps(cleaned)

            where = " AND ".join([f"`{c}` = %s" for c in key_cols])
            params = tuple(row[c] for c in key_cols) + (new_raw,)
            before, after = len(raw), len(new_raw)
            ident = ", ".join(f"{c}={row[c]}" for c in key_cols)

            if self.dry_run:
                print(f"    [dry-run] {table} ({ident}): "
                      f"{before:,} -> {after:,} bytes, would drop {offending}")
            else:
                upd = self.connection.cursor()
                upd.execute(
                    f"UPDATE `{table}` SET `{json_col}` = %s WHERE {where}", params
                )
                upd.close()
                print(f"    ✅ {table} ({ident}): "
                      f"{before:,} -> {after:,} bytes, dropped {offending}")
            repaired += 1

        if not self.dry_run and repaired:
            self.connection.commit()
        return repaired

    def run(self):
        print("=" * 64)
        print("🧹 JSON Persistence Repair")
        print("=" * 64)
        print(f"Database: {self.db_name}")
        print(f"Host: {self.db_config['host']}")
        print(f"Mode: {'DRY RUN' if self.dry_run else 'REPAIR'}")
        print("=" * 64)

        if not self.connect():
            return False

        try:
            total = 0
            print("\n📋 iesg_responses (ESG Ready Questionnaire)")
            total += self._repair_table(
                'iesg_responses', 'response_data', ('id',), IESG_BLOCKED
            )

            print("\n📋 sedg_disclosures (SEDG Disclosure)")
            total += self._repair_table(
                'sedg_disclosures', 'sedg_data', ('id',), SEDG_BLOCKED
            )

            print("\n" + "=" * 64)
            if total == 0:
                print("✅ Nothing to repair - all rows are already clean")
            elif self.dry_run:
                print(f"🔍 Dry run complete: {total} row(s) would be repaired")
            else:
                print(f"🎉 Repair complete: {total} row(s) cleaned")
            print("=" * 64)
            return True
        finally:
            self.disconnect()


def main():
    parser = argparse.ArgumentParser(description="Repair polluted JSON persistence rows")
    parser.add_argument('--dry-run', action='store_true',
                        help="Show what would change without writing")
    args = parser.parse_args()

    repair = PayloadRepair(dry_run=args.dry_run)
    return 0 if repair.run() else 1


if __name__ == '__main__':
    sys.exit(main())
