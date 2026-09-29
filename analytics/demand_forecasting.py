import heapq
import pandas as pd
import numpy as np
from datetime import datetime

from load import execute_dw_query, execute_oltp_query


def load_monthly_sales():
    """Load monthly sales totals from the warehouse fact table."""
    query = """
        SELECT
            dd.year,
            dd.month,
            SUM(fs.revenue_after_discount) AS revenue,
            SUM(fs.quantity) AS units_sold
        FROM fact_sales fs
        JOIN dim_date dd ON fs.date_key = dd.date_key
        WHERE fs.order_status != 'cancelled'
        GROUP BY dd.year, dd.month
        ORDER BY dd.year, dd.month
    """
    return execute_dw_query(query)


def calculate_moving_average(series, window=3):
    """Simple moving average for baseline trend."""
    return series.rolling(window=window, min_periods=1).mean()


def forecast_next_period(revenue_series, window=3):
    """Forecast next period using weighted moving average (DSA: sliding window).

    Weights: more recent months weight heavier.
    """
    weights = np.arange(1, window + 1, dtype=float)
    weights = weights / weights.sum()
    last_window = revenue_series.iloc[-window:].astype(float).values
    forecast = float(np.dot(weights, last_window))
    return forecast


class OrderPriorityQueue:
    """Priority queue for processing orders by urgency (DSA: heap-based PQ)."""

    def __init__(self):
        self._heap = []

    def push(self, priority, order_id, amount):
        heapq.heappush(self._heap, (priority, order_id, amount))

    def pop(self):
        return heapq.heappop(self._heap)

    def __len__(self):
        return len(self._heap)


def build_order_priority_analysis():
    """Simulate priority order processing to demonstrate heap-based queue."""
    orders = execute_oltp_query("""
        SELECT
            o.order_id,
            o.customer_id,
            SUM(oi.line_total) AS total_amount,
            o.status,
            o.order_date
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.status != 'cancelled'
        GROUP BY o.order_id, o.customer_id, o.status, o.order_date
        LIMIT 5000
    """)

    pq = OrderPriorityQueue()

    priority_map = {1: 'urgent', 2: 'high', 3: 'normal', 4: 'low'}

    for _, row in orders.iterrows():
        amount = row['total_amount'] or 0
        order_date = pd.to_datetime(row['order_date'])
        days_ago = (pd.Timestamp.today() - order_date).days

        if amount >= 50000:
            priority = 1
        elif days_ago <= 7:
            priority = 2
        elif amount >= 10000:
            priority = 3
        else:
            priority = 4
        pq.push(priority, row['order_id'], amount)

    processed = []
    while len(pq) > 0:
        priority, order_id, amount = pq.pop()
        processed.append({
            'order_id': order_id,
            'priority': priority_map[priority],
            'amount': amount,
        })

    return pd.DataFrame(processed)


if __name__ == '__main__':
    print("=" * 60)
    print("  DataFusion — Demand Forecasting & Sales Analytics")
    print("=" * 60)

    monthly = load_monthly_sales()
    if monthly.empty:
        print("  No monthly sales data found. Run the ETL first.")
    else:
        print(f"\n[1] Monthly sales ({len(monthly)} months):")
        monthly['baseline'] = calculate_moving_average(monthly['revenue'])
        print(monthly.tail(6).to_string(index=False))

        forecast = forecast_next_period(monthly['revenue'])
        last_month = monthly.iloc[-1]
        last_rev = float(last_month['revenue'])
        print(f"\n[2] Forecast for next month (weighted moving average):")
        print(f"    Last actual:  {last_rev:.2f}")
        print(f"    Forecast:     {forecast:.2f}")
        print(f"    Change:       {((forecast - last_rev) / last_rev * 100):+.1f}%")

        biggest = monthly.sort_values('revenue', ascending=False).head(5)
        print(f"\n[3] Top 5 revenue months:")
        print(biggest[['year', 'month', 'revenue', 'units_sold']].to_string(index=False))

    print("\n[4] Order priority processing (heap-based queue):")
    priority_df = build_order_priority_analysis()
    if not priority_df.empty:
        summary = priority_df.groupby('priority').agg(
            orders=('order_id', 'count'),
            total_value=('amount', 'sum'),
        ).reset_index()
        print(summary.to_string(index=False))
    else:
        print("  No orders to process.")

    print("\nDone!")