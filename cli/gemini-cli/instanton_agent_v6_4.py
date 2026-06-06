"""Wick-Loop Instanton Theorem V6.4.0 (Theorem V2.1 / Governance V6.0) for AI Agent Search and Reasoning.

This module provides classes for detecting cognitive loops in AI agents,
performing instanton-based state tunneling to escape localized reasoning loops,
and applying Governance Framework V6.0 features (Memory Injection/Negative Constraints,
Safe Mode state gating, stable run counter clearing, local action slicing,
external score co-op, serialized state management, non-linear kinetic cost,
deferred annealing, adaptive search noise, mathematical boundary clipping,
dimension safety guards, robust norm scaling, and robust nan/inf validation).
"""

import math
from typing import Any, Callable, Dict, List, Optional, Tuple
import numpy as np
import structlog

__version__ = "6.4.0"
THEOREM_VERSION = "2.1"
GOVERNANCE_VERSION = "6.0"

# structlogの設定
logger = structlog.get_logger()


# タイプヒントのエイリアス
Vector = np.ndarray


class LoopDetector:
    """エージェントの思考履歴（セマンティック埋め込みベクトル）から自己類似性を監視し、
    認知ループを検出するクラス。
    """

    def __init__(self, threshold: float = 0.85, k: int = 4):
        """
        Args:
            threshold (float): ループを判定するためのしきい値 S_threshold.
            k (int): 類似度計算に対象とする過去のステップ数.
        """
        self.threshold = threshold
        self.k = k
        self.history: List[Vector] = []

    def add_state(self, vector: Vector) -> None:
        """エージェントの新しい思考状態ベクトルを履歴に追加します。履歴は最大サイズに制限します。"""
        self.history.append(vector)
        max_history_size = max(self.k * 2, 100)
        if len(self.history) > max_history_size:
            self.history = self.history[-max_history_size:]

    def compute_similarity(self) -> float:
        """現在の状態と過去 k 個の状態とのコサイン類似度の平均 S(t) を計算します。

        S(t) = 1/k * sum_{j=1}^k cos(v_t, v_{t-j})
        """
        if not self.history or len(self.history) < 2:
            return 0.0

        v_t = self.history[-1]
        norm_vt = np.linalg.norm(v_t)
        if norm_vt < 1e-9:
            return 0.0

        steps = min(self.k, len(self.history) - 1)
        sim_sum = 0.0
        valid_steps = 0

        for j in range(1, steps + 1):
            v_prev = self.history[-1 - j]
            norm_prev = np.linalg.norm(v_prev)
            if norm_prev < 1e-9:
                continue
            cos_sim = np.dot(v_t, v_prev) / (norm_vt * norm_prev)
            cos_sim = np.clip(cos_sim, -1.0, 1.0)
            sim_sum += cos_sim
            valid_steps += 1

        return sim_sum / valid_steps if valid_steps > 0 else 0.0

    def is_looping(self) -> bool:
        """計算された類似度平均 S(t) がしきい値を超えている場合、ループ状態と判定します。"""
        return self.compute_similarity() > self.threshold


class InstantonTunnel:
    """離散ユークリッド作用 S_E を計算し、確率的トンネリング判定を行います。

    極小値（ローカルループ）から大域的整合状態（目的ウェル）への直接遷移を実行します。
    """

    def __init__(
        self,
        potential_func: Callable[[Vector], float],
        m: float = 1.0,
        hbar: float = 1.0,
        distance_metric: Optional[Callable[[Vector, Vector], float]] = None,
        rng: Optional[np.random.Generator] = None,
        negative_constraints: Optional[List[Vector]] = None,
        penalty_weight: float = 1.5,
        alpha: float = 0.3,
        k_slice: int = 4,
    ):
        """
        Args:
            potential_func (Callable[[Vector], float]): ポテンシャル関数 V(x).
            m (float): 状態遷移の障壁に対する「有効質量」パラメータ.
            hbar (float): トンネリング確率を制御する「プランク定数」に相当するゆらぎパラメータ.
            distance_metric (Optional[Callable[[Vector, Vector], float]]): 状態間の距離関数 D(x, y).
                                                                          デフォルトはコサイン距離。
            rng (Optional[np.random.Generator]): スレッドセーフなローカル乱数生成器.
            negative_constraints (Optional[List[Vector]]): 過去の失敗や避けるべき負の制約状態ベクトルのリスト.
            penalty_weight (float): 負の制約に近い状態に対するペナルティ係数.
            alpha (float): 連続失敗時の hbar 適応上昇係数.
            k_slice (int): 局所作用計算のための直近スライスウィンドウ幅.
        """
        self.potential_func = potential_func
        self.m = m
        self.hbar = hbar
        self.distance_metric = distance_metric or self._default_cosine_distance
        self._rng = rng or np.random.default_rng()
        self.negative_constraints = negative_constraints or []
        self.penalty_weight = penalty_weight
        self.alpha = alpha
        self.k_slice = k_slice

    def _default_cosine_distance(self, x: Vector, y: Vector) -> float:
        """デフォルトのコサイン距離 D(x, y) = 1 - cos(x, y)"""
        norm_x = np.linalg.norm(x)
        norm_y = np.linalg.norm(y)
        if norm_x < 1e-9 or norm_y < 1e-9:
            return 1.0
        cos_sim = np.dot(x, y) / (norm_x * norm_y)
        cos_sim = np.clip(cos_sim, -1.0, 1.0)
        return 1.0 - cos_sim

    def get_effective_potential(self, x: Vector) -> float:
        """ネガティブ制約によるペナルティを加味した実効ポテンシャル V_eff(x) を計算します。"""
        base_v = self.potential_func(x)
        if not self.negative_constraints:
            return base_v

        penalty = 0.0
        norm_x = np.linalg.norm(x)
        if norm_x > 1e-9:
            for c in self.negative_constraints:
                # 欠陥修正: ベクトルの次元不一致によるクラッシュガードを追加
                if x.shape != c.shape:
                    logger.warn("dimension_mismatch_in_penalty", x_shape=x.shape, c_shape=c.shape)
                    continue

                norm_c = np.linalg.norm(c)
                if norm_c > 1e-9:
                    cos_sim = np.dot(x, c) / (norm_x * norm_c)
                    cos_sim = np.clip(cos_sim, -1.0, 1.0)
                    if cos_sim > 0.7:
                        penalty += self.penalty_weight * math.pow(cos_sim, 2)
        return base_v + penalty

    def compute_action(self, trajectory: List[Vector]) -> float:
        """軌道に対する離散ユークリッド作用 S_E を計算します（台形近似を適用）。
        全履歴累積による作用増大を防ぐため直近 k_slice ステップに制限し、距離の二乗（運動エネルギーに比例）を使用。
        """
        if not trajectory:
            return 0.0

        local_trajectory = trajectory[-self.k_slice :] if len(trajectory) > self.k_slice else trajectory

        if len(local_trajectory) == 1:
            return self.get_effective_potential(local_trajectory[0])

        action = 0.0
        for i in range(1, len(local_trajectory)):
            dist = self.distance_metric(local_trajectory[i], local_trajectory[i - 1])
            v_val = 0.5 * (
                self.get_effective_potential(local_trajectory[i])
                + self.get_effective_potential(local_trajectory[i - 1])
            )
            action += 0.5 * self.m * (dist**2) + v_val

        return action

    def tunneling_probability(self, action: float) -> float:
        """作用 S_E からトンネリング確率 P_tunnel = exp(-S_E / hbar) を算出します。"""
        scaled_action = action / self.hbar
        if scaled_action > 700.0:
            return 1e-15
        return math.exp(-scaled_action)

    def attempt_tunnel(
        self,
        current_trajectory: List[Vector],
        destination_wells: List[Tuple[Vector, float]],
        failed_attempts: int,
        max_attempts: int = 5,
        safe_mode: bool = False,
    ) -> Tuple[bool, Optional[Vector], bool, int]:
        """現在の軌道から、目的地（well）へのトンネリングを確率的に試行します（ステートレス設計）。

        Args:
            current_trajectory (List[Vector]): 現在の思考状態の軌跡.
            destination_wells (List[Tuple[Vector, float]]): 遷移先の候補状態とその予測ポテンシャル V(x) のリスト.
            failed_attempts (int): これまでの連続失敗回数.
            max_attempts (int): トンネリング失敗の最大許容回数 (Stop Rule).
            safe_mode (bool): セーフモードが有効かどうか。

        Returns:
            Tuple[bool, Optional[Vector], bool, int]: (トンネリング成否, 成功した場合は遷移先状態, セーフモード移行の有無, 更新された連続失敗回数)
        """
        if not current_trajectory or not destination_wells:
            return False, None, False, failed_attempts

        valid_wells = [
            w
            for w in destination_wells
            if not math.isinf(w[1]) and not math.isnan(w[1])
        ]
        if not valid_wells:
            logger.warn("attempt_tunnel_no_valid_wells", msg="すべての目的地ウェルの予測スコアが無効です。")
            return False, None, False, failed_attempts

        action = self.compute_action(current_trajectory)

        multiplier = 2.0 if safe_mode else 1.0
        effective_hbar = self.hbar * (1.0 + self.alpha * failed_attempts) * multiplier
        effective_hbar = max(effective_hbar, 1e-6)

        scaled_action = action / effective_hbar
        p_tunnel = 1e-15 if scaled_action > 700.0 else math.exp(-scaled_action)

        if self._rng.random() < p_tunnel:
            dests = [w[0] for w in valid_wells]
            pots = np.array([self.get_effective_potential(w[0]) + w[1] for w in valid_wells])

            min_pot = np.min(pots)
            exp_pots = np.exp(-(pots - min_pot) / effective_hbar)
            sum_exp = np.sum(exp_pots)

            # 欠陥修正: NaN 混入時の暗黙的エラー隠蔽を防止する厳格な判定ガード
            if np.isnan(sum_exp) or np.isnan(pots).any():
                logger.error("tunnel_potential_nan_detected", pots=pots, sum_exp=sum_exp)
                return False, None, False, failed_attempts

            if sum_exp > 0:
                probs = exp_pots / sum_exp
            else:
                probs = np.ones(len(dests)) / len(dests)

            idx = self._rng.choice(len(dests), p=probs)
            return True, dests[idx], False, 0

        new_failed_attempts = failed_attempts + 1
        if new_failed_attempts >= max_attempts:
            return False, None, True, new_failed_attempts

        return False, None, False, new_failed_attempts


# =====================================================================
# LangGraph 統合のシミュレーションと参照用実装テンプレート
# =====================================================================

try:
    from typing_extensions import TypedDict
    from langgraph.graph import END, StateGraph

    # エージェントが保持する状態の定義 (V6.4 対応)
    class InstantonAgentState(TypedDict):
        messages: List[Dict[str, Any]]
        thought_vectors: List[np.ndarray]
        current_thought: np.ndarray
        destination_wells: List[Tuple[np.ndarray, float]]
        tunneling_triggered: bool
        rng_seed: int
        failed_attempts: int
        next_tunnel_state: Optional[np.ndarray]
        safe_mode_enabled: bool
        stable_run_counter: int
        negative_constraints: List[np.ndarray]

    TARGET_GOAL = np.ones(128) / np.sqrt(128)

    def cosine_potential(x: np.ndarray) -> float:
        if x.shape != TARGET_GOAL.shape:
            logger.warn("dimension_mismatch_in_potential", x_shape=x.shape, target_shape=TARGET_GOAL.shape)
            return 1.0

        norm_x = np.linalg.norm(x)
        if norm_x < 1e-9:
            return 1.0
        cos_sim = np.dot(x, TARGET_GOAL) / norm_x
        cos_sim = np.clip(cos_sim, -1.0, 1.0)
        return float(1.0 - cos_sim)

    # 1. ノード定義
    def reasoning_node(state: InstantonAgentState) -> Dict[str, Any]:
        """推論を行うメインのノード"""
        seed = state.get("rng_seed", 42)
        rng = np.random.default_rng(seed)
        current = state.get("current_thought", np.zeros(128))

        safe_mode = state.get("safe_mode_enabled", False)
        noise_scale = 0.05 if safe_mode else 0.01

        raw_next = current + rng.normal(0, noise_scale, size=current.shape)
        
        # 欠陥修正: ノルムが極小時のアンダーフローおよび除算による inf/nan 伝播を防ぐためのガード
        norm = np.linalg.norm(raw_next)
        if norm > 1e-9:
            next_thought = raw_next / norm
        else:
            next_thought = raw_next

        vectors = list(state.get("thought_vectors", []))
        vectors.append(next_thought)

        if len(vectors) > 100:
            vectors = vectors[-100:]

        next_seed = int(rng.integers(0, 1000000))

        return {
            "current_thought": next_thought,
            "thought_vectors": vectors,
            "tunneling_triggered": False,
            "rng_seed": next_seed,
        }

    def tunnel_check_node(state: InstantonAgentState) -> Dict[str, Any]:
        """状態のループ検知、正常稼働カウンター管理、およびトンネル確率判定を統合して行う純粋ノード"""
        vectors = state.get("thought_vectors", [])
        if not vectors:
            return {}

        k_val = 4
        detector = LoopDetector(threshold=0.85, k=k_val)
        for v in vectors:
            detector.add_state(v)

        stable_run_counter = state.get("stable_run_counter", 0)
        failed_attempts = state.get("failed_attempts", 0)
        safe_mode = state.get("safe_mode_enabled", False)

        is_loop = detector.is_looping()

        if not is_loop:
            stable_run_counter += 1
            if stable_run_counter >= 3:
                failed_attempts = 0
                stable_run_counter = 0
                safe_mode = False

            return {
                "next_tunnel_state": None,
                "stable_run_counter": stable_run_counter,
                "failed_attempts": failed_attempts,
                "safe_mode_enabled": safe_mode,
            }

        stable_run_counter = 0

        seed = state.get("rng_seed", 42)
        rng = np.random.default_rng(seed)
        wells = state.get("destination_wells", [])
        constraints = state.get("negative_constraints", [])

        tunnel = InstantonTunnel(
            potential_func=cosine_potential,
            m=1.2,
            hbar=1.0,
            rng=rng,
            negative_constraints=constraints,
            alpha=0.3,
            k_slice=k_val,
        )

        success, next_state, trigger_safe, new_failed_attempts = tunnel.attempt_tunnel(
            vectors, wells, failed_attempts=failed_attempts, max_attempts=5, safe_mode=safe_mode
        )

        next_seed = int(rng.integers(0, 1000000))

        if success and next_state is not None:
            return {
                "next_tunnel_state": next_state,
                "failed_attempts": 0,
                "safe_mode_enabled": False,
                "stable_run_counter": 0,
                "rng_seed": next_seed,
            }
        else:
            return {
                "next_tunnel_state": None,
                "failed_attempts": new_failed_attempts,
                "safe_mode_enabled": safe_mode or trigger_safe,
                "stable_run_counter": 0,
                "rng_seed": next_seed,
            }

    def tunnel_node(state: InstantonAgentState) -> Dict[str, Any]:
        """トンネリング遷移を実行し、エッジで決定された状態を無条件に適用するノード"""
        next_state = state.get("next_tunnel_state")
        vectors = state.get("thought_vectors", [])

        if next_state is not None and vectors:
            new_vectors = list(vectors)
            new_vectors.append(next_state)

            if len(new_vectors) > 100:
                new_vectors = new_vectors[-100:]

            return {
                "current_thought": next_state,
                "thought_vectors": new_vectors,
                "tunneling_triggered": True,
                "failed_attempts": 0,
                "next_tunnel_state": None,
                "safe_mode_enabled": False,
                "stable_run_counter": 0,
            }

        return {"tunneling_triggered": False, "next_tunnel_state": None}

    def safe_mode_recovery_node(state: InstantonAgentState) -> Dict[str, Any]:
        """セーフモード時に実行されるリカバリーノード。
        状態の緩和や、ネガティブ制約への現在状態の追加（教訓インジェクション）を行い、
        デッドロックからの脱出を支援します。
        """
        constraints = list(state.get("negative_constraints", []))
        current = state.get("current_thought")
        if current is not None and not any(np.array_equal(current, c) for c in constraints):
            constraints.append(current)

        wells = state.get("destination_wells", [])
        next_thought = current

        # 状態緩和のための乱数生成器再構築
        seed = state.get("rng_seed", 42)
        rng = np.random.default_rng(seed)

        if wells:
            best_well = min(wells, key=lambda w: w[1])[0]
            next_thought = 0.7 * current + 0.3 * best_well
        else:
            # 欠陥修正: 目的地が空リストの場合、強いノイズ（0.2）を加えて膠着点から引き離す
            next_thought = current + rng.normal(0, 0.2, size=current.shape)

        norm = np.linalg.norm(next_thought)
        if norm > 1e-9:
            next_thought = next_thought / norm
        else:
            next_thought = next_thought

        new_vectors = list(state.get("thought_vectors", []))
        if next_thought is not None:
            new_vectors.append(next_thought)
        if len(new_vectors) > 100:
            new_vectors = new_vectors[-100:]

        next_seed = int(rng.integers(0, 1000000))

        return {
            "current_thought": next_thought,
            "thought_vectors": new_vectors,
            "negative_constraints": constraints,
            "failed_attempts": state.get("failed_attempts", 0) // 2,
            "safe_mode_enabled": True,
            "stable_run_counter": 0,
            "rng_seed": next_seed,
        }

    def error_handler_node(state: InstantonAgentState) -> Dict[str, Any]:
        """ステップ制限に達した際、強制終了のエラーログを State の messages に伝播するノード"""
        messages = list(state.get("messages", []))
        messages.append(
            {
                "role": "system",
                "content": "ERROR: Max steps exceeded. The reasoning trajectory has entered an unresolvable cognitive loop.",
            }
        )
        logger.error(
            "instanton_agent_max_steps_exceeded",
            total_steps=len(state.get("thought_vectors", [])),
            failed_attempts=state.get("failed_attempts"),
        )
        return {
            "messages": messages,
            "safe_mode_enabled": False,
        }

    # 2. 条件付きエッジ（Conditional Edge）
    def route_after_check(state: InstantonAgentState) -> str:
        """tunnel_check_node の結果に基づいて次の遷移先を決定する純粋なエッジ"""
        vectors = state.get("thought_vectors", [])

        if len(vectors) >= 20:
            return "error_handler"

        next_state = state.get("next_tunnel_state")
        safe_mode = state.get("safe_mode_enabled", False)

        if next_state is not None:
            return "tunnel"

        if safe_mode:
            return "safe_mode_recovery"

        return "reasoning"

    def create_instanton_graph() -> StateGraph:
        """LangGraph の StateGraph を生成して返します。"""
        workflow = StateGraph(InstantonAgentState)

        # ノード登録
        workflow.add_node("reasoning", reasoning_node)
        workflow.add_node("tunnel_check", tunnel_check_node)
        workflow.add_node("tunnel", tunnel_node)
        workflow.add_node("safe_mode_recovery", safe_mode_recovery_node)
        workflow.add_node("error_handler", error_handler_node)

        workflow.set_entry_point("reasoning")

        workflow.add_edge("reasoning", "tunnel_check")

        workflow.add_conditional_edges(
            "tunnel_check",
            route_after_check,
            {
                "reasoning": "reasoning",
                "tunnel": "tunnel",
                "safe_mode_recovery": "safe_mode_recovery",
                "error_handler": "error_handler",
            },
        )

        workflow.add_edge("tunnel", "reasoning")
        workflow.add_edge("safe_mode_recovery", "reasoning")
        workflow.add_edge("error_handler", END)

        return workflow

except ImportError:
    pass


if __name__ == "__main__":
    logger.info("instanton_test_start", msg="=== Wick-Loop Instanton Theorem V6.4 動作テスト ===")

    seed_val = 7
    local_rng = np.random.default_rng(seed_val)

    # 1. ループ検知テスト
    v1 = np.array([1.0, 0.0, 0.0])
    v2 = np.array([0.95, 0.05, 0.0])
    v3 = np.array([1.0, 0.01, 0.0])

    detector = LoopDetector(threshold=0.90, k=2)
    detector.add_state(v1)
    detector.add_state(v2)
    logger.info("similarity_step_2", value=f"{detector.compute_similarity():.4f}")

    detector.add_state(v3)
    similarity = detector.compute_similarity()
    is_loop = detector.is_looping()
    logger.info(
        "similarity_step_3",
        threshold=0.90,
        similarity=f"{similarity:.4f}",
        loop_detected=is_loop,
    )

    # 2. トンネリングテスト（次元不一致ガードおよびコサイン類似度クリッピングのテスト）
    target = np.array([0.0, 0.0])

    def cosine_potential_2d(x: np.ndarray) -> float:
        return float(np.linalg.norm(x))

    constraint_vector = np.array([0.1, 0.1])

    tunnel = InstantonTunnel(
        potential_func=cosine_potential_2d,
        m=1.0,
        hbar=1.0,
        rng=local_rng,
        negative_constraints=[constraint_vector],
        penalty_weight=5.0,
        alpha=0.3,
        k_slice=2,
    )

    current_trajectory = [
        np.array([10.0, 10.0]),
        np.array([10.1, 10.0]),
        np.array([10.0, 9.9]),
    ]

    destination_wells = [
        (np.array([0.1, 0.1]), 0.1414),
        (np.array([0.0, 0.0]), 0.0),
        (np.array([0.0, 0.0, 0.0]), 0.0),
    ]

    v_c = tunnel.get_effective_potential(destination_wells[0][0])
    v_z = tunnel.get_effective_potential(destination_wells[1][0])
    v_mismatch = tunnel.get_effective_potential(destination_wells[2][0])
    logger.info(
        "effective_potentials",
        near_constraint=f"{v_c:.4f}",
        far_from_constraint=f"{v_z:.4f}",
        mismatch_dim=f"{v_mismatch:.4f}",
    )

    action = tunnel.compute_action(current_trajectory)
    p_tunnel = tunnel.tunneling_probability(action)
    logger.info("action_probability", action=f"{action:.4f}", p_tunnel=f"{p_tunnel:.6f}")

    # 3. セーフモード状態移行テスト
    logger.info("safe_mode_test_start", msg="--- セーフモード状態移行テスト (V6.4) ---")
    tunnel.hbar = 0.1
    failed_attempts = 0
    safe_triggered = False
    for attempt in range(1, 10):
        success, next_state, trigger_safe, failed_attempts = tunnel.attempt_tunnel(
            current_trajectory, destination_wells[:2], failed_attempts=failed_attempts, max_attempts=5
        )
        logger.info(
            "attempt_result",
            attempt=attempt,
            success=success,
            safe_triggered=trigger_safe,
            failed_attempts=failed_attempts,
        )
        if trigger_safe:
            safe_triggered = True
            logger.info("safe_mode_triggered", msg="[セーフモード検出] クラッシュを回避し、状態ゲートで安全に捕捉されました。")
            break

    assert safe_triggered, "セーフモード移行が正しくトリガーされませんでした。"
    logger.info("safe_mode_test_success", msg="セーフモード移行テスト: 成功")
