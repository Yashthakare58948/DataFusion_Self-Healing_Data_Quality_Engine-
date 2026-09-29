import os
import sys
import subprocess
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
ETL_DIR = os.path.join(ROOT, 'etl')
ANALYTICS_DIR = os.path.join(ROOT, 'analytics')


def run_module(path):
    print(f"\n{'#' * 70}")
    print(f"# Running {os.path.relpath(path, ROOT)}")
    print(f"{'#' * 70}\n")
    env = dict(os.environ)
    env['PYTHONPATH'] = ';'.join([os.path.join(ROOT, 'etl'),
                                  os.path.join(ROOT, 'cloud'),
                                  os.path.join(ROOT, 'analytics')])
    start = time.time()
    result = subprocess.run([sys.executable, path], env=env, capture_output=True, text=True)
    elapsed = time.time() - start
    print(result.stdout)
    if result.returncode != 0:
        print(result.stderr)
    print(f"\n--> Finished in {elapsed:.1f}s (exit code {result.returncode})")
    return result.returncode


if __name__ == '__main__':
    steps = [
        os.path.join(ETL_DIR, 'etl_pipeline.py'),
        os.path.join(ETL_DIR, 'inject_dirty.py'),
        os.path.join(ETL_DIR, 'quality_engine.py'),
        os.path.join(ANALYTICS_DIR, 'inventory_optimizer.py'),
        os.path.join(ANALYTICS_DIR, 'demand_forecasting.py'),
        os.path.join(ANALYTICS_DIR, 'sales_dashboard.py'),
        os.path.join(ROOT, 'tests', 'test_pipeline.py'),
    ]

    print("=" * 70)
    print("  DataFusion — Full Project Runner")
    print(f"  Project root: {ROOT}")
    print("=" * 70)

    failures = 0
    for step in steps:
        if run_module(step) != 0:
            failures += 1

    print(f"\n{'=' * 70}")
    if failures:
        print(f"  COMPLETED with {failures} failed step(s)")
    else:
        print("  ALL STEPS PASSED — project is fully functional!")
    print("=" * 70)