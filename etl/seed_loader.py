import pandas as pd
from sqlalchemy import create_engine
import os

DB_URI = "mysql+mysqlconnector://datafusion:datafusion123@localhost/datafusion_oltp"
engine = create_engine(DB_URI)
RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')

TABLES = [
    ('products.csv', 'products'),
    ('suppliers.csv', 'suppliers'),
    ('customers.csv', 'customers'),
    ('warehouses.csv', 'warehouses'),
    ('inventory.csv', 'inventory'),
    ('orders.csv', 'orders'),
    ('order_items.csv', 'order_items'),
    ('product_suppliers.csv', 'product_suppliers'),
    ('shipments.csv', 'shipments'),
]

if __name__ == '__main__':
    print("Loading seed data into MySQL...")
    with engine.connect() as conn:
        for csv_file, table_name in TABLES:
            path = os.path.join(RAW_DIR, csv_file)
            df = pd.read_csv(path)
            df.to_sql(table_name, conn, if_exists='append', index=False, chunksize=500)
            print(f"  Loaded {len(df)} rows into {table_name}")

    print("Seed data loaded successfully!")
