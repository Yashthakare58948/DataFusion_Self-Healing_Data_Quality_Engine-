import subprocess
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cloud'))
from db_config import DBConfig

OUT_DIR = os.path.join(os.path.dirname(__file__), 'dumps')
os.makedirs(OUT_DIR, exist_ok=True)

DB_NAMES = ['datafusion_oltp', 'datafusion_dw']


def export_for_cloud(db_name):
    """Dump the local database to a .sql file ready for cloud import."""
    cfg = DBConfig('local')
    creds = cfg.LOCAL
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    out = os.path.join(OUT_DIR, f'{db_name}_{timestamp}.sql')

    cmd = [
        'mysqldump',
        f'-u{creds["user"]}',
        f'-p{creds["password"]}',
        '--routines',
        '--triggers',
        '--single-transaction',
        db_name,
    ]

    print(f"Exporting {db_name} -> {out}")
    with open(out, 'w', encoding='utf-8') as f:
        result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
    if result.returncode != 0:
        print(f"  WARNING: mysqldump failed: {result.stderr[:300]}")
    else:
        size_kb = os.path.getsize(out) / 1024
        print(f"  Export complete ({size_kb:.1f} KB)")


if __name__ == '__main__':
    print("=" * 60)
    print("  DataFusion — Export Local DB for Cloud Deployment")
    print("=" * 60)
    print("  Environment: check DATAFUSION_LOCAL_PASSWORD if connection fails")
    for db in DB_NAMES:
        export_for_cloud(db)
    print("\nDone! Import these .sql files into your cloud MySQL instance.")