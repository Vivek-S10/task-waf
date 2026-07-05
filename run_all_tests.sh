#!/bin/bash
set -e

BASE_URL="http://localhost:8000/api/v1"
MOCK_URL="https://mock.internal.tool"

echo "========================================="
echo "       AGENT WAF COMPREHENSIVE TEST      "
echo "========================================="

echo "[1/11] Health Check..."
HEALTH=$(curl -s "http://localhost:8000/health" | jq -r '.status')
if [ "$HEALTH" != "healthy" ]; then echo "FAIL: Health check failed ($HEALTH)"; exit 1; else echo "PASS"; fi

echo "[2/11] Missing X-Target-URL Header..."
RESP=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/proxy" -H "Content-Type: application/json" -d '{"tool_name": "ReadConfig", "parameters": {}}')
if [ "$RESP" != "400" ]; then echo "FAIL: Expected 400, got $RESP"; exit 1; else echo "PASS"; fi

echo "[3/11] Parameter Size Limit (>2000 chars)..."
BIG_PARAM=$(printf '%*s' 2001 | tr ' ' 'a')
RESP=$(curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "Content-Type: application/json" -d "{\"tool_name\": \"ReadConfig\", \"parameters\": {\"data\": \"$BIG_PARAM\"}}" | jq -r '.detail.reason // empty')
if [[ "$RESP" != *"Parameter size exceeded"* ]]; then echo "FAIL: Expected size blocked, got $RESP"; exit 1; else echo "PASS"; fi

echo "[4/11] Parameter Blocklist (XSS)..."
RESP=$(curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "Content-Type: application/json" -d '{"tool_name": "ReadConfig", "parameters": {"data": "<script>alert(1)</script>"}}' | jq -r '.detail.reason')
if [[ "$RESP" != *"blocklist"* ]]; then echo "FAIL: Expected blocklist violation, got $RESP"; exit 1; else echo "PASS"; fi

echo "[5/11] Parameter Blocklist (SQLi) with Stateful Header..."
RESP=$(curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "X-Agent-ID: sqli_tester" -H "Content-Type: application/json" -d '{"tool_name": "QueryDB", "parameters": {"data": "'\'' OR 1=1; --"}}' | jq -r '.detail.reason')
if [[ "$RESP" != *"blocklist"* ]]; then echo "FAIL: Expected blocklist violation, got $RESP"; exit 1; else echo "PASS"; fi

echo "[6/11] Stateful Sequence Rules (Default: WireTransfer needs VerifyUserIdentity)..."
SESS_ID="sess_$(date +%s)"
RESP1=$(curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "X-Agent-ID: default_agent" -H "X-Session-ID: $SESS_ID" -H "Content-Type: application/json" -d '{"tool_name": "ExecuteWireTransfer", "parameters": {}}' | jq -r '.detail.reason')
if [[ "$RESP1" != *"Sequence violation"* ]]; then echo "FAIL: Expected sequence violation, got $RESP1"; exit 1; else echo "PASS (Blocked without prereq)"; fi

curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "X-Agent-ID: default_agent" -H "X-Session-ID: $SESS_ID" -H "Content-Type: application/json" -d '{"tool_name": "VerifyUserIdentity", "parameters": {}}' > /dev/null
RESP2=$(curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "X-Agent-ID: default_agent" -H "X-Session-ID: $SESS_ID" -H "Content-Type: application/json" -d '{"tool_name": "ExecuteWireTransfer", "parameters": {}}' | jq -r '.status')
if [[ "$RESP2" != "success" ]]; then echo "FAIL: Expected success after prereq, got $RESP2"; exit 1; else echo "PASS (Allowed after prereq)"; fi

echo "[7/11] Stateless Rate Limit (Fallback to IP)..."
# Wait 1 sec just to be safe
sleep 1
SUCCESS_COUNT=0
BLOCK_COUNT=0
for i in {1..7}; do
  RES=$(curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "Content-Type: application/json" -d '{"tool_name": "Ping", "parameters": {}}')
  if echo "$RES" | grep -q '"status":"success"'; then
    SUCCESS_COUNT=$((SUCCESS_COUNT+1))
  elif echo "$RES" | grep -q 'Rate limit exceeded'; then
    BLOCK_COUNT=$((BLOCK_COUNT+1))
  fi
done
if [ "$BLOCK_COUNT" -lt 1 ]; then echo "FAIL: Expected rate limit to block, but got $BLOCK_COUNT blocks and $SUCCESS_COUNT successes"; exit 1; else echo "PASS"; fi

echo "[8/11] Registry API (Create Configuration)..."
AGENT="custom_agent_$(date +%s)"
RESP=$(curl -s -X POST "$BASE_URL/registry" -H "Content-Type: application/json" -d "{
  \"agent_id\": \"$AGENT\",
  \"sequence_rules\": {\"DeployCode\": \"RunTests\"},
  \"rate_limit_max\": 2
}" | jq -r '.status')
if [ "$RESP" != "success" ]; then echo "FAIL: Registry failed"; exit 1; else echo "PASS"; fi

echo "[9/11] Registry Sequence Override..."
SESS_ID="sess_custom_$(date +%s)"
RESP1=$(curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "X-Agent-ID: $AGENT" -H "X-Session-ID: $SESS_ID" -H "Content-Type: application/json" -d '{"tool_name": "DeployCode", "parameters": {}}' | jq -r '.detail.reason')
if [[ "$RESP1" != *"Sequence violation"* ]]; then echo "FAIL: Expected custom sequence violation, got $RESP1"; exit 1; else echo "PASS (Blocked without custom prereq)"; fi

echo "[10/11] Registry Rate Limit Override..."
curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "X-Agent-ID: $AGENT" -H "X-Session-ID: $SESS_ID" -H "Content-Type: application/json" -d '{"tool_name": "RunTests", "parameters": {}}' > /dev/null
curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "X-Agent-ID: $AGENT" -H "X-Session-ID: $SESS_ID" -H "Content-Type: application/json" -d '{"tool_name": "RunTests", "parameters": {}}' > /dev/null
# That was 2 valid calls hitting the rate limiter. Max is 2. The 3rd should fail.
RESP=$(curl -s -X POST "$BASE_URL/proxy" -H "X-Target-URL: $MOCK_URL" -H "X-Agent-ID: $AGENT" -H "X-Session-ID: $SESS_ID" -H "Content-Type: application/json" -d '{"tool_name": "RunTests", "parameters": {}}' | jq -r '.detail.reason')
if [[ "$RESP" != *"Rate limit exceeded"* ]]; then echo "FAIL: Expected custom rate limit block, got $RESP"; exit 1; else echo "PASS"; fi

echo "[11/11] MongoDB Logging Check..."
# Wait for background task to write to Mongo
sleep 1
LOGS=$(curl -s "$BASE_URL/logs")
STATEFUL=$(echo "$LOGS" | jq '[.[] | select(.mode=="Stateful")] | length')
STATELESS=$(echo "$LOGS" | jq '[.[] | select(.mode=="Stateless")] | length')
if [ "$STATEFUL" -gt 0 ] && [ "$STATELESS" -gt 0 ]; then
  echo "PASS (Stateful logs: $STATEFUL, Stateless logs: $STATELESS)"
else
  echo "FAIL: Expected both stateful and stateless logs to exist. Stateful: $STATEFUL, Stateless: $STATELESS"
  exit 1
fi

echo "========================================="
echo "          ALL TESTS PASSED!              "
echo "========================================="
