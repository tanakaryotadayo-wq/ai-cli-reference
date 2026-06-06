---
name: gh-fix-ci
description: "GitHub ActionsのCI失敗を診断・修復する。ghコマンドで失敗チェックとログを取得し、失敗スニペットを要約してから修復プランを提示。承認後に実装。原典: Codex CLI gh-fix-ci"
---

# GH Fix CI（Codex CLI 移植）

GitHub PRの失敗チェックを特定し、GitHub Actionsログから実用的な失敗情報を取得、要約してから修復プランを提案・実装する。

## 前提条件
`gh auth login` で認証済みであること（repo + workflow スコープ必要）。`gh auth status` で確認。

## ワークフロー

1. **認証確認**: `gh auth status`
   - 未認証なら `gh auth login` を案内（repo + workflow スコープ確保）

2. **PR特定**: 
   - カレントブランチ: `gh pr view --json number,url`
   - ユーザー指定: PR番号またはURLをそのまま使用

3. **失敗チェック検査**（GitHub Actionsのみ）:
   - `gh pr checks <pr> --json name,state,bucket,link,startedAt,completedAt,workflow`
   - **フィールドエラー時のフォールバック**: gh がフィールドを拒否した場合、エラーメッセージに表示される利用可能フィールドで再実行する
   - 各失敗チェックのrun IDを `detailsUrl` から抽出:
     - `gh run view <run_id> --json name,workflowName,conclusion,status,url,event,headBranch,headSha`
     - `gh run view <run_id> --log`
   - **進行中のジョブ**: run logが"in progress"の場合、ジョブログを直接取得:
     - `gh api "/repos/<owner>/<repo>/actions/jobs/<job_id>/logs"`

4. **外部CIのスコープ**: `detailsUrl` がGitHub Actionsのrunでない場合、外部CIとしてURLのみ報告。Buildkite等の分析は行わない。

5. **失敗の要約**: 
   - 失敗チェック名
   - run URL（存在する場合）
   - 簡潔なログスニペット（エラー箇所の前後）
   - ログが取得できない場合は明示的に報告

6. **修復プラン作成**: 承認を要求してから実装

7. **承認後に実装**: diff/テストを要約し、PR作成を提案

8. **再確認**: 修正後にテスト再実行と `gh pr checks` で確認
