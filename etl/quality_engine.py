import pandas as pd
import numpy as np
from collections import defaultdict
from datetime import datetime
from sqlalchemy import text

from load import execute_oltp_query, get_engine, OLTP_URI


class DataQualityEngine:
    def __init__(self):
        self.issues = []
        self.heals = 0
        self.log = []

    def _log(self, table, anomaly_type, records, action, severity):
        entry = {
            'pipeline_run': f"DQ-{datetime.now().strftime('%Y%m%d%H%M')}",
            'table_name': table,
            'anomaly_type': anomaly_type,
            'records_affected': records,
            'action_taken': action,
            'severity': severity,
            'detected_at': datetime.now(),
        }
        self.log.append(entry)
        self.issues.append({**entry})
        if records > 0:
            self.heals += records

    # ------------------------------------------------------------------
    # 1. NULL / missing value detection + auto-fill (hash-map pattern library)
    # ------------------------------------------------------------------
    def check_and_fix_nulls(self, df, table):
        null_map = defaultdict(list)
        for col in df.columns:
            n = df[col].isna().sum()
            if n > 0:
                null_map[col] = df[df[col].isna()].index.tolist()

        if not null_map:
            return df, 0

        for col, idx_list in null_map.items():
            # Heuristic fill strategies based on data type
            if pd.api.types.is_numeric_dtype(df[col]):
                fill_value = df[col].median()
                df.loc[idx_list, col] = fill_value
                action = f"Filled {len(idx_list)} nulls in {col} with median {fill_value}"
            else:
                fill_value = 'Unknown'
                df.loc[idx_list, col] = fill_value
                action = f"Filled {len(idx_list)} nulls in {col} with '{fill_value}'"

            severity = 'medium' if len(idx_list) > 100 else 'low'
            self._log(table, f'MISSING_VALUE_{col.upper()}', len(idx_list), action, severity)

        return df, sum(len(v) for v in null_map.values())

    # ------------------------------------------------------------------
    # 2. Duplicate detection using Bloom Filter (DSA)
    # ------------------------------------------------------------------
    def check_duplicates(self, df, table, key_cols):
        from transform import BloomFilter

        # Size the filter for ~0.1% false positive rate: m = -n*ln(p)/(ln2)^2
        n_expected = len(df) * 2 + 1000
        p = 0.001
        bf_size = int(-n_expected * np.log(p) / (np.log(2) ** 2)) + 1
        hash_count = max(3, int(bf_size / n_expected * np.log(2)))

        bf = BloomFilter(size=bf_size, hash_count=hash_count)
        dup_indices = []

        for i, row in df.iterrows():
            key = tuple(row[c] for c in key_cols)
            if bf.might_contain(key):
                dup_indices.append(i)
            else:
                bf.add(key)

        if dup_indices:
            df = df.drop(index=dup_indices).reset_index(drop=True)
            self._log(table, f'DUPLICATE_{"_".join(key_cols).upper()}', len(dup_indices),
                      f"Dropped {len(dup_indices)} duplicate rows via Bloom Filter", 'medium')
        return df, len(dup_indices)

    # ------------------------------------------------------------------
    # 3. Range / bounds validation with auto-clipping (Sliding Window)
    # ------------------------------------------------------------------
    def check_ranges(self, df, table, column, min_val=None, max_val=None):
        issues = 0
        if min_val is not None:
            outliers = df[df[column] < min_val]
            if not outliers.empty:
                df.loc[df[column] < min_val, column] = min_val
                issues += len(outliers)
        if max_val is not None:
            outliers = df[df[column] > max_val]
            if not outliers.empty:
                df.loc[df[column] > max_val, column] = max_val
                issues += len(outliers)

        if issues > 0:
            self._log(table, f'OUT_OF_RANGE_{column.upper()}', issues,
                      f"Clipped {issues} values in {column} to [{min_val}, {max_val}]", 'medium')
        return df, issues

    # ------------------------------------------------------------------
    # 4. Schema drift detection (compare expected vs actual columns)
    # ------------------------------------------------------------------
    def check_schema_drift(self, df, table, expected_columns):
        missing = set(expected_columns) - set(df.columns)
        extra = set(df.columns) - set(expected_columns)

        if missing or extra:
            self._log(table, 'SCHEMA_DRIFT',
                      len(missing) + len(extra),
                      f"Drift detected: missing={list(missing)}, extra={list(extra)}", 'high')
        return len(missing) + len(extra)

    # ------------------------------------------------------------------
    # 5. Statistical anomaly detection (Z-score with sliding window)
    # ------------------------------------------------------------------
    def check_statistical_anomalies(self, df, table, column, window=50, threshold=3.0):
        from transform import SlidingWindowAnomalyDetector

        values = df[column].astype(float).values
        detector = SlidingWindowAnomalyDetector(window_size=window, threshold=threshold)
        detection = detector.detect(pd.Series(values))

        anomaly_flags = detection[len(detection) - len(values):] if len(detection) > len(values) else detection
        anomalies = [i for i, flag in enumerate(anomaly_flags) if flag and i >= window]

        if anomalies:
            self._log(table, f'STATISTICAL_ANOMALY_{column.upper()}', len(anomalies),
                      f"Detected {len(anomalies)} statistical anomalies in {column}", 'medium')
        return anomalies

    # ------------------------------------------------------------------
    # 6. Self-healing validation on MySQL data + log to data_quality_log
    # ------------------------------------------------------------------
    def run_on_oltp_tables(self):
        from load import get_engine, OLTP_URI
        engine = get_engine(OLTP_URI)

        tables_to_check = {
            'products': {
                'query': "SELECT * FROM products",
                'key_cols': ['product_id'],
                'ranges': {'unit_price': (1, 100000)},
            },
            'orders': {
                'query': "SELECT * FROM orders",
                'key_cols': ['order_id'],
                'ranges': {'total_amount': (0, 100000000)},
            },
            'order_items': {
                'query': "SELECT order_id, product_id, quantity, unit_price FROM order_items",
                'key_cols': ['order_id', 'product_id'],
                'ranges': {'quantity': (1, 1000), 'unit_price': (1, 100000)},
            },
            'inventory': {
                'query': "SELECT * FROM inventory",
                'key_cols': ['inventory_id'],
                'ranges': {'quantity': (0, 100000)},
            },
        }

        for table, config in tables_to_check.items():
            df = execute_oltp_query(config['query'])
            print(f"\n  Checking {table} ({len(df)} rows)")

            df, n = self.check_and_fix_nulls(df, table)
            if n:
                print(f"    - Fixed {n} null values")

            df, n = self.check_duplicates(df, table, config['key_cols'])
            if n:
                print(f"    - Removed {n} duplicates")

            for col, (lo, hi) in config['ranges'].items():
                if col in df.columns:
                    df, n = self.check_ranges(df, table, col, lo, hi)
                    if n:
                        print(f"    - Clipped {n} out-of-range in {col}")

        engine.dispose()

    def run_on_staging_tables(self):
        """Run quality checks on injected dirty staging data (self-healing demo)."""
        engine = get_engine(OLTP_URI)

        with engine.connect() as conn:
            tables = []
            result = conn.execute(text(
                "SHOW TABLES LIKE '%_staging'"
            ))
            for row in result.fetchall():
                tables.append(row[0])

        for staging_table in tables:
            table = staging_table.replace('_staging', '')
            df = pd.read_sql(f"SELECT * FROM {staging_table}", engine)
            print(f"\n  Checking {staging_table} ({len(df)} rows, dirty data)")

            key_cols = {
                'orders': ['order_id'],
                'inventory': ['inventory_id'],
                'order_items': ['order_id', 'product_id'],
            }.get(table, None)

            if key_cols:
                df, n = self.check_duplicates(df, table, key_cols)
                if n:
                    print(f"    + Healed {n} duplicate rows")

            df, n = self.check_and_fix_nulls(df, table)
            if n:
                print(f"    + Healed {n} null/missing values")

            ranges = {
                'orders': {'total_amount': (0, 100000000)},
                'inventory': {'quantity': (0, 100000)},
                'order_items': {'quantity': (1, 1000)},
            }.get(table, {})

            for col, (lo, hi) in ranges.items():
                if col in df.columns:
                    df, n = self.check_ranges(df, table, col, lo, hi)
                    if n:
                        print(f"    + Healed {n} out-of-range values in {col}")

        engine.dispose()

    # ------------------------------------------------------------------
    def persist_log(self):
        engine = get_engine(OLTP_URI)

        with engine.begin() as conn:
            for entry in self.log:
                conn.execute(
                    text("""
                        INSERT INTO data_quality_log
                        (pipeline_run, table_name, anomaly_type, records_affected, action_taken, severity)
                        VALUES (:run, :table, :type, :records, :action, :severity)
                    """),
                    {
                        'run': entry['pipeline_run'],
                        'table': entry['table_name'],
                        'type': entry['anomaly_type'],
                        'records': entry['records_affected'],
                        'action': entry['action_taken'],
                        'severity': entry['severity'],
                    }
                )
        engine.dispose()

    # ------------------------------------------------------------------
    # Master run: detect + heal + log
    # ------------------------------------------------------------------
    def run(self, persist=True):
        print("=" * 60)
        print("  DataFusion Self-Healing Data Quality Engine")
        print("=" * 60)

        self.run_on_oltp_tables()
        self.run_on_staging_tables()

        print("\n" + "=" * 60)
        print(f"  Summary: {self.heals} records self-healed")
        print(f"           {len(self.issues)} quality issues detected")
        print(f"           {len(self.log)} log entries")
        print("=" * 60)

        if persist:
            self.persist_log()
            print("  Quality log persisted to MySQL data_quality_log")

        return self

    @staticmethod
    def get_quality_report():
        engine = get_engine(OLTP_URI)
        with engine.connect() as conn:
            df = pd.read_sql("SELECT * FROM data_quality_log ORDER BY log_id DESC", conn)
        engine.dispose()
        return df


if __name__ == '__main__':
    engine = DataQualityEngine()
    engine.run()
