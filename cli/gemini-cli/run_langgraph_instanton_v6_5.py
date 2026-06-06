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

# カレントディレクトリをパスに追加してローカルの instanton_agent をインポート可能にする
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from instanton_agent_v6_4 import (
    create_instanton_graph,
    cosine_potential,
    TARGET_GOAL,
)

def run_simulation():
    print("================================================================")
    print("   LangGraph × Wick-Loop Instanton 実機稼働シミュレーション")
    print("================================================================\n")

    # 1. グラフのコンパイル
    workflow = create_instanton_graph()
    app = workflow.compile()

    # 2. 初期状態の設定
    # 正解（TARGET_GOAL）から極めて遠い（直交に近い）、エラーポテンシャルの高い初期状態を作成
    rng = np.random.default_rng(42)
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
        "local_rng": rng
    }

    # 3. グラフの実行ストリーミング
    print("--- 実行開始 ---")
    step_count = 0
    
    # LangGraph のストリーミング実行
    for event in app.stream(initial_state):
        step_count += 1
        node_name = list(event.keys())[0]
        state_update = event[node_name]
        
        # 状態パラメータの取得
        current_thought = state_update.get("current_thought")
        failed_attempts = state_update.get("failed_attempts", 0)
        tunneling_triggered = state_update.get("tunneling_triggered", False)
        
        # ゴール（TARGET_GOAL）とのコサイン類似度とエラーポテンシャルを測定
        if current_thought is not None:
            similarity_to_goal = np.dot(current_thought, TARGET_GOAL)
            error_potential = cosine_potential(current_thought)
            
            print(f"[ステップ {step_count:02d}] 実行ノード: <{node_name}>")
            print(f"  - 現在の思考の正解類似度: {similarity_to_goal:.4f}")
            print(f"  - 現在の論理不整合度 (V): {error_potential:.4f}")
            
            if tunneling_triggered:
                print("  => 【ワープ検知】トンネル効果により、中間の思考をすっ飛ばして正解状態にテレポートしました！")
            elif failed_attempts > 0:
                # 失敗に伴い、hbarを引き上げていく様子を出力
                effective_hbar = 0.8 * (1.0 + 0.5 * (failed_attempts - 1))
                print(f"  => 【ループ検知】トンネル判定に失敗。ひらめき度 (hbar) を {effective_hbar:.2f} に引き上げて再挑戦します。")
            print("-" * 60)
            
            # トンネリングが成功した後に無事に reasoning ノードに戻り、
            # 安定状態でゴールに到達した場合は強制終了させるためのダミー処理
            if similarity_to_goal > 0.99 and not tunneling_triggered:
                print("\n[成功] エージェントは正解状態（整合性 99% 以上）を維持し、安定状態でタスクを完了しました。")
                break

    print("\n--- 実行終了 ---")

if __name__ == "__main__":
    run_simulation()
