#!/bin/bash
set -e
PROJECT=clawthon-iseai
GCLOUD=$(which gcloud || echo "/usr/bin/gcloud")
ZONE=asia-northeast1-b
DOMAIN=iseai.neuratools.ai
DNS_ZONE=iseai-neuratools
MANAGEMENT_IP=34.84.2.212

PARTICIPANT_ID=${1:?"Usage: $0 <participant_id> <litellm_key> [model]"}
LITELLM_KEY=${2:?"Usage: $0 <participant_id> <litellm_key> [model]"}
MODEL=${3:-"openrouter/anthropic/claude-sonnet-4-5"}
VM_NAME="clawthon-p${PARTICIPANT_ID}"

echo "=== 参加者VM作成: p${PARTICIPANT_ID} ==="

# cloud-initテンプレートを変数展開
TMPFILE=$(mktemp /tmp/cloud-init-XXXXXX.yaml)
sed "s|LITELLM_KEY_PLACEHOLDER|${LITELLM_KEY}|g; \
     s|MANAGEMENT_IP_PLACEHOLDER|${MANAGEMENT_IP}|g; \
     s|MODEL_PLACEHOLDER|${MODEL}|g" \
  /opt/clawthon/infra/cloud-init-participant.yaml > $TMPFILE

# VM作成
$GCLOUD compute instances create $VM_NAME \
  --project=$PROJECT \
  --zone=$ZONE \
  --machine-type=e2-standard-2 \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --image-family=ubuntu-2404-lts-amd64 \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-balanced \
  --tags=clawthon-vm,clawthon-participant \
  --metadata-from-file=user-data=$TMPFILE \
  --description="Clawthon participant: ${PARTICIPANT_ID}"

rm $TMPFILE

# IP取得
VM_IP=$($GCLOUD compute instances describe $VM_NAME \
  --project=$PROJECT --zone=$ZONE \
  --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

# Cloud DNSにレコード追加
$GCLOUD dns record-sets create "p${PARTICIPANT_ID}.${DOMAIN}." \
  --project=$PROJECT \
  --zone=$DNS_ZONE \
  --type=A --ttl=60 \
  --rrdatas=$VM_IP 2>/dev/null || \
$GCLOUD dns record-sets update "p${PARTICIPANT_ID}.${DOMAIN}." \
  --project=$PROJECT \
  --zone=$DNS_ZONE \
  --type=A --ttl=60 \
  --rrdatas=$VM_IP

echo "完了: $VM_NAME / $VM_IP"
echo "URL: http://p${PARTICIPANT_ID}.${DOMAIN}"
