# DataFusion — Autonomous Data Quality & Self-Healing ETL Engine

An industrial-grade supply chain analytics platform showcasing **PL/SQL**, **MySQL**,
**Data Warehousing**, **Python**, **DSA**, and **Cloud** — with a self-healing data
quality engine at its core.

**46,000+ records** flow through a real ETL pipeline into an OLTP database, a star-schema
data warehouse, then into analytics that detect and auto-correct data anomalies.

---

## 🏗️ Architecture

```
Raw CSV (46K records)
        │
        ▼ Python ETL Pipeline (Bloom Filter dedup, merge sort, anomaly detection)
        ▼
   MySQL OLTP (3NF) ── Stored Procedures / Triggers / Functions
        │
        ▼ SQL ETL (procedures)
        ▼
   Data Warehouse (Star Schema: 5 dims + 3 facts, SCD Type 2)
        │
        ├──► Analytics: Dijkstra sourcing optimizer, demand forecast, priority queue
        ├──► Self-Healing Quality Engine (nulls, dups, ranges, stats, schema drift)
        ├──► Matplotlib/Seaborn dashboards + insights
        └──► Cloud export + config to switch between local / cloud MySQL
```

---

## 📁 Project Layout

```
datafusion/
├── database/
│   ├── oltp_schema.sql          # 11 normalized tables (3NF)
│   ├── oltp_procedures.sql      # 7 stored procedures (PL/SQL-style)
│   ├── oltp_triggers.sql        # 6 triggers + 3 functions
│   ├── warehouse_schema.sql     # Star schema + dim_date population
│   └── warehouse_etl.sql        # 8 ETL procedures + master orchestrator
├── etl/
│   ├── generate_data.py         # Faker-based synthetic data (46K records)
│   ├── seed_loader.py           # Bulk-load CSVs into OLTP
│   ├── extract.py               # Extract layer
│   ├── transform.py             # DSA: BloomFilter, MergeSort, SlidingWindow, TopoSort
│   ├── load.py                  # Load into OLTP + trigger warehouse ETL
│   ├── etl_pipeline.py          # Orchestrator (runs in ~9 seconds)
│   ├── quality_engine.py        # Self-healing data quality engine ⭐
│   └── inject_dirty.py          # Simulates dirty incoming data for testing
├── analytics/
│   ├── inventory_optimizer.py   # Dijkstra's algorithm on supplier graph ⭐
│   ├── demand_forecasting.py    # Weighted moving average + heap priority queue
│   ├── sales_dashboard.py       # 4 matplotlib/seaborn charts
│   └── reports/                 # Generated PNG dashboards
├── cloud/
│   ├── db_config.py             # Central local/cloud MySQL config
│   ├── deploy.py                # mysqldump exports for cloud import
│   └── README.md                # Cloud deployment guide
├── tests/
│   └── test_pipeline.py         # 6 unit tests (all pass)
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup

### Prerequisites

- Python 3.10+
- MySQL 8.0 (running on localhost:3306)
- pip

### 1. Install dependencies

```powershell
pip install -r requirements.txt
```

### 2. Create MySQL user and schemas

```powershell
mysql -u root -p -e "CREATE USER 'datafusion'@'localhost' IDENTIFIED BY 'datafusion123';
GRANT ALL PRIVILEGES ON *.* TO 'datafusion'@'localhost'; FLUSH PRIVILEGES;"
```

```powershell
mysql -u datafusion -pdatafusion123 -e "source database/oltp_schema.sql"
mysql -u datafusion -pdatafusion123 -e "source database/oltp_procedures.sql"
mysql -u datafusion -pdatafusion123 -e "source database/oltp_triggers.sql"
mysql -u datafusion -pdatafusion123 -e "source database/warehouse_schema.sql"
mysql -u datafusion -pdatafusion123 -e "source database/warehouse_etl.sql"
```

> Note: PowerShell does not support `<` redirection; use the `-e "source ..."` form above.

### 3. Generate + load seed data (if not already loaded)

```powershell
python etl/generate_data.py      # creates 46K+ CSV records in data/raw/
python etl/seed_loader.py        # loads CSVs into MySQL OLTP
```

### 4. Load the Data Warehouse

```powershell
mysql -u datafusion -pdatafusion123 -e "USE datafusion_dw; CALL sp_run_full_etl();"
```

---

## ▶️ Run Everything

```powershell
# 1. Full ETL pipeline (~9s): extract -> transform -> load OLTP -> load DW
python etl/etl_pipeline.py

# 2. Inject dirty data to demonstrate self-healing
python etl/inject_dirty.py

# 3. Self-healing quality engine (detect + fix + log to MySQL)
python etl/quality_engine.py

# 4. Analytics
python analytics/inventory_optimizer.py   # Dijkstra sourcing routes
python analytics/demand_forecasting.py    # Forecast + priority queue
python analytics/sales_dashboard.py       # 4 charts into analytics/reports/

# 5. Tests
python tests/test_pipeline.py             # 6/6 pass
```

---

## 💾 Database Contents

| Layer | Table | Rows |
|-------|-------|------|
| OLTP | products | 500 |
| OLTP | suppliers / customers / warehouses | 50 / 1000 / 5 |
| OLTP | inventory | 1,750 |
| OLTP | orders | 10,000 |
| OLTP | order_items / shipments / product_suppliers | 24,947 / 7,133 / 984 |
| DW | dim_product / dim_supplier / dim_warehouse / dim_customer / dim_date | 500 / 50 / 5 / 1000 / 2191 |
| DW | fact_sales / fact_inventory / fact_shipments | 24,947 / 1,750 / 7,133 |

---

## 🧠 DSA Modules

| Algorithm | Where | Why |
|-----------|-------|-----|
| Bloom Filter | transform.py, quality_engine.py | Fast duplicate detection on bulk streams |
| Merge Sort | transform.py | Priority ordering of records |
| Sliding Window + Z-score | transform.py | Statistical anomaly detection |
| Topological Sort | transform.py, etl_pipeline.py | Order ETL loads by dependencies |
| Dijkstra (heap) | inventory_optimizer.py | Cheapest sourcing route in supplier graph |
| Priority Queue (heap) | demand_forecasting.py | Order processing by urgency |

---

## ☁️ Cloud Deployment

Switching the entire project between local and cloud MySQL is a single env var:

```powershell
$env:DATAFUSION_ENV = "cloud"
$env:DATAFUSION_CLOUD_HOST = "<host>"
$env:DATAFUSION_CLOUD_USER = "<user>"
$env:DATAFUSION_CLOUD_PASSWORD = "<password>"
```

Provision a free MySQL instance (Aiven / Railway / Clever Cloud), import the dumps from
`python cloud/deploy.py`, and re-run the pipeline pointing at the cloud. Full guide in
`cloud/README.md`.

---

## 🏆 Resume Bullet Points

- Designed a **data warehouse star schema** (5 dims + 3 fact tables, SCD Type 2) fed by a
  Python ETL pipeline processing **46,000+ records** end-to-end in ~9 seconds.
- Wrote **7 MySQL stored procedures, 6 triggers, and 3 functions** implementing order
  placement, reorder logic, audit logging, and inventory alerts.
- Built an **autonomous data quality engine** that detected and self-healed **496 records**
  across 4 anomaly types (duplicates, nulls, out-of-range, statistical spikes) with a
  Bloom-filter-based duplicate detector and sliding-window anomaly detection.
- Implemented **DSA algorithms** in production code — Dijkstra's shortest path for supplier
  sourcing, heap-based priority queues for order processing, and topological sort for ETL
  dependency ordering.
- Deployed the database to **cloud MySQL** via automated exports with environment-based
  connection switching between local and cloud instances.