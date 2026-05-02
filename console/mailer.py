import smtplib, os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_NAME = os.getenv("FROM_NAME", "Clawthon ISEAI")
FROM_ADDR = os.getenv("FROM_EMAIL", SMTP_USER)
DOMAIN = os.getenv("DOMAIN", "iseai.neuratools.ai")


def send_email(to: str, subject: str, html: str) -> bool:
    if not SMTP_USER or not SMTP_PASS:
        print(f"[mailer] SMTP未設定 — 送信スキップ: {to} / {subject}")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{FROM_NAME} <{FROM_ADDR}>"
        msg["To"] = to
        msg.attach(MIMEText(html, "html", "utf-8"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.ehlo()
            s.starttls()
            s.ehlo()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(FROM_ADDR, to, msg.as_string())
        print(f"[mailer] 送信成功: {to}")
        return True
    except Exception as e:
        print(f"[mailer] 送信失敗: {e}")
        return False


def send_welcome(to: str, name: str, pid: str, vscode_pass: str = "clawthon2026"):
    base_url = f"https://p{pid}.{DOMAIN}"
    openhands_url = f"{base_url}/openhands/"
    vscode_url = f"{base_url}/code/"

    subject = "【Clawthon ISEAI】あなたの開発環境が準備できました"
    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:'Helvetica Neue',Arial,'Hiragino Sans',sans-serif">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0">
    <tr><td align="center">
      <table width="580" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08)">

        <!-- ヘッダー -->
        <tr>
          <td style="background:#111827;padding:32px 40px">
            <table width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td>
                  <span style="font-family:'Space Grotesk',Arial,sans-serif;font-size:20px;font-weight:700;color:#ffffff;letter-spacing:-0.5px">Claw<span style="color:#ff747d">thon</span></span>
                  <span style="font-family:Arial,sans-serif;font-size:12px;color:#6b7280;margin-left:8px">ISEAI</span>
                </td>
                <td align="right">
                  <span style="background:#ff747d;color:white;font-size:11px;font-weight:700;padding:4px 10px;border-radius:20px;letter-spacing:1px">READY</span>
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- ボディ -->
        <tr>
          <td style="padding:40px">
            <h1 style="font-size:22px;font-weight:700;color:#111827;margin:0 0 8px">
              開発環境の準備ができました 🎉
            </h1>
            <p style="font-size:15px;color:#6b7280;margin:0 0 32px;line-height:1.6">
              {name} さん、Clawthon ISEAIへようこそ。<br>
              専用の開発環境が起動しました。以下の情報を使って始めてください。
            </p>

            <!-- URL情報ボックス -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#f9fafb;border:1.5px solid #e5e7eb;border-radius:12px;margin-bottom:28px">
              <tr>
                <td style="padding:24px">
                  <p style="font-family:Arial,sans-serif;font-size:11px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#9ca3af;margin:0 0 16px">アクセス情報</p>

                  <table width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                      <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;width:120px;font-size:12px;color:#6b7280;vertical-align:top;padding-top:10px">参加者ID</td>
                      <td style="padding:8px 0;border-bottom:1px solid #e5e7eb;font-size:14px;font-weight:600;color:#111827">p{pid}</td>
                    </tr>
                    <tr>
                      <td style="padding:10px 0;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280;vertical-align:top;padding-top:12px">OpenHands<br><span style="font-size:10px;color:#9ca3af">(AIエージェント)</span></td>
                      <td style="padding:10px 0;border-bottom:1px solid #e5e7eb">
                        <a href="{openhands_url}" style="color:#ff747d;font-size:13px;text-decoration:none;word-break:break-all">{openhands_url}</a>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding:10px 0;border-bottom:1px solid #e5e7eb;font-size:12px;color:#6b7280;vertical-align:top;padding-top:12px">VSCode<br><span style="font-size:10px;color:#9ca3af">(コードエディタ)</span></td>
                      <td style="padding:10px 0;border-bottom:1px solid #e5e7eb">
                        <a href="{vscode_url}" style="color:#ff747d;font-size:13px;text-decoration:none;word-break:break-all">{vscode_url}</a>
                      </td>
                    </tr>
                    <tr>
                      <td style="padding:10px 0;font-size:12px;color:#6b7280;vertical-align:top;padding-top:12px">VSCodeパスワード</td>
                      <td style="padding:10px 0">
                        <code style="background:#f3f4f6;border:1px solid #e5e7eb;padding:4px 10px;border-radius:6px;font-size:13px;color:#374151">{vscode_pass}</code>
                      </td>
                    </tr>
                  </table>
                </td>
              </tr>
            </table>

            <!-- CTAボタン -->
            <table cellpadding="0" cellspacing="0" style="margin-bottom:28px">
              <tr>
                <td style="border-radius:8px;background:#ff747d">
                  <a href="{base_url}" style="display:inline-block;padding:14px 32px;color:white;text-decoration:none;font-size:14px;font-weight:700;letter-spacing:0.3px">
                    開発環境を開く →
                  </a>
                </td>
              </tr>
            </table>

            <!-- 注意書き -->
            <table width="100%" cellpadding="0" cellspacing="0" style="background:#fff7ed;border:1px solid #fed7aa;border-radius:8px">
              <tr>
                <td style="padding:16px 20px;font-size:13px;color:#92400e;line-height:1.6">
                  ⚠️ <strong>注意：</strong>ハッカソン終了後にVMは削除されます。成果物は必ずGitHubにpushしてください。
                </td>
              </tr>
            </table>
          </td>
        </tr>

        <!-- フッター -->
        <tr>
          <td style="background:#f9fafb;border-top:1px solid #e5e7eb;padding:20px 40px">
            <p style="font-size:11px;color:#9ca3af;margin:0;text-align:center">
              Clawthon ISEAI — このメールに返信しても届きません
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""
    return send_email(to, subject, html)


def send_vm_ready(to: str, name: str, participant_id: str, ip: str):
    return send_welcome(to, name, participant_id)
