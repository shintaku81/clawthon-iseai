# Clawthon ISEAI — 実装仕様書

> 作成: 2026-05-02  
> ステータス: 実装待ち

---

## タスク一覧（優先順）

| # | タスク | 対象ファイル | ステータス |
|---|--------|-------------|----------|
| T1 | 参加者ポータルリンクを管理コンソールに追加 | `console/templates/index.html` | 未着手 |
| T2 | manual.html — OpenClaw中心へ全面改修 | `console/templates/manual.html` | 未着手 |
| T3 | cloud-init — Claude Code CLI インストール | `infra/cloud-init-participant.yaml` | 未着手 |
| T4 | APIキーマスキング（複数登録・GitHub式） | `console/app.py`, `console/templates/index.html` | 未着手 |
| T5 | SMTP設定をメールVMに更新（SSH） | サーバー上 `/opt/clawthon/console/.env` | 未着手 |
| T6 | OpenClawバージョン表示（管理コンソール） | `console/app.py`, `console/templates/index.html` | 未着手 |

---

## T1: 参加者ポータルリンク

**要件**: 管理コンソールのヘッダーナビから参加者向けポータルURLを開けるようにする

### 実装内容

`console/templates/index.html` のヘッダー `<div class="header-nav">` に追加:

```html
<a href="https://console.iseai.neuratools.ai/portal" target="_blank">参加者ポータル</a>
```

実際の参加者URLは各VMごとに異なるため、参加者テーブル内の「アクセス」列に
`https://pXX.iseai.neuratools.ai/` へのリンクを追加する（既存の `/openhands/`, `/code/` に加えて）。

また、ヘッダーに「参加者向けページを開く」ドロップダウンまたはリンクを追加:
- p01〜p10 それぞれのトップURL

**ヘッダーナビ追加案**:
```html
<a href="#" onclick="openParticipantSelector()">参加者ページ ↗</a>
```

もしくは、各参加者行にトップURLリンクを追加するシンプルな実装でよい。

---

## T2: manual.html — OpenClaw中心改修

**要件**: ハッカソンの主役は OpenClaw (Claude Code CLI)。OpenHandsはサブ機能に格下げ。

### 変更点

**サイドナビ変更**:
```
Before: OpenHands（メインセクション）
After:  OpenClaw / Claude Code（メインセクション）
        OpenHands（サブセクション）
```

**概要セクション変更**:
- 「OpenHands + VSCode の開発環境」→「**Claude Code (OpenClaw)** による AI コーディング環境」
- 参加者は Claude Code CLI をターミナルから使用する

**VMサービス一覧テーブル変更**:
| サービス | 変更 |
|---------|-----|
| OpenHands | 「サブツール（任意）」に格下げ |
| VSCode | 「ターミナル・ファイル操作用」に変更 |
| OpenClaw | 新規追加「**メインツール** - Claude Code CLI」 |

**新規セクション「OpenClaw の操作」**:
- Claude Code のインストール確認方法
- 使い方: `cd /opt/clawthon/workspace && claude`
- APIキーの設定方法
- 基本コマンド集

**OpenHandsセクション**:
- タイトルを「OpenHands（サブ機能）」に変更
- 「任意のツール。使いたい場合はAPIキーを設定してください」に変更

---

## T3: cloud-init — Claude Code CLI インストール

**要件**: 参加者VMにClaude Code CLIを自動インストール

### 実装内容

`infra/cloud-init-participant.yaml` の `runcmd` に追加:

```yaml
# Claude Code (OpenClaw) インストール
- npm install -g @anthropic-ai/claude-code || true
- ln -sf $(which claude) /usr/local/bin/claw || true
```

**前提**: Node.js が必要 → packages に `nodejs`, `npm` 追加

```yaml
packages:
  - docker.io
  - docker-compose-v2
  - nginx
  - certbot
  - python3-certbot-nginx
  - nodejs      # 追加
  - npm         # 追加
```

**バージョン確認コマンド（VMで）**:
```bash
claude --version
```

---

## T4: APIキーマスキング

**要件**: 
- 1参加者に複数APIキー登録可能
- 登録後はマスキング表示（GitHubシークレット式）
- 先頭3文字 + `...` + 末尾3文字 のみ表示
- キー種類（Anthropic / OpenRouter / OpenAI）をラベル表示

### データ構造変更

`participants.json` の各参加者に `api_keys` 配列を追加:

```json
{
  "id": "01",
  "name": "参加者名",
  "email": "...",
  "api_keys": [
    {
      "id": "k1",
      "type": "anthropic",
      "label": "Anthropic",
      "masked": "sk-ant-...XXX",
      "created_at": "2026-05-02T10:00:00"
    }
  ]
}
```

### UI変更 (index.html)

テーブルの「APIキー / モデル」列:
```html
<div class="api-key-chip">
  <span class="key-type-badge anthropic">Anthropic</span>
  <code>sk-ant-...XXX</code>
  <button onclick="deleteKey(pid, kid)">×</button>
</div>
<button onclick="addKey(pid)">+ キー追加</button>
```

### API変更 (app.py)

- `POST /api/vm/{pid}/keys` — キー追加（生値を受け取りマスク後保存）
- `DELETE /api/vm/{pid}/keys/{kid}` — キー削除
- マスク関数: `mask_key(key) → key[:6] + "..." + key[-4:]`

---

## T5: SMTP設定更新（サーバー）

**要件**: 新設のメールVMに向けてSMTP設定を変更

### 設定値

```env
SMTP_HOST=136.110.101.127
SMTP_PORT=587
SMTP_USER=noreply@iseai.neuratools.ai
SMTP_PASS=i6wWnOwY7Y4/7/c6
FROM_EMAIL=noreply@iseai.neuratools.ai
FROM_NAME=Clawthon ISEAI
```

**実施コマンド（SSH）**:
```bash
ssh shintaku81@34.84.2.212 "sudo tee -a /opt/clawthon/console/.env << 'EOF'
SMTP_HOST=136.110.101.127
...
EOF
sudo systemctl restart clawthon-console"
```

---

## T6: OpenClawバージョン表示

**要件**: 管理コンソールのダッシュボードにClaude Codeバージョンを表示

### 実装内容

`app.py` に新エンドポイント:
```python
@app.get("/api/openclaw-version")
async def get_openclaw_version():
    result = subprocess.run(["claude", "--version"], capture_output=True, text=True)
    return {"version": result.stdout.strip()}
```

`index.html` のヘッダー stat-pill:
```html
<div class="stat-pill">
  <span>OpenClaw</span>
  <b id="oc-version">v?.?.?</b>
</div>
```

---

## デプロイフロー

1. ローカル変更 → `git commit` → `git push`
2. GitHub Actions が自動デプロイ（`deploy.yml`）
3. SSH でサーバー側 `.env` 更新が必要な場合は別途実施
