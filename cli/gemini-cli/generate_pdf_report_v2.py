#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "markdown",
#     "requests",
#     "structlog",
# ]
# ///

import argparse
import sys
from pathlib import Path
import markdown
import requests
import structlog

# structlogの設定
structlog.configure(processors=[structlog.processors.JSONRenderer()])
logger = structlog.get_logger()

# プレミアムなCSSを内包したHTMLテンプレート (Wick-Loop 定量評価用)
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>Wick-Loop ループ脱出制御 定量ベンチマークレポート</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&family=Outfit:wght@400;700&display=swap');
        
        body {{
            font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
            color: #1e293b;
            background-color: #ffffff;
            line-height: 1.6;
            margin: 0;
            padding: 0;
        }}
        
        .container {{
            max-width: 850px;
            margin: 0 auto;
            padding: 40px 30px;
        }}
        
        /* プレミアムなグラデーションヘッダー (コバルトブルーからダークスレートへ) */
        .header {{
            background: linear-gradient(135deg, #1e3a8a 0%, #0f172a 100%);
            color: #ffffff;
            padding: 40px;
            border-radius: 16px;
            margin-bottom: 40px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.15), 0 8px 10px -6px rgba(0, 0, 0, 0.15);
        }}
        
        .header h1 {{
            font-family: 'Outfit', sans-serif;
            font-size: 34px;
            font-weight: 700;
            margin: 0 0 10px 0;
            letter-spacing: -0.02em;
        }}
        
        .header p {{
            font-size: 16px;
            color: #93c5fd;
            margin: 0;
            font-weight: 500;
        }}
        
        h2 {{
            font-family: 'Outfit', sans-serif;
            font-size: 22px;
            color: #0f172a;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 8px;
            margin-top: 40px;
            margin-bottom: 20px;
        }}
        
        h3 {{
            font-family: 'Outfit', sans-serif;
            font-size: 18px;
            color: #1e293b;
            margin-top: 30px;
        }}
        
        /* テーブルのプレミアムデザイン (Wick-Loop用ハイライトあり) */
        table {{
            width: 100%;
            border-collapse: separate;
            border-spacing: 0;
            margin: 24px 0;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #cbd5e1;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }}
        
        th {{
            background-color: #f1f5f9;
            color: #1e293b;
            font-weight: 600;
            text-align: left;
            padding: 14px 16px;
            border-bottom: 2px solid #cbd5e1;
            font-size: 13px;
            letter-spacing: 0.02em;
        }}
        
        td {{
            padding: 14px 16px;
            border-bottom: 1px solid #e2e8f0;
            font-size: 13px;
            color: #334155;
        }}
        
        tr:last-child td {{
            border-bottom: none;
        }}
        
        tr:nth-child(even) {{
            background-color: #f8fafc;
        }}
        
        /* Wick-Loopの行をプレミアムグリーンでハイライト */
        tr.highlight-row {{
            background-color: #f0fdf4 !important;
            font-weight: 600;
        }}
        tr.highlight-row td {{
            color: #15803d;
            border-bottom: 1px solid #bbf7d0;
        }}
        
        /* 特徴的な指標バッジ */
        .metric-val {{
            font-weight: 600;
            color: #0f172a;
        }}
        
        /* リストの調整 */
        ul {{
            padding-left: 20px;
        }}
        
        li {{
            margin-bottom: 8px;
            color: #475569;
            font-size: 14px;
        }}
        
        /* 印刷用のページ崩れ対策 */
        @media print {{
            .container {{
                padding: 0;
            }}
            .header {{
                box-shadow: none;
                border: 1px solid #cbd5e1;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>QUANTITATIVE BENCHMARK REPORT</h1>
            <p>Wick-Loop Instanton Theorem V6.4 - 量子作用ループ脱出実測評価証明書</p>
        </div>
        <div class="content">
            {content}
        </div>
    </div>
</body>
</html>
"""


def render_markdown_to_html(md_path: Path) -> str:
    """
    Markdownファイルを読み込み、HTMLにレンダリングする。
    Wick-Loopの行を検出し、ハイライト行用のクラスを追加する。
    """
    if not md_path.exists():
        logger.error("markdown_file_not_found", path=str(md_path))
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    md_text = md_path.read_text(encoding="utf-8")

    # markdownパッケージでHTML化
    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])

    # Wick-Loop (V6.4) のテーブル行にクラスを付与する
    # 例: "<tr>\n<td><strong>Wick-Loop (V6.4)</strong></td>" -> "<tr class="highlight-row">\n<td><strong>Wick-Loop (V6.4)</strong></td>"
    html_body = html_body.replace(
        "<tr>\n<td><strong>Wick-Loop (V6.4)</strong></td>",
        '<tr class="highlight-row">\n<td><strong>Wick-Loop (V6.4)</strong></td>'
    )
    # 改行コードの差異を吸収するための予備置換
    html_body = html_body.replace(
        "<tr><td><strong>Wick-Loop (V6.4)</strong></td>",
        '<tr class="highlight-row"><td><strong>Wick-Loop (V6.4)</strong></td>'
    )


    # テンプレートに埋め込む
    final_html = HTML_TEMPLATE.format(content=html_body)
    logger.info("markdown_rendered_to_html", source=str(md_path))
    return final_html


def convert_html_to_pdf_via_gotenberg(
    html_content: str, output_pdf_path: Path, gotenberg_url: str
) -> bool:
    """
    Gotenberg APIに対してHTMLコンテンツをPOST送信し、PDFを生成して保存する。
    """
    try:
        convert_url = f"{gotenberg_url}/forms/chromium/convert/html"

        files = {"files": ("index.html", html_content, "text/html")}

        # A4サイズと余白
        data = {
            "paperWidth": "8.27",
            "paperHeight": "11.7",
            "marginTop": "0.5",
            "marginBottom": "0.5",
            "marginLeft": "0.5",
            "marginRight": "0.5",
        }

        logger.info("gotenberg_api_request_started", url=convert_url)
        response = requests.post(convert_url, files=files, data=data, timeout=30)

        if response.status_code != 200:
            logger.error(
                "gotenberg_api_failed", status=response.status_code, error=response.text
            )
            return False

        output_pdf_path.write_bytes(response.content)
        logger.info(
            "pdf_report_generated",
            path=str(output_pdf_path),
            size_bytes=len(response.content),
        )
        return True

    except Exception as e:
        logger.error("gotenberg_connection_error", error=str(e))
        return False


def main():
    parser = argparse.ArgumentParser(
        description="MarkdownベンチマークレポートをGotenbergでPDFに変換する"
    )
    parser.add_argument(
        "--input", type=str, required=True, help="入力マークダウンファイルのパス"
    )
    parser.add_argument(
        "--output", type=str, default="benchmark_report.pdf", help="出力PDFファイルのパス"
    )
    parser.add_argument(
        "--url", type=str, default="http://localhost:3000", help="GotenbergのベースURL"
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    logger.info(
        "pdf_generation_started", input=str(input_path), output=str(output_path)
    )

    try:
        html_content = render_markdown_to_html(input_path)
        success = convert_html_to_pdf_via_gotenberg(html_content, output_path, args.url)

        if success:
            logger.info("pdf_generation_completed", success=True)
            sys.exit(0)
        else:
            logger.error("pdf_generation_completed", success=False)
            sys.exit(1)

    except Exception as e:
        logger.error("pdf_generation_failed", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
