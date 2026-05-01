import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_NAME = "Clawthon ISEAI"
FROM_ADDR = os.getenv("FROM_EMAIL", SMTP_USER)


def send_email(to: str, subject: str, html: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print(f"[mailer] SMTP未設定 — メール送信スキップ: {to} / {subject}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_ADDR}>"
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_ADDR, to, msg.as_string())
        print(f"[mailer] 送信成功: {to}")
        return True
    except Exception as e:
        print(f"[mailer] 送信失敗: {e}")
        return False


def send_welcome(to: str, name: str, participant_id: str, url: str, vscode_url: str, password: str = "clawthon2026"):
    subject = "【Clawthon ISEAI】あなたの開発環境ができました"
    html = f"""
<!DOCTYPE html>
<html lang="ja">
<head><meta charset="UTF-8"></head>
<body style="font-family:system-ui;background:#0a0a0f;color:#e0e0e0;padding:40px;max-width:600px;margin:0 auto">
  <div style="background:#13131a;border:1px solid #2a2a3a;border-radius:12px;padding:32px">
    <h2 style="color:#a78bfa;margin-top:0">Clawthon ISEAI へようこそ！</h2>
    <p>{name} さん、参加者登録が完了しました。</p>

    <div style="background:#1e1e2e;border-radius:8px;padding:20px;margin:24px 0">
      <p style="margin:0 0 12px;color:#9ca3af;font-size:13px">あなたの開発環境</p>
      <table style="width:100%;font-size:14px">
        <tr>
          <td style="color:#6b7280;padding:4px 0">参加者ID</td>
          <td style="font-weight:bold">p{participant_id}</td>
        </tr>
        <tr>
          <td style="color:#6b7280;padding:4px 0">OpenHands URL</td>
          <td><a href="{url}" style="color:#a78bfa">{url}</a></td>
        </tr>
        <tr>
          <td style="color:#6b7280;padding:4px 0">VSCode URL</td>
          <td><a href="{vscode_url}" style="color:#a78bfa">{vscode_url}</a></td>
        </tr>
        <tr>
          <td style="color:#6b7280;padding:4px 0">パスワード</td>
          <td style="font-family:monospace">{password}</td>
        </tr>
      </table>
    </div>

    <a href="{url}" style="display:inline-block;background:#7c3aed;color:white;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:600">
      開発環境を開く →
    </a>

    <p style="color:#6b7280;font-size:12px;margin-top:24px">
      VMはハッカソン終了後に削除されます。成果物は必ずGit pushしてください。
    </p>
  </div>
</body>
</html>"""
    return send_email(to, subject, html)


def send_vm_ready(to: str, name: str, participant_id: str, ip: str):
    url = f"http://p{participant_id}.iseai.neuratools.ai"
    vscode_url = f"http://p{participant_id}.iseai.neuratools.ai:8080"
    return send_welcome(to, name, participant_id, url, vscode_url)
