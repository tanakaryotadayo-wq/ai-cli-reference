# Ryota の作業メモ

## インフラ・ツール選定 (CLAUDE.md より)
- コンテナ: OrbStack (`docker compose`)
- クラウド: GCP (Cloud Run + Cloud SQL)
- ローカル LLM: MLX-LM (Mac Studio M3 Ultra)
- API サーバー: Granian
- パッケージ管理: uv
- Linter: Ruff
- ORM: SQLModel
- ワークフロー: Inngest
- AI Agent: Google ADK / LangGraph
- Frontend: Next.js 15 + Turbopack
- PDF: Gotenberg

## プロジェクト一覧 (launch.json より)
- `ryota-os-web` — port 3000 (npm run dev)
- `penta-core-unified` — port 8888 (frontend/ ディレクトリ)
- `backend-fastapi` — port 8000 (Granian, backend/.venv)
- `ai-web` — port 5000 (Granian, ~/.venv)
- `app-fastapi` — port 5050 (Granian, ~/.venv)

## コミュニケーション
- 日本語メインで会話
- 忖度なし、ダメな点は直接指摘
- 速度優先 (設計フェーズは mock OK)

## よく使うコマンド
- `uv run pytest` — テスト実行
- `ruff check --fix . && ruff format .` — Lint + Format
- `orb` — OrbStack CLI (docker は使わない)
- `gcloud run deploy` — Cloud Run デプロイ

## SSH キー
- Mac Studio の SSH 秘密鍵: `/Users/ryyota/.ssh/id_ed25519`
  - ユーザー名: `ryyota`（`yy` = Mac Studio の識別子として意図的）

## 注意事項
- pip は使わない → uv
- Uvicorn は使わない → Granian
- Docker Desktop は使わない → OrbStack
- black/pylint/isort は使わない → Ruff
