import os
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np

from load import execute_dw_query, execute_oltp_query

REPORT_DIR = os.path.join(os.path.dirname(__file__), 'reports')
os.makedirs(REPORT_DIR, exist_ok=True)

sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)


def load_sales_trend():
    return execute_dw_query("""
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
    """)


def load_category_revenue():
    return execute_dw_query("""
        SELECT
            dp.category,
            SUM(fs.revenue_after_discount) AS revenue,
            COUNT(DISTINCT fs.order_id) AS orders
        FROM fact_sales fs
        JOIN dim_product dp ON fs.product_key = dp.product_key
        WHERE fs.order_status != 'cancelled'
        GROUP BY dp.category
        ORDER BY revenue DESC
    """)


def load_warehouse_performance():
    return execute_dw_query("""
        SELECT
            dw.warehouse_name,
            dw.region,
            SUM(fs.revenue_after_discount) AS revenue,
            SUM(fs.quantity) AS units
        FROM fact_sales fs
        JOIN dim_warehouse dw ON fs.warehouse_key = dw.warehouse_key
        WHERE fs.order_status != 'cancelled'
        GROUP BY dw.warehouse_name, dw.region
        ORDER BY revenue DESC
    """)


def load_quality_summary():
    return execute_oltp_query("""
        SELECT
            anomaly_type,
            COUNT(*) AS events,
            SUM(records_affected) AS total_affected
        FROM data_quality_log
        GROUP BY anomaly_type
    """)


def plot_1_sales_trend(df):
    df['period'] = df['year'].astype(str) + '-' + df['month'].astype(str).str.zfill(2)
    fig, ax = plt.subplots()
    ax.plot(df['period'], df['revenue'] / 1e6, marker='o', linewidth=2)
    ax.set_title('Monthly Revenue Trend (Rs Millions)')
    ax.set_xlabel('Month')
    ax.set_ylabel('Revenue (Millions)')
    ax.tick_params(axis='x', rotation=45)
    plt.tight_layout()
    path = os.path.join(REPORT_DIR, 'revenue_trend.png')
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def plot_2_category_revenue(df):
    fig, ax = plt.subplots()
    categories = df['category'].tolist()
    values = (df['revenue'] / 1e6).tolist()
    ax.barh(categories[::-1], values[::-1], color='steelblue')
    ax.set_title('Revenue by Category (Rs Millions)')
    ax.set_xlabel('Revenue (Millions)')
    plt.tight_layout()
    path = os.path.join(REPORT_DIR, 'category_revenue.png')
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def plot_3_warehouse(df):
    fig, ax = plt.subplots()
    colors = plt.cm.viridis(np.linspace(0.2, 0.9, len(df)))
    ax.bar(df['warehouse_name'], df['revenue'] / 1e6, color=colors)
    ax.set_title('Revenue by Warehouse (Rs Millions)')
    ax.set_ylabel('Revenue (Millions)')
    ax.set_xlabel('Warehouse')
    plt.tight_layout()
    path = os.path.join(REPORT_DIR, 'warehouse_revenue.png')
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def plot_4_quality(df):
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    axes[0].bar(df['anomaly_type'], df['events'], color='coral')
    axes[0].set_title('Quality Events by Type')
    axes[0].tick_params(axis='x', rotation=30)
    axes[1].bar(df['anomaly_type'], df['total_affected'], color='indianred')
    axes[1].set_title('Records Affected by Anomaly Type')
    axes[1].tick_params(axis='x', rotation=30)
    plt.tight_layout()
    path = os.path.join(REPORT_DIR, 'quality_events.png')
    plt.savefig(path, dpi=120)
    plt.close()
    return path


def generate_dashboard():
    print("=" * 60)
    print("  DataFusion — Analytics Dashboard Generator")
    print("=" * 60)

    trend = load_sales_trend()
    categories = load_category_revenue()
    warehouses = load_warehouse_performance()
    quality = load_quality_summary()

    print(f"\n[1] Sales trend data: {len(trend)} months")
    print(f"[2] Category revenue data: {len(categories)} categories")
    print(f"[3] Warehouse performance: {len(warehouses)} warehouses")
    print(f"[4] Quality summary: {len(quality)} anomaly types")

    paths = [
        plot_1_sales_trend(trend),
        plot_2_category_revenue(categories),
        plot_3_warehouse(warehouses),
        plot_4_quality(quality),
    ]

    print(f"\nReports generated in {REPORT_DIR}:")
    for p in paths:
        print(f"  - {p}")
        if os.path.exists(p):
            size_kb = os.path.getsize(p) / 1024
            print(f"    ({size_kb:.1f} KB)")

    # Text summary
    print("\n" + "=" * 60)
    print("  KEY INSIGHTS")
    print("=" * 60)

    if not trend.empty:
        total_rev = float(trend['revenue'].sum())
        avg_month = float(trend['revenue'].mean())
        best_month = trend.loc[trend['revenue'].idxmax()]
        print(f"  Total revenue: Rs {total_rev:,.0f}")
        print(f"  Avg monthly revenue: Rs {avg_month:,.0f}")
        print(f"  Best month: {best_month['year']}-{best_month['month']:02d} "
              f"(Rs {float(best_month['revenue']):,.0f})")

    if not categories.empty:
        top_cat = categories.iloc[0]
        print(f"  Top category: {top_cat['category']} "
              f"(Rs {float(top_cat['revenue']):,.0f})")

    if not quality.empty:
        print(f"  Total quality events: {int(quality['events'].sum())}, "
              f"records self-healed: {int(quality['total_affected'].sum())}")

    return paths


if __name__ == '__main__':
    generate_dashboard()