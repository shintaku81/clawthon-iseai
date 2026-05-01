# Clawthon-ISEAI Infrastructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** ハッカソン（Clawthon-ISEAI）参加者向けにGCP上でOpenHands環境を提供し、運営が管理コンソールから参加者VMの起動・停止・API キー割当を一元管理できる仕組みを構築する。

**Architecture:**
- Management VM（常時起動）: FastAPI管理コンソール + LiteLLM Proxy を稼働
- Participant VM（オンデマンド）: OpenHands + code-server をDockerで動かす e2-standard-2 Spot VM
- DNS: Value Domain で `iseai.neuratools.ai` サブドメインを管理VM IPに向け、参加者VMは `p1.iseai.neuratools.ai` 〜 `pN.iseai.neuratools.ai` のサブドメインで提供
- SSL: Let's Encrypt（certbot）で自動取得・更新

**Tech Stack:** GCP Compute Engine, Ubuntu 24.04, Docker, OpenHands, code-server, FastAPI, LiteLLM Proxy, nginx, certbot, Value Domain DNS

---

## File Structure

```
Clawthon-ISEAI/
├── infra/
│   ├── setup-network.sh           # VPC・ファイアウォール設定
│   ├── setup-management-vm.sh     # 管理VM作成スクリプト
│   ├── cloud-init-management.yaml # 管理VMの初期化設定
│   ├── create-participant-vm.sh   # 参加者VM作成（引数: PARTICIPANT_ID）
│   ├── cloud-init-participant.yaml # 参加者VMの初期化設定テンプレート
│   ├── delete-participant-vm.sh   # 参加者VM削除
│   └── cleanup-all.sh             # 全VM一括削除（ハッカソン終了時）
├── console/
│   ├── app.py                     # FastAPI管理コンソール本体
│   ├── requirements.txt
│   ├── participants.json          # 参加者データ（VM状態・APIキー）
│   ├── templates/
│   │   └── index.html             # 管理ダッシュボードUI
│   └── Dockerfile
├── litellm/
│   └── config.yaml                # LiteLLM Proxy設定（モデル・予算上限）
├── nginx/
│   ├── management.conf            # 管理VMのnginx設定
│   └── participant.conf.template  # 参加者VMのnginx設定テンプレート
└── docs/
    ├── dns-setup.md               # Value Domain DNS設定手順
    ├── participant-manual.md      # 参加者向けマニュアル
    └── operator-manual.md        # 運営向けマニュアル
```

---

## Task 1: ネットワーク・ファイアウォール設定

**Files:**
- Create: `infra/setup-network.sh`

- [ ] **Step 1: setup-network.sh を作成する**

```bash
# infra/setup-network.sh
#!/bin/bash
set -e
PROJECT=clawthon-iseai
GCLOUD="/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud"

# HTTP/HTTPS
$GCLOUD compute firewall-rules create allow-http-https \
  --project=$PROJECT \
  --allow=tcp:80,tcp:443 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-vm \
  --description="HTTP/HTTPS for all Clawthon VMs"

# code-server (参加者VM)
$GCLOUD compute firewall-rules create allow-code-server \
  --project=$PROJECT \
  --allow=tcp:8080 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-participant \
  --description="code-server browser IDE"

# OpenHands (参加者VM)
$GCLOUD compute firewall-rules create allow-openhands \
  --project=$PROJECT \
  --allow=tcp:3000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-participant \
  --description="OpenHands web UI"

# 管理コンソール
$GCLOUD compute firewall-rules create allow-console \
  --project=$PROJECT \
  --allow=tcp:8000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-management \
  --description="FastAPI management console"

# LiteLLM Proxy
$GCLOUD compute firewall-rules create allow-litellm \
  --project=$PROJECT \
  --allow=tcp:4000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=clawthon-management \
  --description="LiteLLM proxy API"

echo "Firewall rules created."
```

- [ ] **Step 2: 実行して確認する**

```bash
chmod +x infra/setup-network.sh && bash infra/setup-network.sh
/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud compute firewall-rules list --project=clawthon-iseai --filter="name~clawthon"
```

期待出力: 5つのファイアウォールルールが表示される

---

## Task 2: 管理VM作成

管理コンソール・LiteLLM Proxy を動かす常時起動VMを作成する。

**Files:**
- Create: `infra/setup-management-vm.sh`
- Create: `infra/cloud-init-management.yaml`

- [ ] **Step 1: cloud-init-management.yaml を作成する**

```yaml
# infra/cloud-init-management.yaml
#cloud-config
package_update: true
package_upgrade: false

packages:
  - docker.io
  - docker-compose
  - nginx
  - certbot
  - python3-certbot-nginx
  - python3-pip
  - git
  - jq

runcmd:
  - systemctl enable docker
  - systemctl start docker
  - usermod -aG docker ubuntu
  # LiteLLM Proxy
  - pip3 install litellm[proxy]
  # 管理コンソール依存
  - pip3 install fastapi uvicorn jinja2 aiofiles httpx google-cloud-compute
  # 作業ディレクトリ
  - mkdir -p /opt/clawthon/console
  - mkdir -p /opt/clawthon/litellm
  echo "Management VM ready" > /tmp/init-done.txt
```

- [ ] **Step 2: setup-management-vm.sh を作成する**

```bash
# infra/setup-management-vm.sh
#!/bin/bash
set -e
PROJECT=clawthon-iseai
GCLOUD="/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud"
ZONE=asia-northeast1-b
VM_NAME=clawthon-management

$GCLOUD compute instances create $VM_NAME \
  --project=$PROJECT \
  --zone=$ZONE \
  --machine-type=e2-small \
  --image-family=ubuntu-2404-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-standard \
  --tags=clawthon-vm,clawthon-management \
  --metadata-from-file=user-data=infra/cloud-init-management.yaml \
  --description="Clawthon management console + LiteLLM proxy"

# Static IPを予約して割当
$GCLOUD compute addresses create clawthon-management-ip \
  --project=$PROJECT \
  --region=asia-northeast1

STATIC_IP=$($GCLOUD compute addresses describe clawthon-management-ip \
  --project=$PROJECT --region=asia-northeast1 --format="value(address)")

$GCLOUD compute instances delete-access-config $VM_NAME \
  --project=$PROJECT --zone=$ZONE --access-config-name="external-nat" 2>/dev/null || true

$GCLOUD compute instances add-access-config $VM_NAME \
  --project=$PROJECT --zone=$ZONE \
  --access-config-name="external-nat" \
  --address=$STATIC_IP

echo "Management VM IP: $STATIC_IP"
echo "次のステップ: Value DomainでAレコードを設定してください"
echo "  console.iseai.neuratools.ai → $STATIC_IP"
```

- [ ] **Step 3: 管理VMを作成する**

```bash
chmod +x infra/setup-management-vm.sh && bash infra/setup-management-vm.sh
```

期待出力: `Management VM IP: xxx.xxx.xxx.xxx`

- [ ] **Step 4: IPアドレスをメモしてValue DomainでDNS設定する**

Value Domain コントロールパネル (https://www.value-domain.com/cp/) で：
1. `neuratools.ai` のDNS設定を開く
2. 以下を追加:
   - `A console.clawthon 300 {管理VM IP}`
   - `A *.clawthon 300 {管理VM IP}` (参加者VMも後で個別に上書き)
3. 保存

---

## Task 3: 参加者VM テンプレート（1台目）

OpenHands + code-server が動く参加者VMを1台手動で作成して動作確認する。

**Files:**
- Create: `infra/cloud-init-participant.yaml`
- Create: `infra/create-participant-vm.sh`

- [ ] **Step 1: cloud-init-participant.yaml を作成する**

```yaml
# infra/cloud-init-participant.yaml
# 変数: ${PARTICIPANT_ID}, ${LITELLM_KEY}, ${LITELLM_BASE_URL}
#cloud-config
package_update: true

packages:
  - docker.io
  - docker-compose
  - nginx
  - certbot
  - python3-certbot-nginx

write_files:
  - path: /opt/clawthon/docker-compose.yml
    content: |
      version: '3.8'
      services:
        openhands:
          image: docker.all-hands.dev/all-hands-ai/openhands:0.38
          environment:
            - LLM_API_KEY=${LITELLM_KEY}
            - LLM_BASE_URL=${LITELLM_BASE_URL}
            - LLM_MODEL=openrouter/anthropic/claude-sonnet-4-5
            - SANDBOX_RUNTIME_CONTAINER_IMAGE=docker.all-hands.dev/all-hands-ai/runtime:0.38-nikolaik
          volumes:
            - /opt/clawthon/workspace:/opt/workspace
            - /var/run/docker.sock:/var/run/docker.sock
          ports:
            - "3000:3000"
          restart: unless-stopped

        code-server:
          image: codercom/code-server:latest
          environment:
            - PASSWORD=clawthon2026
          volumes:
            - /opt/clawthon/workspace:/home/coder/project
          ports:
            - "8080:8080"
          restart: unless-stopped

  - path: /etc/nginx/sites-available/clawthon
    content: |
      server {
          listen 80;
          server_name ${PARTICIPANT_ID}.iseai.neuratools.ai;
          location /code/ {
              proxy_pass http://localhost:8080/;
              proxy_set_header Host $host;
              proxy_set_header Upgrade $http_upgrade;
              proxy_set_header Connection upgrade;
          }
          location / {
              proxy_pass http://localhost:3000/;
              proxy_set_header Host $host;
              proxy_set_header Upgrade $http_upgrade;
              proxy_set_header Connection upgrade;
          }
      }

runcmd:
  - systemctl enable docker && systemctl start docker
  - mkdir -p /opt/clawthon/workspace
  - cd /opt/clawthon && docker compose up -d
  - ln -sf /etc/nginx/sites-available/clawthon /etc/nginx/sites-enabled/clawthon
  - rm -f /etc/nginx/sites-enabled/default
  - nginx -t && systemctl reload nginx
  - echo "Participant VM ready: ${PARTICIPANT_ID}" > /tmp/init-done.txt
```

- [ ] **Step 2: create-participant-vm.sh を作成する**

```bash
# infra/create-participant-vm.sh
#!/bin/bash
set -e
PROJECT=clawthon-iseai
GCLOUD="/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud"
ZONE=asia-northeast1-b

PARTICIPANT_ID=${1:?"Usage: $0 <participant_id> <litellm_key>"}
LITELLM_KEY=${2:?"Usage: $0 <participant_id> <litellm_key>"}
LITELLM_BASE_URL="http://$(${GCLOUD} compute instances describe clawthon-management \
  --project=$PROJECT --zone=$ZONE \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)'):4000"

VM_NAME="clawthon-p${PARTICIPANT_ID}"

# cloud-initのテンプレートを変数展開して一時ファイルに書き出し
TMPFILE=$(mktemp /tmp/cloud-init-XXXXXX.yaml)
sed "s/\${PARTICIPANT_ID}/${PARTICIPANT_ID}/g; \
     s|\${LITELLM_KEY}|${LITELLM_KEY}|g; \
     s|\${LITELLM_BASE_URL}|${LITELLM_BASE_URL}|g" \
  infra/cloud-init-participant.yaml > $TMPFILE

$GCLOUD compute instances create $VM_NAME \
  --project=$PROJECT \
  --zone=$ZONE \
  --machine-type=e2-standard-2 \
  --provisioning-model=SPOT \
  --instance-termination-action=STOP \
  --image-family=ubuntu-2404-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-balanced \
  --tags=clawthon-vm,clawthon-participant \
  --metadata-from-file=user-data=$TMPFILE \
  --description="Clawthon participant VM: ${PARTICIPANT_ID}"

rm $TMPFILE

VM_IP=$($GCLOUD compute instances describe $VM_NAME \
  --project=$PROJECT --zone=$ZONE \
  --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

echo "Created: $VM_NAME / IP: $VM_IP"
echo "URL: http://p${PARTICIPANT_ID}.iseai.neuratools.ai"
echo "Value DomainでAレコードを追加: p${PARTICIPANT_ID}.clawthon ${VM_IP}"
```

- [ ] **Step 3: 1台目を作成して動作確認する（LiteLLM設定後に実施）**

```bash
# Task 4（LiteLLM設定）完了後に実行
chmod +x infra/create-participant-vm.sh
bash infra/create-participant-vm.sh 1 sk-test-key-placeholder
```

---

## Task 4: LiteLLM Proxy 設定・起動

管理VM上でLiteLLM Proxyを起動し、参加者ごとに仮想APIキーを発行できるようにする。

**Files:**
- Create: `litellm/config.yaml`

- [ ] **Step 1: litellm/config.yaml を作成する**

```yaml
# litellm/config.yaml
model_list:
  - model_name: claude-sonnet
    litellm_params:
      model: openrouter/anthropic/claude-sonnet-4-5
      api_key: os.environ/OPENROUTER_API_KEY
      api_base: https://openrouter.ai/api/v1

  - model_name: claude-haiku
    litellm_params:
      model: openrouter/anthropic/claude-haiku-3-5
      api_key: os.environ/OPENROUTER_API_KEY
      api_base: https://openrouter.ai/api/v1

  - model_name: gemini-flash
    litellm_params:
      model: gemini/gemini-2.0-flash
      api_key: os.environ/GEMINI_API_KEY

litellm_settings:
  max_budget: 50  # プロジェクト全体の最大予算（USD）
  budget_duration: "1d"

general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL  # SQLiteでOK

router_settings:
  routing_strategy: usage-based-routing
```

- [ ] **Step 2: 管理VMにLiteLLM設定をデプロイするスクリプトを作成する**

```bash
# infra/deploy-litellm.sh
#!/bin/bash
set -e
PROJECT=clawthon-iseai
GCLOUD="/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud"
ZONE=asia-northeast1-b
VM_NAME=clawthon-management

# 設定ファイルをVMにコピー
$GCLOUD compute scp litellm/config.yaml ${VM_NAME}:/opt/clawthon/litellm/config.yaml \
  --project=$PROJECT --zone=$ZONE

# LiteLLM起動コマンドをVMで実行
$GCLOUD compute ssh ${VM_NAME} --project=$PROJECT --zone=$ZONE --command="
  export OPENROUTER_API_KEY='${OPENROUTER_API_KEY}'
  export GEMINI_API_KEY='${GEMINI_API_KEY}'
  export LITELLM_MASTER_KEY='${LITELLM_MASTER_KEY:-clawthon-master-key}'
  nohup litellm --config /opt/clawthon/litellm/config.yaml \
    --port 4000 --host 0.0.0.0 \
    > /opt/clawthon/litellm/litellm.log 2>&1 &
  echo 'LiteLLM started'
"
```

- [ ] **Step 3: 参加者キーを発行するスクリプトを作成する**

```bash
# infra/create-participant-key.sh
#!/bin/bash
# Usage: bash create-participant-key.sh <participant_id> [budget_usd]
PARTICIPANT_ID=${1:?"Usage: $0 <participant_id> [budget_usd]"}
BUDGET=${2:-5}  # デフォルト5ドル

MANAGEMENT_IP=$(/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud \
  compute instances describe clawthon-management \
  --project=clawthon-iseai --zone=asia-northeast1-b \
  --format="value(networkInterfaces[0].accessConfigs[0].natIP)")

MASTER_KEY=${LITELLM_MASTER_KEY:-clawthon-master-key}

RESPONSE=$(curl -s -X POST "http://${MANAGEMENT_IP}:4000/key/generate" \
  -H "Authorization: Bearer ${MASTER_KEY}" \
  -H "Content-Type: application/json" \
  -d "{
    \"key_alias\": \"participant-${PARTICIPANT_ID}\",
    \"max_budget\": ${BUDGET},
    \"budget_duration\": \"1d\",
    \"metadata\": {\"participant_id\": \"${PARTICIPANT_ID}\"}
  }")

KEY=$(echo $RESPONSE | python3 -c "import sys,json; print(json.load(sys.stdin)['key'])")
echo "Participant ${PARTICIPANT_ID} key: ${KEY}"
echo "${PARTICIPANT_ID},${KEY}" >> participants-keys.csv
```

---

## Task 5: 管理コンソール（FastAPI）

運営が参加者VMの状態確認・起動・停止・キー発行をブラウザから操作できる管理UIを作成する。

**Files:**
- Create: `console/app.py`
- Create: `console/requirements.txt`
- Create: `console/templates/index.html`
- Create: `console/participants.json`

- [ ] **Step 1: requirements.txt を作成する**

```
fastapi==0.115.0
uvicorn[standard]==0.32.0
jinja2==3.1.4
aiofiles==24.1.0
httpx==0.27.2
google-cloud-compute==1.19.3
google-auth==2.35.0
```

- [ ] **Step 2: participants.json（初期データ）を作成する**

```json
{
  "participants": []
}
```

- [ ] **Step 3: console/app.py を作成する**

```python
# console/app.py
import json, subprocess, os
from pathlib import Path
from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
import httpx

app = FastAPI()
templates = Jinja2Templates(directory="templates")

PROJECT = "clawthon-iseai"
ZONE = "asia-northeast1-b"
GCLOUD = "/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud"
DATA_FILE = Path("participants.json")
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "clawthon-master-key")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")


def load_participants():
    return json.loads(DATA_FILE.read_text())["participants"]


def save_participants(participants):
    DATA_FILE.write_text(json.dumps({"participants": participants}, indent=2, ensure_ascii=False))


def gcloud_run(args: list[str]) -> str:
    result = subprocess.run(
        [GCLOUD] + args,
        capture_output=True, text=True, timeout=60
    )
    return result.stdout.strip()


def get_vm_status(participant_id: str) -> str:
    vm_name = f"clawthon-p{participant_id}"
    out = gcloud_run([
        "compute", "instances", "describe", vm_name,
        f"--project={PROJECT}", f"--zone={ZONE}",
        "--format=value(status)"
    ])
    if "did not find" in out or not out:
        return "NOT_EXISTS"
    return out  # RUNNING / TERMINATED / STAGING


def get_vm_ip(participant_id: str) -> str:
    vm_name = f"clawthon-p{participant_id}"
    return gcloud_run([
        "compute", "instances", "describe", vm_name,
        f"--project={PROJECT}", f"--zone={ZONE}",
        "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"
    ])


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    participants = load_participants()
    for p in participants:
        p["vm_status"] = get_vm_status(p["id"])
        p["vm_ip"] = get_vm_ip(p["id"]) if p["vm_status"] == "RUNNING" else ""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "participants": participants
    })


@app.post("/participants/add")
async def add_participant(name: str = Form(...), email: str = Form(...)):
    participants = load_participants()
    new_id = str(len(participants) + 1).zfill(2)
    participants.append({
        "id": new_id,
        "name": name,
        "email": email,
        "litellm_key": "",
        "url": f"http://p{new_id}.iseai.neuratools.ai"
    })
    save_participants(participants)
    return RedirectResponse("/", status_code=303)


@app.post("/vm/{participant_id}/start")
async def start_vm(participant_id: str):
    gcloud_run([
        "compute", "instances", "start", f"clawthon-p{participant_id}",
        f"--project={PROJECT}", f"--zone={ZONE}"
    ])
    return RedirectResponse("/", status_code=303)


@app.post("/vm/{participant_id}/stop")
async def stop_vm(participant_id: str):
    gcloud_run([
        "compute", "instances", "stop", f"clawthon-p{participant_id}",
        f"--project={PROJECT}", f"--zone={ZONE}"
    ])
    return RedirectResponse("/", status_code=303)


@app.post("/vm/{participant_id}/create")
async def create_vm(participant_id: str):
    participants = load_participants()
    p = next((x for x in participants if x["id"] == participant_id), None)
    if not p:
        return {"error": "participant not found"}

    # LiteLLMキー発行
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{LITELLM_URL}/key/generate",
            headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
            json={
                "key_alias": f"participant-{participant_id}",
                "max_budget": 5.0,
                "budget_duration": "1d",
                "metadata": {"participant_id": participant_id}
            }
        )
        key = resp.json().get("key", "")

    p["litellm_key"] = key
    save_participants(participants)

    # VM作成
    subprocess.Popen([
        "bash", "../infra/create-participant-vm.sh",
        participant_id, key
    ])
    return RedirectResponse("/", status_code=303)


@app.post("/vm/{participant_id}/delete")
async def delete_vm(participant_id: str):
    gcloud_run([
        "compute", "instances", "delete", f"clawthon-p{participant_id}",
        f"--project={PROJECT}", f"--zone={ZONE}", "--quiet"
    ])
    return RedirectResponse("/", status_code=303)


@app.get("/api/status")
async def api_status():
    participants = load_participants()
    return [
        {"id": p["id"], "name": p["name"], "status": get_vm_status(p["id"])}
        for p in participants
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 4: console/templates/index.html を作成する**

```html
<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Clawthon 管理コンソール</title>
  <style>
    body { font-family: system-ui; max-width: 1200px; margin: 0 auto; padding: 20px; background: #0f0f0f; color: #e0e0e0; }
    h1 { color: #7c3aed; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #2a2a2a; }
    th { background: #1a1a1a; color: #a0a0a0; font-size: 12px; text-transform: uppercase; }
    .status-RUNNING { color: #4ade80; font-weight: bold; }
    .status-TERMINATED { color: #f87171; }
    .status-NOT_EXISTS { color: #6b7280; }
    .btn { padding: 5px 12px; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
    .btn-start { background: #16a34a; color: white; }
    .btn-stop { background: #dc2626; color: white; }
    .btn-create { background: #7c3aed; color: white; }
    .btn-delete { background: #374151; color: #9ca3af; }
    .add-form { margin-top: 30px; padding: 16px; background: #1a1a1a; border-radius: 8px; }
    .add-form input { padding: 8px; margin: 4px; background: #2a2a2a; border: 1px solid #3a3a3a; color: white; border-radius: 4px; }
    .refresh { float: right; color: #6b7280; font-size: 13px; }
  </style>
  <script>setTimeout(() => location.reload(), 30000);</script>
</head>
<body>
  <h1>Clawthon 管理コンソール</h1>
  <span class="refresh">30秒ごとに自動更新</span>
  <p>参加者数: {{ participants|length }} / VMステータス自動更新中</p>

  <table>
    <thead>
      <tr><th>#</th><th>名前</th><th>メール</th><th>VM状態</th><th>URL</th><th>APIキー</th><th>操作</th></tr>
    </thead>
    <tbody>
      {% for p in participants %}
      <tr>
        <td>{{ p.id }}</td>
        <td>{{ p.name }}</td>
        <td>{{ p.email }}</td>
        <td class="status-{{ p.vm_status }}">{{ p.vm_status }}</td>
        <td>
          {% if p.vm_ip %}
          <a href="http://{{ p.vm_ip }}:3000" target="_blank" style="color:#7c3aed">OpenHands</a> /
          <a href="http://{{ p.vm_ip }}:8080" target="_blank" style="color:#7c3aed">VSCode</a>
          {% else %}-{% endif %}
        </td>
        <td style="font-family:monospace;font-size:11px">{{ p.litellm_key[:20] if p.litellm_key else '-' }}...</td>
        <td>
          {% if p.vm_status == 'NOT_EXISTS' %}
            <form method="post" action="/vm/{{ p.id }}/create" style="display:inline">
              <button class="btn btn-create">作成</button>
            </form>
          {% elif p.vm_status == 'TERMINATED' %}
            <form method="post" action="/vm/{{ p.id }}/start" style="display:inline">
              <button class="btn btn-start">起動</button>
            </form>
          {% elif p.vm_status == 'RUNNING' %}
            <form method="post" action="/vm/{{ p.id }}/stop" style="display:inline">
              <button class="btn btn-stop">停止</button>
            </form>
          {% endif %}
          <form method="post" action="/vm/{{ p.id }}/delete" style="display:inline"
                onsubmit="return confirm('本当に削除しますか？')">
            <button class="btn btn-delete">削除</button>
          </form>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="add-form">
    <h3 style="margin-top:0">参加者を追加</h3>
    <form method="post" action="/participants/add">
      <input type="text" name="name" placeholder="名前" required>
      <input type="email" name="email" placeholder="メールアドレス" required>
      <button type="submit" class="btn btn-create">追加</button>
    </form>
  </div>
</body>
</html>
```

---

## Task 6: 管理コンソールを管理VMにデプロイ

**Files:**
- Create: `infra/deploy-console.sh`

- [ ] **Step 1: deploy-console.sh を作成する**

```bash
# infra/deploy-console.sh
#!/bin/bash
set -e
PROJECT=clawthon-iseai
GCLOUD="/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud"
ZONE=asia-northeast1-b
VM_NAME=clawthon-management

# コンソールファイルをVMにコピー
$GCLOUD compute scp --recurse console/ ${VM_NAME}:/opt/clawthon/console \
  --project=$PROJECT --zone=$ZONE
$GCLOUD compute scp infra/create-participant-vm.sh ${VM_NAME}:/opt/clawthon/infra/ \
  --project=$PROJECT --zone=$ZONE
$GCLOUD compute scp infra/cloud-init-participant.yaml ${VM_NAME}:/opt/clawthon/infra/ \
  --project=$PROJECT --zone=$ZONE

# 起動
$GCLOUD compute ssh ${VM_NAME} --project=$PROJECT --zone=$ZONE --command="
  cd /opt/clawthon/console
  pip3 install -r requirements.txt -q
  export LITELLM_MASTER_KEY='${LITELLM_MASTER_KEY:-clawthon-master-key}'
  export LITELLM_URL='http://localhost:4000'
  nohup python3 app.py > /opt/clawthon/console/console.log 2>&1 &
  echo 'Console started on :8000'
"
```

- [ ] **Step 2: デプロイして動作確認する**

```bash
chmod +x infra/deploy-console.sh && bash infra/deploy-console.sh
# ブラウザで http://{管理VM IP}:8000 を開く
```

---

## Task 7: 一括削除・終了スクリプト

ハッカソン終了時に全リソースをきれいに片付けるスクリプト。

**Files:**
- Create: `infra/cleanup-all.sh`

- [ ] **Step 1: cleanup-all.sh を作成する**

```bash
# infra/cleanup-all.sh
#!/bin/bash
PROJECT=clawthon-iseai
GCLOUD="/Users/shintaku81/Downloads/google-cloud-sdk/bin/gcloud"
ZONE=asia-northeast1-b

echo "=== Clawthon 終了処理 ==="
echo "参加者VMを全件削除します..."

# 参加者VM一覧を取得して削除
VMS=$($GCLOUD compute instances list \
  --project=$PROJECT --zones=$ZONE \
  --filter="name~clawthon-p" \
  --format="value(name)")

if [ -z "$VMS" ]; then
  echo "参加者VMはありません"
else
  echo $VMS | tr ' ' '\n' | while read vm; do
    echo "削除中: $vm"
    $GCLOUD compute instances delete $vm \
      --project=$PROJECT --zone=$ZONE --quiet &
  done
  wait
  echo "全参加者VM削除完了"
fi

echo ""
echo "管理VMは残したまま終了します"
echo "管理VMも削除する場合は以下を実行:"
echo "  gcloud compute instances delete clawthon-management --project=$PROJECT --zone=$ZONE"
```

- [ ] **Step 2: 実行権限を付与する**

```bash
chmod +x infra/cleanup-all.sh
```

---

## Task 8: DNS設定ドキュメント

**Files:**
- Create: `docs/dns-setup.md`

- [ ] **Step 1: docs/dns-setup.md を作成する**

```markdown
# DNS設定手順（Value Domain）

## 設定先
Value Domain コントロールパネル: https://www.value-domain.com/cp/
対象ドメイン: neuratools.ai

## 追加するDNSレコード

| タイプ | ホスト名 | 値 | TTL |
|---|---|---|---|
| A | console.clawthon | {管理VM IP} | 300 |
| A | *.clawthon | {管理VM IP} | 300 |

## 参加者VM追加時（VMごとに個別IPが必要な場合）

| タイプ | ホスト名 | 値 | TTL |
|---|---|---|---|
| A | p01.clawthon | {参加者01 VM IP} | 300 |
| A | p02.clawthon | {参加者02 VM IP} | 300 |

## 確認コマンド
\`\`\`bash
dig console.iseai.neuratools.ai
\`\`\`

## 補足
- ワイルドカード `*.clawthon` を設定しておくと参加者VM追加のたびにDNS設定が不要
- ただしワイルドカードでは参加者VMに直接IPでのアクセスが必要になるケースもある
```

---

## Self-Review

### Spec Coverage
| 要件 | タスク |
|---|---|
| VM1台最小構成 | Task 2, 3 |
| OpenClaw（OpenHands）セットアップ | Task 3 |
| 管理コンソール | Task 5, 6 |
| 自動デプロイ | Task 3, 6 |
| 停止・起動機能 | Task 5 |
| ログインキー割当 | Task 4, 5 |
| ドメイン設定（neuratools.ai / Value Domain） | Task 2, 8 |
| 全員分クリーンアップ | Task 7 |

### 実行順序
1. Task 1 → Task 2（管理VM作成）
2. Task 8（DNS設定）
3. Task 4（LiteLLM起動）
4. Task 3（参加者VM 1台テスト）
5. Task 5, 6（管理コンソールデプロイ）
6. Task 7（終了時）
