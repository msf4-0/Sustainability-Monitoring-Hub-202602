"""
COSIRI Documents Migration
Adds the file_content column the COSIRI page stores uploaded files in, and
makes file_path optional (files are stored in the database, not on disk).

Databases created with scripts/setup_db.py between 10 Feb 2026 and this fix
are missing the column, which breaks listing and uploading COSIRI documents
("Unknown column 'cd.file_content'"). Safe to run more than once.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mysql.connector
from mysql.connector import Error
from config.settings import config


def get_columns(cursor):
    """Return {column_name: is_nullable} for the cosiri_documents table"""
    cursor.execute("""
        SELECT COLUMN_NAME, IS_NULLABLE
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'cosiri_documents'
    """, (config.database_config['database'],))
    return {name: nullable == 'YES' for name, nullable in cursor.fetchall()}


def migrate():
    """Add file_content and make file_path nullable if needed"""
    try:
        connection = mysql.connector.connect(**config.database_config)
        cursor = connection.cursor()

        columns = get_columns(cursor)
        if not columns:
            print("❌ Table cosiri_documents not found. Run scripts/setup_db.py first.")
            return False

        if 'file_content' in columns:
            print("  ⏭️  file_content column already exists")
        else:
            print("📝 Adding file_content column...")
            cursor.execute("ALTER TABLE cosiri_documents ADD COLUMN file_content LONGBLOB NULL AFTER file_path")
            connection.commit()
            print("  ✅ Added file_content (LONGBLOB)")

        if columns.get('file_path'):
            print("  ⏭️  file_path is already nullable")
        else:
            print("📝 Making file_path nullable...")
            cursor.execute("ALTER TABLE cosiri_documents MODIFY COLUMN file_path VARCHAR(500) NULL")
            connection.commit()
            print("  ✅ file_path is now nullable")

        columns = get_columns(cursor)
        cursor.close()
        connection.close()

        ok = 'file_content' in columns and columns.get('file_path')
        print("\n🎉 Migration completed successfully!" if ok else "\n❌ Verification failed")
        return ok

    except Error as e:
        print(f"❌ Migration failed: {e}")
        return False


def main():
    print("=" * 70)
    print("📄 COSIRI Documents Migration")
    print("=" * 70)
    print(f"\n🔗 Database: {config.database_config['database']}")
    print(f"   Host: {config.database_config['host']}\n")
    return migrate()


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
