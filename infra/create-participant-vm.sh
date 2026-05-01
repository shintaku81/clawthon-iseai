#!/bin/bash
set -e
PROJECT=clawthon-iseai
GCLOUD=$(which gcloud || echo "/snap/bin/gcloud")
ZONE=asia-northeast1-b
DOMAIN=iseai.neuratools.ai
DNS_ZONE=iseai-neuratools
MANAGEMENT_IP=34.84.2.212
ADMIN_EMAIL=masahiro@takechi.jp

PARTICIPANT_ID=${1:?"Usage: $0 <participant_id> <litellm_key> [model] [oh_version]"}
LITELLM_KEY=${2:?"Usage: $0 <participant_id> <litellm_key> [model] [oh_version]"}
MODEL=${3:-"anthropic/claude-sonnet-4-5"}
OH_VERSION=${4:-"latest"}
VM_NAME="clawthon-p${PARTICIPANT_ID}"

echo "=== 参加者VM作成: p${PARTICIPANT_ID} (OpenHands:${OH_VERSION}) ==="

# cloud-initテンプレートを変数展開
TMPFILE=$(mktemp /tmp/cloud-init-XXXXXX.yaml)
sed "s|LITELLM_KEY_PLACEHOLDER|${LITELLM_KEY}|g; \
     s|MANAGEMENT_IP_PLACEHOLDER|${MANAGEMENT_IP}|g; \
     s|MODEL_PLACEHOLDER|${MODEL}|g; \
     s|OH_VERSION_PLACEHOLDER|${OH_VERSION}|g; \
     s|PARTICIPANT_ID_PLACEHOLDER|${PARTICIPANT_ID}|g; \
     s|DOMAIN_PLACEHOLDER|${DOMAIN}|g" \
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

echo "DNS登録完了: p${PARTICIPANT_ID}.${DOMAIN} -> ${VM_IP}"

# VM起動完了を待ってSSL証明書を取得（cloud-init完了後にnginxが起動）
echo "SSL証明書の取得を待機中（VMの起動に数分かかります）..."
sleep 120  # cloud-init完了まで待機

# SSL証明書取得（リトライあり）
for attempt in 1 2 3; do
  echo "SSL証明書取得 試行 ${attempt}/3..."
  if $GCLOUD compute ssh $VM_NAME \
    --project=$PROJECT --zone=$ZONE \
    --command="sudo certbot --nginx -d p${PARTICIPANT_ID}.${DOMAIN} \
      --non-interactive --agree-tos -m ${ADMIN_EMAIL} 2>&1" 2>/dev/null; then
    echo "SSL証明書取得成功"
    break
  else
    echo "SSL取得失敗、30秒後にリトライ..."
    sleep 30
  fi
done

# ランディングページをデプロイ
$GCLOUD compute ssh $VM_NAME \
  --project=$PROJECT --zone=$ZONE \
  --command="
    sudo mkdir -p /var/www/clawthon
    sudo tee /var/www/clawthon/index.html > /dev/null << 'HTMLEOF'
$(sed "s|{{VM_NAME}}|p${PARTICIPANT_ID}|g" /opt/clawthon/infra/participant-landing.html)
HTMLEOF
    sudo nginx -t && sudo systemctl reload nginx
    echo 'ランディングページ設置完了'
  " 2>/dev/null || echo "ランディングページ設置スキップ（後で手動設定可）"

echo "=== VM作成完了 ==="
echo "URL: https://p${PARTICIPANT_ID}.${DOMAIN}"
