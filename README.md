# Zerobus Ingest Demo

End-to-end demo showing events streaming into a Unity Catalog Delta table via [Zerobus Ingest](https://docs.databricks.com/aws/en/ingestion/zerobus/), visualized in a Databricks App.

Zerobus writes directly to Delta tables with no intermediate message bus. The local producer sends protobuf-encoded sensor events over gRPC, and the Streamlit dashboard shows them arriving in near real-time.

## Architecture

```
Local terminal                  Databricks
┌──────────────┐    gRPC     ┌─────────────────────────┐
│   producer   │ ──────────> │  Zerobus Ingest         │
│  (protobuf)  │             │    ↓                    │
└──────────────┘             │  Delta table            │
                             │    ↓                    │
                             │  Streamlit App (DBSQL)  │
                             └─────────────────────────┘
```

## Project Structure

```
databricks-zerobus-demo/
├── databricks.yml              # DAB bundle config
├── deploy.sh                   # One-command deploy script
├── requirements.txt            # Local Python deps (producer)
├── .env.example                # Template for producer env vars
├── resources/
│   ├── setup_job.yml           # Job resource (table setup notebook)
│   └── zerobus_app.yml         # App resource (Streamlit dashboard)
└── src/
    ├── app/                    # Streamlit dashboard (Databricks App)
    │   ├── app.py
    │   ├── app.yaml
    │   └── requirements.txt
    ├── notebooks/              # Databricks job notebooks
    │   └── setup_table.ipynb   # Creates schema, table, and grants
    └── producer/               # Local Zerobus producer
        ├── producer.py
        ├── zerobus_events.proto
        └── zerobus_events_pb2.py
```

## Prerequisites

- [Databricks CLI](https://docs.databricks.com/dev-tools/cli/install.html) configured with a profile
- Python 3.10+
- A Databricks workspace with:
  - A Unity Catalog catalog and schema
  - A SQL warehouse
  - A service principal with an OAuth secret for Zerobus access

## Setup

### 1. Configure the bundle

Edit `databricks.yml` to set your target workspace profile and variables:

```yaml
variables:
  service_principal_client_id:
    default: "<your-sp-client-id>"
  sql_warehouse_id:
    default: "<your-warehouse-id>"

targets:
  dev:
    workspace:
      profile: <your-databricks-cli-profile>
```

### 2. Configure the producer

```bash
cp .env.example .env
```

Fill in your `.env`:

```
ZEROBUS_SERVER_ENDPOINT=https://<workspace-id>.zerobus.<region>.cloud.databricks.com
DATABRICKS_WORKSPACE_URL=https://<your-workspace>.cloud.databricks.com
ZEROBUS_TABLE_NAME=<catalog>.<schema>.zerobus_events
DATABRICKS_CLIENT_ID=<service-principal-client-id>
DATABRICKS_CLIENT_SECRET=<service-principal-oauth-secret>
```

The Zerobus endpoint follows the format `https://<workspace-id>.zerobus.<region>.cloud.databricks.com`. You can find your workspace ID in the workspace URL.

### 3. Install local dependencies

```bash
pip install -r requirements.txt
```

## Deploy

Run the deploy script to deploy everything in one command:

```bash
./deploy.sh
```

This will:
1. Deploy the bundle (upload files, create job and app resources)
2. Run the setup job (create schema, table, and grant permissions to the producer SP)
3. Grant the app's service principal read access to the catalog, schema, and table
4. Start the Streamlit app

You can also deploy to a specific target:

```bash
./deploy.sh prod
```

### Manual deployment

If you prefer to run steps individually:

```bash
databricks bundle deploy -t dev
databricks bundle run setup_table -t dev
databricks bundle run zerobus_app -t dev
```

## Run the Producer

```bash
python src/producer/producer.py
```

The producer displays a live-updating terminal table showing each record as it's sent and acknowledged:

```
       Zerobus Producer | 42 events sent | catalog.schema.zerobus_events
┏━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━┓
┃ device_id ┃ timestamp           ┃ metric_value ┃  status  ┃    ack    ┃
┡━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━┩
│ sensor-03 │ 2026-03-04 18:52:01 │        28.41 │    OK    │ offset 41 │
│ sensor-01 │ 2026-03-04 18:52:00 │        19.73 │   WARN   │ offset 40 │
│ sensor-05 │ 2026-03-04 18:51:59 │        33.12 │ CRITICAL │ offset 39 │
│ ...       │                     │              │          │           │
└───────────┴─────────────────────┴──────────────┴──────────┴───────────┘
```

Press `Ctrl+C` to stop.

## Dashboard

The Streamlit app auto-refreshes every 5 seconds and shows:

- **KPI row** — total events, unique devices, average metric value
- **Status distribution** — pie chart of OK / WARN / CRITICAL events
- **Metric value over time** — scatter plot color-coded by device
- **Recent events** — table of the last 100 records

## Bundle Variables

| Variable | Description | Where used |
|----------|-------------|------------|
| `service_principal_client_id` | SP client ID for Zerobus table access | Setup job (grants) |
| `sql_warehouse_id` | SQL warehouse for the Streamlit app | App resource binding |

Override at deploy time:

```bash
databricks bundle deploy -t dev --var service_principal_client_id=<id>
```

## How It Works

1. The **producer** runs locally and sends protobuf-encoded sensor events to Zerobus over gRPC
2. **Zerobus Ingest** writes the events directly into a Delta table in Unity Catalog — no Kafka, no Kinesis, no intermediate bus
3. The **Streamlit app** queries the Delta table via a SQL warehouse and displays the results
4. Each record is acknowledged by Zerobus, confirming it has been durably committed to the table
