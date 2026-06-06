# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "numpy",
#     "langgraph",
#     "scipy",
#     "structlog",
# ]
# ///

import sys
import os
import numpy as np
import structlog

# structlogの設定
logger = structlog.get_logger()

# カレントディレクトリをパスに追加してローカルの instanton_agent_v6_4 をインポート可能にする
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from instanton_agent_v6_4 import (  # noqa: E402
    create_instanton_graph,
    cosine_potential,
    TARGET_GOAL,
)


def run_simulation():
    logger.info("simulation_init", msg="================================================================")
    logger.info("simulation_init", msg="   LangGraph × Wick-Loop Instanton V6.4 実機稼働シミュレーション")
    logger.info("simulation_init", msg="================================================================\n")

    # 1. グラフのコンパイル
    workflow = create_instanton_graph()
    app = workflow.compile()

    # 2. 初期状態の設定
    # 正解（TARGET_GOAL）から極めて遠い初期状態を作成
    initial_thought = np.zeros(128)
    initial_thought[0] = 1.0  # TARGET_GOAL (全員1) と直交に近い
    initial_thought = initial_thought / np.linalg.norm(initial_thought)

    # 目的地（正解ウェル: TARGET_GOAL）
    destination_wells = [
        (TARGET_GOAL, 0.0)  # 正解ベクトル, ポテンシャル(エラー) = 0.0
    ]

    # 初期状態ディクショナリ
    initial_state = {
        "messages": [{"role": "user", "content": "複雑な課題を解決してください。"}],
        "thought_vectors": [initial_thought],
        "current_thought": initial_thought,
        "destination_wells": destination_wells,
        "tunneling_triggered": False,
        "failed_attempts": 0,
        "next_tunnel_state": None,
        "rng_seed": 42,
        "safe_mode_enabled": False,
        "stable_run_counter": 0,
        "negative_constraints": []
    }

    # 3. グラフの実行ストリーミング
    logger.info("simulation_run", msg="--- 実行開始 ---")
    step_count = 0
    
    # LangGraph のストリーミング実行
    for event in app.stream(initial_state):
        step_count += 1
        node_name = list(event.keys())[0]
        state_update = event[node_name]
        
        current_thought = state_update.get("current_thought")
        failed_attempts = state_update.get("failed_attempts", 0)
        tunneling_triggered = state_update.get("tunneling_triggered", False)
        
        if current_thought is not None:
            similarity_to_goal = np.dot(current_thought, TARGET_GOAL)
            error_potential = cosine_potential(current_thought)
            
            logger.info(
                "step_execution",
                step=step_count,
                node=node_name,
                similarity_to_goal=f"{similarity_to_goal:.4f}",
                error_potential=f"{error_potential:.4f}"
            )
            
            if tunneling_triggered:
                logger.info("tunnel_success", msg="=> 【ワープ検知】トンネル効果により、中間の思考をすっ飛ばして正解状態にテレポートしました！")
            elif failed_attempts > 0:
                # 失敗に伴い、hbarを引き上げていく様子を出力
                effective_hbar = 1.0 * (1.0 + 0.3 * failed_attempts)
                logger.info("tunnel_retry", msg=f"=> 【ループ検知】トンネル判定に失敗。ひらめき度 (hbar) を {effective_hbar:.2f} に引き上げて再挑戦します。")
            
            # 安定状態でゴールに到達した場合は強制終了させるための処理
            if similarity_to_goal > 0.99 and not tunneling_triggered:
                logger.info("simulation_success", msg="[成功] エージェントは正解状態（整合性 99% 以上）を維持し、安定状態でタスクを完了しました。")
                break
        
        if node_name == "error_handler":
            logger.error("simulation_failed", msg="[強制終了] エージェントはステップ制限に達し、エラー終了しました。")
            break

    logger.info("simulation_run", msg="--- 実行終了 ---")

if __name__ == "__main__":
    run_simulation()
