import os
import sys
import pandas as pd
from sqlalchemy import create_engine, text

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cloud'))
from db_config import DBConfig

_config = DBConfig()
OLTP_URI = _config.oltp_uri()
DW_URI = _config.dw_uri()


def get_engine(uri):
    return create_engine(uri)


def get_table_columns(conn, table):
    result = conn.execute(text(f"SHOW COLUMNS FROM {table}"))
    cols = []
    for row in result.fetchall():
        name, extra = row[0], row[5]
        if 'generated' not in str(extra).lower():
            cols.append(name)
    return cols


def load_to_oltp(cleaned_data, batch_size=1000):
    engine = get_engine(OLTP_URI)
    table_order = [
        'products', 'suppliers', 'customers', 'warehouses',
        'product_suppliers', 'inventory', 'orders', 'order_items', 'shipments'
    ]

    with engine.begin() as conn:
        conn.execute(text("SET FOREIGN_KEY_CHECKS=0"))
        for table in reversed(table_order):
            try:
                conn.execute(text(f"TRUNCATE TABLE {table}"))
            except Exception as e:
                print(f"  Warn clearing {table}: {e}")
        conn.execute(text("SET FOREIGN_KEY_CHECKS=1"))

    with engine.begin() as conn:
        for table in table_order:
            if table in cleaned_data:
                df = cleaned_data[table]
                if isinstance(df, pd.DataFrame):
                    schema_cols = get_table_columns(conn, table)
                    for col in df.columns:
                        if col not in schema_cols:
                            df = df.drop(columns=[col])
                    df.to_sql(table, conn, if_exists='append', index=False, chunksize=batch_size)
                    print(f"  Loaded {len(df)} rows into OLTP.{table}")


def load_to_dw():
    engine = get_engine(DW_URI)
    etl_procedures = [
        "CALL sp_etl_dim_product()",
        "CALL sp_etl_dim_supplier()",
        "CALL sp_etl_dim_warehouse()",
        "CALL sp_etl_dim_customer()",
        "CALL sp_etl_fact_sales()",
        "CALL sp_etl_fact_inventory()",
        "CALL sp_etl_fact_shipments()",
    ]

    with engine.connect() as conn:
        for proc in etl_procedures:
            try:
                conn.execute(text(proc))
                conn.commit()
                print(f"  Executed {proc}")
            except Exception as e:
                print(f"  WARNING {proc}: {e}")


def _clean_result(df):
    """Convert Decimal columns to float for downstream numeric work."""
    from decimal import Decimal
    for col in df.columns:
        if df[col].dtype == object and len(df) > 0 and isinstance(df[col].iloc[0], Decimal):
            df[col] = df[col].astype(float)
    return df


def execute_oltp_query(query):
    engine = get_engine(OLTP_URI)
    with engine.connect() as conn:
        result = conn.execute(text(query))
        return _clean_result(pd.DataFrame(result.fetchall(), columns=result.keys()))


def execute_dw_query(query):
    engine = get_engine(DW_URI)
    with engine.connect() as conn:
        result = conn.execute(text(query))
        return _clean_result(pd.DataFrame(result.fetchall(), columns=result.keys()))


if __name__ == '__main__':
    from extract import extract_all
    from transform import transform_all

    print("Extracting...")
    raw = extract_all()
    print("Transforming...")
    cleaned = transform_all(raw)
    print("Loading to OLTP...")
    load_to_oltp(cleaned)
    print("Loading to Data Warehouse...")
    load_to_dw()
    print("Done!")
