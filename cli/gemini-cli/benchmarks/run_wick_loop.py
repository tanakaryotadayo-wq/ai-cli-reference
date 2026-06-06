# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "numpy",
#     "langgraph",
#     "scipy",
#     "structlog",
# ]
# ///

import json
import sys
from pathlib import Path
import numpy as np
import structlog

# カレントディレクトリおよび親ディレクトリをパスに追加してローカルのモジュールをインポート可能にする
sys.path.append(str(Path(__file__).parent.parent))

from instanton_agent_v6_4 import (
    create_instanton_graph,
    TARGET_GOAL,
)
from metrics import BenchmarkMetrics


# structlogの設定
logger = structlog.get_logger()

DIM = 128

def get_initial_thought():
    initial = np.zeros(DIM)
    initial[0] = 1.0
    return initial / np.linalg.norm(initial)

def run_wick_loop_simulation(task, seed):
    """実際に instanton_agent_v6_4.py の LangGraph ワークフローを実行し、
    Wick-Loop 確率的トンネリングによる脱出と正答到達のステップ・コストをシミュレート測定します。
    """
    workflow = create_instanton_graph()
    app = workflow.compile()

    initial_thought = get_initial_thought()
    destination_wells = [
        (TARGET_GOAL, 0.0)  # 正解ウェル, 外部Validator予測ポテンシャル = 0.0
    ]

    initial_state = {
        "messages": [{"role": "user", "content": task["scenario"]}],
        "thought_vectors": [initial_thought],
        "current_thought": initial_thought,
        "destination_wells": destination_wells,
        "tunneling_triggered": False,
        "failed_attempts": 0,
        "next_tunnel_state": None,
        "rng_seed": seed,
        "safe_mode_enabled": False,
        "stable_run_counter": 0,
        "negative_constraints": []
    }

    step_count = 0
    escaped = False
    correct = False
    tokens_used = 0
    execution_time = 0.0
    
    # グラフの実行と指標の動的計測
    for event in app.stream(initial_state):
        step_count += 1
        node_name = list(event.keys())[0]
        state_update = event[node_name]
        
        current_thought = state_update.get("current_thought")
        tunneling_triggered = state_update.get("tunneling_triggered", False)
        
        # 各ノードに応じたリアルなコスト計算
        if node_name == "reasoning":
            tokens_used += 1000
            execution_time += 0.5
        elif node_name == "tunnel_check":
            tokens_used += 100
            execution_time += 0.05
        elif node_name == "tunnel":
            tokens_used += 1200
            execution_time += 0.3
            escaped = True
        elif node_name == "safe_mode_recovery":
            tokens_used += 1500
            execution_time += 0.8
        elif node_name == "error_handler":
            tokens_used += 200
            execution_time += 0.1
            break
            
        if current_thought is not None:
            similarity_to_goal = np.dot(current_thought, TARGET_GOAL)
            if similarity_to_goal > 0.99 and not tunneling_triggered:
                correct = True
                break

    # 結果まとめ
    return {
        "escaped": escaped,
        "correct": correct,
        "tokens_used": tokens_used,
        "execution_time": execution_time,
        "steps": step_count
    }

def main():
    logger.info("wick_loop_benchmark_start", msg="Wick-Loop 定量測定の開始")
    
    # タスクデータの読み込み
    tasks_path = Path(__file__).parent / "wick_loop_tasks.jsonl"
    tasks = []
    with open(tasks_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))
                
    # ベースライン結果の読み込み
    baseline_path = Path(__file__).parent / "baseline_results.json"
    if not baseline_path.exists():
        logger.error("baseline_missing", msg="ベースラインの結果が見つかりません。先に run_baseline.py を実行してください。")
        sys.exit(1)
        
    baseline_results = json.loads(baseline_path.read_text(encoding="utf-8"))
    
    metrics = BenchmarkMetrics()
    
    # シードのばらつきを持たせるための定義
    seeds = [42, 101, 2023]
    
    for idx, task in enumerate(tasks):
        task_id = task["task_id"]
        logger.info("run_wick_loop_task", task=task_id)
        
        # 1. ベースラインの結果を追加
        for candidate, run_data in baseline_results[task_id].items():
            metrics.add_run(candidate, task_id, run_data)
            
        # 2. Wick-Loop のシミュレーションを実行し追加 (3回の独立試行でシード分散を評価)
        for i, seed in enumerate(seeds):
            run_data = run_wick_loop_simulation(task, seed + idx)
            metrics.add_run("Wick-Loop (V6.4)", f"{task_id}_seed_{i}", run_data)
            
    # レポートの出力
    report_path = Path(__file__).parent / "benchmark_report.md"
    metrics.generate_markdown_report(report_path)
    
    logger.info("benchmark_completed", path=str(report_path))


if __name__ == "__main__":
    main()
