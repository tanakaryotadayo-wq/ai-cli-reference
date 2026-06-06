---
name: gh-address-comments
description: "GitHub PRのレビューコメント・issueコメントを番号付きで一覧化し、ユーザーが選択したものだけ修正を適用する。原典: Codex CLI gh-address-comments"
---

# GH Address Comments（Codex CLI 移植）

PRのレビュー/issueコメントをghコマンドで取得し、対応する。

## 前提条件
`gh auth login` で認証済みであること。`gh auth status` で確認。

## ワークフロー

1. **コメント取得**: PRの全コメント・レビュースレッドを取得
2. **一覧提示**: 全レビュースレッドとコメントに番号を振り、各項目の修正に必要な内容の短い要約を提示
3. **ユーザーに選択させる**: どの番号のコメントに対応するか確認
4. **選択されたコメントのみ修正**: ユーザーが選んだものだけ修正を適用

## 注意事項
- gh で認証/レート制限エラーが出たら、`gh auth login` での再認証を促してリトライ
