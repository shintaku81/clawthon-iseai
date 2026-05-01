#!/bin/bash
# 参加者VMのOpenHandsコンテナを指定バージョンで再起動するスクリプト
# 使用法: restart-openhands.sh <pid> <oh_version> <litellm_url> <litellm_key>
set -e

PID="$1"
OH_VERSION="${2:-latest}"
LITELLM_URL="${3:-http://localhost:4000}"
LITELLM_KEY="${4:-sk-placeholder}"
PROJECT="clawthon-iseai"
ZONE="asia-northeast1-b"

VM_STATUS=$(/snap/bin/gcloud compute instances describe "clawthon-p${PID}" \
  --project="${PROJECT}" --zone="${ZONE}" --format="value(status)" 2>/dev/null || echo "NOT_EXISTS")

if [ "$VM_STATUS" != "RUNNING" ]; then
  echo "VM clawthon-p${PID} is not running (${VM_STATUS}), skipping"
  exit 0
fi

/snap/bin/gcloud compute ssh "clawthon-p${PID}" \
  --project="${PROJECT}" --zone="${ZONE}" \
  --command="
    sudo docker stop openhands 2>/dev/null || true
    sudo docker rm openhands 2>/dev/null || true
    sudo docker pull ghcr.io/all-hands-ai/openhands:${OH_VERSION}
    sudo docker run -d --name openhands --restart=unless-stopped \
      -p 3000:3000 \
      -e LLM_API_KEY='${LITELLM_KEY}' \
      -e LLM_BASE_URL='${LITELLM_URL}' \
      -e LLM_MODEL='anthropic/claude-sonnet-4-5' \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v ~/.openhands:/root/.openhands \
      ghcr.io/all-hands-ai/openhands:${OH_VERSION}
    echo 'OpenHands ${OH_VERSION} started on clawthon-p${PID}'
  "
