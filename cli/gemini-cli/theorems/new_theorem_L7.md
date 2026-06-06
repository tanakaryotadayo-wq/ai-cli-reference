# API制約下の縮退運転境界定理 (Degraded Operation Boundary Theorem under API Constraints) - v4.0 (Final)

## 1. 定義 (Definition)

「API制約下の縮退運転境界定理」は、外部APIの呼び出し制限（レートリミット、429エラー、接続遮断等）が発生する環境において、L7（エージェント）レイヤーの自律エージェントが、ハングアップ（応答停止）やチャタリングを回避し、安全に機能を縮小した「縮退運転（Degraded Operation）」へ遷移するための限界条件（臨界点）および制御則を規定する定理である。

### 1.1. 状態空間の定義
エージェントが実行するタスクを $T$、絶対デッドラインを $D$、現在時刻を $t$ とし、残余許容時間（Slack Time）を以下のように定義する。
$$L(t) = D - t$$

エージェントの動的動作モード $M(t)$ は、以下の**多段縮退状態空間（Multi-tier Degradation State Space）** $M$ をとる：
$$M(t) \in \{M^{(0)}, M^{(1)}, M^{(2)}, M^{(3)}, M^{(4)}\}$$
各モードの定義および期待効用（Utility） $U(M^{(k)})$ は以下の通りであり、単調減少関係にある。
$$U(M^{(0)}) > U(M^{(1)}) > U(M^{(2)}) > U(M^{(3)}) > U(M^{(4)})$$

1.  **$M^{(0)} = M_{normal}$ (通常運転モード)**:
    *   クラウド上の最高性能モデル（Premium Cloud API: Gemini Pro, GPT-4等）を使用する。
2.  **$M^{(1)} = M_{degraded\_local}$ (ローカル縮退モード)**:
    *   Mac Studio上のローカル推論エンジン（MLX-LM等）で動作する軽量LLMを使用する。
3.  **$M^{(2)} = M_{degraded\_rule}$ (ルールベース縮退モード)**:
    *   推論を伴わないキャッシュ、または正規表現・ルールベースによる即時応答を使用する。
4.  **$M^{(3)} = M_{hitl}$ (人間介入モード)**:
    *   人間（Operator/User）への状況エスカレーションおよび直接入力を要請する。
5.  **$M^{(4)} = M_{fail}$ (安全な失敗モード)**:
    *   タスク実行不可能と判断し、後続プロセスへエラーまたは安全なデフォルト値を即座に返却して自己停止する。

### 1.2. 確率的レイテンシと安全マージンの定式化
各モード $M^{(k)}$ におけるタスク実行レイテンシ（通信時間、内部処理、および推論オーバーヘッドの合計）を、確率平均 $\mu^{(k)}$ および標準偏差 $\sigma^{(k)}$ を持つ確率変数 $\mathcal{T}^{(k)}$ としてモデル化する。
不確実性下でデッドラインを遵守するため、リスク許容度を示す安全係数 $\lambda_k > 0$ を用いて、**リスク調整後実行レイテンシ（Risk-adjusted Latency）** $\tau^{(k), safe}$ を以下のように定義する。
$$\tau^{(k), safe} = \mu^{(k)} + \lambda_k \sigma^{(k)}$$

### 1.3. トークンバケット待機時間モデル
APIエンドポイント $e_i$ に対する呼び出し制限を、バケット容量 $B_i$、トークン補充レート $r_i$ (tokens/sec) のトークンバケットモデルとして定義する。
1回のリクエストに必要なトークン数を $N_{req}$、時刻 $t$ におけるバケット残量を $C_i(t)$ としたとき、API制限に伴う**実効待機時間（Effective Waiting Time）** $W^{(0)}_i(t)$ を以下のように定義する。
$$W^{(0)}_i(t) = \begin{cases} 0 & \text{if } C_i(t) \ge N_{req} \\ \min \left( R_{reset, i}(t), \frac{N_{req} - C_i(t)}{r_i} \right) & \text{if } C_i(t) < N_{req} \end{cases}$$
ここで、$R_{reset, i}(t)$ はAPIプロバイダから提供されるハードウィンドウのリセット時間（Time to Reset）である。
なお、ローカルおよびルールベースモード（$k \ge 1$）は外部API制約を受けないため、以下が成立する。
$$W^{(k)}(t) = 0 \quad (\forall k \ge 1)$$

### 1.4. 境界関数 (Boundary Function)
各モード $M^{(k)}$ について、デッドラインに対する時間的余裕を示す**縮退運転境界関数 $\Gamma^{(k)}(t)$** を以下のように定義する。
$$\Gamma^{(k)}(t) = W^{(k)}(t) + \tau^{(k), safe} - L(t)$$

---

## 2. 主張 (Assertions)

### 第一主張：多段縮退環境における応答性保証の必要十分条件
タスク $T$ がデッドライン $D$ を超過せず（$t_{end} \le D$）、かつ無限待機（ハングアップ）を回避するための必要十分条件は、任意の評価時刻 $t$ において、エージェントが以下の評価式に基づき、実行可能な最小インデックス（最高効用）のモード $M^{(k^*)}$ を動的に選択し続けることである。

$$k^*(t) = \min \left\{ k \in \{0, 1, 2\} \;\middle|\; \Gamma^{(k)}(t) \le 0 \right\}$$

もし集合 $\{k \in \{0, 1, 2\} \mid \Gamma^{(k)}(t) \le 0\}$ が空集合である（＝すべての自動化モードでデッドラインに間に合わない）場合、システムは即座に $M^{(3)} (M_{hitl})$ または $M^{(4)} (M_{fail})$ へ遷移しなければならない。これを怠った場合、システムは生存性（Liveness）を喪失する。

### 第二主張：最低保証性能の非ゼロ性と他レイヤー連携
縮退運転モード $M^{(1)}, M^{(2)}$ において、タスク達成度（Utility） $U$ は、事前に定義された最小許容実効値 $U_{min} > 0$ を下回らない。
$$U(M^{(k)}) \ge U_{min} > 0 \quad (k \in \{1, 2\})$$

この実効値を担保するため、L7は以下の他レイヤーの定理と密結合する：
*   **L1（プロンプトセマンティクス収束定理）との結合**:
    $M^{(1)}$ への遷移時、ローカルモデルのコンテキスト制限に適合させるため、プロンプト表現密度 $\mathcal{D}(P)$ を限界閾値 $\mathcal{D}_c$ に近づけて高密度圧縮（$\mathcal{C}_{L1}(P)$）を行う。これにより、セマンティクスを維持したまま、ローカル推論の $\mu^{(1)}$ を極小化する。
*   **L6（記憶容量制限下の最適忘却定理）との結合**:
    ローカルモデル実行時のコンテキストウィンドウ制限を遵守するため、状態遷移と同時にL6の最適忘却・要約フェーズをトリガーし、メモリ空間を動的に圧縮・スワップアウトする。

### 第三主張：ハイブリッドシステムにおける非チャタリング制御とリアプノフ安定性
モードの上昇遷移（例: 縮退 $M^{(1)}$ から通常 $M^{(0)}$ への復帰）において、頻繁な状態遷移によるチャタリング（Zeno動作）を防ぐため、コントローラに以下の**容量ヒステリシスマージン $\Delta_C > 0$** および **最小滞在時間（Dwell Time） $T_{dwell} > 0$** を課す。

通常モード $M^{(0)}$ への復帰（アップグレード）判定は、前回のモード遷移時刻を $t_{trans}$ としたとき、以下の条件をすべて満たす場合にのみ実行される。
1.  **時間条件**: $t - t_{trans} \ge T_{dwell}$
2.  **容量条件**: $C_i(t) \ge N_{req} + \Delta_C$
3.  **境界条件**: $\Gamma^{(0)}(t) + \Delta_{\Gamma} \le 0 \quad (\Delta_{\Gamma} > 0)$

#### 【数理証明：Zeno動作（無限回遷移）の排除】
モード遷移が発生する時刻の無限系列を $\{t_1, t_2, t_3, \dots\}$ とする。
上記「時間条件」より、任意の隣接する遷移時刻 $t_j, t_{j+1}$ の間には必ず以下の不等式が成立する。
$$t_{j+1} - t_j \ge T_{dwell} > 0$$
任意の有限時間区間 $[0, T]$ における総遷移回数を $N(T)$ とすると、以下が成り立つ。
$$N(T) \le \frac{T}{T_{dwell}} < \infty$$
これにより、有限時間内に無限回の状態遷移が発生する「Zeno動作（チャタリング）」が数学的に完全に排除される。

#### 【数理証明：リアプノフ安定性】
システムの不連続な状態遷移を記述するリアプノフ的なポテンシャル関数 $V(M(t), C(t))$ を以下のように定義する。
$$V(M(t), C(t)) = \Phi(M(t)) + E_{api}(t)$$
ここで、$\Phi(M^{(k)}) = k \cdot \gamma$ （$\gamma > 0$ はモード退行に伴うポテンシャル散逸定数）はモードポテンシャルであり、$E_{api}(t) = \max\left(0, 1 - \frac{C_i(t)}{N_{req} + \Delta_C}\right)$ はAPIバケット容量の未回復による不適合エネルギーを表す。

1.  **通常時の挙動**: モードが固定され、API容量が補充される過程では、$E_{api}(t)$ は単調減少するため、$\dot{V} \le 0$ が維持される。
2.  **退行遷移時 ($M^{(k)} \to M^{(k+1)}$)**: API枯渇（$C_i(t) \to 0$）に伴い、$\Gamma^{(k)}(t) > 0$ となってモードが退行する。このとき、ポテンシャル変化は $\Delta V = \gamma - E_{api}$ となり、閾値設計 $\gamma < E_{api}(t_{trans})$ により $\Delta V < 0$（エネルギーの散逸）が保証される。
3.  **復旧遷移時 ($M^{(k)} \to M^{(k-1)}$)**: $C_i(t) \ge N_{req} + \Delta_C$ を満たした時点で復帰するため、遷移直前の $E_{api}(t) = 0$ である。復帰直後のポテンシャルは $\Phi(M^{(k-1)}) = (k-1)\gamma$ となり、遷移に伴う $\Delta V = -\gamma < 0$ が得られる。

以上より、すべての遷移および通常実行時において $V(t)$ は単調非増加（$\Delta V \le 0$）であり、システムは定常かつ安定な動作点に漸近収束する。

### 第四主張：有向タスクグラフ最小経路との意思決定統合 (L5 HITL Integration)
すべての自動モードにおいて $\Gamma^{(k)}(t) > 0$ となり、タスクがデッドライン内に完了できないと判断された場合、エージェントが $M^{(3)} (M_{hitl})$ を選択するか、あるいは $M^{(4)} (M_{fail})$ を選択するかの最適意思決定は、L5（有向タスクグラフ最小経路定理）における期待コスト比較に帰着される。

-   **縮退完了（自動フォールバック継続）の期待コスト**:
    $$\mathbb{E}[C_{degraded}] = C_{local} + (1 - P_{success\_degraded}) \cdot C_{fail} + U_{lost}$$
-   **人間介入（HITL）の期待コスト**:
    $$\mathbb{E}[C_{hitl}] = C_{hitl\_intervention}$$

$$\mathbb{E}[C_{degraded}] < \mathbb{E}[C_{hitl}]$$
上記不等式が成立する場合は、実現可能な最小効用モード（$M^{(1)}$ または $M^{(2)}$）を選択し、そうでない場合は即座に $M^{(3)} (M_{hitl})$ を要求する。

---

## 3. 2026年技術エコシステムへの適合 (Ecosystem Alignment)

本定理の実装および制御フローは、以下の2026年標準開発技術エコシステムに完全に適合するように設計されている。

-   **Granian (ASGIサーバー)**:
    *   コントローラは非同期ASGIインターフェースに準拠し、Granianのクライアント並行処理性能を最大化する非ブロッキング非同期処理（`async/await`）で実装される。
-   **uv (パッケージ・ランタイム管理)**:
    *   高速なPython依存関係解決およびランタイム実行を保証するため、パッケージマネージャーとして `uv` を使用し、仮想環境の自動ロックおよびスクリプトインライン依存関係（PEP 723）をサポートする。
-   **Ruff (Linter/Formatter)**:
    *   厳格な静的解析ルール（F, E, W, I, N, UP, B, A, C4, RET等）に完全に準拠し、不要なインポートの排除、型ヒントの徹底、高速な実行パスの保証を行う。
-   **Next.js 15 + Turbopack**:
    *   エージェントの動作モード遷移（$M_{normal} \rightleftharpoons M_{degraded\_local}$）のリアルタイムUI表示のため、Server-Sent Events (SSE) または非同期APIポーリングを統合するNext.js 15 クライアントコンポーネントを標準実装する。

---

## 4. アーキテクチャと相互接続モデル

L7定理は、以下のようにL1〜L9の各定理と密結合して自律ループを構成する。

```mermaid
graph TD
    subgraph L7 レイヤー (本定理)
        L7_Controller[L7: 縮退運転境界コントローラ]
        L7_Boundary[Γ_k 境界関数 / 待機時間算出]
        L7_Stability[Hysteresis / Dwell-Time 制御]
    end

    subgraph 入力・意味論 (L1-L3)
        L1[L1: プロンプトセマンティクス収束] -->|コンテキスト高密度圧縮| L7_Controller
        L3[L3: スキル直交排他] -->|誤判定率/成功率| L5[L5: 有向タスクグラフ最小経路]
        L2[L2: 状態遷移ループフリー] -->|状態ポテンシャル減少保証| L7_Controller
    end

    subgraph 実行・セキュリティ (L4-L6)
        L4[L4: 自己免疫サンドボックス] -->|リスク I >= I_crit 時 成功率=0| L5
        L6[L6: 記憶容量最適忘却] -->|メモリ忘却 / コンテキスト削減| L7_Controller
    end

    subgraph 観測・修復 (L8-L9)
        L7_Controller -->|状態ログエントロピー最小化| L8[L8: 構造化ログ]
        L7_Controller -->|例外発生時のAST自己修復| L9[L9: 自己修復ループ不動点]
    end

    L7_Controller -->|モード評価| L7_Boundary
    L7_Boundary -->|チャタリング防止検証| L7_Stability
    L7_Stability -->|最適モード決定| L5
    L5 -->|期待コスト比較| L7_Controller
```

---

## 5. 制御実装コード (Implementation Code)

### 5.1. バックエンド: Granian 適合非同期コントローラ (Python, Ruff準拠)

```python
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "structlog>=24.1.0",
#     "fastapi>=0.110.0",
# ]
# ///
import time
import asyncio
from typing import Dict, Any, Callable, Awaitable, Tuple
import structlog

logger = structlog.get_logger()

class DeadlineExceededException(Exception):
    """デッドライン超過によりタスクが継続不能なことを示す例外"""
    pass

class AsyncTokenBucket:
    """APIレートリミットをシミュレートする非同期トークンバケット"""
    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_update = time.time()
        self._lock = asyncio.Lock()

    async def get_tokens(self) -> float:
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_update = now
            return self.tokens

    async def consume(self, amount: float) -> bool:
        async with self._lock:
            tokens = await self._get_tokens_unlocked()
            if tokens >= amount:
                self.tokens -= amount
                return True
            return False

    async def _get_tokens_unlocked(self) -> float:
        now = time.time()
        elapsed = now - self.last_update
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_update = now
        return self.tokens

class AsyncDegradedOperationController:
    def __init__(
        self,
        endpoint_name: str,
        task_deadline: float,
        latency_stats: Dict[str, Tuple[float, float]] = None,
        safety_coeff: float = 2.0,
        hysteresis_capacity: float = 10.0,
        hysteresis_gamma: float = 0.5,
        dwell_time: float = 5.0,
        cost_hitl: float = 100.0,
        cost_fail: float = 250.0,
    ):
        self.endpoint_name = endpoint_name
        self.deadline = task_deadline
        self.stats = latency_stats or {
            "NORMAL": (3.5, 0.8),
            "DEGRADED_LOCAL": (1.2, 0.2),
            "DEGRADED_RULE": (0.05, 0.01)
        }
        self.lambda_k = safety_coeff
        self.delta_c = hysteresis_capacity
        self.delta_gamma = hysteresis_gamma
        self.t_dwell = dwell_time
        self.c_hitl = cost_hitl
        self.c_fail = cost_fail
        
        self.mode = "NORMAL"
        self.last_transition_time = 0.0

        self.tau_safe = {
            m: mu + self.lambda_k * sigma
            for m, (mu, sigma) in self.stats.items()
        }

    async def _calculate_waiting_time(
        self, token_bucket: AsyncTokenBucket, tokens_req: float, time_to_reset: float
    ) -> float:
        current_tokens = await token_bucket.get_tokens()
        if current_tokens >= tokens_req:
            return 0.0
        refill_time = (tokens_req - current_tokens) / token_bucket.refill_rate
        return min(time_to_reset, refill_time)

    async def evaluate_mode(
        self, token_bucket: AsyncTokenBucket, tokens_req: float, time_to_reset: float
    ) -> str:
        current_time = time.time()
        slack = self.deadline - current_time
        
        if slack <= 0:
            logger.error("Absolute deadline exceeded in boundary evaluation.", slack=slack)
            self.mode = "FAIL"
            return self.mode

        w_normal = await self._calculate_waiting_time(token_bucket, tokens_req, time_to_reset)
        
        gamma_normal = w_normal + self.tau_safe["NORMAL"] - slack
        gamma_local = self.tau_safe["DEGRADED_LOCAL"] - slack
        gamma_rule = self.tau_safe["DEGRADED_RULE"] - slack

        proposed_mode = self.mode

        if gamma_normal <= 0:
            proposed_mode = "NORMAL"
        elif gamma_local <= 0:
            proposed_mode = "DEGRADED_LOCAL"
        elif gamma_rule <= 0:
            proposed_mode = "DEGRADED_RULE"
        else:
            p_success_degraded = 0.75
            u_lost = 30.0
            expected_c_degraded = self.tau_safe["DEGRADED_LOCAL"] + (1 - p_success_degraded) * self.c_fail + u_lost
            
            if expected_c_degraded < self.c_hitl:
                proposed_mode = "DEGRADED_RULE"
            else:
                proposed_mode = "HITL"

        if self._is_upgrade(self.mode, proposed_mode):
            time_elapsed = current_time - self.last_transition_time
            tokens_recovered = (await token_bucket.get_tokens()) >= (tokens_req + self.delta_c)
            boundary_clear = gamma_normal + self.delta_gamma <= 0

            if not (time_elapsed >= self.t_dwell and tokens_recovered and boundary_clear):
                logger.debug(
                    "Upgrade blocked by chattering prevention constraints.",
                    current_mode=self.mode,
                    proposed_mode=proposed_mode,
                    time_elapsed=time_elapsed,
                    tokens_recovered=tokens_recovered,
                    boundary_clear=boundary_clear
                )
                return self.mode

        if proposed_mode != self.mode:
            logger.warn(
                "L7 Boundary triggered state transition.",
                prev_mode=self.mode,
                next_mode=proposed_mode,
                slack=slack,
                gamma_normal=gamma_normal
            )
            self.mode = proposed_mode
            self.last_transition_time = current_time

        return self.mode

    def _is_upgrade(self, current: str, proposed: str) -> bool:
        mode_order = {"NORMAL": 0, "DEGRADED_LOCAL": 1, "DEGRADED_RULE": 2, "HITL": 3, "FAIL": 4}
        return mode_order[proposed] < mode_order[current]

    async def execute_task(
        self,
        task_input: str,
        api_client_fn: Callable[[str], Awaitable[Any]],
        local_fallback_fn: Callable[[str], Awaitable[Any]],
        rule_fallback_fn: Callable[[str], Awaitable[Any]],
        token_bucket: AsyncTokenBucket,
        tokens_req: float,
        time_to_reset: float,
        l1_compressor: Callable[[str], str],
        l6_memory_manager: Callable[[], None]
    ) -> Any:
        current_mode = await self.evaluate_mode(token_bucket, tokens_req, time_to_reset)

        if current_mode == "FAIL":
            raise DeadlineExceededException("Unable to complete task within deadline constraints safely.")

        elif current_mode == "HITL":
            logger.warn("HITL escalation required.")
            return {"status": "HITL_REQUIRED", "task": task_input}

        elif current_mode == "DEGRADED_RULE":
            logger.info("Executing via DEGRADED_RULE (Rule-based/Cache).")
            return await rule_fallback_fn(task_input)

        elif current_mode == "DEGRADED_LOCAL":
            logger.info("Executing via DEGRADED_LOCAL (Local LLM MLX-LM).")
            l6_memory_manager()
            compressed_input = l1_compressor(task_input)
            return await local_fallback_fn(compressed_input)

        try:
            logger.info("Executing via NORMAL (Premium Cloud API).")
            if not await token_bucket.consume(tokens_req):
                logger.warn("Token acquisition failed at runtime. Re-evaluating boundary.")
                return await self.execute_task(
                    task_input, api_client_fn, local_fallback_fn, rule_fallback_fn,
                    token_bucket, tokens_req, 0.0, l1_compressor, l6_memory_manager
                )
            return await api_client_fn(task_input)
            
        except Exception as e:
            logger.error("Execution error in NORMAL mode. Forcing degradation.", error=str(e))
            return await self.execute_task(
                task_input, api_client_fn, local_fallback_fn, rule_fallback_fn,
                token_bucket, tokens_req, time_to_reset=3600.0,
                l1_compressor=l1_compressor, l6_memory_manager=l6_memory_manager
            )
```

### 5.2. フロントエンド: Next.js 15 UI 状態表示コンポーネント (TypeScript)

```typescript
'use client';

import React, { useEffect, useState } from 'react';

type AgentMode = 'NORMAL' | 'DEGRADED_LOCAL' | 'DEGRADED_RULE' | 'HITL' | 'FAIL';

interface AgentStatusProps {
  taskId: string;
}

export default function AgentStatusTracker({ taskId }: AgentStatusProps) {
  const [mode, setMode] = useState<AgentMode>('NORMAL');
  const [slackTime, setSlackTime] = useState<number>(0);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    const eventSource = new EventSource(`/api/agent/status?taskId=${taskId}`);

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.mode) setMode(data.mode);
        if (data.slack_time) setSlackTime(data.slack_time);
      } catch (err) {
        console.error('Failed to parse SSE payload', err);
      }
    };

    eventSource.onerror = (err) => {
      console.error('SSE Connection failed', err);
      setErrorMsg('エージェントステータス通信にエラーが発生しました');
      eventSource.close();
    };

    return () => {
      eventSource.close();
    };
  }, [taskId]);

  const getBadgeStyle = (currentMode: AgentMode) => {
    switch (currentMode) {
      case 'NORMAL':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'DEGRADED_LOCAL':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'DEGRADED_RULE':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      case 'HITL':
        return 'bg-orange-100 text-orange-800 border-orange-200 animate-pulse';
      case 'FAIL':
        return 'bg-red-100 text-red-800 border-red-200 font-bold';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className="p-4 max-w-md mx-auto bg-white rounded-xl shadow-md space-y-4 border border-gray-100">
      <div className="flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-900">L7 エージェント動作状態</h3>
        <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getBadgeStyle(mode)}`}>
          {mode}
        </span>
      </div>
      
      <div className="space-y-2 text-sm text-gray-600">
        <div className="flex justify-between">
          <span>残余許容時間 (Slack Time):</span>
          <span className="font-mono font-bold text-gray-800">{slackTime.toFixed(2)}s</span>
        </div>
        <div className="w-full bg-gray-100 rounded-full h-2">
          <div 
            className={`h-2 rounded-full transition-all duration-500 ${slackTime > 5 ? 'bg-green-500' : 'bg-red-500'}`}
            style={{ width: `${Math.max(0, Math.min(100, (slackTime / 30) * 100))}%` }}
          />
        </div>
      </div>

      {errorMsg && (
        <div className="p-2 text-xs text-red-700 bg-red-50 rounded-lg border border-red-100">
          {errorMsg}
        </div>
      )}
    </div>
  );
}
```
