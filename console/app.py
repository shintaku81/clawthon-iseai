import json, subprocess, os, secrets, hashlib
from mailer import send_vm_ready
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Request, Form, Cookie, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
import httpx

app = FastAPI()
templates = Jinja2Templates(directory="templates")

PROJECT = "clawthon-iseai"
ZONE = "asia-northeast1-b"
GCLOUD = os.getenv("GCLOUD_PATH", "/usr/bin/gcloud")
DATA_FILE = Path("/opt/clawthon/console/participants.json")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "clawthon2026")
ADMIN_TOKEN = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()
LITELLM_MASTER_KEY = os.getenv("LITELLM_MASTER_KEY", "clawthon-master-key")
LITELLM_URL = os.getenv("LITELLM_URL", "http://localhost:4000")
DNS_ZONE = "iseai-neuratools"
DOMAIN = "iseai.neuratools.ai"
STAR_NAMES = ["vega", "altair", "rigel", "sirius", "deneb", "antares", "aldebaran", "betelgeuse", "arcturus", "spica"]
CLOUD_INIT_TEMPLATE = Path("/opt/clawthon/infra/cloud-init-participant.yaml")


def load_data():
    if not DATA_FILE.exists():
        DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        DATA_FILE.write_text(json.dumps({"participants": []}, indent=2))
    return json.loads(DATA_FILE.read_text())


def save_data(data):
    DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))


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


def is_admin(session_token: str = None) -> bool:
    return session_token == ADMIN_TOKEN


# ─── 認証 ────────────────────────────────────────────

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})


@app.post("/login")
async def login(password: str = Form(...)):
    if hashlib.sha256(password.encode()).hexdigest() == ADMIN_TOKEN:
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie("session", ADMIN_TOKEN, httponly=True, max_age=86400*7)
        return resp
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
    participants = data["participants"]
    # 全VMのステータスを並列取得
    statuses = await asyncio.gather(*[get_vm_status_async(p["id"]) for p in participants])

    async def maybe_ip(pid, st):
        return await get_vm_ip_async(pid) if st == "RUNNING" else ""

    ips = await asyncio.gather(*[maybe_ip(p["id"], st) for p, st in zip(participants, statuses)])
    for p, st, ip in zip(participants, statuses, ips):
        p["vm_status"] = st
        p["vm_ip"] = ip
        p["url_openhands"] = f"http://p{p['id']}.{DOMAIN}"
        p["url_vscode"] = f"http://p{p['id']}.{DOMAIN}:8080"
    return templates.TemplateResponse("index.html", {
        "request": request,
        "participants": participants,
        "total": len(participants),
        "running": sum(1 for p in participants if p["vm_status"] == "RUNNING"),
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
        "model": "claude-sonnet",
        "created_at": datetime.now().isoformat(),
    })
    save_data(data)
    return RedirectResponse("/", status_code=303)


@app.post("/participants/{pid}/update")
async def update_participant(
    pid: str,
    api_key: str = Form(""),
    model: str = Form("claude-sonnet"),
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


# ─── VM操作 ──────────────────────────────────────────

@app.post("/vm/{pid}/create")
async def create_vm(pid: str, session: str = Cookie(default="")):
    if not is_admin(session):
        raise HTTPException(403)
    data = load_data()
    p = next((x for x in data["participants"] if x["id"] == pid), None)
    if not p:
        raise HTTPException(404)

    # LiteLLMキー発行
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{LITELLM_URL}/key/generate",
                headers={"Authorization": f"Bearer {LITELLM_MASTER_KEY}"},
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
        pid, p["litellm_key"], p["model"]
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
    # DNS削除
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
