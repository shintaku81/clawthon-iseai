"""
Clawthon 管理コンソール E2Eテスト
実行: pytest tests/test_console.py --headed  (ブラウザ表示あり)
     pytest tests/test_console.py           (ヘッドレス)

環境変数:
  CONSOLE_URL   管理コンソールのURL (デフォルト: http://34.84.2.212:8000)
  ADMIN_PASS    管理パスワード       (デフォルト: clawthon2026)
  P01_URL       参加者01のURL       (デフォルト: http://34.84.208.211)
  P02_URL       参加者02のURL       (デフォルト: http://34.84.240.90)
"""
import os
import pytest
from playwright.sync_api import Page, expect

CONSOLE_URL = os.getenv("CONSOLE_URL", "http://34.84.2.212:8000")
ADMIN_PASS  = os.getenv("ADMIN_PASS",  "clawthon2026")
P01_URL     = os.getenv("P01_URL",     "http://34.84.208.211")
P02_URL     = os.getenv("P02_URL",     "http://34.84.240.90")


# ─── ヘルパー ────────────────────────────────────────

def login(page: Page):
    page.goto(f"{CONSOLE_URL}/login")
    page.fill("input[name=password]", ADMIN_PASS)
    page.click("button[type=submit]")
    # gcloudコマンド実行のため20秒待つ
    page.wait_for_url(f"{CONSOLE_URL}/", timeout=20000)
    page.wait_for_load_state("networkidle", timeout=20000)


# ─── テスト ──────────────────────────────────────────

class TestLogin:
    def test_login_page_loads(self, page: Page):
        page.goto(f"{CONSOLE_URL}/login")
        expect(page.locator("h1")).to_contain_text("Clawthon ISEAI")
        expect(page.locator("input[name=password]")).to_be_visible()

    def test_wrong_password_rejected(self, page: Page):
        page.goto(f"{CONSOLE_URL}/login")
        page.fill("input[name=password]", "wrongpassword")
        page.click("button[type=submit]")
        expect(page).to_have_url(f"{CONSOLE_URL}/login?error=%E3%83%91%E3%82%B9%E3%83%AF%E3%83%BC%E3%83%89%E3%81%8C%E9%81%95%E3%81%84%E3%81%BE%E3%81%99")
        expect(page.locator(".error")).to_be_visible()

    def test_correct_password_redirects_to_dashboard(self, page: Page):
        login(page)
        expect(page.locator("header h1")).to_contain_text("Clawthon ISEAI 管理コンソール")

    def test_unauthenticated_redirects_to_login(self, page: Page):
        page.goto(CONSOLE_URL)
        expect(page).to_have_url(f"{CONSOLE_URL}/login")

    def test_logout(self, page: Page):
        login(page)
        page.goto(f"{CONSOLE_URL}/logout")
        expect(page).to_have_url(f"{CONSOLE_URL}/login")


class TestDashboard:
    def test_dashboard_shows_participant_count(self, page: Page):
        login(page)
        expect(page.locator("header .stat").first).to_contain_text("参加者")

    def test_participants_listed(self, page: Page):
        login(page)
        rows = page.locator("table tbody tr")
        expect(rows).to_have_count(2)

    def test_participant_emails_visible(self, page: Page):
        login(page)
        content = page.locator("table tbody").inner_text()
        assert "masahiro@takechi.jp" in content

    def test_vm_status_badges_visible(self, page: Page):
        login(page)
        badges = page.locator(".badge")
        expect(badges.first).to_be_visible()

    def test_add_participant_form_exists(self, page: Page):
        login(page)
        expect(page.locator("input[name=name]")).to_be_visible()
        expect(page.locator("input[name=email]")).to_be_visible()

    def test_add_participant(self, page: Page):
        login(page)
        initial_count = page.locator("table tbody tr").count()
        page.fill("input[name=name]", "テスト追加ユーザー")
        page.fill("input[name=email]", "test_add@example.com")
        page.click("button.btn-add")
        page.wait_for_url(CONSOLE_URL + "/", timeout=25000)
        page.wait_for_load_state("networkidle", timeout=25000)
        new_count = page.locator("table tbody tr").count()
        assert new_count == initial_count + 1
        # テスト後にクリーンアップ（追加した参加者を削除）
        response = page.request.delete(f"{CONSOLE_URL}/api/participants/test_cleanup")
        # 削除APIがなくてもOK（次回テスト前にリセット）

    def test_api_status_endpoint(self, page: Page):
        login(page)
        response = page.request.get(f"{CONSOLE_URL}/api/status")
        assert response.status == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 2


class TestVMAccess:
    def test_p01_nginx_responds(self, page: Page):
        response = page.request.get(P01_URL, timeout=10000)
        assert response.status in [200, 302, 301]

    def test_p02_nginx_responds(self, page: Page):
        response = page.request.get(P02_URL, timeout=10000)
        assert response.status in [200, 302, 301]

    def test_p01_code_server_responds(self, page: Page):
        response = page.request.get(f"{P01_URL}:8080", timeout=15000)
        assert response.status in [200, 302, 301]

    def test_p02_code_server_responds(self, page: Page):
        response = page.request.get(f"{P02_URL}:8080", timeout=15000)
        assert response.status in [200, 302, 301]

    def test_code_server_login_page(self, page: Page):
        page.goto(f"{P01_URL}:8080/login", timeout=15000)
        expect(page.locator("body")).to_be_visible()


class TestVMOperations:
    def test_vm_stop_button_visible_for_running(self, page: Page):
        login(page)
        # RUNNING状態のVMに「停止」ボタンがあること
        running_rows = page.locator("tr:has(.badge-RUNNING)")
        if running_rows.count() > 0:
            stop_btn = running_rows.first.locator(".btn-stop")
            expect(stop_btn).to_be_visible()

    def test_api_key_settings_expandable(self, page: Page):
        login(page)
        # detailsを展開してAPIキー設定フォームが見えること
        details = page.locator("details").first
        details.click()
        expect(page.locator("input[name=api_key]").first).to_be_visible()
