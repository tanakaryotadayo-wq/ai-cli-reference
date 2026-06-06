# 構造化ログのエントロピー最小化定理 (Entropy Minimization Theorem for Structured Logging) - v4.0 (R3 最終版)

## 1. 定理の定義 (Definition)

構造化ログのエントロピー最小化定理とは、分散システムおよびマルチエージェント協調環境において、**「実行時のトレーサビリティ（異常の一意特定性と状態軌跡の再現性）を完全に維持しながら、ログ出力のデータ肥大化（情報冗長性）を極小化するための情報理論的境界とログ構造化設計基準を定義する定理」**である。

本定理は、ログメッセージを単なる「テキスト情報の伝達媒体」ではなく「システム状態空間内の特定の軌跡に対する射影」として再定義し、シャノンエントロピーの観点から最適化を行う。

---

## 2. 定理の主張 (Claim)

### 数理モデルと定式化

実行時のシステム（またはエージェント）の状態空間を $\mathcal{S}$、コンテキスト空間を $\mathcal{C}$、静的コード位置（ログポイント）の集合を $\mathcal{M}$ とする。
長さ $N$ の実行軌跡（状態遷移系列）は次のように表される。

$$\mathcal{P} = (s_0, s_1, \dots, s_N) \quad (\text{where } s_k \in \mathcal{S})$$

このとき、各遷移 $s_{k-1} \to s_k$ が実行されるソースコード上のログ出力位置（抽象構文木（AST）ノードなど）を $loc_k \in \mathcal{M}$ し、対応するログポイント系列を以下のように表す。

$$\mathcal{M}_{path} = (loc_1, loc_2, \dots, loc_N) \quad (\text{where } loc_k \in \mathcal{M})$$

各ログポイント $loc_k$ は、システム全体で一意の静的識別子（Fingerprint / Hash） $ID_k = \phi(loc_k)$ に静的マージ（射影）される。ここで $\phi: \mathcal{M} \to \mathcal{ID}$ は単射または多対1の射影である。

伝搬される共通トレースコンテキスト（`trace_id`, `agent_id` などの動的だがスコープ内で不変な変数群）を $C \in \mathcal{C}$ とする。

ステップ $k$ における構造化ログエントリ $L_k$ は、静的識別子 $ID_k$ と、そのポイントにおける動的状態の差分ペイロード $\Delta s_k = s_k \ominus s_{k-1}$ の直和（構造的結合）として表される。

$$L_k = ID_k \oplus \Delta s_k$$

ログストリーム $\mathcal{L} = (L_1, \dots, L_N)$ の初期状態 $s_0$ およびコンテキスト $C$ の下での条件付きエントロピー $H(\mathcal{L} | s_0, C)$ は、エントロピーの連鎖律により以下のように定式化される。

$$H(\mathcal{L} | s_0, C) = \sum_{k=1}^N H(L_k | L_{<k}, s_0, C)$$

ここで、履歴 $\mathcal{L}_{<k}$ および初期状態 $s_0$、コンテキスト $C$ から直前のシステム状態 $s_{k-1}$ が一意にデコード（再構成）可能である（すなわち $H(s_{k-1} | L_{<k}, s_0, C) = 0$）というトレーサビリティの保存を前提とすると、各ステップ $k$ における条件付きエントロピーは以下のように簡約・分解される。

$$H(L_k | L_{<k}, s_0, C) = H(ID_k, s_k | s_{k-1}, C)$$

エントロピーの連鎖律をさらに適用することにより、以下を得る。

$$H(ID_k, s_k | s_{k-1}, C) = H(s_k | s_{k-1}, C) + H(ID_k | s_k, s_{k-1}, C)$$

### 定理的限界（エントロピー最小化境界）

> **【定理：構造化ログのエントロピー最小化境界（R3決定版）】**
>
> 実行時の状態軌跡およびコード実行パスを完全に再構成する（$H(\mathcal{P}, \mathcal{M}_{path} | \mathcal{L}, s_0, C) = 0$）ために必要な、各ステップにおける最小ログ情報エントロピー $H_{min}(L_k | L_{<k}, s_0, C)$ は、以下の境界によって一意に決定される。
>
> $$H_{min}(L_k | L_{<k}, s_0, C) = H(s_k | s_{k-1}, C) + H(ID_k | s_k, s_{k-1}, C)$$
>
> ここで：
> 1. **$H(s_k | s_{k-1}, C)$ （動的状態遷移エントロピー）**:
>    直前状態 $s_{k-1}$ とコンテキスト $C$ の下での、システム状態遷移の非決定論的な不確実性。
> 2. **$H(ID_k | s_k, s_{k-1}, C)$ （コード実行パス曖昧性エントロピー）**:
>    特定の状態遷移 $s_{k-1} \to s_k$ が発生したときに、どのコード位置（ログポイント）を経由したかに関する曖昧性。

### パラメーターの極限値（エッジケース）における整合性検証

1. **完全決定論的極限 (Deterministic Limit)**:
   - **条件**: システムの遷移が完全に決定論的（$H(s_k | s_{k-1}, C) = 0$）であり、かつ各状態遷移に対応するログポイントが一意（$H(ID_k | s_k, s_{k-1}, C) = 0$）である。
   - **挙動**: $H_{min} = 0$ となり、ログ出力は一切不要（出力サイズ 0）である。静的コードマップと初期値・コンテキストのみで実行時の動作を完全リプレイ可能。
2. **完全カオス極限 (Chaotic / Maximum Entropy Limit)**:
   - **条件**: 状態遷移が完全に非決定論的（$H(s_k | s_{k-1}, C) \to \log_2 |\mathcal{S}|$）である。
   - **挙動**: 必要ログサイズは状態空間の記述長に発散する。ログの肥大化を防ぐために状態表現 $\mathcal{S}$ 自体の「粗視化（Abstraction）」を行い、状態の解像度を下げることで $H(s_k | s_{k-1}, C)$ を人工的に抑制する設計が必要となる。
3. **コードパス完全重複極限 (Code Path Ambiguity Limit)**:
   - **条件**: 同じ状態遷移（例：`status: active -> inactive`）がシステム内の無数のログポイントで発生し、状態の変化だけでは「どのコード行が実行されたか」が全く特定できない（$H(ID_k | s_k, s_{k-1}, C) \to \log_2 |\mathcal{M}|$）場合。
   - **挙動**: このとき静的識別子 $ID_k$ を明示的にログに記録することで $H(ID_k | s_k, s_{k-1}, C) = 0$ にリセットし、コードレベルのトレーサビリティを回復する。
4. **コンテキスト喪失極限 (Zero Context Limit)**:
   - **条件**: 分散トレンスコンテキストが伝搬されていない（$C = \emptyset$）場合。
   - **挙動**: 式は $H_{min} = H(s_k | s_{k-1}) + H(ID_k | s_k, s_{k-1})$ に退化する。情報理論的性質 $H(s_k | s_{k-1}) \ge H(s_k | s_{k-1}, C)$ より、コンテキストの欠如が必要最小エントロピーの下限を引き上げ、ログサイズを大幅に増大させる。

---

## 3. 他レイヤー（L1〜L9）との数理的・機能的整合性 (Cross-Layer Integration)

本定理は、エージェント工学の他レイヤーと密接に結合し、相乗効果を発揮する。

1. **L1 (プロンプトセマンティクス収束定理) との連携**:
   L1における意味多様体上の意味密度分布 $\rho_P(x)$ から決定される球充填境界（Sphere Packing Bound）およびSoftmaxアテンションノイズに基づき、エージェントのプロンプト解釈の曖昧性（セマンティクスエントロピー）が動的状態遷移 $H(s_k | s_{k-1}, C)$ の初期ノイズ分布に射影される。L8はプロンプトのセマンティクス乖離度（L1評価値）を最小ペイロードで記録し、L1の過圧縮・過希釈境界をリアルタイム監視する。
2. **L2 (状態遷移ループフリー不動点定理) との連携**:
   L2のポテンシャル関数 $\Phi(s)$ により、遷移可能な状態空間は $\mathcal{S}_{valid}(s_{k-1}) = \{s \in \mathcal{S} \mid \Phi(s) < \Phi(s_{k-1})\}$ に制限される。これにより、動的状態遷移エントロピーは以下のように上界が抑制される：
   $$H(s_k | s_{k-1}, C) \le \log_2 |\mathcal{S}_{valid}(s_{k-1})| < \log_2 |\mathcal{S}|$$
   L8の動的ペイロード $\Delta s_k$ には、ポテンシャルの変化量 $\Delta \Phi_k$ またはそれを計算可能な最小状態差分が記録され、Critic側でループフリー境界条件の動的検証が最小エントロピーで実行できる。
3. **L3 (スキル記述の直交排他定理) との連携**:
   L3における直交排他境界（正規化Euclidean距離 $d_2$ と遷移境界マージン $\Delta$）を維持するための決定コストが、L8のログに出力される。スキルの重複チャタリング（L3違反）が発生した場合、L8は最小限の衝突イベントID（$ID_{clash}$）のみを出力し、ログ肥大化を防ぎつつルーティングエラーを特定可能にする。
4. **L4 (自己免疫的サンドボックス隔離定理) との連携**:
   L4が定める隔離境界 $\mathcal{B}(t)$ の変化、および生存最小権限 $\mathcal{B}_{min}$ と破壊的権限 $\mathcal{P}_{destructive}$ の分離状態をL8が記録する。L4のセキュリティ例外が発生した場合、L8はそのコンテキスト $C$ に紐づく実行スナップショットのメタデータのみをログし、安全領域への迅速な復元処理を支援する。
5. **L5 (有向タスクグラフ最小経路定理) との連携**:
   L5はタスクDAGにおける期待遷移コストの最小化を決定する。タスクDAGのトポロジーにより、遷移可能なタスクノードは現在のノード $v_{k-1}$ のアウトエッジ集合 $\mathcal{A}(v_{k-1})$ に制限され、さらにルーティング最適化によって期待遷移確率が特定ノードに収束するため、状態遷移エントロピー $H(s_k | s_{k-1}, C)$ が大幅に低下する。
6. **L6 (記憶容量制限下の最適忘却定理) との連携**:
   L6は認知負荷制限下のメモリ圧縮や破棄（忘却）を制御する。L8はメモリの相転移（圧縮、外部スワップ、完全忘却）が発生した事実とそのメタデータ（メモリID、圧縮率等）のみを最小エントロピーで記録し、忘却されたメモリの具体的内容自体はログに出力しない。これにより、ログ肥大化の防止とセキュリティ/プライバシー保護（不要情報の物理的排除）を二重に担保する。
7. **L7 (API制約下の縮退運転境界定理) との連携**:
   L7はAPI制限に基づく通常運転と縮退運転のモード境界 $\Gamma(t) \le 0$ を管理する。モード $m_k \in \{ \text{Normal}, \text{Degraded} \}$ は状態 $s_k$ に内包される。$\Gamma(t) > 0$ においてシステムが縮退運転 $M_{degraded}$ へ遷移する決定論的ルールにより、このモード遷移にかかるエントロピーは $H(m_k | \Gamma(t) > 0) = 0$ となり、境界交差イベント発生の瞬間のみ最小限に記録される。
8. **L9 (自己修復ループの不動点収束定理) との連携**:
   L9はAST編集距離とテスト結果に基づくコード修復ループを定義する。L8が出力する $ID_{err} = \phi(loc_{err})$ により、L9のバグ箇所特定にかかる探索空間のエントロピーを $H(\text{repair})$ から $H(\text{repair} | ID_{err})$ に縮小し、自己修復の収束時間を劇的に短縮する。

---

## 4. エージェント工学への適用意義 (Significance in Agent Engineering)

1. **LLMトークン消費とロギングコストの削減**:
   自律エージェントの推論プロセス（思考木、ツール呼び出し、自己反省）は膨大なログを生成する。本定理を適用することで、各ステップの冗長なコンテキストを動的に排除し、状態の変位（Delta）のみを構造化ログとして記録することで、ストレージおよびLLMにコンテキストを入力する際のトークン消費を最小化できる。
2. **推論パスの決定論的デバッグ**:
   エージェントの自律的な分岐（非決定的な挙動）に対して、静的識別子 $ID_i$ をコードの AST（抽象構文木）の特定ノードと紐付けることで、どの意思決定ポイントで異常（ハルシネーションや不整合）が発生したかを一意かつ瞬時に特定できる。
3. **エージェント状態の分散観測**:
   複数のエージェントが協調して動作する際、メッセージバス上の共通トレースコンテキスト $C$ を介してログが自動的にマージされるため、個々のエージェントが持つべきログ状態を最小化しつつ、システム全体としてのオブザーバビリティを維持できる。

---

## 5. 2026年推奨エコシステム準拠の実装例 (Ecosystem Implementation)

以下は、2026年の推奨技術スタックである **uv**, **Granian**, **Ruff**, **structlog**, および **Google Antigravity SDK** のライフサイクルフックを使用した、本定理に準拠する可観測性エンジンの実装コードである。

### プロジェクト構成と依存関係 (`pyproject.toml`)
依存関係は `uv` を用いて一元管理され、コードスタイルは `Ruff` を用いて静的に強制される。

```toml
[project]
name = "agy-observability-engine"
version = "4.0.0"
dependencies = [
    "structlog>=26.1.0",
    "google-antigravity>=2.0.0",
    "fastapi>=0.115.0",
    "granian[all]>=1.6.0",
]
```

### 観測サーバー実装 (`app.py`)
Next.js 15 + Turbopack フロントエンドから連携されるトレースIDを ASGI 経由で伝搬し、エントロピーを極小化した構造化ログを出力する。

```python
import structlog
import uuid
from typing import Any, Dict
from fastapi import FastAPI, Request
from google.antigravity import Agent
from google.antigravity.connections.local import LocalAgentConfig
from google.antigravity.hooks import hooks
from google.antigravity import types

# 1. structlog の 2026年標準構成 (RuffによるLinter対応)
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ]
)
logger = structlog.get_logger()

# 2. FastAPI アプリケーション (Granian で実行される ASGI)
app = FastAPI()

@app.middleware("http")
async def extract_tracing_headers_middleware(request: Request, call_next: Any) -> Any:
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    response = await call_next(request)
    return response

# 3. Google Antigravity SDK ライフサイクルフックを用いた観測エンジン (L8実装)
class L8AgentObservabilityEngine:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id

    @hooks.on_compaction
    async def handle_compaction(self, data: Any) -> None:
        logger.info(
            "context_compaction_event",
            static_id="EVT_L6_COMPACTION",
            compaction_ratio=getattr(data, "ratio", 0.5),
            active_memory_slots=getattr(data, "slots", 10),
        )

    @hooks.on_tool_error
    async def handle_tool_error(self, error: Exception) -> None:
        ast_node_id = getattr(error, "ast_node_id", "AST_NODE_UNKNOWN")
        logger.error(
            "tool_execution_failed",
            static_id="EVT_L9_TOOL_ERROR",
            error_type=type(error).__name__,
            ast_node_id=ast_node_id,
            msg_brief=str(error)[:100]
        )
        return None

    @hooks.post_tool_call
    async def handle_post_tool_call(self, result: types.ToolCallResult) -> None:
        prev_state: Dict[str, Any] = result.metadata.get("previous_state", {})
        curr_state: Dict[str, Any] = result.metadata.get("current_state", {})
        
        delta_state = {k: curr_state[k] for k in curr_state if prev_state.get(k) != curr_state[k]}

        prev_phi = prev_state.get("potential_phi", 1.0)
        curr_phi = curr_state.get("potential_phi", 1.0)
        potential_diff = curr_phi - prev_phi

        logger.info(
            "state_transition",
            static_id="EVT_L2_L5_STATE_SHIFT",
            delta=delta_state,
            potential_diff=potential_diff,
            degraded_mode=curr_state.get("degraded_mode", False),
        )

# 4. エージェント実行のエンドポイント
@app.post("/run-agent")
async def run_agent(payload: Dict[str, Any]) -> Dict[str, Any]:
    obs_engine = L8AgentObservabilityEngine(agent_id="l8_critic_agent")
    
    config = LocalAgentConfig(
        api_key=payload.get("api_key"),
        hooks=[
            obs_engine.handle_compaction,
            obs_engine.handle_tool_error,
            obs_engine.handle_post_tool_call,
        ]
    )
    
    async with Agent(config) as agent:
        response = await agent.chat(payload.get("prompt", "Start diagnostics."))
        return {"response": response.text}
```
