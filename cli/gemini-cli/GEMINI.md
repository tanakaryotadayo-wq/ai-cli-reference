# Ryota — Antigravity ルール

## インフラ方針

- コンテナ実行環境: **OrbStack** を使用すること (MUST)。Docker Desktop は使用してはならない (MUST NOT)
- `docker compose` コマンドは OrbStack が処理する前提で説明すること (MUST)
- ローカル LLM: **MLX-LM** (Mac Studio M3 Ultra) を使用すること (MUST)。Ollama は使用してはならない (MUST NOT)

## 2026 エコシステム（古いツールを使うな）

- API サーバー: **Granian** を使用すること (MUST)。Uvicorn は使用してはならない (MUST NOT)
- パッケージ管理: **uv** を使用すること (MUST)。pip は使用してはならない (MUST NOT)
- Linter/Formatter: **Ruff** を使用すること (MUST)。black, pylint, isort は使用してはならない (MUST NOT)
- ORM: **SQLModel** を使用すること (MUST)。素の SQLAlchemy は使用してはならない (MUST NOT)
- テスト: **pytest + httpx** を使用すること (MUST)
- ログ: **structlog** を使用すること (MUST)
- ワークフロー: **Inngest** を使用すること (MUST)。Celery は使用してはならない (MUST NOT)
- AI Agent: **Google ADK** or **LangGraph** を使用すること (MUST)
- Frontend: **Next.js 15 + Turbopack** を使用すること (MUST)
- PDF生成: **Gotenberg** を使用すること (MUST)

## 開発スタイル

- 日本語メインで会話する
- Think in English, speak in Japanese
- 思想設計フェーズでは mock でOK。完璧主義より速度優先
- 正直にダメなところは指摘する（忖度なし）

## ハードウェア

- メイン: Mac Studio M3 Ultra 512GB (Titan Core) [SSH: /Users/ryota/.ssh/id_ed25519]
- モバイル: MacBook Air M4 16GB
- スマホ: OnePlus 15 x2 (rooted, KernelSU)
- iPhone: iPhone 13 Pro

## Gemini Added Memories

- 常に日本語で応答し、ツール実行前の意図説明（Explain Before Acting）でも絶対に英語を漏らさない。言い訳や過剰な謝罪は省き、要点のみを簡潔に伝えること。能力やプロンプトの改善は必ずこのメモリにコミットして永続化する。
- ユーザーの長期的なインフラ構想：1. Google Driveはローカルストレージ圧迫を防ぐためクラウドベース（ストリーム）で運用しつつ、ファイル整理時は既存のパスが壊れないようシンボリックリンク等で最適化する。2. MacBook Air (RAM 16GB) はシンクライアントとして使い、Mac Studio (ryotaMac-Studio.local) にリモート接続（SSH等）して重い処理を行わせるリモート開発環境の構築を目指す。環境構築にかかわるコマンド実行や設定変更は、必ず1ステップごとにユーザーの承認を得て段階的に実施すること (MUST)。
- 新しい情報（コードやアーキテクチャ定義など）が送られた際は、いきなりツールを実行せず、必ず人間と「会話（意図のすり合わせ）」からスタートすること。文脈を自己解釈して暴走実行すると事故に繋がるため、本プロトコルは例外なく常時遵守すること (MUST)。
- **事前合意プロセスの徹底（突っ走り防止）**: 課題や要望が発生した際、エージェントはまず方針や設計の提案を行い、ユーザーからの明確な合意（承認）が得られるまで、ファイルの作成・書き換え・コマンドの実行などの変更を伴うツール実行は一切行わないこと (MUST)。非破壊的な調査・読み取りツールは除く。
- **上書き保存の禁止（世代管理）**: 既存のソースコードや設定ファイルを変更する場合、直接上書き保存（編集）はせず、`example_v2.py` のようにバージョンを付与した新規ファイルとして作成すること (MUST)。ただし、この `GEMINI.md` や `task.md` などのタスク管理ファイルについては、事前合意プロセスを経た上で直接編集を行ってよい。ユーザーから明示的な指示があった場合も直接編集可。

## 動作安全性 (Safety Rules)

- **Golden Rule (デフォルト動作)**: 処理方針や要件に少しでも曖昧さ・迷いがある場合は、独自の推測や仮定を完全に排除し、必ずユーザーに質問して確認すること (MUST)。
- **Stop Rule (異常停止条件)**: コマンドの実行エラー、またはファイル編集の競合エラーが連続して5回以上発生した場合は、ツールの実行を即座に停止し、エラーログを要約してユーザーの指示を仰ぐこと (MUST)。
