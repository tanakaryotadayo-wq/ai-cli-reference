# 収集元ソース一覧

## スキル・エージェント

| ソース | URL | 収集数 | 備考 |
|---|---|---|---|
| **GitHub Awesome Copilot** | https://github.com/github/awesome-copilot | スキル30 + エージェント40 | 349個中から厳選 |
| **Gemini CLI / Antigravity** | ローカル `~/.gemini/config/skills/` | 11 | 現在のスキル一式 |
| **OpenAI Codex CLI** | ローカル `~/.codex/` | TBD | 内蔵エージェント設定 |
| **Claude Code** | ローカル `~/.claude/` | TBD | 設定・指示ファイル |

## CLI設定・ドキュメント

| ソース | URL | 備考 |
|---|---|---|
| Copilot CLI 公式ドキュメント | https://docs.github.com/en/copilot/using-github-copilot/using-github-copilot-in-the-command-line | |
| Claude Code ドキュメント | https://docs.anthropic.com/en/docs/claude-code | |
| Gemini CLI ドキュメント | https://github.com/google-gemini/gemini-cli | |
| Codex CLI | https://github.com/openai/codex | |

## スキル仕様

| ソース | URL | 備考 |
|---|---|---|
| Agent Skills Specification | https://agentskills.io/specification | 業界標準SKILL.md仕様 |
| Awesome Copilot Website（検索可能） | https://awesome-copilot.github.com | 全リソース検索・フィルタ |
| Awesome Copilot llms.txt | https://awesome-copilot.github.com/llms.txt | AI向け構造化リスト |

## 厳選基準

349個のスキルから以下の基準で30個を厳選：
1. **環境非依存** — Azure/C#/.NET固有でないもの
2. **メタスキル** — スキル作成・評価・改善に使えるもの
3. **セキュリティ** — エージェントガバナンス・監査系
4. **自動化** — ワークフロー・CI/CD系
5. **レビュー** — コード・コミット・PR系
