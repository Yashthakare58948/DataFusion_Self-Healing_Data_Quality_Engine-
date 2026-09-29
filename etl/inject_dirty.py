import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from load import get_engine, OLTP_URI


def inject_dirty_orders(n_duplicates=200, n_nulls=150, n_outliers=50):
    """Simulate imperfect incoming data by injecting anomalies into a staging copy."""
    engine = get_engine(OLTP_URI)

    with engine.connect() as conn:
        orders = pd.read_sql("SELECT * FROM orders", conn)

    dirty = orders.sample(n=len(orders), random_state=42).copy()

    # Inject duplicate order_ids (violate PK semantics)
    dup_orders = orders.sample(n=n_duplicates, random_state=7).copy()
    dirty = pd.concat([dirty, dup_orders], ignore_index=True)

    # Inject nulls into payment_method
    null_idx = dirty.sample(n=n_nulls, random_state=21).index
    dirty.loc[null_idx, 'payment_method'] = np.nan

    # Inject outliers into total_amount (negative / absurdly high)
    outlier_idx = dirty.sample(n=n_outliers, random_state=99).index
    dirty.loc[outlier_idx, 'total_amount'] = np.random.choice([-5000, 999999999], n_outliers)

    return dirty


def inject_dirty_inventory(n_invalid=100):
    engine = get_engine(OLTP_URI)
    with engine.connect() as conn:
        inventory = pd.read_sql("SELECT * FROM inventory", conn)

    dirty = inventory.sample(n=len(inventory), random_state=42).copy()
    invalid_idx = dirty.sample(n=n_invalid, random_state=5).index
    dirty.loc[invalid_idx, 'quantity'] = -1  # negative stock is invalid

    return dirty


def staging_load(df, table):
    """Load a dirty dataframe into a staging table for quality checking."""
    engine = get_engine(OLTP_URI)
    with engine.begin() as conn:
        conn.execute(text(f"DROP TABLE IF EXISTS {table}_staging"))
        df.to_sql(f"{table}_staging", conn, index=False)


if __name__ == '__main__':
    print("Injecting dirty data for self-healing demo...")

    dirty_orders = inject_dirty_orders()
    staging_load(dirty_orders, 'orders')
    print(f"  orders_staging: {len(dirty_orders)} rows "
          f"(extra {200} dups, {150} nulls, {50} outliers injected)")

    dirty_inventory = inject_dirty_inventory()
    staging_load(dirty_inventory, 'inventory')
    print(f"  inventory_staging: {len(dirty_inventory)} rows "
          f"({100} negative quantity injected)")
