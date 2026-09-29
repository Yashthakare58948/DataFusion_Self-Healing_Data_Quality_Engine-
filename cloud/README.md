# DataFusion — Cloud Deployment Guide

The project runs fully locally, and can be deployed to a cloud MySQL instance
in 3 steps. All connection settings are centralized in `cloud/db_config.py`.

## Option A: Cloud MySQL (recommended for resume)

### Step 1 — Provision a free MySQL instance

Pick one free tier:

| Provider   | Product                        | Free tier notes                          |
|------------|--------------------------------|------------------------------------------|
| Aiven      | MySQL                          | Free plan, 5 GB storage                  |
| Railway    | MySQL                          | $5 credit / trial                        |
| Kaggle     | (not MySQL hosting)            | n/a                                      |
| Clever Cloud | MySQL                       | Small free plan                          |

In the provider dashboard create an instance and note:
- host, port, database name, user, password
- Allowed IPs (enable "anywhere" for demo, or whitelist your IP)

### Step 2 — Import the databases

Using MySQL Workbench or CLI, import the dumps created by:

```
python cloud/deploy.py
```

This produces `cloud/dumps/datafusion_oltp_<timestamp>.sql` and
`cloud/dumps/datafusion_dw_<timestamp>.sql`. Import both into the cloud
instance (the SQL files already create the databases).

Alternatively, point the cloud instance at the schema files directly:

```
mysql -h <host> -P <port> -u <user> -p < database/oltp_schema.sql
mysql -h <host> -P <port> -u <user> -p < database/warehouse_schema.sql
```

then load seed data with `python etl/seed_loader.py` after setting env vars below.

### Step 3 — Point the project at the cloud instance

Set these environment variables, then run any script normally:

```powershell
$env:DATAFUSION_ENV = "cloud"
$env:DATAFUSION_CLOUD_HOST = "<your-host>"
$env:DATAFUSION_CLOUD_PORT = "3306"
$env:DATAFUSION_CLOUD_USER = "<user>"
$env:DATAFUSION_CLOUD_PASSWORD = "<password>"
```

Example:

```powershell
$env:DATAFUSION_ENV="cloud"
python etl/etl_pipeline.py
python analytics/sales_dashboard.py
```

## Option B: Local Only (zero cloud dependency)

The default `DATAFUSION_ENV` is `local`, using MySQL on localhost with the
`datafusion` user. No configuration needed.

## Verification checklist

- [ ] `python etl/etl_pipeline.py` runs and prints OLTP query results
- [ ] `python etl/quality_engine.py` detects + heals injected dirty data
- [ ] `python analytics/sales_dashboard.py` writes 4 PNG reports
- [ ] `python cloud/deploy.py` exports both databases

## Screenshot material for resume / interview

- Run `python analytics/sales_dashboard.py` and screenshot `analytics/reports/*.png`
- Run `python etl/quality_engine.py` and screenshot the self-heal summary
- In MySQL Workbench, show `datafusion_dw.fact_sales` with the star schema ERD