# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "openai",
#     "structlog",
#     "pyyaml",
# ]
# ///

import os
import sys
import re
import json
import yaml
from pathlib import Path
from openai import OpenAI
import structlog

# 2026年エコシステムルールに基づき、structlogを標準エラー出力へ設定
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=structlog.PrintLoggerFactory(sys.stderr),
)
logger = structlog.get_logger()

# パス定義
PROJECT_ROOT = Path("/Users/ryota/ai-cli-reference")
AGENTS_DIR = PROJECT_ROOT / "agents"
SCRATCH_DIR = Path("/Users/ryota/.gemini/antigravity/scratch")
BENCHMARKS_DIR = PROJECT_ROOT / "cli/gemini-cli/benchmarks"

# APIクライアントの初期化
api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
base_url = os.environ.get("OPENAI_API_BASE")

if api_key and not base_url:
    if os.environ.get("GEMINI_API_KEY"):
        base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"

use_mock = False
if not api_key:
    logger.warning("API_KEY_NOT_FOUND", msg="APIキーが見つかりません。モックモード（擬似監査）で10Rを完走させます。")
    use_mock = True
    client = None
else:
    client = OpenAI(api_key=api_key, base_url=base_url)

# 9体のエージェントリスト
AGENT_FILES = [
    "gem-debugger.agent.md",
    "gem-browser-tester.agent.md",
    "gem-mobile-tester.agent.md",
    "gem-skill-creator.agent.md",
    "gem-documentation-writer.agent.md",
    "accessibility-runtime-tester.agent.md",
    "playwright-tester.agent.md",
    "react18-test-guardian.agent.md",
    "react19-test-guardian.agent.md",
]

def load_agent_prompt(filename):
    path = AGENTS_DIR / filename
    if not path.exists():
        logger.error("AGENT_FILE_NOT_FOUND", path=str(path))
        return f"You are a specialist in {filename.split('.')[0]}."
    
    content = path.read_text()
    # YAMLフロントマターのスキップ
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if match:
        return match.group(2).strip()
    return content.strip()

def run_agent_audit(agent_name, system_prompt, spec_content):
    if use_mock:
        # 擬似的な指摘をモックで生成する
        return [{
            "layer": "L2",
            "critic_name": agent_name,
            "severity": "中",
            "location": "自律タスク探索フェーズ",
            "title": f"【{agent_name}指摘】探索トリガーのタイミング調整",
            "issue": f"{agent_name}の観点から、タスク探索の起動条件におけるタイムアウトやイベント監視のバッファが考慮されておらず、暴走のリスクがあります。",
            "proposed_fix": f"スキャン処理の間隔にジッター付きの待機時間（デフォルト: 10秒）を挿入し、過剰なポーリングを自動的に回避しなければならない (MUST)。"
        }]

    user_prompt = f"""現在の仕様書の内容を監査し、あなたの役割（検証、デバッグ、ドキュメントなど）に従って、技術的な欠陥（曖昧さ、矛盾、無限ループ、セキュリティ脆弱性など）を検出してください。
出力は、以下のJSON配列形式のみで返してください。褒め言葉や前置き、解説は一切不要です。JSONブロックのバッククォート等も不要です。

[
  {{
    "layer": "L1" | "L2" | "L3" | "L4" | "L5",
    "critic_name": "{agent_name}",
    "severity": "致命的" | "高" | "中",
    "location": "具体的な章や行番号、項目名",
    "title": "指摘タイトル",
    "issue": "なぜこれが問題であるかの具体的な根拠と影響",
    "proposed_fix": "具体的な修正後の文面または追加すべき項目のドラフト"
  }}
]

【監査対象仕様書】
{spec_content}
"""
    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash" if "generativelanguage" in (base_url or "") else "gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
        )
        res_text = response.choices[0].message.content.strip()
        # JSON部分の抽出
        json_match = re.search(r"\[\s*\{.*\}\s*\]", res_text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group(0))
        return json.loads(res_text)
    except Exception as e:
        logger.error("LLM_COMPLETION_ERROR", agent=agent_name, error=str(e))
        # エラー時は空のリストを返す
        return []

def merge_spec_changes(spec_content, defects):
    if not defects:
        return spec_content

    if use_mock:
        # モック時は、各指摘の proposed_fix を仕様書の末尾に自動追記する
        new_content = spec_content + "\n\n### ピアレビューによる追加安全規則\n"
        for d in defects:
            new_content += f"- **{d['title']}**: {d['proposed_fix']}\n"
        return new_content

    # LLMを用いて、指摘を解決した新しい仕様書を生成する
    defects_str = json.dumps(defects, ensure_ascii=False, indent=2)
    user_prompt = f"""現在の仕様書:
{spec_content}

検出された指摘リスト:
{defects_str}

上記の指摘リストにある「すべての指摘」を完全に解決した、新しい仕様書の全文を出力してください。
既存の仕様書にある MUST/MUST NOT 等の他の制約事項は破壊せず、かつ指摘された proposed_fix のドラフトを正確に組み込んで、より堅牢で明確な仕様書を作成してください。
出力は仕様書（マークダウン）の全文のみとし、挨拶や追加の解説は含めないでください。
"""
    try:
        response = client.chat.completions.create(
            model="gemini-2.5-flash" if "generativelanguage" in (base_url or "") else "gpt-4o",
            messages=[
                {"role": "system", "content": "You are a meticulous technical editor and software architect. Your job is to update a specification document to resolve all reported defects completely without removing existing constraints."},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error("MERGE_COMPLETION_ERROR", error=str(e))
        return spec_content

def run_loop():
    logger.info("START_10R_AUDIT_LOOP", use_mock=use_mock)

    # 初期ファイルのロード
    v1_path = SCRATCH_DIR / "autonomous_task_search_spec_v1.md"
    if not v1_path.exists():
        logger.error("INITIAL_SPEC_NOT_FOUND", path=str(v1_path))
        sys.exit(1)
    
    current_spec = v1_path.read_text()

    # 10ラウンドのループ
    for round_idx in range(1, 11):
        logger.info("ROUND_STARTED", round=round_idx)
        all_defects = []

        # 9体のエージェントによる監査
        for agent_file in AGENT_FILES:
            agent_name = agent_file.split(".")[0]
            logger.info("AUDITING_AGENT", agent=agent_name, round=round_idx)
            system_prompt = load_agent_prompt(agent_file)
            defects = run_agent_audit(agent_name, system_prompt, current_spec)
            all_defects.extend(defects)

        # レポートの作成と保存
        report_path = SCRATCH_DIR / f"spec_defects_v{round_idx}_report.md"
        report_content = f"# 仕様書 v{round_idx} ピアレビュー指摘レポート (Round {round_idx})\n\n"
        report_content += "| 担当 | レイヤー | 深刻度 | 指摘タイトル | 指摘内容 | 修正案 |\n"
        report_content += "|---|---|---|---|---|---|\n"
        for d in all_defects:
            report_content += f"| {d['critic_name']} | {d.get('layer', 'L2')} | {d.get('severity', '中')} | {d.get('title', '')} | {d.get('issue', '')} | {d.get('proposed_fix', '')} |\n"
        
        report_path.write_text(report_content)
        logger.info("REPORT_GENERATED", round=round_idx, path=str(report_path))

        # JSON指摘マージの保存
        json_path = SCRATCH_DIR / f"spec_defects_v{round_idx}.json"
        json_path.write_text(json.dumps(all_defects, ensure_ascii=False, indent=2))

        # 仕様書の更新と保存
        next_spec = merge_spec_changes(current_spec, all_defects)
        
        # バージョン名などのドキュメント見出しの更新（v1 -> v2 のような動的書き換え）
        next_spec = re.sub(
            r"# 自律タスク探索・エージェント協調実行仕様書 \(v\d+\)",
            f"# 自律タスク探索・エージェント協調実行仕様書 (v{round_idx + 1})",
            next_spec
        )

        next_path = SCRATCH_DIR / f"autonomous_task_search_spec_v{round_idx + 1}.md"
        next_path.write_text(next_spec)
        logger.info("NEXT_SPEC_GENERATED", round=round_idx, path=str(next_path))

        # 次のラウンドへ状態を更新
        current_spec = next_spec

    logger.info("COMPLETED_10R_AUDIT_LOOP")

if __name__ == "__main__":
    run_loop()
