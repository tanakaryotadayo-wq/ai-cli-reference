---
name: playwright-browser
description: "Playwright CLIでブラウザ操作を自動化する。ナビゲーション、フォーム入力、スナップショット、スクリーンショット、データ抽出、UIフローのデバッグ。原典: Codex CLI playwright"
---

# Playwright Browser（Codex CLI 移植）

ターミナルからブラウザを操作する。CLI操作優先。テストスペック生成はユーザーが明示的に求めた場合のみ。

## 前提条件
`npx` が利用可能であること。なければ Node.js/npm のインストールを案内。

## コアワークフロー
1. **ページを開く**: `open <url>`
2. **スナップショット取得**: `snapshot` で安定した要素refを取得
3. **操作**: 最新のスナップショットのrefを使って操作
4. **再スナップショット**: ナビゲーションや大きなDOM変更の後
5. **アーティファクト取得**: screenshot, pdf, traces

## 再スナップショットが必要なタイミング
- ナビゲーション後
- UIを大きく変更する要素のクリック後
- モーダル/メニューの開閉後
- タブ切り替え後
- refが見つからないエラー発生時

## 主要パターン

### フォーム入力・送信
```bash
open <url>/form → snapshot → fill e1 "value" → fill e2 "value" → click e3 → snapshot
```

### UIフローのデバッグ（トレース付き）
```bash
open <url> --headed → tracing-start → 操作... → tracing-stop
```

### マルチタブ
```bash
tab-new <url> → tab-list → tab-select 0 → snapshot
```

## ガードレール
- 要素参照（e12等）を使う前に必ずsnapshot
- refsが古くなったら再snapshot
- `eval`/`run-code`より明示的コマンドを優先
- `--headed` でビジュアル確認が有効な場面で使う
