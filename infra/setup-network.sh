#!/bin/bash
set -e
PROJECT=clawthon-iseai
GCLOUD="/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud"

echo "=== Clawthon ファイアウォール設定 ==="

$GCLOUD compute firewall-rules create allow-http-https \
  --project=$PROJECT \
  --allow=tcp:80,tcp:443 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-vm \
  --description="HTTP/HTTPS for all Clawthon VMs" 2>/dev/null || echo "allow-http-https: already exists"

$GCLOUD compute firewall-rules create allow-code-server \
  --project=$PROJECT \
  --allow=tcp:8080 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-participant \
  --description="code-server browser IDE" 2>/dev/null || echo "allow-code-server: already exists"

$GCLOUD compute firewall-rules create allow-openhands \
  --project=$PROJECT \
  --allow=tcp:3000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-participant \
  --description="OpenHands web UI" 2>/dev/null || echo "allow-openhands: already exists"

$GCLOUD compute firewall-rules create allow-console \
  --project=$PROJECT \
  --allow=tcp:8000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-management \
  --description="FastAPI management console" 2>/dev/null || echo "allow-console: already exists"

$GCLOUD compute firewall-rules create allow-litellm \
  --project=$PROJECT \
  --allow=tcp:4000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-management \
  --description="LiteLLM proxy API" 2>/dev/null || echo "allow-litellm: already exists"

echo ""
echo "=== 完了 ==="
$GCLOUD compute firewall-rules list --project=$PROJECT --filter="name~clawthon" --format="table(name,allowed,targetTags)"
