import time
import os
from extract import extract_all
from transform import transform_all, build_etl_dependency_graph
from load import load_to_oltp, load_to_dw, execute_oltp_query


def run_pipeline():
    run_id = f"RUN-{int(time.time())}"
    print(f"\n{'='*60}")
    print(f"  DataFusion ETL Pipeline — Run {run_id}")
    print(f"{'='*60}\n")

    start = time.time()

    etl_order = build_etl_dependency_graph()
    print(f"ETL dependency order: {etl_order}\n")

    print("[1/4] EXTRACTING raw data...")
    t = time.time()
    raw_data = extract_all()
    print(f"  Extracted {sum(len(v) for v in raw_data.values() if hasattr(v, 'values'))} rows in {time.time()-t:.2f}s\n")

    print("[2/4] TRANSFORMING data...")
    t = time.time()
    cleaned_data = transform_all(raw_data)
    print(f"  Cleaned {len(cleaned_data)} datasets in {time.time()-t:.2f}s")
    if cleaned_data.get('anomaly_dates'):
        print(f"  Anomaly dates detected: {len(cleaned_data['anomaly_dates'])}")
    print()

    print("[3/4] LOADING to OLTP...")
    t = time.time()
    load_to_oltp(cleaned_data)
    print(f"  OLTP load completed in {time.time()-t:.2f}s\n")

    print("[4/4] LOADING to Data Warehouse...")
    t = time.time()
    load_to_dw()
    print(f"  DW load completed in {time.time()-t:.2f}s\n")

    total = time.time() - start
    print(f"{'='*60}")
    print(f"  Pipeline completed in {total:.2f}s")
    print(f"{'='*60}\n")

    print("Sample OLTP queries:")
    result = execute_oltp_query("SELECT COUNT(*) as total_orders FROM orders")
    print(f"  Total orders: {result['total_orders'].iloc[0]}")
    result = execute_oltp_query("SELECT category, COUNT(*) as cnt FROM products GROUP BY category ORDER BY cnt DESC")
    print(f"  Products by category:\n{result.to_string(index=False)}")

    return run_id


if __name__ == '__main__':
    run_pipeline()
