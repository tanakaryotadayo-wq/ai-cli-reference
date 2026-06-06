---
name: docx-generator
description: "DOCX/PDFドキュメントの生成・編集・レンダリング検証。python-docxで作成し、soffice→PDF→PNGで全ページ目視確認。原典: Codex CLI doc"
---

# DOCX Generator（Codex CLI 移植）

## 使用タイミング
- DOCXコンテンツの読み取り・レビュー（レイアウトが重要な場合）
- プロフェッショナルなフォーマットのDOCX作成・編集
- 納品前のビジュアルレイアウト検証

## ワークフロー
1. **ビジュアルレビュー優先**: `soffice` + `pdftoppm` で DOCX→PDF→PNG 変換
2. **python-docx で編集**: 見出し、スタイル、テーブル、リスト
3. **変更のたびに再レンダリング・検査**
4. ビジュアルレビュー不可の場合は python-docx でテキスト抽出（レイアウトリスクを明示）

## レンダリングコマンド
```bash
# DOCX → PDF
soffice -env:UserInstallation=file:///tmp/lo_profile_$$ --headless --convert-to pdf --outdir $OUTDIR $INPUT_DOCX

# PDF → PNG
pdftoppm -png $OUTDIR/$BASENAME.pdf $OUTDIR/$BASENAME
```

## 依存関係（uv優先）
```bash
uv pip install python-docx pdf2image
brew install libreoffice poppler  # macOS
```

## 品質基準
- 一貫したタイポグラフィ、スペーシング、マージン、明確な階層構造
- クリップ/オーバーラップ、壊れたテーブル、文字化けなし
- ASCIIハイフンのみ使用（U+2011禁止）
- プレースホルダー文字列を残さない

## 最終チェック
- 全ページを100%ズームで再レンダリング・検査
- スペーシング/アライメント/ページネーションの問題を修正→再レンダリング
- 一時ファイルの残りがないことを確認
