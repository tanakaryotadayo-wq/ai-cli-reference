# AI CLI 参考データ

AI CLI ツール（Copilot CLI, Claude Code, Codex CLI, Gemini CLI/Antigravity 等）のスキル・エージェント・MCP・設定の参照用知識ベース。

## 構造

```
ai-cli-reference/
├── skills/              # スキル定義の参照コレクション
│   ├── review/          # レビュー系（コード・プロンプト・セキュリティ）
│   ├── automation/      # 自動化・ワークフロー系
│   ├── security/        # セキュリティ・監査・ガバナンス系
│   ├── devops/          # CI/CD・GitHub Actions・デプロイ系
│   └── meta/            # スキル作成・改善・評価系
├── agents/              # エージェント定義の参照
├── cli/                 # CLI設定・使い方の参照
│   ├── copilot-cli/     # GitHub Copilot CLI
│   ├── claude-code/     # Claude Code
│   ├── codex-cli/       # OpenAI Codex CLI
│   └── gemini-cli/      # Gemini CLI / Antigravity
├── mcp/                 # MCPサーバー定義の参照
├── schemas/             # スキルスキーマテンプレート等
└── sources.md           # 収集元URL一覧
```

## 収集元

- [github/awesome-copilot](https://github.com/github/awesome-copilot) — GitHub公式コミュニティスキル集
- OpenAI Codex CLI 内蔵エージェント
- Claude Code 設定・スキル
- Gemini CLI / Antigravity SDK
- その他コミュニティソース

## 用途

- 新しいスキルを作成する際のパターン参照
- 既存スキルの改善（prompt-critic 等）の比較材料
- CLI設定のベストプラクティス集
- `grep` で横断検索して設計パターンを発見
