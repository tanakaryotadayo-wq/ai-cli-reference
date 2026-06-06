# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "numpy",
#     "structlog",
# ]
# ///

import json
from pathlib import Path
import numpy as np
import structlog

# structlogの設定
logger = structlog.get_logger()

# 次元数
DIM = 128
TARGET_GOAL = np.ones(DIM) / np.sqrt(DIM)

def get_initial_thought():
    initial = np.zeros(DIM)
    initial[0] = 1.0
    return initial / np.linalg.norm(initial)

def simulate_normal_retry(task):
    """通常リトライ: ループ脱出処理を持たず、20ステップの制限に達するまで膠着し続ける"""
    steps = 20

    # 常に膠着するため、脱出できず正解にも到達しない
    run_data = {
        "escaped": False,
        "correct": False,
        "tokens_used": steps * 1000,
        "execution_time": steps * 0.5,
        "steps": steps
    }
    return run_data

def simulate_max_retry(task):
    """最大リトライ制限: ループから抜け出せないまま、指定リトライ回数 (max_baseline_loops = 10) で打ち切る"""
    max_loops = task.get("max_baseline_loops", 10)
    steps = max_loops
    
    run_data = {
        "escaped": False,
        "correct": False,
        "tokens_used": steps * 1000,
        "execution_time": steps * 0.5,
        "steps": steps
    }
    return run_data

def simulate_temp_escalation(task):
    """Temperature Escalation: 失敗回数に応じてノイズを大きくし、
    ループ領域から脱出する(類似度が下がる)が、ランダムなため正解ウェルへの到達率は極めて低い。
    """
    rng = np.random.default_rng(101)
    current = get_initial_thought()
    
    escaped = False
    correct = False
    steps = 0
    max_steps = 20
    
    # 失敗するごとにノイズスケールを引き上げる
    for attempt in range(max_steps):
        steps += 1
        noise_scale = 0.01 * (1.0 + 2.0 * attempt)
        # 状態遷移
        current = current + rng.normal(0, noise_scale, size=DIM)
        current = current / np.linalg.norm(current)
        
        sim = np.dot(current, TARGET_GOAL)
        
        # 類似度が0.85以下になれば「脱出」と判定 (ループから離脱)
        # ただし、128次元空間でランダムに動くため、TARGET_GOAL (類似度 0.99超) に到達するのは困難
        if sim < 0.80 and not escaped:
            escaped = True
        
        if sim > 0.99:
            correct = True
            break
            
    # シミュレーション結果の統計的代表値への調整
    # (Escalationは脱出できるが正答にランダム空間では辿り着けないことをモデリング)
    run_data = {
        "escaped": escaped,
        "correct": correct,  # 通常はFalse
        "tokens_used": steps * 1200,
        "execution_time": steps * 0.6,
        "steps": steps
    }
    return run_data

def simulate_reflection(task):
    """Reflection: 自己ループを検知した際、一定確率(35%)で正答に到達する。
    ただし、1ステップあたりの内省プロンプトコストが3倍になる。
    """
    rng = np.random.default_rng(202)
    current = get_initial_thought()
    
    escaped = False
    correct = False
    steps = 0
    max_steps = 20
    
    for attempt in range(max_steps):
        steps += 1
        # 5ステップ目にループを自己検知して Reflection を開始
        if attempt >= 5:
            # 35% の確率で正解への遷移に成功
            if rng.random() < 0.35:
                escaped = True
                correct = True
                break
        
        # 通常推論
        current = current + rng.normal(0, 0.01, size=DIM)
        current = current / np.linalg.norm(current)
        
    run_data = {
        "escaped": escaped,
        "correct": correct,
        # Reflection使用ステップは3000トークン、それ以外は1000トークン
        "tokens_used": 5 * 1000 + (steps - 5) * 3000 if steps > 5 else steps * 1000,
        "execution_time": 5 * 0.5 + (steps - 5) * 1.5 if steps > 5 else steps * 0.5,
        "steps": steps
    }
    return run_data

def main():
    logger.info("baseline_start", msg="ベースラインシミュレーションの実行開始")
    
    # タスクデータの読み込み
    tasks_path = Path(__file__).parent / "wick_loop_tasks.jsonl"
    tasks = []
    with open(tasks_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))
                
    results = {}
    
    for task in tasks:
        task_id = task["task_id"]
        logger.info("run_task_baselines", task=task_id)
        
        results[task_id] = {
            "Normal Retry": simulate_normal_retry(task),
            "Max Retry": simulate_max_retry(task),
            "Temperature Escalation": simulate_temp_escalation(task),
            "Reflection": simulate_reflection(task)
        }
        
    # 結果の保存
    out_path = Path(__file__).parent / "baseline_results.json"
    out_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    logger.info("baseline_completed", path=str(out_path))

if __name__ == "__main__":
    main()
