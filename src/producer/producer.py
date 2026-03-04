"""
Zerobus producer - streams synthetic sensor events into a Delta table.

Run locally: python src/producer/producer.py

Required env vars (set in .env):
  ZEROBUS_SERVER_ENDPOINT   - e.g. https://<workspace-id>.zerobus.<region>.cloud.databricks.com
  DATABRICKS_WORKSPACE_URL  - e.g. https://<workspace>.cloud.databricks.com
  ZEROBUS_TABLE_NAME        - e.g. startups_catalog.dw_zerobus.zerobus_events
  DATABRICKS_CLIENT_ID      - Service principal client ID
  DATABRICKS_CLIENT_SECRET  - Service principal client secret
"""

import logging
import os
import random
import sys
import time
from collections import deque
from datetime import datetime, timezone

from dotenv import load_dotenv
from rich.live import Live
from rich.table import Table
from rich.text import Text

# Suppress SDK logging before import
logging.getLogger("databricks_zerobus_ingest_sdk").setLevel(logging.CRITICAL)
logging.getLogger("zerobus").setLevel(logging.CRITICAL)
os.environ["RUST_LOG"] = "error"

from zerobus import RecordType, StreamConfigurationOptions, TableProperties, ZerobusSdk

# Allow importing the generated protobuf module from the same directory
sys.path.insert(0, os.path.dirname(__file__))
from zerobus_events_pb2 import ZerobusEvent

load_dotenv()

MAX_ROWS = 20
STATUS_COLORS = {"OK": "green", "WARN": "yellow", "CRITICAL": "red"}


def build_table(table_name: str, sent_count: int, recent: deque) -> Table:
    table = Table(title=f"Zerobus Producer | {sent_count} events sent | {table_name}")
    table.add_column("device_id", style="cyan")
    table.add_column("timestamp", style="white")
    table.add_column("metric_value", justify="right", style="magenta")
    table.add_column("status", justify="center")
    table.add_column("ack", justify="center", style="dim")

    for row in recent:
        status_text = Text(row["status"], style=STATUS_COLORS.get(row["status"], "white"))
        table.add_row(
            row["device_id"],
            row["ts"],
            str(row["metric_value"]),
            status_text,
            row["ack"],
        )
    return table


def main():
    endpoint = os.environ["ZEROBUS_SERVER_ENDPOINT"]
    workspace_url = os.environ["DATABRICKS_WORKSPACE_URL"]
    table_name = os.environ["ZEROBUS_TABLE_NAME"]
    client_id = os.environ["DATABRICKS_CLIENT_ID"]
    client_secret = os.environ["DATABRICKS_CLIENT_SECRET"]

    sdk = ZerobusSdk(host=endpoint, unity_catalog_url=workspace_url)
    table_props = TableProperties(
        table_name=table_name,
        descriptor_proto=ZerobusEvent.DESCRIPTOR,
    )
    options = StreamConfigurationOptions(record_type=RecordType.PROTO)

    stream = sdk.create_stream(
        client_id=client_id,
        client_secret=client_secret,
        table_properties=table_props,
        options=options,
    )

    devices = [f"sensor-{i:02d}" for i in range(1, 6)]
    statuses = ["OK", "WARN", "CRITICAL"]
    status_weights = [0.8, 0.15, 0.05]

    recent = deque(maxlen=MAX_ROWS)
    sent_count = 0

    with Live(build_table(table_name, sent_count, recent), refresh_per_second=2) as live:
        try:
            while True:
                event = ZerobusEvent(
                    device_id=random.choice(devices),
                    ts=int(time.time() * 1_000_000),
                    metric_value=round(random.uniform(15.0, 35.0), 2),
                    status=random.choices(statuses, weights=status_weights, k=1)[0],
                )

                offset = stream.ingest_record_offset(event.SerializeToString())
                stream.wait_for_offset(offset)
                sent_count += 1

                ts_str = datetime.fromtimestamp(event.ts / 1_000_000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                recent.appendleft({
                    "device_id": event.device_id,
                    "ts": ts_str,
                    "metric_value": event.metric_value,
                    "status": event.status,
                    "ack": f"offset {offset}",
                })
                live.update(build_table(table_name, sent_count, recent))
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    stream.flush()
    stream.close()
    print(f"\nStopped. {sent_count} events sent.")


if __name__ == "__main__":
    main()
