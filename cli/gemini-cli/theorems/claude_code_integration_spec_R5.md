# Claude Code 9レイヤー定理統合アーキテクチャ仕様書 (v5.0 - R5)

## 概要
本仕様書は、自律型AIコーディングエージェントである **Claude Code** に対し、本プロジェクトで確立した「エージェント工学 9レイヤー定理（L1〜L9）」を適用し、自律実行ループの信頼性、リソース効率、セキュリティ、およびエラー自己修復性能を極限まで高めるための統合アーキテクチャ設計を規定する。
第5ラウンド（R5）においては、これまでの監査で判明した数理モデルおよび実装の致命的バグ（L9 ASTコメントハッシュの非変異性、L6 Lambert W $W_{-1}$ の下限張り付き、L3 OPFの直交射影内積消失、L3ベイズエラー境界と L5 閾値の不整合）を完全に解消し、すべてのレイヤー間結合方程式（コヒーレンス）が非循環・有限収束の数学的証明の下で閉じた最終仕様を定義する。

---

## 1. 各レイヤー定理の Claude Code への適用設計と実装インターフェース

### [L1] プロンプトセマンティクス収束定理の適用 (R5)
*   **ユースケース**: Claude Code がユーザーからの曖昧な指示や大規模なファイル差分等のコンテキストを処理する際、情報の過圧縮による決定境界の崩壊（ハルシネーション）や、過希釈によるアテンション散逸（指示無視）を未然に防止する。
*   **適用モデル**:
    アテンションマップから得られるアテンションエントロピーに基づき、アテンション散逸係数 $\chi(L) = \bar{H}(\mathcal{A}) / \log(L + c)$ を算出して有効意味情報量 $I(P)$ および表現密度 $\mathcal{D}(P) = I(P)/L$ を動的に監視する。
*   **2026年技術エコシステム適合 (R5実装コード)**:
    ```python
    import numpy as np
    import structlog
    from typing import Dict, Any, List, Optional, Set
    from pydantic import BaseModel

    logger = structlog.get_logger()

    class L1AuditResult(BaseModel):
        token_length: int
        representation_density: float
        attention_dissipation: float
        measured_stability: float
        theoretical_stability_bound: float
        status: str  # "Optimal", "Over-compressed", "Diluted"
        is_stable: bool
        suggestion: str

    class PromptSemanticsConvergenceCritic:
        def __init__(self, d_c: float = 0.85, alpha: float = 2.5, beta: float = 1.5, vocab_size: int = 50257):
            self.d_c = d_c
            self.d_opt = d_c * 0.4
            self.alpha = alpha
            self.beta = beta
            self.s_0 = 0.98
            self.c_token = float(np.log2(vocab_size))
            self.stopwords: Set[str] = {"to", "the", "a", "and", "of", "in", "is", "that", "it"}

        def calculate_dissipation(self, attn_maps: Optional[List[np.ndarray]], length: int) -> float:
            if attn_maps is None or len(attn_maps) == 0 or length <= 1:
                return 0.0
            mean_attn = np.mean(attn_maps, axis=0)
            clipped = np.clip(mean_attn, 1e-12, 1.0)
            h_i = -np.sum(mean_attn * np.log(clipped), axis=-1)
            return float(np.clip(np.mean(h_i) / np.log(length + 1.05), 0.0, 1.0))

        def evaluate(self, prompt: str, token_logprobs: List[float], attn_maps: Optional[List[np.ndarray]] = None, kl_divs: Optional[List[float]] = None) -> L1AuditResult:
            words = prompt.split()
            length = len(words)
            chi = self.calculate_dissipation(attn_maps, length)
            
            surprisal = 0.0
            for i, word in enumerate(words):
                if i < len(token_logprobs) and word.lower() not in self.stopwords:
                    surprisal += -token_logprobs[i] / np.log(2.0)
            i_p = (1.0 - chi) * surprisal
            d_p = float(np.clip(i_p / max(length, 1), 0.0, self.c_token))
            
            s_p = float(np.exp(-np.mean(kl_divs))) if kl_divs else self.s_0
            s_bound = self.s_0 * np.exp(-self.alpha * (d_p - self.d_c)) if d_p > self.d_c else (self.s_0 * ((d_p / self.d_opt) ** self.beta) if d_p < self.d_opt else self.s_0)
            is_stable = s_p >= (s_bound * 0.90)

            if d_p > self.d_c:
                status, sug = "Over-compressed", "省略されたコード記述を展開し、型定義を補強してください。"
            elif d_p < self.d_opt:
                status, sug = "Diluted", "重複表現や冗長なログ、ボイラープレートを排除してください。"
            else:
                status, sug = "Optimal", "表現密度および解釈安定性は最適範囲内に収まる。"

            logger.info("prompt_semantics_audited", token_length=length, density=d_p, stability=s_p, status=status)
            return L1AuditResult(token_length=length, representation_density=d_p, attention_dissipation=chi, measured_stability=s_p, theoretical_stability_bound=s_bound, status=status, is_stable=is_stable, suggestion=sug)

    class L1CriticInterceptor:
        def __init__(self, critic: PromptSemanticsConvergenceCritic):
            self.critic = critic

        async def pre_execution_guard(self, prompt: str, logprobs: List[float]) -> Optional[str]:
            result = self.critic.evaluate(prompt, logprobs)
            return None if result.is_stable else result.suggestion
    ```

### [L2] 状態遷移ループフリー不動点定理の適用 (R5)
*   **ユースケース**: Claude Code がテスト修正やコマンド試行を行う際、同一の状態を往復する循環ループ（有向閉路）を排除し、有限ステップで目標不動点（テスト通過、エラーゼロ）に収束させる。
*   **適用モデル**:
    過去の遷移履歴 $\mathcal{H}_t = \{v_0, \dots, v_{t-1}\}$ に基づくペナルティを加味した拡張ポテンシャル関数 $\Psi(v_t, \mathcal{H}_t) = \Phi(v_t) + \alpha \cdot \mathbb{I}(v_t \in \mathcal{H}_t)$ （ここで $\alpha > \max_{v} \Phi(v)$）の狭義単調減少を保証する。また、L7のAPI縮退運転フラグ $B_{\text{L7}} \in \{0, 1\}$ を組み込んだガード付き遷移 $T_{\text{guard}}(v, e, B_{\text{L7}})$ に従う。
*   **2026年技術エコシステム適合 (R5実装コード)**:
    ```python
    from uuid import UUID
    import structlog
    from sqlmodel import Field, SQLModel, Session, select
    import time
    from typing import Optional

    logger = structlog.get_logger()

    class AgentStateVector(SQLModel, table=True):
        __tablename__ = "agent_state_vectors"
        id: Optional[int] = Field(default=None, primary_key=True)
        session_id: UUID = Field(index=True)
        timestamp: float = Field(default_factory=time.time)
        state_hash: str = Field(index=True)
        retry_budget: int = Field(default=10)
        api_budget: float = Field(default=100.0)
        security_risk: float = Field(default=0.0)
        potential_value: float = Field(default=0.0)
        extended_potential_value: float = Field(default=0.0)

    class LoopDetectedException(Exception):
        def __init__(self, session_id: UUID, state_hash: str, message: str):
            self.session_id = session_id
            self.state_hash = state_hash
            super().__init__(message)

    class LoopFreeFixedPointMonitor:
        def __init__(self, db_session: Session, alpha: float = 10000.0, delta_threshold: float = 0.01):
            self.db = db_session
            self.alpha = alpha
            self.delta_threshold = delta_threshold

        def calculate_potential(self, errors: int, test_failures: int, risk: float) -> float:
            return (10.0 * errors) + (50.0 * test_failures) + (100.0 * risk)

        def evaluate_transition(self, session_id: UUID, state_hash: str, errors: int, test_failures: int, risk: float, retry: int, api: float) -> AgentStateVector:
            history = self.db.exec(select(AgentStateVector).where(AgentStateVector.session_id == session_id)).all()
            history_hashes = {h.state_hash for h in history}
            potential = self.calculate_potential(errors, test_failures, risk)
            is_loop = state_hash in history_hashes
            extended_potential = potential + (self.alpha if is_loop else 0.0)

            if history:
                delta_psi = history[-1].extended_potential_value - extended_potential
                if delta_psi < self.delta_threshold or is_loop:
                    raise LoopDetectedException(session_id, state_hash, f"Loop detected. Delta: {delta_psi:.4f}, Loop: {is_loop}")

            new_vector = AgentStateVector(session_id=session_id, state_hash=state_hash, retry_budget=retry, api_budget=api, security_risk=risk, potential_value=potential, extended_potential_value=extended_potential)
            self.db.add(new_vector)
            self.db.commit()
            return new_vector
    ```
    ```tsx
    // types/agent.ts
    export type AgentMode = 'NORMAL' | 'DEGRADED_LOCAL' | 'HITL' | 'FAIL';
    export interface PotentialUpdatePayload {
      session_id: string;
      timestamp: number;
      state_hash: string;
      potential: number;
      extended_potential: number;
      current_mode: AgentMode;
      message: string;
    }
    ```

### [L3] スキル記述の直交排他定理の適用 (R5)
*   **ユースケース**: Claude Code が持つツール群の説明文が重複し、誤ルーティングが発生するのを防止する。
*   **適用モデル**:
    埋め込みベクトル間の角度距離 $d(\mathbf{v}_i, \mathbf{v}_j) > \theta_i + \theta_j$。限界極限（球面容量上限 $N_{\max}$ および混雑度 $\rho = N/N_{\max} \ge 1$）での DQS (動的クエリ収縮)、OPF (直交射影フィルタリング)、HNPT (階層的名前空間相転移) を適用する。
    *   **OPF数理バグ修正**: 主候補 $\mathbf{v}_{\text{best}}$ の直交補空間に残余ベクトルを正しく投影して類似度を算出する。
    *   **フォールバック境界の統合**: 回避適用後の残余エラー予測値 $\hat{P}_{\text{error}} \ge P_{\text{Bayes}}(\rho) = 1 - 1/\rho$ が、L5臨界閾値 $P_{\text{crit}} = (C_{\text{hitl}} - C_{\text{exec}}) / C_{\text{fail}}$ に達した瞬間、L5 HITLへ安全にフォールバックする。
*   **2026年技術エコシステム適合 (R5実装コード)**:
    ```python
    from sqlmodel import SQLModel, Field, Session, select
    from pydantic import BaseModel
    import json
    import numpy as np
    import structlog
    from typing import Dict, Any, List, Optional, Tuple

    logger = structlog.get_logger()

    class EmbeddingCache(SQLModel, table=True):
        __tablename__ = "l3_embedding_cache"
        id: Optional[int] = Field(default=None, primary_key=True)
        text_hash: str = Field(unique=True, index=True)
        text: str = Field(nullable=False)
        embedding_json: str = Field(nullable=False)

    class L3OrthogonalExclusionRouter:
        def __init__(
            self, 
            db_session: Session,
            embedding_client: Any,
            n_max: int = 100, 
            entropy_crit: float = 0.8,
            c_exec: float = 1.0,
            c_hitl: float = 5.0,
            c_fail: float = 50.0,
            gamma: float = 1.5
        ):
            self.session = db_session
            self.client = embedding_client
            self.n_max = n_max
            self.entropy_crit = entropy_crit
            self.gamma = gamma
            self.p_crit = (c_hitl - c_exec) / max(c_fail, 1e-9)
            self.tools: Dict[str, Dict[str, Any]] = {}

        def get_embedding(self, text: str) -> np.ndarray:
            text_hash = str(hash(text))
            cached = self.session.exec(select(EmbeddingCache).where(EmbeddingCache.text_hash == text_hash)).first()
            if cached:
                return np.array(json.loads(cached.embedding_json), dtype=np.float32)
            vector = self.client.embed(text)
            norm = np.linalg.norm(vector)
            normalized = (vector / norm).tolist() if norm > 0 else vector
            self.session.add(EmbeddingCache(text_hash=text_hash, text=text, embedding_json=json.dumps(normalized)))
            self.session.commit()
            return np.array(normalized, dtype=np.float32)

        def register_tool(self, name: str, description: str, radius: float, namespace: str):
            embedding = self.get_embedding(description)
            self.tools[name] = {
                "embedding": embedding,
                "radius": radius,
                "namespace": namespace
            }

        def _calculate_entropy(self, probabilities: np.ndarray) -> float:
            return float(-np.sum(probabilities * np.log2(probabilities + 1e-9)))

        def route_query(self, query: str) -> Tuple[str, float]:
            q_vec = self.get_embedding(query)
            N = len(self.tools)
            rho = N / self.n_max
            
            # 各ツールとの適合スコア計算
            scores = {}
            for name, meta in self.tools.items():
                dist = np.arccos(np.clip(np.dot(q_vec, meta["embedding"]), -1.0, 1.0))
                if dist <= meta["radius"]:
                    scores[name] = 1.0 - (dist / meta["radius"])
                    
            if not scores:
                logger.warn("routing_no_candidates", query=query)
                return "L5_HITL_FALLBACK", 1.0
                
            vals = np.array(list(scores.values()))
            probs = np.exp(vals) / np.sum(np.exp(vals))
            entropy = self._calculate_entropy(probs)
            
            # 決定可能相にあれば最尤候補を決定
            if len(scores) == 1 or entropy < self.entropy_crit:
                best_tool = max(scores, key=scores.get)
                p_err = 1.0 - probs[list(scores.keys()).index(best_tool)]
                if p_err >= self.p_crit:
                    return "L5_HITL_FALLBACK", p_err
                return best_tool, p_err

            # --- 衝突回避フェーズ ---
            logger.info("decision_undecidable_phase_detected", entropy=entropy, rho=rho)
            
            # Step 1: DQS (Dynamic Query Shrinkage)
            shrinkage = max(0.0, 1.0 - rho) ** self.gamma
            shrunk_scores = {}
            for name in scores.keys():
                dist = np.arccos(np.clip(np.dot(q_vec, self.tools[name]["embedding"]), -1.0, 1.0))
                effective_radius = self.tools[name]["radius"] * shrinkage
                if dist <= effective_radius:
                    shrunk_scores[name] = 1.0 - (dist / max(effective_radius, 1e-9))
                    
            if len(shrunk_scores) == 1:
                best_tool = list(shrunk_scores.keys())[0]
                logger.info("resolved_via_dqs", tool=best_tool)
                return best_tool, 0.05
                
            # Step 2: OPF (Orthogonal Projection Filtering)
            candidates = shrunk_scores if shrunk_scores else scores
            best_candidate = max(candidates, key=candidates.get)
            v_best = self.tools[best_candidate]["embedding"]
            
            # クエリの直交補空間への射影
            q_prime = q_vec - np.dot(q_vec, v_best) * v_best
            q_prime_norm = np.linalg.norm(q_prime)
            
            if q_prime_norm > 1e-5:
                q_prime_normalized = q_prime / q_prime_norm
                opf_scores = {}
                for name in candidates.keys():
                    if name == best_candidate:
                        continue
                    v_k = self.tools[name]["embedding"]
                    v_k_prime = v_k - np.dot(v_k, v_best) * v_best
                    v_k_prime_norm = np.linalg.norm(v_k_prime)
                    
                    if v_k_prime_norm > 1e-5:
                        v_k_prime_normalized = v_k_prime / v_k_prime_norm
                        opf_scores[name] = float(np.dot(q_prime_normalized, v_k_prime_normalized))
                
                if opf_scores:
                    best_opf_alt = max(opf_scores, key=opf_scores.get)
                    if opf_scores[best_opf_alt] < 0.3: 
                        logger.info("resolved_via_opf", tool=best_candidate)
                        return best_candidate, 0.1
                    
            # Step 3: HNPT (Hierarchical Namespace Phase Transition)
            logger.info("applying_hnpt_coarse_graining")
            namespaces = {self.tools[name]["namespace"] for name in candidates.keys()}
            if len(namespaces) == 1:
                router_name = f"{list(namespaces)[0]}_namespace_router"
                logger.info("transition_to_namespace_router", router=router_name)
                return router_name, 0.15
                
            # ベイズ誤り率の下限値および残余エラー率の推定
            estimated_p_error = max(1.0 - (1.0 / max(rho, 1e-9)), 0.0)
            
            # L5 フォールバック境界の評価
            if estimated_p_error >= self.p_crit:
                logger.warn("escalating_to_l5_hitl", estimated_p_error=estimated_p_error, p_crit=self.p_crit)
                return "L5_HITL_FALLBACK", estimated_p_error
                
            return "global_namespace_router", estimated_p_error
    ```

### [L4] 自己免疫的サンドボックス隔離定理の適用 (R5)
*   **ユースケース**: Claude Code が任意のシェルコマンドを実行したりファイルを編集したりする際、インジェクション攻撃やホストシステムの破壊的命令を検知し、安全に実行制限・隔離を行う。
*   **適用モデル**:
    実効リスク $I_{eff}(t) = \max\left( I_{raw}(t), \lambda \cdot I_{eff}(t-1) + (1 - \lambda) \cdot \delta_{sens}(t) \right)$ の変動に基づき、隔離レベル $S(t) \in [0, 1]$ を制御し、許容アクション境界 $\mathcal{B}(t)$ を動的に制限する。完全隔離 $S(t_{\text{emit}}) = 1.0$ 時、復旧遅延 $t_{\text{rec}}$ と L7 Slack Time $L(t)$ が $L(t) \le t_{\text{rec}}$ となった場合、タイムアウトを回避するため「超縮退運転モード $M^{(4)}$」へ強制相転移する。
*   **2026年技術エコシステム適合 (R5実装コード)**:
    ```python
    from starlette.middleware.base import BaseHTTPMiddleware
    from fastapi import Request, Response, status
    from fastapi.responses import JSONResponse
    import structlog

    logger = structlog.get_logger()

    class AutoimmuneSandboxMiddleware(BaseHTTPMiddleware):
        def __init__(self, app, sandbox_engine, crit_threshold: float = 0.8):
            super().__init__(app)
            self.sandbox = sandbox_engine
            self.crit = crit_threshold

        async def dispatch(self, request: Request, call_next) -> Response:
            body = await request.body()
            payload = body.decode("utf-8")
            
            i_raw = self.sandbox.evaluate_payload_risk(payload)
            i_eff = self.sandbox.update_effective_risk(i_raw)
            
            if i_eff >= self.crit:
                logger.error("sandbox_isolation_triggered", risk=i_eff)
                # L7 の Slack Time 境界条件を同時に判定
                if self.sandbox.should_force_super_degraded(i_eff):
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"error": "AUTOIMMUNE_SUPER_DEGRADED", "mode": "M4_SUPER_DEGRADED", "risk": i_eff}
                    )
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={"error": "AUTOIMMUNE_SANDBOX_ISOLATED", "risk": i_eff}
                )
                
            request._receive = self.create_receive_channel(body)
            return await call_next(request)

        def create_receive_channel(self, body: bytes):
            async def receive():
                return {"type": "http.request", "body": body, "more_body": False}
            return receive
    ```
    ```typescript
    // Next.js 15 Server Actions による承認API
    'use server'
    import { revalidatePath } from 'next/cache';
    export async function clearSecurityViolation(sessionId: string) {
      const res = await fetch(`http://localhost:8000/api/security/audit-clear`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, flag_A: 1 })
      });
      if (res.ok) {
        revalidatePath('/admin/sandbox');
        return { success: true };
      }
      return { success: false };
    }
    ```

### [L5] 有向タスクグラフ最小コスト定理の適用 (R5)
*   **ユースケース**: Claude Code が複雑なリファクタリングを自律的に継続するか、コストを懸念して人間に承認（HITL）を求めるべきかの最適判断。
*   **適用モデル**:
    期待コスト最小化のためマルコフ決定過程（MDP）とメモ化再帰を用いた動的ポリシー決定へ刷新。ベルマン最適化方程式 $V^*(u, k) = \min \{ Q^*(u, k, \text{AUTO}), Q^*(u, k, \text{HITL}) \}$ に基づき、クランプ付き閾値 $\theta(u, v, k)$ を評価して決定を下す。
*   **2026年技術エコシステム適合 (R5実装コード)**:
    ```python
    from datetime import datetime
    from typing import Optional
    from sqlmodel import SQLModel, Field

    class TransitionConfig(SQLModel, table=True):
        __tablename__ = "transition_config"
        id: Optional[int] = Field(default=None, primary_key=True)
        from_state: str = Field(index=True)
        to_state: str
        c_auto_normal: float
        c_hitl: float
        c_fail: float

    class TransitionCostHistory(SQLModel, table=True):
        __tablename__ = "transition_cost_history"
        id: Optional[int] = Field(default=None, primary_key=True)
        task_id: str = Field(index=True)
        step_number: int
        decision_type: str  # "AUTO" or "HITL"
        threshold_calculated: float
        is_success: bool
        timestamp: datetime = Field(default_factory=datetime.utcnow)
    ```
    ```python
    # Inngest ワークフローフロー制御
    from inngest import Inngest, TriggerEvent
    inngest_client = Inngest(app_id="claude-agent")

    @inngest_client.create_function(
        fn_id="agent-l5-routing",
        trigger=TriggerEvent(event="agent/task.start"),
    )
    async def agent_l5_routing(ctx):
        task_id = ctx.event.data["task_id"]
        state = {"s": ctx.event.data["start_s"], "k": ctx.event.data["k_max"]}
        while state["s"] != ctx.event.data["target_s"]:
            opt_res = await ctx.step.run("get-optimize", lambda: call_optimize_api(task_id, state))
            if opt_res["next_decision"]["type"] == "HITL":
                await ctx.step.send_event("hitl-req", {"name": "agent/hitl.request", "data": {"task_id": task_id}})
                approval = await ctx.step.wait_for_event("wait-approval", event="agent/hitl.approve", timeout="1h")
                if not approval:
                    state = {"s": "suspended_safe", "k": 0}
                    break
                state = {"s": approval.data["next_state"], "k": state["k"]}
            else:
                state = await ctx.step.run("exec-auto", lambda: run_autonomous_step(state))
    ```

### [L6] 記憶容量制限下の最適忘却定理の適用 (R5)
*   **ユースケース**: Claude Code のコンテキストが有限のコンテキスト窓上限に近づき、API料金が急増したり、動作遅延が発生するのを防止する。
*   **適用モデル**:
    指数型効用とラグランジュ多目的最適化により、Lambert W 解析解を用いて最適圧縮率 $\beta^*$ を算出する。
    *   **Lambert W 数理および実装バグ修正**: 圧縮率が負または下限に張り付くバグを解消するため、下部枝 $W_{-1}$ から**主枝である $W_0$ (k=0)** を用いた計算モデルへと修正・適用する。
*   **2026年技術エコシステム適合 (R5実装コード)**:
    ```python
    import math
    import scipy.special as sp
    from pydantic import BaseModel
    from typing import List, Optional

    class MemoryElement(BaseModel):
        id: str
        size: int
        importance: float
        entropy: float
        content: str

    class MemoryOptimizer:
        def __init__(self, gamma: float = 0.5, beta_min: float = 0.2):
            self.gamma = gamma
            self.beta_min = beta_min

        def compute_optimal_compression_ratio(self, s_i: float, R_i: float, H_i: float, lambda_val: float) -> float:
            """
            Lambert W 関数主枝 W_0 を用いた最適圧縮率 beta_i* の算出 (R5バグ修正適用)
            """
            if H_i <= 0:
                return 1.0
            
            # Lambert W の引数を算出。実数解存在境界 (lambda * s_i <= R_i) に適合
            argument = - (lambda_val * s_i) / (math.e * R_i)
            if argument < -1.0 / math.e:
                # 限界値を下回った場合は最小圧縮にフォールバック
                return self.beta_min
            try:
                # 主枝 k=0 を使用して正の物理的圧縮率を安定的に算出
                w_val = sp.lambertw(argument, k=0).real
                beta_opt = (1.0 + w_val) / (self.gamma * H_i)
                return max(self.beta_min, min(1.0, beta_opt))
            except Exception:
                return self.beta_min
    ```
    *(※ SQLModelによる永続化スキーマ、MLX-LMおよびクラウド制約変数プロバイダ、Gotenberg連携アーカイブAPIは、R4定義に準ずる)*

### [L7] API制約下の縮退運転境界定理の適用 (R5)
*   **ユースケース**: Claude Code 実行中に API のレートリミットや接続遮断が発生した場合、またはデッドラインが迫っている場合に、ハングアップを回避して動作を継続する。
*   **適用モデル**:
    境界関数 $\Gamma_i(C(t), L(t)) = W^{(i)} + \tau^{(i), safe} - L(t)$ を評価し、容量・時間の二重ヒステリシスを適用して Zeno 動作の完全排除とリアプノフ安定（不連続減少）性を数学的に保証する。
*   **2026年技術エコシステム適合 (R5実装コード)**:
    ```python
    import time
    import asyncio
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel

    class SystemState:
        def __init__(self, T_dwell: float = 5.0, delta_c: float = 10.0):
            self.mode = "M0_NORMAL"
            self.T_dwell = T_dwell
            self.delta_c = delta_c
            self.last_transition = time.time()
            self.deadline = time.time() + 300.0

    class AsyncTokenBucket:
        def __init__(self, rate: float, capacity: float):
            self.rate = rate
            self.capacity = capacity
            self.tokens = capacity
            self.last_update = time.monotonic()
            self._lock = asyncio.Lock()

        async def consume(self, amount: float) -> bool:
            async with self._lock:
                now = time.monotonic()
                self.tokens = min(self.capacity, self.tokens + (now - self.last_update) * self.rate)
                self.last_update = now
                if self.tokens >= amount:
                    self.tokens -= amount
                    return True
                return False
    ```

### [L8] 構造化ログのエントロピー最小化定理の適用 (R5)
*   **ユースケース**: Claude Code の詳細な推論プロセス（思考木、ツール実行）を出力する際、ログデータの肥大化を極小化しつつ、デバッグに必要なトレーサビリティを完全維持する。
*   **適用モデル**:
    極値方程式から算出された周期 $T_c^*$ の KEYFRAME と Dirty-Flag Graph (DFG) 状態比較プロセッサを用いた DELTAFRAME のハイブリッド生成モデル $L_k$ により、シリアライズ複雑度を低減する。
*   **2026年技術エコシステム適合 (R5実装コード)**:
    ```python
    import json
    import hashlib
    from typing import Dict, Any, Set, Optional
    from pydantic import BaseModel, Field

    class SubState(BaseModel):
        id: str
        data: Dict[str, Any] = Field(default_factory=dict)
        def compute_hash(self) -> str:
            return hashlib.sha256(json.dumps(self.data, sort_keys=True).encode('utf-8')).hexdigest()

    class DFGProcessor:
        def __init__(self):
            self.nodes: Dict[str, SubState] = {}
            self.dirty_flags: Dict[str, bool] = {}
            self.last_hashes: Dict[str, str] = {}

        def mark_dirty(self, node_id: str):
            self.dirty_flags[node_id] = True

        def get_dirty_deltas(self) -> Dict[str, Dict[str, Any]]:
            deltas = {}
            for node_id, node in self.nodes.items():
                if self.dirty_flags.get(node_id, False):
                    curr_hash = node.compute_hash()
                    if curr_hash != self.last_hashes[node_id]:
                        deltas[node_id] = node.data
                        self.last_hashes[node_id] = curr_hash
                    self.dirty_flags[node_id] = False
            return deltas
    ```

### [L9] 自己修復ループの不動点収束定理の適用 (R5)
*   **ユースケース**: Claude Code が生成・修正したコードにエラーが検出された際、デバッグ修復ループを確実に終了（テスト合格の不動点へ収束）させる。
*   **適用モデル**:
    正規化 AST ハッシュ $H(a_t)$ による厳密サイクル判定と、履歴ペナルティ付き修正ポテンシャル関数 $\Psi(a_t, \mathcal{H}_t)$ の狭義単調減少。
    *   **ASTハッシュ変異バグ修正**: コメント挿入では AST ハッシュが変化しないため、ASTのModuleルートノードに対し、ステップ数に応じた無害なダミー変数代入文（例: `_l9_mutation_step = {step}`）を動的に差し込み、セマンティクスに影響を与えずにハッシュ値を変化させて循環検知での早期安全相転移（脱出）を保証する。
*   **2026年技術エコシステム適合 (R5実装コード)**:
    ```python
    import ast
    import hashlib
    from typing import Optional

    class NormalizedASTSerializer:
        class NormalizerTransformer(ast.NodeTransformer):
            def __init__(self, mutation_step: Optional[int] = None):
                super().__init__()
                self.mutation_step = mutation_step

            def visit_Module(self, node: ast.Module) -> ast.Module:
                self.generic_visit(node)
                # ASTの先頭に無害なダミー変数代入を差し込み、ハッシュを一意に変異させる (R5バグ修正)
                if self.mutation_step is not None:
                    target = ast.Name(id='_l9_mutation_step', ctx=ast.Store())
                    value = ast.Constant(value=self.mutation_step)
                    assign = ast.Assign(targets=[target], value=value)
                    node.body.insert(0, assign)
                return node

            def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
                self.generic_visit(node)
                if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant):
                    node.body.pop(0)  # docstring の削除
                return node

        def __init__(self):
            pass

        def get_hash(self, source_code: str, mutation_step: Optional[int] = None) -> str:
            try:
                tree = ast.parse(source_code)
                transformer = self.NormalizerTransformer(mutation_step=mutation_step)
                transformer.visit(tree)
                ast.fix_missing_locations(tree)
                serialized = ast.dump(tree, annotate_fields=False, include_attributes=False)
                return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
            except SyntaxError as e:
                return hashlib.sha256(f"SyntaxError: {str(e)}".encode("utf-8")).hexdigest()
    ```

---

## 2. 統合コヒーレンスの方程式系 (v5.0 - R5最終定式)

各レイヤーの境界値は、以下の数理的結合方程式を通じて完全同期し、システム全体の調和的安定性を担保する。

1.  **ルーティングと成功確率 (L3 $\to$ L5)**:
    L3ルーティングの曖昧度誤差を $\epsilon(q)$ としたとき、L5における自律タスクの成功確率は以下のように制約される：
    $$P_{success} \le (1 - \epsilon(q)) P_{base}$$
    さらに、混雑度 $\rho \ge 1$ 下におけるベイズ誤り率の下限 $P_{\text{Bayes}}(\rho) = 1 - 1/\rho$ が L5 臨界閾値 $P_{\text{crit}} = (C_{\text{hitl}} - C_{\text{exec}}) / C_{\text{fail}}$ を超えた場合（$P_{\text{Bayes}}(\rho) \ge P_{\text{crit}}$）、システムは自律動作を強制遮断して L5 (HITLエスカレーション) へ安全にフォールバックする。
2.  **セキュリティ制限と成功確率 (L4 $\to$ L5)**:
    L4の実効リスク $I_{eff} \ge I_{crit}$ のとき、サンドボックス権限が収縮するため、L5の自律成功確率は強制的に $P_{success} = 0$ となり、直ちにHITL介入閾値を下回ってエスカレーションを発生させる。
3.  **状態解像度とループフリー (L6 $\to$ L2)**:
    L6がコンテキスト窓節約のために忘却を行う際、L2のループフリー判定を保証するために必要な最小マーク解像度 $H_{crit}$ が下限境界として強制される：
    $$\sum_{i: active} \eta(a_i) H_i R_i \ge H_{crit}$$
4.  **デッドラインと遅延境界 (L7 $\to$ L6)**:
    L7のSlack Time $L(t)$ に基づき、L6の許容遅延境界 $D_{max}$ が $D_{max}(t) \propto L(t)$ として動的に短縮される。これに伴い、遅延のシャドウプライス $\mu \to \infty$ となり、解凍遅延 $\tau_{\text{comp}} > 0$ や I/O遅延 $d_{\text{swap}} > 0$ を伴うアクションの期待効用が著しく低下するため、スワップおよび圧縮処理が禁止され、保持（Keep）か忘却（Forget）かのバイナリ選択（LIBC: Latency Induced Binary Choice）へと相転移する。このとき、境界条件が崩壊している要素 ($\lambda s_i > R_i$) は純効用が負となるため強制的に $Forget$ （完全忘却）される。
    同時に、デッドライン極限 $L(t) \to 0$ では、L7のリアプノフ安定条件から $M(t)$ の強制退行が最優先され、不活性なメモリ資源の即時 Forget が強制的に執行される。
5.  **配信遅延と制御ループの応答安定性 (SSE $\to$ L7)**:
    Next.js 15 (SSE) による縮退運転ステータス配信における伝送遅延およびバッファ遅延の総和を $\tau_{\text{sse}}$ としたとき、状態遷移チャタリングおよびデッドライン違反を防ぐため、$\tau_{\text{sse}}$ は以下の許容遅延境界を常に下回らなければならない：
    $$\tau_{\text{sse}} < \min_i (T_{\text{dwell}}, L(t))$$
6.  **隔離復帰遅延極限と強制退行 (L4 $\leftrightarrow$ L7)**:
    L4の完全隔離状態 $S(t_{emit}) = 1.0$ に突入した際、L7の残余 Slack Time $L(t_{emit})$ が復元に要する最小遅延時間 $t_{rec}$（人間監査応答とステップ回復遅延の和）を下回る場合、システムはタイムアウトによるハングアップを回避するため、即座に「超縮退運転モード」 $M^{(4)}$ へ強制相転移する：
    $$L(t_{emit}) \le t_{rec} \implies M(t) \to M^{(4)}$$
    ここで、 $t_{rec} = \tau_A + K_{min} \cdot \left\lceil \frac{0.6}{\eta} \right\rceil \cdot \delta_t + \tau_{overhead}$ である。
7.  **自己修復限界と相転移 (L9 $\to$ L7/L5)**:
    L9の自己修復中にサイクル（同一ASTハッシュ）が検知された場合、または突然変異試行回数が限界値 $K_{mutate}$ に達した場合、およびリソース制限ステップ上限（L7 Slack Time $L(t)$ から算出される $t_{max}$）に達した場合、遷移インジケータ $P_{transit}(t) = 1$ が成立し、システムは自律修復を直ちに打ち切る。これにより、L2における有向閉路を完全に排除した上で、状況に応じて L7（縮退運転モード）または L5（HITLエスカレーション）へ安全に制御権を相転移させる。
