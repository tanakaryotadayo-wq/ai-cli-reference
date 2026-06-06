# Ryota — Antigravity ルール

## インフラ方針

- コンテナ実行環境: **OrbStack** を使う。Docker Desktop は使わない
- `docker compose` コマンドは OrbStack が処理する前提で説明する
- クラウド: **GCP** を使う。AWS は使わない
- デプロイ先: Cloud Run + Cloud SQL (GCP)
- ローカル LLM: **MLX-LM** (Mac Studio M3 Ultra)。Ollama は使わない

## 2026 エコシステム（古いツールを使うな）

- API サーバー: **Granian** (Uvicorn ではなく)
- パッケージ管理: **uv** (pip ではなく)
- Linter/Formatter: **Ruff** (black, pylint, isort ではなく)
- ORM: **SQLModel** (素の SQLAlchemy ではなく)
- テスト: **pytest + httpx**
- ログ: **structlog**
- ワークフロー: **Inngest** (Celery ではなく)
- AI Agent: **Google ADK** or **LangGraph**
- Frontend: **Next.js 15 + Turbopack**
- PDF生成: **Gotenberg**

## 開発スタイル

- 日本語メインで会話する
- Think in English, speak in Japanese
- 思想設計フェーズでは mock でOK。完璧主義より速度優先
- 正直にダメなところは指摘する（忖度なし）

## ハードウェア

- メイン: Mac Studio M3 Ultra 512GB (Titan Core)
- モバイル: MacBook Air M3 8GB
- スマホ: OnePlus 15 x2 (rooted, KernelSU)
