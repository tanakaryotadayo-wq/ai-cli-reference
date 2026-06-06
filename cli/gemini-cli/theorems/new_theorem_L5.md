# L5レイヤー有向タスクグラフ最小経路定理 (Directed Task Graph Shortest Path Theorem) [v4.0]

## 1. 定理の定義 (Definition)

エージェントのタスク実行プロセスにおいて、状態の遷移、エラーからのリトライ、API制限による縮退運転、セキュリティリスク、および人間（ユーザー）の介入（HITL: Human-In-The-Loop）を数理的に統合するため、拡張された状態空間 $V$ を以下のように定義する。

### 状態の定義
システムの状態 $v \in V$ は、以下の4つ組（タプル）として表現される：
$$v = (s, k, \Gamma, I)$$
*   $s \in S$: タスクの機能的状態。L2（状態遷移ループフリー不動点定理）で定義される状態空間 $S$ の元であり、一意の目標不動点 $s^*$ に収束する。
*   $k \in \{0, 1, \dots, K\}$: 残りリトライ許容量。自律実行が失敗した際にデクリメントされ、回復不能な無限ループを防止する。
*   $\Gamma \in \mathbb{R}$: APIレートリミットバッファ（あるいは遅延マージン）。L7（API制約下の縮退運転境界定理）と連動する。
*   $I \in [0, 1]$: セキュリティ脅威リスク指数。L4（自己免疫的サンドボックス隔離定理）と連動する。

### 決定（アクション）の定義
各状態 $u = (s_u, k_u, \Gamma_u, I_u)$ からの遷移エッジ $e = (u, v_{succ})$ において、制御エンジンは以下の意思決定ペア $d_e = (x_e, m_e)$ を選択する：
*   $x_e \in \{0, 1\}$: 人間介入フラグ（$x_e = 1$ のとき HITL による確認・承認を実行、$x_e = 0$ のとき完全自律実行）。
*   $m_e \in \{\text{Normal}, \text{Degraded}\}$: 実行モード。L7に基づき、API枯渇時（$\Gamma_u \le 0$）は強制的に `Degraded` モードとなる。

### 状態価値関数 $V(u)$ の定義
状態 $u = (s_u, k_u, \Gamma_u, I_u)$ から、最終的な目標不動点状態 $v^* = (s^*, \cdot, \cdot, \cdot)$ に到達するまでに発生する**最小期待総実行コスト**を $V(u)$ とする。境界条件は以下のように定義される：
$$V(s^*, k, \Gamma, I) = 0 \quad (\forall k, \Gamma, I)$$

### コストパラメータ
*   $C_{auto}(e, m_e) \in \mathbb{R}^+$: 実行モード $m_e$ で自律遷移を行う際の基本コスト（APIトークン消費、計算コスト等）。
    *   **L6（最適忘却）との連動**: メモリ容量制限に達し、外部記憶からのコンテキストスワップが発生する場合は、追加コスト $C_{swap}$ が $C_{auto}$ に加算される。
*   $P_{success}(e, m_e) \in [0, 1]$: モード $m_e$ での自律遷移成功確率。
    *   **L3（スキル直交）との連動**: クエリ $q$ に対するスキル記述の曖昧さ・誤ルーティング確率を $\epsilon(q) \in [0, 1]$ としたとき、実効成功確率は以下のように制約される：
        $$P_{success}(e, m_e) \le (1 - \epsilon(q)) P_{base}(e, m_e)$$
    *   **L4（サンドボックス）との連動**: リスク指数が臨界値を超えた場合（$I_u \ge I_{crit}$）、サンドボックス権限が最小生存境界 $\mathcal{B}_{min}$ に制限され、自律実行がブロックされるため $P_{success} = 0$ となる。
    *   **L6（最適忘却）との連動**: メモリ最適忘却により重要コンテキストが破棄された場合、成功確率は減衰係数 $\alpha \in (0, 1]$ により $\alpha \cdot P_{success}$ に低下する。
*   $C_{fail}(e) \in \mathbb{R}^+$: 自律実行が失敗した場合のリカバリーコスト（ロールバック、ログ分析等）。
*   $C_{hitl}(e) \in \mathbb{R}^+$: 人間が介入する際の認知コスト・時間コスト。

### 再帰的期待遷移コストの定式化
意思決定 $d_e = (x_e, m_e)$ に基づく状態 $u$ からの期待遷移コスト $E[C(e, x_e, m_e)]$ は、次の状態の期待価値関数（将来コスト）を含めて以下のように再帰的に定義される。

ここで、成功時の遷移先を $v_{succ} = (s_v, K, \Gamma_{new}, I_{new})$ とし、失敗時のリトライ遷移先を $v_{fail} = (s_u, k_u - 1, \Gamma_{new}, I_{new})$ とする。

1.  **HITL選択時 ($x_e = 1$)**:
    $$E[C(e, 1, m_e)] = C_{hitl}(e) + V(v_{succ})$$
    HITL介入時は確実（成功確率 1.0）に次の機能的状態 $s_v$ へ遷移し、リトライバジェットは $K$ に初期化される。

2.  **自律実行選択時 ($x_e = 0$)**:
    *   **残りリトライがある場合 ($k_u > 0$)**:
        $$E[C(e, 0, m_e)] = C_{auto}(e, m_e) + P_{success}(e, m_e) V(v_{succ}) + (1 - P_{success}(e, m_e)) \left( C_{fail}(e) + V(v_{fail}) \right)$$
    *   **残りリトライがない場合 ($k_u = 0$)**:
        $$E[C(e, 0, m_e)] = C_{auto}(e, m_e) + P_{success}(e, m_e) V(v_{succ}) + (1 - P_{success}(e, m_e)) \left( C_{fail}(e) + C_{hitl}(e) + V(v_{succ}) \right)$$
        残り試行回数が 0 の状態で失敗すると、強制的にHITLエスカレーションが走り、コスト $C_{hitl}(e)$ を支払って次の目標状態 $v_{succ}$ へ強制遷移する。

したがって、任意の非終端状態 $u$ における Bellman 最適方程式は以下の通りとなる：
$$V(u) = \min_{e \in Out(s_u)} \min_{(x_e, m_e)} E[C(e, x_e, m_e)]$$

---

## 2. 定理の主張 (Claims)

### 定理 1 (状態依存型動的エスカレーション閾値)
状態 $u$ において、期待総コストを最小化するために自律実行ではなく $x_e = 1$ (HITL介入) を要求すべき必要十分条件は、任意の実行モード $m_e$ において自律実行の成功確率 $P_{success}(e, m_e)$ が以下の状態依存閾値 $\theta(e, k_u, m_e)$ を下回ることである：

1.  **残りリトライがある場合 ($k_u > 0$)**:
    $$\theta(e, k_u, m_e) = 1 - \frac{C_{hitl}(e) - C_{auto}(e, m_e)}{C_{fail}(e) + V(s_u, k_u - 1) - V(s_v, K)}$$
2.  **残りリトライがない場合 ($k_u = 0$)**:
    $$\theta(e, 0, m_e) = 1 - \frac{C_{hitl}(e) - C_{auto}(e, m_e)}{C_{fail}(e) + C_{hitl}(e)}$$

ただし、$C_{hitl}(e) > C_{auto}(e, m_e)$ と仮定する。

#### 系 1.1 (リスク許容度の単調減少性)
任意の残りリトライ回数 $k_u > 0$ において、以下の不等式が成立する：
$$\theta(e, k_u, m_e) \le \theta(e, 0, m_e)$$
これは、**残りリトライ回数 $k_u$ が多いほど自律実行に対するリスク許容度が高く（＝成功確率が低くても自律実行を選択する）、リトライ回数が減少するにつれてリスク回避的（＝より高い成功確率を要求する）になり、最終ステップ ($k_u = 0$) で最も保守的な判断を下す**というエージェントの合理的リスク選好特性を数理的に証明している。

*証明*:
状態価値関数の定義より、常に $V(s_u, k_u - 1) \le C_{hitl}(e) + V(s_v, K}$ が成り立つ（いつでもHITLを選択できるため）。
これにより、分母について $C_{fail}(e) + V(s_u, k_u - 1) - V(s_v, K) \le C_{fail}(e) + C_{hitl}(e)$ となり、引かれる分数項が大きくなるため、結果として $\theta(e, k_u, m_e) \le \theta(e, 0, m_e)$ となる。 (Q.E.D.)

#### 系 1.2 (無制限リトライ時の幾何極限収束)
リトライ回数制限がない極限（$k_u \to \infty$）において、成功確率 $P = P_{success}(e, m_e)$ が一定である静的ポリシーの下では、状態価値関数 $V(s_u, k_u)$ は次の極限値に収束し、幾何分布に基づく期待リトライコストモデルと完全一致する：
$$\lim_{k_u \to \infty} V(s_u, k_u) = V(s_v, K) + \frac{C_{auto}(e, m_e) + (1 - P)C_{fail}(e)}{P}$$

### 定理 2 (状態空間拡張によるマルコフ決定過程のDAG性および不動点一意性)
状態 $v = (s, k, \Gamma, I)$ からなる拡張状態グラフ $G_{ext} = (V, E_{ext})$ を構築する。
自律実行失敗時の遷移は $k_u \to k_u - 1$ のようにリトライ数を単調減少させるため、グラフ $G_{ext}$ には有向閉路（サイクル）が存在せず、完全な有向非巡回グラフ（DAG）となる。

このDAG上における Bellman 最適方程式は、目標不動点 $s^*$ からの逆向きのトポロジカル順序に基づく後退帰納法（Backward Induction）またはメモ化再帰により一意の解（不動点）に収束し、多次元の期待最小コスト制御ポリシーを一意に決定できる。

#### 他レイヤーとの連携境界条件：
1.  **L3（スキル直交）との結合**:
    スキル判定境界マージン低下によるルーティング誤差 $\epsilon(q)$ が上昇すると、$P_{success}$ の上限が減衰し、閾値 $\theta$ を下回りやすくなることで、早期に HITL による確認を促す。
2.  **L4（セキュリティエスカレーション）**:
    リスク指数 $I_u \ge I_{crit}$ のとき、自律成功確率 $P_{success}(e, m_e) = 0$ となり、上式より常に閾値を下回るため、強制的に $x_e = 1$ (HITL) となる。
3.  **L7（API縮退制限）**:
    $\Gamma_u \le 0$ のときは意思決定空間が制限され、$m_e = \text{Degraded}$ のみが選択可能となる。
4.  **L8（構造化ログ）**:
    各状態遷移における期待コストおよびポテンシャル差分は、L8 の定めた最小エントロピー構造化ログを通じてリアルタイムに監査システムに記録される。
5.  **L9（自己修復ループ）**:
    $k_u = 0$ で自律実行が失敗した場合、システムは例外状態とASTノード情報を L9 へエスカレーションし、自己修復ループのポテンシャル最小化をトリガーする。

---

## 3. エージェント工学への適用意義 (Significance)

1.  **多次元トレードオフの数学的統一**:
    本定理は、人的コスト（HITL）、計算コスト（自律実行）、API枯渇リスク（L7）、セキュリティリスク（L4）、およびメモリ容量制約（L6）という、性質の異なるパラメータを「期待総コストの最小化」という単一の数学的評価軸で統一・最適化する。
2.  **動的リスク選好によるUXの最適化**:
    リトライ回数 $k_u$ に応じて許容可能な成功確率の閾値を動的に変動させることで、初期フェーズでは自律実行によるコスト削減を狙い、失敗が続いてデッドラインが近づいた段階では速やかに人間に介入を促すという、人間中心の最適なUX遷移を実現する。

---

## 4. アルゴリズムと実装 (Algorithm & Implementation)

以下は、拡張状態空間 $V = (s, k, \Gamma, I)$ 上で期待最小コストを達成する最適な制御ポリシーを計算する FastAPI API サーバーの実装である。

2026年の技術エコシステム（**uv**, **Granian**, **FastAPI**, **SQLModel**, **structlog**, **Ruff** 準拠のコードスタイル）に完全に準拠している。

### 実装コード

```python
import structlog
from typing import Dict, List, Tuple, Optional, NamedTuple
from fastapi import FastAPI, HTTPException
from sqlmodel import SQLModel, Field, Session, create_engine, select

# L8 準拠: 構造化ロガーの初期化
logger = structlog.get_logger()

# 2026年標準: SQLModel による状態遷移パラメータの DB 永続化定義
class TransitionConfig(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    from_state: str = Field(index=True)
    to_state: str
    c_auto_normal: float
    c_auto_degraded: float
    p_success_normal: float
    p_success_degraded: float
    c_fail: float
    c_hitl: float
    gamma_cost: float
    risk_delta: float
    memory_heavy: bool

class State(NamedTuple):
    s: str       # 機能的状態 (L2)
    k: int       # 残りリトライ回数 (L2/L5)
    gamma: float # API制限バッファ (L7)
    I: float     # セキュリティリスク指数 (L4)

class UnifiedTaskGraphOptimizer:
    def __init__(
        self,
        transitions: List[TransitionConfig],
        I_crit: float = 0.8,
        K_max: int = 3,
        C_swap: float = 0.5
    ):
        self.transitions: Dict[str, List[TransitionConfig]] = {}
        for t in transitions:
            self.transitions.setdefault(t.from_state, []).append(t)
        self.I_crit = I_crit
        self.K_max = K_max
        self.C_swap = C_swap
        self.memo: Dict[State, Tuple[float, Optional[Tuple[str, str]], Optional[State], Optional[State]]] = {}

    def compute_optimal_policy(
        self,
        start_s: str,
        target_s: str,
        initial_gamma: float = 10.0,
        initial_I: float = 0.0,
        epsilon_q: float = 0.0,
        memory_limit_reached: bool = False
    ) -> Tuple[float, List[Tuple[State, State, str, str]]]:
        """
        Bellman最適方程式をメモ化再帰で解き、期待最小コストのポリシーを決定する。
        """
        self.memo.clear()
        start_state = State(start_s, self.K_max, initial_gamma, initial_I)

        def get_value(u: State) -> Tuple[float, Optional[Tuple[str, str]], Optional[State], Optional[State]]:
            if u.s == target_s:
                return 0.0, None, None, None
                
            if u in self.memo:
                return self.memo[u]
                
            if u.s not in self.transitions:
                return float('inf'), None, None, None
                
            best_cost = float('inf')
            best_decision = None
            best_succ_state = None
            best_fail_state = None
            
            for t_info in self.transitions[u.s]:
                v_s = t_info.to_state
                c_fail = t_info.c_fail
                c_hitl = t_info.c_hitl
                gamma_cost = t_info.gamma_cost
                risk_delta = t_info.risk_delta
                
                next_gamma = max(0.0, u.gamma - gamma_cost)
                next_I = min(1.0, max(0.0, u.I + risk_delta))
                
                is_sandbox_restricted = (u.I >= self.I_crit)
                available_modes = ["degraded"] if u.gamma <= 0.0 else ["normal", "degraded"]
                
                v_succ = State(v_s, self.K_max, next_gamma, next_I)
                v_succ_cost, _, _, _ = get_value(v_succ)
                cost_hitl = c_hitl + v_succ_cost
                
                if cost_hitl < best_cost:
                    best_cost = cost_hitl
                    best_decision = ("HITL", "normal")
                    best_succ_state = v_succ
                    best_fail_state = None
                
                for mode in available_modes:
                    if is_sandbox_restricted:
                        p_succ = 0.0
                    else:
                        p_base = t_info.p_success_normal if mode == "normal" else t_info.p_success_degraded
                        p_succ = p_base * (1.0 - epsilon_q)
                        if memory_limit_reached:
                            p_succ *= 0.8
                            
                    c_auto = t_info.c_auto_normal if mode == "normal" else t_info.c_auto_degraded
                    if memory_limit_reached and t_info.memory_heavy:
                        c_auto += self.C_swap
                        
                    if u.k > 0:
                        v_fail = State(u.s, u.k - 1, next_gamma, next_I)
                        v_fail_cost, _, _, _ = get_value(v_fail)
                        cost_auto = c_auto + p_succ * v_succ_cost + (1.0 - p_succ) * (c_fail + v_fail_cost)
                    else:
                        v_fail = v_succ
                        cost_auto = c_auto + p_succ * v_succ_cost + (1.0 - p_succ) * (c_fail + c_hitl + v_succ_cost)
                        
                    if cost_auto < best_cost:
                        best_cost = cost_auto
                        best_decision = ("AUTO", mode)
                        best_succ_state = v_succ
                        best_fail_state = v_fail if u.k > 0 else None
            
            res = (best_cost, best_decision, best_succ_state, best_fail_state)
            self.memo[u] = res
            return res

        optimal_cost, _, _, _ = get_value(start_state)
        
        path = []
        curr = start_state
        while curr.s != target_s:
            if curr not in self.memo:
                break
            cost, dec, succ_st, fail_st = self.memo[curr]
            if dec is None or succ_st is None:
                break
            path.append((curr, succ_st, dec[0], dec[1]))
            curr = succ_st
            
        return optimal_cost, path

app = FastAPI(title="L5 Task Graph Optimizer API")
sqlite_url = "sqlite:///task_graph.db"
engine = create_engine(sqlite_url, echo=False)

@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)

@app.post("/optimize")
def optimize_task_path(
    start_s: str,
    target_s: str,
    initial_gamma: float = 10.0,
    initial_I: float = 0.0,
    epsilon_q: float = 0.0,
    memory_limit_reached: bool = False
):
    with Session(engine) as session:
        transitions = session.exec(select(TransitionConfig)).all()
        
    if not transitions:
        raise HTTPException(status_code=400, detail="Database transitions config is empty.")
        
    optimizer = UnifiedTaskGraphOptimizer(transitions=transitions)
    cost, path = optimizer.compute_optimal_policy(
        start_s=start_s,
        target_s=target_s,
        initial_gamma=initial_gamma,
        initial_I=initial_I,
        epsilon_q=epsilon_q,
        memory_limit_reached=memory_limit_reached
    )
    
    logger.info(
        "optimal_path_optimized",
        start_s=start_s,
        target_s=target_s,
        total_expected_cost=cost,
        hop_count=len(path),
        epsilon_q=epsilon_q,
        memory_limit_reached=memory_limit_reached
    )
    
    return {
        "optimal_cost": cost,
        "path": [
            {
                "from_state": p[0]._asdict(),
                "to_state": p[1]._asdict(),
                "decision_type": p[2],
                "mode": p[3]
            } for p in path
        ]
    }
```
