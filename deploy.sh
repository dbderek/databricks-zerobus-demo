#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-dev}"
APP_NAME="zerobus-demo-app"
CATALOG="startups_catalog"
SCHEMA="dw_zerobus"
TABLE="zerobus_events"
WAREHOUSE_ID="2cf2b0e904c6805f"

echo "=== Deploying bundle (target: $TARGET) ==="
databricks bundle deploy -t "$TARGET"

echo ""
echo "=== Running setup job ==="
databricks bundle run setup_table -t "$TARGET"

echo ""
echo "=== Granting app service principal permissions ==="
APP_SP=$(databricks apps get "$APP_NAME" -o json | python -c "import json,sys; print(json.load(sys.stdin)['service_principal_client_id'])")
echo "App SP client ID: $APP_SP"

run_sql() {
    databricks api post /api/2.0/sql/statements \
        --json "{\"statement\": \"$1\", \"warehouse_id\": \"$WAREHOUSE_ID\", \"wait_timeout\": \"30s\"}" \
        --profile vm 2>&1 | python -c "import json,sys; d=json.load(sys.stdin); s=d.get('status',{}); print(f'  {s.get(\"state\",\"?\")}: $1')" || true
}

run_sql "GRANT USE CATALOG ON CATALOG $CATALOG TO \`$APP_SP\`"
run_sql "GRANT USE SCHEMA ON SCHEMA $CATALOG.$SCHEMA TO \`$APP_SP\`"
run_sql "GRANT SELECT ON TABLE $CATALOG.$SCHEMA.$TABLE TO \`$APP_SP\`"

echo ""
echo "=== Starting app ==="
databricks bundle run zerobus_app -t "$TARGET"

echo ""
echo "=== Done ==="
echo "App is deploying. Check the Databricks workspace for the app URL."
echo "To start the producer: python src/producer/producer.py"
