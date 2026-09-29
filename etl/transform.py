import pandas as pd
import numpy as np
from collections import defaultdict


class BloomFilter:
    def __init__(self, size=10000, hash_count=3):
        self.size = size
        self.hash_count = hash_count
        self.bit_array = [0] * size

    def _hashes(self, key):
        results = []
        for i in range(self.hash_count):
            h = hash(f"{key}_{i}") % self.size
            results.append(abs(h))
        return results

    def add(self, key):
        for pos in self._hashes(key):
            self.bit_array[pos] = 1

    def might_contain(self, key):
        return all(self.bit_array[pos] for pos in self._hashes(key))


class MergeSorter:
    @staticmethod
    def merge_sort(arr, key=None):
        if len(arr) <= 1:
            return arr
        mid = len(arr) // 2
        left = MergeSorter.merge_sort(arr[:mid], key)
        right = MergeSorter.merge_sort(arr[mid:], key)
        return MergeSorter._merge(left, right, key)

    @staticmethod
    def _merge(left, right, key):
        result = []
        i = j = 0
        while i < len(left) and j < len(right):
            l_val = key(left[i]) if key else left[i]
            r_val = key(right[j]) if key else right[j]
            if l_val <= r_val:
                result.append(left[i])
                i += 1
            else:
                result.append(right[j])
                j += 1
        result.extend(left[i:])
        result.extend(right[j:])
        return result


class SlidingWindowAnomalyDetector:
    def __init__(self, window_size=7, threshold=2.5):
        self.window_size = window_size
        self.threshold = threshold

    def detect(self, series):
        anomalies = []
        values = series.values
        for i in range(len(values)):
            start = max(0, i - self.window_size)
            window = values[start:i]
            if len(window) < 3:
                anomalies.append(False)
                continue
            mean = np.mean(window)
            std = np.std(window)
            if std == 0:
                anomalies.append(False)
            else:
                z_score = abs(values[i] - mean) / std
                anomalies.append(z_score > self.threshold)
        return anomalies


class TopologicalSort:
    def __init__(self):
        self.graph = defaultdict(list)
        self.in_degree = defaultdict(int)

    def add_edge(self, u, v):
        self.graph[u].append(v)
        self.in_degree[v] += 1
        if u not in self.in_degree:
            self.in_degree[u] = 0

    def sort(self):
        queue = [n for n in self.in_degree if self.in_degree[n] == 0]
        result = []
        while queue:
            queue.sort()
            node = queue.pop(0)
            result.append(node)
            for neighbor in self.graph[node]:
                self.in_degree[neighbor] -= 1
                if self.in_degree[neighbor] == 0:
                    queue.append(neighbor)
        if len(result) != len(self.in_degree):
            raise ValueError("Cycle detected in ETL dependency graph")
        return result


def hash_deduplicate(df, key_columns):
    seen = set()
    deduped_rows = []
    for _, row in df.iterrows():
        key = tuple(row[col] for col in key_columns)
        if key not in seen:
            seen.add(key)
            deduped_rows.append(row)
    return pd.DataFrame(deduped_rows, columns=df.columns)


def clean_products(df):
    df['product_name'] = df['product_name'].str.strip().str.title()
    df['category'] = df['category'].str.strip().str.title()
    df['subcategory'] = df['subcategory'].str.strip().str.title()
    df['unit_price'] = df['unit_price'].clip(lower=1.0)
    df['cost_price'] = df['cost_price'].clip(lower=0.5)
    df['weight_kg'] = df['weight_kg'].clip(lower=0.01)
    df['profit_margin'] = ((df['unit_price'] - df['cost_price']) / df['unit_price'] * 100).round(2)
    return df


def clean_orders(df):
    df['order_date'] = pd.to_datetime(df['order_date'])
    df['total_amount'] = df['total_amount'].clip(lower=0)
    df['final_amount'] = df['total_amount'] * (1 - df['discount_pct'] / 100)
    df['final_amount'] = df['final_amount'].round(2)
    return df


def clean_order_items(df):
    df['line_total'] = df['quantity'] * df['unit_price']
    df['line_total'] = df['line_total'].round(2)
    return df


def clean_customers(df):
    df['first_name'] = df['first_name'].str.strip().str.title()
    df['last_name'] = df['last_name'].str.strip().str.title()
    df['full_name'] = df['first_name'] + ' ' + df['last_name']
    return df


def transform_orders_with_anomalies(orders_df):
    detector = SlidingWindowAnomalyDetector(window_size=14, threshold=2.0)
    daily_revenue = orders_df.groupby('order_date')['final_amount'].sum().sort_index()
    anomalies = detector.detect(daily_revenue)
    anomaly_dates = daily_revenue.index[anomalies]
    return orders_df, anomaly_dates.tolist()


def build_etl_dependency_graph():
    topo = TopologicalSort()
    topo.add_edge('products', 'order_items')
    topo.add_edge('suppliers', 'product_suppliers')
    topo.add_edge('customers', 'orders')
    topo.add_edge('warehouses', 'orders')
    topo.add_edge('orders', 'order_items')
    topo.add_edge('orders', 'shipments')
    topo.add_edge('products', 'inventory')
    topo.add_edge('warehouses', 'inventory')
    topo.add_edge('products', 'product_suppliers')
    topo.add_edge('product_suppliers', 'order_items')
    return topo.sort()


def backfill_order_amounts(orders_df, order_items_df):
    """Compute order totals from line items and update orders DataFrame."""
    if order_items_df.empty or orders_df.empty:
        return orders_df
    agg = order_items_df.groupby('order_id')['line_total'].sum().reset_index()
    agg.columns = ['order_id', 'total_amount']
    merged = orders_df.merge(agg, on='order_id', how='left', suffixes=('', '_calc'))
    merged['total_amount'] = merged['total_amount_calc'].fillna(merged['total_amount'])
    merged['final_amount'] = round(merged['total_amount'] * (1 - merged['discount_pct'] / 100), 2)
    merged = merged.drop(columns=['total_amount_calc'])
    return merged


def transform_all(raw_data):
    result = {}
    result['products'] = clean_products(raw_data['products'])
    result['suppliers'] = raw_data['suppliers'].copy()
    result['customers'] = clean_customers(raw_data['customers'])
    result['warehouses'] = raw_data['warehouses'].copy()
    result['inventory'] = raw_data['inventory'].copy()
    result['orders'] = clean_orders(raw_data['orders'])
    result['order_items'] = clean_order_items(raw_data['order_items'])
    result['shipments'] = raw_data['shipments'].copy()
    result['product_suppliers'] = raw_data['product_suppliers'].copy()

    bloom = BloomFilter(size=50000, hash_count=4)
    result['orders'] = hash_deduplicate(result['orders'], ['order_id'])
    for oid in result['orders']['order_id']:
        bloom.add(f"order_{oid}")

    result['order_items'] = hash_deduplicate(result['order_items'], ['order_id', 'product_id'])

    # Backfill order totals from line items
    result['orders'] = backfill_order_amounts(result['orders'], result['order_items'])

    _, anomaly_dates = transform_orders_with_anomalies(result['orders'])
    result['anomaly_dates'] = anomaly_dates
    result['bloom_filter'] = bloom

    return result


if __name__ == '__main__':
    from extract import extract_all
    raw = extract_all()
    print("Raw data extracted.")

    cleaned = transform_all(raw)
    print(f"Transformed {len(cleaned)} tables.")
    print(f"Anomaly dates detected: {len(cleaned['anomaly_dates'])}")

    order = build_etl_dependency_graph()
    print(f"ETL dependency order: {order}")
