import pandas as pd
import os

RAW_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'raw')
CLEAN_DIR = os.path.join(os.path.dirname(__file__), '..', 'data', 'clean')
os.makedirs(CLEAN_DIR, exist_ok=True)


def extract_products():
    return pd.read_csv(os.path.join(RAW_DIR, 'products.csv'))


def extract_suppliers():
    return pd.read_csv(os.path.join(RAW_DIR, 'suppliers.csv'))


def extract_customers():
    return pd.read_csv(os.path.join(RAW_DIR, 'customers.csv'))


def extract_warehouses():
    return pd.read_csv(os.path.join(RAW_DIR, 'warehouses.csv'))


def extract_inventory():
    return pd.read_csv(os.path.join(RAW_DIR, 'inventory.csv'))


def extract_orders():
    return pd.read_csv(os.path.join(RAW_DIR, 'orders.csv'))


def extract_order_items():
    return pd.read_csv(os.path.join(RAW_DIR, 'order_items.csv'))


def extract_shipments():
    return pd.read_csv(os.path.join(RAW_DIR, 'shipments.csv'))


def extract_product_suppliers():
    return pd.read_csv(os.path.join(RAW_DIR, 'product_suppliers.csv'))


def extract_all():
    return {
        'products': extract_products(),
        'suppliers': extract_suppliers(),
        'customers': extract_customers(),
        'warehouses': extract_warehouses(),
        'inventory': extract_inventory(),
        'orders': extract_orders(),
        'order_items': extract_order_items(),
        'shipments': extract_shipments(),
        'product_suppliers': extract_product_suppliers(),
    }


if __name__ == '__main__':
    data = extract_all()
    for name, df in data.items():
        print(f"  Extracted {name}: {len(df)} rows, {len(df.columns)} cols")
