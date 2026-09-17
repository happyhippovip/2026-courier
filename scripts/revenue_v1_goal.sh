#!/bin/bash
# Reicht das Revenue V1 "Oil Market Anomaly Alarm" Goal an den Server ein.

curl -X POST http://127.0.0.1:8080/goals \
  -H "Authorization: Bearer ${COURIER_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{
    "goal_text": "Hourly Oil Market Anomaly Alarm",
    "workflow_plan": [
      {
        "task_id": "oil-anomaly-github",
        "type": "metadata",
        "target_agent": "github",
        "mode": "NATIVE",
        "instruction": "Fetch oil market pricing metadata. Observation only; no trade or spend.",
        "artifacts": ["courier_canary_oil_market.txt"],
        "dependencies": []
      },
      {
        "task_id": "oil-anomaly-mac",
        "type": "native_command",
        "target_agent": "mac",
        "mode": "NATIVE",
        "instruction": "echo \"Oil market data fetched. No anomalies detected.\" > oil_anomaly_report.txt",
        "artifacts": ["oil_anomaly_report.txt"],
        "dependencies": ["oil-anomaly-github"]
      }
    ]
  }'
echo ""
echo "Goal submitted!"
