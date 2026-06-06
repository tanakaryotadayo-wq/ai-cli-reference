---
name: docx-generator
description: "DOCX/PDFドキュメントの生成・編集・レンダリング検証。python-docxで作成し、soffice→PDF→PNGで全ページ目視確認。原典: Codex CLI doc"
metadata:
  version: v2
---

# DOCX Generator (DOCX・PDFドキュメント生成ルール)

`python-docx` を用いて高品質なドキュメントを作成・編集し、`soffice` を用いた PDF 変換およびレンダリング確認を一貫して実行する。

## Golden Rule (曖昧性収縮定理)

フォントサイズ、マージン、ページの配置などの視覚的レイアウトや段落スタイルに少しでも不整合・曖昧さがある場合は、推測でファイルを出力してはならない (MUST NOT)。必ず PDF および PNG レンダリングを行い、生成された全ページについてアライメントや重なりがないか視覚的に確認しなければならない (MUST)。

## Stop Rule (散逸停止定理)

`soffice` (LibreOffice) による PDF 変換、または `pdftoppm` による画像化コマンドの実行エラー、あるいはディスク容量不足等の書き込み例外が連続して **5回以上** 発生した場合は、即座に処理を停止し、実行中の環境状態（LibreOfficeのインストール状況やパーミッション）を要約してエラー報告しなければならない (MUST)。

## Task Execution Workflow (最小作用ワークフロー定理)

ドキュメント作成・編集時、エージェントは以下の手順を厳格に実行しなければならない (MUST)。

1. **要件とスタイルの定義**: ドキュメントの構成（見出し階層、テーブル、リスト等）および一貫したスタイル（フォント、余白、カラー等）を定義する。
2. **python-docx による作成/編集**: 定義した要件に基づき、プログラムからドキュメントファイルを生成する。
3. **PDFおよびPNGへの変換**: レンダリング検証のため、LibreOffice および pdftoppm を使用して、生成した DOCX を一時的に PDF に変換し、さらに各ページを PNG 画像化する。
   ```bash
   # DOCX → PDF
   soffice -env:UserInstallation=file:///tmp/lo_profile_$$ --headless --convert-to pdf --outdir $OUTDIR $INPUT_DOCX
   
   # PDF → PNG
   pdftoppm -png $OUTDIR/$BASENAME.pdf $OUTDIR/$BASENAME
   ```
4. **全ページの目視・レイアウト検証**: 画像化されたすべてのページについて、テキストのオーバーラップ、表の崩れ、プレースホルダーの残存がないか徹底して確認し、不具合があれば手順2に戻って修正する。

## 開発環境・ツールチェーン要件 (Ecosystem Constraint)

依存ライブラリのインストールは、必ず `uv` を使用してプロジェクト仮想環境内で行わなければならない (MUST)。
```bash
# 推奨インストール例
uv add python-docx pdf2image
brew install libreoffice poppler  # macOS環境
```
