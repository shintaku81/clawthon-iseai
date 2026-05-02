import json, subprocess, os, secrets, hashlib
from mailer import send_vm_ready, send_welcome
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, Form, Cookie, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import httpx

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

PROJECT = "clawthon-iseai"
ZONE = "asia-northeast1-b"
GCLOUD = os.getenv("GCLOUD_PATH", "/usr/bin/gcloud")
DATA_FILE = Path("/opt/clawthon/console/participants.json")
SETTINGS_FILE = Path("/opt/clawthon/console/settings.json")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "clawthon2026")
ADMIN_EMAILS = {e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "r.sonoda@protocore.co.jp,masahiro@takechi.jp").split(",") if e.strip()}
ADMIN_TOKEN = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "clawthon-master-key")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
DNS_ZONE = "iseai-neuratools"
DOMAIN = "iseai.neuratools.ai"
STAR_NAMES = ["vega", "altair", "rigel", "sirius", "deneb", "antares", "aldebaran", "betelgeuse", "arcturus", "spica"]
CLOUD_INIT_TEMPLATE = Path("/opt/clawthon/infra/cloud-init-participant.yaml")
DEFAULT_OH_VERSION = "latest"


def load_data():
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps({"participants": []}, indent=2))
    return json.loads(DATA_FILE.read_text())


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def load_settings():
    if not SETTINGS_FILE.exists():
        defaults = {
            "oh_version": DEFAULT_OH_VERSION,
            "litellm_url": LITELLM_URL,
            "litellm_master_key": LITELLM_MASTER_KEY,
        }
        SETTINGS_FILE.write_text(json.dumps(defaults, indent=2))
        return defaults
    return json.loads(SETTINGS_FILE.read_text())


def save_settings(s):
    SETTINGS_FILE.write_text(json.dumps(s, indent=2))


import asyncio
from concurrent.futures import ThreadPoolExecutor
_executor = ThreadPoolExecutor(max_workers=8)


def gcloud_run(args: list[str], timeout=30) -> str:
    try:
        result = subprocess.run(
            [GCLOUD] + args,
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return ""


async def gcloud_run_async(args: list[str]) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, lambda: gcloud_run(args))


def get_vm_status(pid: str) -> str:
    out = gcloud_run([
        "compute", "instances", "describe", f"clawthon-p{pid}",
        f"--project={PROJECT}", f"--zone={ZONE}",
        "--format=value(status)"
    ])
    if not out or "ERROR" in out:
        return "NOT_EXISTS"
    return out


async def get_vm_status_async(pid: str) -> str:
    out = await gcloud_run_async([
        "compute", "instances", "describe", f"clawthon-p{pid}",
        f"--project={PROJECT}", f"--zone={ZONE}",
        "--format=value(status)"
    ])
    if not out or "ERROR" in out:
        return "NOT_EXISTS"
    return out


async def get_vm_ip_async(pid: str) -> str:
    return await gcloud_run_async([
        "compute", "instances", "describe", f"clawthon-p{pid}",
        f"--project={PROJECT}", f"--zone={ZONE}",
        "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"
    ])


def get_vm_ip(pid: str) -> str:
    return gcloud_run([
        "compute", "instances", "describe", f"clawthon-p{pid}",
        f"--project={PROJECT}", f"--zone={ZONE}",
        "--format=value(networkInterfaces[0].accessConfigs[0].natIP)"
    ])


async def check_openhands_async(vm_ip: str) -> bool:
    """OpenHandsポート3000が応答するか確認"""
    if not vm_ip:
        return False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"http://{vm_ip}:3000/", follow_redirects=True)
            return r.status_code < 500
    except Exception:
        return False


def is_admin(session_token: str = None) -> bool:
    return session_token == ADMIN_TOKEN


# ─── 認証 ────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login(email: str = Form(...), password: str = Form(...)):
    email_ok = email.lower().strip() in ADMIN_EMAILS
    pass_ok = hashlib.sha256(password.encode()).hexdigest() == ADMIN_TOKEN
    if email_ok and pass_ok:
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("session", ADMIN_TOKEN, httponly=True, max_age=86400*7)
        return resp
    if not email_ok:
        return RedirectResponse("/login?error=メールアドレスが正しくありません", status_code=303)
    return RedirectResponse("/login?error=パスワードが違います", status_code=303)


@app.get("/logout")
async def logout():
    resp = RedirectResponse("/login", status_code=303)
    resp.delete_cookie("session")
    return resp


# ─── ダッシュボード ───────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, session: str = Cookie(default="")):
    if not is_admin(session):
        return RedirectResponse("/login")
    data = load_data()
    settings = load_settings()
    participants = data["participants"]
    # 全VMのステータスを並列取得
    statuses = await asyncio.gather(*[get_vm_status_async(p["id"]) for p in participants])

    async def maybe_ip(pid, st):
        return await get_vm_ip_async(pid) if st == "RUNNING" else ""

    ips = await asyncio.gather(*[maybe_ip(p["id"], st) for p, st in zip(participants, statuses)])

    async def _false():
        return False

    # OpenHandsステータスを並列チェック
    oh_statuses = await asyncio.gather(*[
        check_openhands_async(ip) if st == "RUNNING" else _false()
        for ip, st in zip(ips, statuses)
    ])

    for p, st, ip, oh in zip(participants, statuses, ips, oh_statuses):
        p["vm_status"] = st
        p["vm_ip"] = ip
        p["oh_status"] = oh
        p["url_openhands"] = f"https://p{p['id']}.{DOMAIN}/openhands/"
        p["url_vscode"] = f"https://p{p['id']}.{DOMAIN}/code/"

    running_count = sum(1 for p in participants if p["vm_status"] == "RUNNING")
    # コスト概算（円）: 管理VM e2-small $0.017/h + 参加者VM e2-standard-2 SPOT $0.025/h
    MGMT_HOURLY_JPY = 0.017 * 150  # $0.017 × 150円/ドル
    PART_HOURLY_JPY = 0.025 * 150
    cost_hourly = MGMT_HOURLY_JPY + PART_HOURLY_JPY * running_count
    cost_daily = cost_hourly * 24
    cost_event = cost_daily * 2  # ハッカソン2日間想定

    return templates.TemplateResponse("index.html", {
        "request": request,
        "participants": participants,
        "total": len(participants),
        "running": running_count,
        "oh_version": settings.get("oh_version", DEFAULT_OH_VERSION),
        "litellm_url": settings.get("litellm_url", LITELLM_URL),
        "litellm_master_key": settings.get("litellm_master_key", LITELLM_MASTER_KEY),
        "cost_hourly": round(cost_hourly),
        "cost_daily": round(cost_daily),
        "cost_event": round(cost_event),
    })


# ─── 参加者管理 ──────────────────────────────────────

@app.post("/participants/add")
async def add_participant(
    name: str = Form(...),
    email: str = Form(...),
    session: str = Cookie(default="")
):
    if not is_admin(session):
        raise HTTPException(403)
    data = load_data()
    new_id = str(len(data["participants"]) + 1).zfill(2)
    data["participants"].append({
        "id": new_id,
        "name": name,
        "email": email,
        "litellm_key": "",
        "api_key": "",
        "model": "claude-sonnet-4-5",
        "created_at": datetime.now().isoformat(),
    })
    save_data(data)
    return RedirectResponse("/", status_code=303)


@app.post("/participants/{pid}/update")
async def update_participant(
    pid: str,
    api_key: str = Form(""),
    model: str = Form("claude-sonnet-4-5"),
    session: str = Cookie(default="")
):
    if not is_admin(session):
        raise HTTPException(403)
    data = load_data()
    for p in data["participants"]:
        if p["id"] == pid:
            p["api_key"] = api_key
            p["model"] = model
            break
    save_data(data)
    return RedirectResponse("/", status_code=303)


# ─── OpenHands設定 ────────────────────────────────────

@app.post("/settings/openhands")
async def update_oh_settings(
    oh_version: str = Form(DEFAULT_OH_VERSION),
    litellm_url: str = Form(LITELLM_URL),
    litellm_master_key: str = Form(LITELLM_MASTER_KEY),
    session: str = Cookie(default="")
):
    if not is_admin(session):
        raise HTTPException(403)
    settings = load_settings()
    settings["oh_version"] = oh_version
    settings["litellm_url"] = litellm_url
    settings["litellm_master_key"] = litellm_master_key
    save_settings(settings)
    # 全稼働VMのOpenHandsを再起動（バックグラウンド）
    data = load_data()
    for p in data["participants"]:
        subprocess.Popen([
            "bash", "/opt/clawthon/infra/restart-openhands.sh",
            p["id"], oh_version, litellm_url, litellm_master_key
        ])
    return RedirectResponse("/", status_code=303)


# ─── VM操作 ──────────────────────────────────────────

@app.post("/vm/{pid}/create")
async def create_vm(pid: str, session: str = Cookie(default="")):
    if not is_admin(session):
        raise HTTPException(403)
    data = load_data()
    settings = load_settings()
    p = next((x for x in data["participants"] if x["id"] == pid), None)
    if not p:
        raise HTTPException(404)

    # APIキーが設定されていない場合はエラー
    if not p.get("api_key") and not p.get("litellm_key"):
        return RedirectResponse("/?error=APIキーを設定してからVMを作成してください", status_code=303)

    # LiteLLMキー発行
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings['litellm_url']}/key/generate",
                headers={"Authorization": f"Bearer {settings['litellm_master_key']}"},
                json={
                    "key_alias": f"p{pid}",
                    "max_budget": 5.0,
                    "budget_duration": "1d",
                    "metadata": {"participant_id": pid, "email": p["email"]}
                }
            )
            p["litellm_key"] = resp.json().get("key", p.get("api_key", ""))
    except Exception:
        p["litellm_key"] = p.get("api_key", "sk-placeholder")

    save_data(data)

    # VM作成をバックグラウンドで実行
    subprocess.Popen([
        "bash", "/opt/clawthon/infra/create-participant-vm.sh",
        pid, p["litellm_key"], p["model"], settings.get("oh_version", DEFAULT_OH_VERSION)
    ])
    return RedirectResponse("/", status_code=303)


@app.post("/vm/{pid}/start")
async def start_vm(pid: str, session: str = Cookie(default="")):
    if not is_admin(session):
        raise HTTPException(403)
    gcloud_run([
        "compute", "instances", "start", f"clawthon-p{pid}",
        f"--project={PROJECT}", f"--zone={ZONE}"
    ])
    return RedirectResponse("/", status_code=303)


@app.post("/vm/{pid}/stop")
async def stop_vm(pid: str, session: str = Cookie(default="")):
    if not is_admin(session):
        raise HTTPException(403)
    gcloud_run([
        "compute", "instances", "stop", f"clawthon-p{pid}",
        f"--project={PROJECT}", f"--zone={ZONE}"
    ])
    return RedirectResponse("/", status_code=303)


@app.post("/vm/{pid}/delete")
async def delete_vm(pid: str, session: str = Cookie(default="")):
    if not is_admin(session):
        raise HTTPException(403)
    gcloud_run([
        "compute", "instances", "delete", f"clawthon-p{pid}",
        f"--project={PROJECT}", f"--zone={ZONE}", "--quiet"
    ])
    gcloud_run([
        "dns", "record-sets", "delete", f"p{pid}.{DOMAIN}.",
        f"--project={PROJECT}", f"--zone={DNS_ZONE}", "--type=A"
    ])
    return RedirectResponse("/", status_code=303)


# ─── API ─────────────────────────────────────────────

@app.get("/api/status")
async def api_status(session: str = Cookie(default="")):
    if not is_admin(session):
        raise HTTPException(403)
    data = load_data()
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "status": get_vm_status(p["id"]),
            "ip": get_vm_ip(p["id"])
        }
        for p in data["participants"]
    ]


@app.get("/manual", response_class=HTMLResponse)
async def manual(request: Request, session: str = Cookie(default="")):
    if not is_admin(session):
        return RedirectResponse("/login")
    return templates.TemplateResponse("manual.html", {"request": request})


# ─── VM監視API ───────────────────────────────────────

async def ssh_run_async(vm_name: str, command: str) -> str:
    """VM上でコマンドを非同期実行"""
    def _run():
        try:
            result = subprocess.run(
                [GCLOUD, "compute", "ssh", vm_name,
                 f"--project={PROJECT}", f"--zone={ZONE}",
                 "--command", command],
                capture_output=True, text=True, timeout=15
            )
            return result.stdout.strip()
        except Exception:
            return ""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_executor, _run)


@app.get("/api/vm/{pid}/metrics")
async def vm_metrics(pid: str, session: str = Cookie(default="")):
    if not is_admin(session):
        raise HTTPException(403)
    vm_name = f"clawthon-p{pid}"
    status = get_vm_status(pid)
    if status != "RUNNING":
        return {"error": "VM is not running", "status": status}

    metrics_cmd = (
        "echo '=CPU=' && top -bn1 | grep 'Cpu(s)' | awk '{print $2+$4}' | tr -d '%us,';"
        "echo '=MEM=' && free -m | awk 'NR==2{printf \"%s/%s MB\\n\", $3,$2}';"
        "echo '=DISK=' && df -h / | awk 'NR==2{print $3\"/\"$2\" (\"$5\" used)\"}';"
        "echo '=DOCKER=' && sudo docker ps --format '{{.Names}}:{{.Status}}' 2>/dev/null || echo 'none';"
        "echo '=OH_VER=' && sudo docker inspect openhands --format '{{.Config.Image}}' 2>/dev/null || echo 'not running';"
        "echo '=UPTIME=' && uptime -p"
    )
    raw = await ssh_run_async(vm_name, metrics_cmd)

    def extract(key):
        marker = f"={key}="
        lines = raw.split('\n')
        result = []
        capture = False
        for line in lines:
            if line.strip() == marker:
                capture = True
                continue
            if capture:
                if line.startswith('=') and line.endswith('='):
                    break
                if line.strip():
                    result.append(line.strip())
        return '\n'.join(result)

    return {
        "pid": pid,
        "status": status,
        "cpu_percent": extract("CPU"),
        "memory": extract("MEM"),
        "disk": extract("DISK"),
        "docker_containers": extract("DOCKER"),
        "oh_version": extract("OH_VER"),
        "uptime": extract("UPTIME"),
    }


@app.get("/api/vm/{pid}/logs")
async def vm_logs(pid: str, lines: int = 100, session: str = Cookie(default="")):
    if not is_admin(session):
        raise HTTPException(403)
    vm_name = f"clawthon-p{pid}"
    status = get_vm_status(pid)
    if status != "RUNNING":
        return JSONResponse({"error": "VM is not running"})

    logs_cmd = f"sudo docker logs openhands --tail {lines} 2>&1 || echo 'OpenHandsコンテナが見つかりません'"
    logs = await ssh_run_async(vm_name, logs_cmd)
    return JSONResponse({"pid": pid, "logs": logs})


@app.get("/api/vm/{pid}/service-logs")
async def service_logs(pid: str, service: str = "clawthon-console", session: str = Cookie(default="")):
    """管理コンソール自体のサービスログを取得（pid='management'の場合）"""
    if not is_admin(session):
        raise HTTPException(403)
    if pid == "management":
        def _get_logs():
            result = subprocess.run(
                ["journalctl", "-u", service, "-n", "100", "--no-pager"],
                capture_output=True, text=True
            )
            return result.stdout
        loop = asyncio.get_event_loop()
        logs = await loop.run_in_executor(_executor, _get_logs)
        return JSONResponse({"pid": "management", "logs": logs})
    return JSONResponse({"error": "Invalid pid"})


@app.post("/api/vm/{pid}/send-welcome")
async def api_send_welcome(pid: str, session: str = Cookie(default="")):
    if not is_admin(session):
        raise HTTPException(403)
    data = load_data()
    p = next((x for x in data["participants"] if x["id"] == pid), None)
    if not p:
        return JSONResponse({"ok": False, "error": "参加者が見つかりません"})
    email = p.get("email", "")
    if not email:
        return JSONResponse({"ok": False, "error": "メールアドレスが未設定です"})
    name = p.get("name", f"参加者{pid}")
    ok = send_welcome(email, name, pid)
    if ok:
        return JSONResponse({"ok": True, "message": f"{email} に送信しました"})
    else:
        return JSONResponse({"ok": False, "error": "SMTP未設定またはメール送信に失敗しました。サーバー環境変数 SMTP_USER / SMTP_PASS を確認してください。"})


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
