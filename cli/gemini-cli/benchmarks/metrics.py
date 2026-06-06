#!/usr/bin/env python3
from pathlib import Path
from typing import Dict, List, Any
import numpy as np
import structlog

# structlogの設定
structlog.configure(processors=[structlog.processors.JSONRenderer()])
logger = structlog.get_logger()


class BenchmarkMetrics:
    """
    エージェントのループ脱出ベンチマーク指標を算出し、集計およびレポート生成を行う。
    """

    def __init__(self):
        self.results: Dict[str, List[Dict[str, Any]]] = {}

    def add_run(self, candidate_name: str, task_id: str, run_data: Dict[str, Any]):
        """
        特定の比較対象（ベースライン、候補アルゴリズム）の実行結果を追加する。
        run_data 期待スキーマ:
          - escaped: bool (ループ脱出に成功したか)
          - correct: bool (最終的に正答に到達したか)
          - tokens_used: int (消費トークン)
          - execution_time: float (実行時間 秒)
          - steps: int (総ステップ数)
        """
        if candidate_name not in self.results:
            self.results[candidate_name] = []

        data = {"task_id": task_id, **run_data}
        self.results[candidate_name].append(data)
        logger.info(
            "run_result_added",
            candidate=candidate_name,
            task=task_id,
            escaped=run_data.get("escaped"),
        )

    def compute_summary(self) -> Dict[str, Dict[str, float]]:
        """
        各候補アルゴリズムごとの集計指標（平均、分散等）を算出する。
        """
        summary = {}
        for name, runs in self.results.items():
            if not runs:
                continue

            escaped_list = [r["escaped"] for r in runs]
            correct_list = [r["correct"] for r in runs]
            tokens_list = [r["tokens_used"] for r in runs]
            time_list = [r["execution_time"] for r in runs]

            # 脱出後正答率（脱出に成功したランのうち、最終的に正答できた割合）
            escaped_indices = [i for i, esc in enumerate(escaped_list) if esc]
            escaped_correct = (
                [correct_list[i] for i in escaped_indices] if escaped_indices else []
            )

            escape_rate = float(np.mean(escaped_list))
            final_correctness = float(np.mean(correct_list))
            escaped_correctness_rate = (
                float(np.mean(escaped_correct)) if escaped_correct else 0.0
            )

            summary[name] = {
                "loop_escape_rate": escape_rate,
                "final_correctness": final_correctness,
                "escaped_correctness_rate": escaped_correctness_rate,
                "avg_tokens_used": float(np.mean(tokens_list)),
                "std_tokens_used": float(np.std(tokens_list)),
                "avg_execution_time": float(np.mean(time_list)),
                "std_execution_time": float(np.std(time_list)),
                "total_runs": len(runs),
            }

        logger.info("metrics_summary_computed", candidates=list(summary.keys()))
        return summary

    def generate_markdown_report(self, output_path: Path) -> str:
        """
        集計結果をマークダウン形式の美しいレポートテーブルとして出力する。
        """
        summary = self.compute_summary()

        md = []
        md.append("# Wick-Loop ループ脱出制御 定量ベンチマークレポート")
        md.append(
            "\n本レポートは、従来のループ対処法と Wick-Loop モデルによるループ脱出制御の性能比較結果を示す。"
        )

        md.append("\n## 1. 総合評価サマリー")
        md.append(
            "\n| 比較対象 | ループ脱出率 | 最終正答率 | 脱出後正答率 | 平均消費トークン | 平均実行時間 (秒) |"
        )
        md.append("|---|---|---|---|---|---|")

        for name, metrics in summary.items():
            md.append(
                f"| **{name}** | {metrics['loop_escape_rate']:.2%} | {metrics['final_correctness']:.2%} | "
                f"{metrics['escaped_correctness_rate']:.2%} | {metrics['avg_tokens_used']:.1f} ± {metrics['std_tokens_used']:.1f} | "
                f"{metrics['avg_execution_time']:.2f}s ± {metrics['std_execution_time']:.2f}s |"
            )

        md.append("\n## 2. 指標解説")
        md.append(
            "- **ループ脱出率 (loop_escape_rate)**: ループ検知後に正常に膠着状態から抜け出せた割合。"
        )
        md.append(
            "- **最終正答率 (final_correctness)**: 最終的に正しい結果（ゴール）に到達できた割合（脱出後、間違った状態へワープしたケースを検知するため）。"
        )
        md.append(
            "- **脱出後正答率 (escaped_correctness_rate)**: ループから脱出したランのうち、最終的に正答できた割合（ワープ精度）。"
        )
        md.append(
            "- **平均消費トークン**: 実行あたりに消費した総トークン数。Wick-Loopが余計なリトライを削減できているかを測る。"
        )

        report_text = "\n".join(md)
        output_path.write_text(report_text, encoding="utf-8")
        logger.info("markdown_report_generated", path=str(output_path))
        return report_text
