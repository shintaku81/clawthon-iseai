# Clawthon ISEAI — 開発用コマンド

.PHONY: dev test test-local deploy check

# ローカル開発サーバー起動
dev:
	cd console && \
	DATA_FILE=/tmp/clawthon-test-participants.json \
	ADMIN_PASSWORD=clawthon2026 \
	ADMIN_EMAILS=masahiro@takechi.jp,r.sonoda@protocore.co.jp \
	uvicorn app:app --reload --port 8000

# E2Eテスト (本番)
test:
	cd e2e && npx playwright test

# E2Eテスト (ローカル)
test-local:
	cd e2e && CONSOLE_URL=http://localhost:8000 npx playwright test

# ローカルでテストしてからデプロイ (推奨フロー)
check:
	@echo "=== 構文チェック ==="
	python3 -c "import ast; ast.parse(open('console/app.py').read()); print('app.py OK')"
	@echo "=== E2Eテスト (ローカル) ==="
	@echo "※ make dev を別ターミナルで起動してから実行してください"
	cd e2e && CONSOLE_URL=http://localhost:8000 npx playwright test

# デプロイ (git push → GitHub Actions)
deploy:
	git push
