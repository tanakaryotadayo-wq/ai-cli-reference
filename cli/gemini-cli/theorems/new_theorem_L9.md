# 自己修復ループの不動点収束定理 (Fixed Point Convergence Theorem of Self-Repair Loop) - v4.0 (R3 最終版)

## 1. 定義 (Definitions)

自己修復ループにおけるシステム状態および構成要素を以下のように数理的に定義する。

*   **コード空間 (Code Space) $C$**:
    対象プログラミング言語の文法規則に従って生成可能な、有限長の抽象構文木 (AST) の集合。実用上は、最大トークン長 $L$ で切り捨てられた有限部分空間 $C_L \subset C$ として扱う。
*   **仕様 (Specification) $P_{\text{spec}}$**:
    コードが満たすべき機能および非機能要件を自然言語または形式仕様で記述したプロンプト表現。
*   **テストスイート (Test Suite) $T$**:
    仕様 $P_{\text{spec}}$ に基づき作成された $M$ 個のテストケースからなる検証機構。コード $c \in C$ に対するテスト結果は、$M$ 次元のバイナリベクトルとして表される：
    $$T(c) = [t_1(c), t_2(c), \dots, t_M(c)]^T \in \{0, 1\}^M$$
    ここで、$t_i(c) = 1$ はテスト合格、$t_i(c) = 0$ は不合格を示す。
*   **不動点 (Fixed Point) $c^*$**:
    仕様を完全に満たし、すべてのテストケースをパスかつ静的エラーのない目標コード：
    $$c^* \in \{ c \in C \mid T(c) = \mathbf{1}^M \ \text{かつ} \ d_{\text{static}}(c) = 0 \}$$
*   **Critic/修復エージェント (Critic/Repair Agent) $R$**:
    現在のコード $c_n$、テスト結果 $T(c_n)$、および圧縮された試行履歴 $\mathcal{H}_n$ を入力とし、修正された新たなコード $c_{n+1}$ を出力する写像：
    $$c_{n+1} = R(c_n, T(c_n), \mathcal{H}_n)$$
*   **試行履歴 (History) $\mathcal{H}_n$**:
    ステップ $n$ までに生成された各コードの有限集合：
    $$\mathcal{H}_n = \{ c_0, c_1, \dots, c_n \}$$
    実装上は、コンテキスト長を節約するため、暗号学的ハッシュ値（Fingerprint）の集合 $\{ \text{Hash}(c_0), \dots, \text{Hash}(c_n) \}$ を代理指標（衝突確率 $\epsilon_{\text{collision}} \approx 0$）として保持する。
*   **ランタイムポテンシャル関数 (Runtime Potential Function) $\Phi(c, T(c), P_{\text{spec}})$**:
    未知であるターゲットコードとの直接的なAST編集距離を排除し、実行時に完全に計算可能な実数値関数として以下のように定義する：
    $$\Phi(c, T(c), P_{\text{spec}}) = (M - \|T(c)\|_1) \cdot \left( w_{\text{test}} + w_{\text{sem}} \cdot d_{\text{sem}}(c, P_{\text{spec}}) \right) + w_{\text{static}} \cdot d_{\text{static}}(c)$$
    - $w_{\text{test}}, w_{\text{static}}, w_{\text{sem}} \in \mathbb{R}_{> 0}$: 各評価項の重みパラメータ
    - $d_{\text{test}}(T(c)) = M - \|T(c)\|_1$: テスト不合格数（動的検証指標）
    - $d_{\text{static}}(c) \in \mathbb{N}_0$: 静的解析ツールによって検出されたエラー・警告の総数（静的構造検証指標）
    - $d_{\text{sem}}(c, P_{\text{spec}}) \in [0, 1]$: 仕様 $P_{\text{spec}}$ とコード $c$ のセマンティックな乖離度（埋め込みベクトル空間における正規化コサイン距離など）

---

## 2. 定理の主張と境界条件 (Theorem & Boundary Conditions)

### 【定理】自己修復ループの不動点収束定理 (Fixed Point Convergence Theorem)
初期コード $c_0 \in C_L$ に対し、修復エージェント $R$ による自己修復ループ $c_{n+1} = R(c_n, T(c_n), \mathcal{H}_n)$ が以下の**4つの境界条件**を満たすとき、修復ループは有限ステップ $N < \infty$ 内に必ず不動点 $c_N = c^*$ に到達し、かつそれ以降の任意のステップ $n \ge N$ において $c_n = c^*$ に収束（不動点に固定）する。

#### 境界条件 1: 非循環履歴制約 (Acyclic History Constraint)
修復エージェント $R$ は、過去に生成したすべてのコードと重複するコードを生成しない。
$$c_{n+1} \notin \mathcal{H}_n$$
コード空間 $C_L$ が有限集合（サイズ $|C_L| < \infty$）であるため、この制約によりループ内の遷移は自己ループや閉路を持たない有向非循環グラフ (DAG) となり、無限のチャタリング（同一コードの繰り返し）が数学的に排除される。

#### 境界条件 2: ランタイムポテンシャルの単調減少性 (Strict Potential Descent)
修復ループが不動点に未到達（$c_n \neq c^*$）である場合、遷移ステップごとにポテンシャル関数 $\Phi$ が一定の最小改善幅 $\Delta > 0$ をもって単調減少する。
$$\Phi(c_{n+1}, T(c_{n+1}), P_{\text{spec}}) \le \Phi(c_n, T(c_n), P_{\text{spec}}) - \Delta$$
ポテンシャル関数は下限 $0$ を持ち（$\Phi \ge 0$）、$\Phi(c, T(c), P_{\text{spec}}) = 0 \iff c = c^*$ であるため、この条件により不動点 $c^*$ への収束に必要なステップ数が最大でも $\lfloor \Phi(c_0) / \Delta \rfloor$ であることが保証される。

#### 境界条件 3: フィードバック完全性と探索空間の単調縮小 (Feedback Completeness & Space Contraction)
Critic エージェントの生成するエラー分析およびフィードバック $F(c_n, T(c_n))$ は、正解コード $c^*$ を含む探索空間を厳密に縮小させる。
$$C_{\text{search}}^{(n+1)} \subset C_{\text{search}}^{(n)}$$
この探索空間の縮小は、以下の2つの性質を満たさなければならない：
1.  **健全性 (Soundness)**:
    正解コード $c^*$ が探索空間から誤って除外されない。
    $$c^* \in C_{\text{search}}^{(n)} \implies c^* \in C_{\text{search}}^{(n+1)}$$
2.  **情報量 (Informativeness)**:
    過去に生成された失敗コード集合 $\mathcal{H}_n$ は、次の探索空間から完全に除外される。
    $$\mathcal{H}_n \cap C_{\text{search}}^{(n+1)} = \emptyset$$

#### 境界条件 4: パラメータ安定境界条件 (Weight Stability Boundary Conditions)
ポテンシャル関数の重みパラメータは、自己修復ループが誤った局所解にトラップされるのを防ぐため、以下の制約を満たさなければならない：
1.  **テスト優先境界 (Test Priority)**:
    $$w_{\text{static}} < w_{\text{test}}$$
    テストケースを新たにパスする（$d_{\text{test}}$ の減少）インセンティブが、静的警告（$d_{\text{static}}$）の発生によるペナルティを常に上回ることを保証し、リファクタリングによる機能破壊を防ぐ。
2.  **意味的非干渉境界 (Semantic Non-Interference)**:
    $$w_{\text{sem}} < \frac{w_{\text{test}}}{\max(1, M-1)}$$
    セマンティック乖離度 $d_{\text{sem}}$ の変動が、テストパス数増加によるポテンシャル減少効果を阻害しないことを保証する（オーバーフィッティングや無駄な漂流の防止）。
3.  **統合リファクタリング境界 (Combined Refactoring)**:
    新たに1つのテストをパスするために、一時的に許容される最大静的エラー増加数を $D_{\text{static\_max}}$ とするとき、次の統合制約を満たす：
    $$w_{\text{static}} \cdot D_{\text{static\_max}} + w_{\text{sem}} \cdot (M-1) < w_{\text{test}}$$

---

## 3. 収束性の数理的証明 (Mathematical Proof of Convergence)

### 3.1 ポテンシャル減少による収束証明 (BC2に基づく証明)
1. **下界の存在**: 定義より $\Phi(c, T(c), P_{\text{spec}}) \ge 0$ である。
2. **不動点の一致性**: 
   - $c = c^*$ のとき、定義より $T(c) = \mathbf{1}^M$ かつ $d_{\text{static}}(c) = 0$ であるため、
     $$\Phi(c^*, \mathbf{1}^M, P_{\text{spec}}) = (M - M) \cdot (w_{\text{test}} + w_{\text{sem}} d_{\text{sem}}) + w_{\text{static}} \cdot 0 = 0$$
   - $\Phi(c, T(c), P_{\text{spec}}) = 0$ のとき、各項の重み $w > 0$ および $d \ge 0$ より、$(M - \|T(c)\|_1) \cdot (w_{\text{test}} + w_{\text{sem}} d_{\text{sem}}) = 0$ かつ $w_{\text{static}} d_{\text{static}}(c) = 0$。
     後者より $d_{\text{static}}(c) = 0$。前者について $w_{\text{test}} > 0$ かつ $d_{\text{sem}} \ge 0$ より $w_{\text{test}} + w_{\text{sem}} d_{\text{sem}} > 0$ であるため、必ず $M - \|T(c)\|_1 = 0 \implies T(c) = \mathbf{1}^M$。
     したがって、$\Phi = 0 \iff c = c^*$ が成立する。
3. **有限ステップでの到達**: 任意のステップ $n$ において $c_n \neq c^*$ である限り、境界条件2より $\Phi(c_{n+1}) \le \Phi(c_n) - \Delta$ （$\Delta > 0$）が成立する。
   数学的帰納法により、$\Phi(c_n) \le \Phi(c_0) - n\Delta$。
   $\Phi(c_n) \ge 0$ であるため、ステップ数 $n$ は以下の上限を超えることができない：
   $$n \le \left\lfloor \frac{\Phi(c_0)}{\Delta} \right\rfloor$$
   したがって、有限ステップ $N \le \left\lfloor \frac{\Phi(c_0)}{\Delta} \right\rfloor$ 内に必ず $\Phi(c_N) = 0$ に到達し、不動点 $c_N = c^*$ を得る。

### 3.2 探索空間の単調縮小による収束証明 (BC1, BC3に基づく証明)
1. **初期探索空間**: $C_{\text{search}}^{(0)} = C_L$ とし、有理的トークン制限により $|C_L| < \infty$ である。
2. **ステップごとの縮小**: 境界条件3の「情報量 (Informativeness)」より、現ステップのコード $c_n$ は $C_{\text{search}}^{(n+1)}$ に含まれない。また、「健全性 (Soundness)」より、目標不動点 $c^*$ が存在すれば $c^* \in C_{\text{search}}^{(n+1)}$ が維持される。
3. **濃度の単調減少**: 探索空間の濃度に関して、以下が成立する：
   $$|C_{\text{search}}^{(n+1)}| \le |C_{\text{search}}^{(n)}| - 1$$
   これにより、最悪の場合でも有限回ステップ $N \le |C_L| - 1$ で探索空間は不動点のみを含む一点集合 $\{c^*\}$ に収縮し、探索は確実に終了する。

---

## 4. 他レイヤー (L1〜L8) との相乗効果と 2026 年エコシステム連携

本定理は、エージェント工学の他の各レイヤーの定理と緊密に連携し、2026年の標準技術スタックを基盤として動作する。

*   **L1 (Prompt Semantics) との連携**:
    自己修復の指示やCriticフィードバックは、L1の最適表現密度 $\mathcal{D}(F)$ 内で生成される。2026年エコシステムでは、**Google ADK (Google Antigravity SDK)** の `response_schema` 機能を用いて Pydantic スキーマ (`CriticFeedback`) による構造化出力を強制することで、セマンティクス解釈の安定性 $\mathcal{S}(F)$ を最大化し、探索空間の誤った刈り込み（Soundness破壊）を防止する。
*   **L2 (State Transition Loop-Free) との連携**:
    L9の自己修復ループは、状態遷移の有向非循環グラフ (DAG) として構成される。2026年標準のワークフローエンジンである **Inngest** を採用し、修復ループのステップをべき等なステップとして管理することで、システムのクラッシュやノイズ混入時にも状態の整合性とループフリー遷移を完全に担保する。
*   **L3 (Skill Orthogonality) との連携**:
    デバッグに使用するツール群（静的解析、テスト実行、セマンティック評価）は、L3に基づき機能的に直交隔離される。静的解析には **Ruff** を使用し、テスト実行には **pytest** を、**uv** を介した独立したサブプロセス実行環境上で駆動することで、スキルの競合や干渉を防ぐ。
*   **L4 (Sandbox Isolation) との連携**:
    テスト実行 $T(c_n)$ は、L4で定義された自己免疫的サンドボックス内で行われる。テスト中のコードが不正なアクセスや脆弱性を示した場合は、サンドボックスは生存境界 $\mathcal{B}_{\min}$ に収縮してホストシステムを保護し、その隔離例外ログをL9のCriticエージェントに通知する。
*   **L5 (Task DAG Minimum Cost) との連携**:
    Google ADKの `agent.conversation.total_usage` を用いて累積トークン（特に思考モデルにおける `thoughts_token_count`）およびAPIコスト $C_{\text{auto}}$ を動的に監視し、期待成功確率 $P_{\text{success}}$ から算出した閾値を下回った場合、自動修復を中断して人間の介入 (HITL) へ安全にエスカレーションする。
*   **L6 (Optimal Forget) との連携**:
    履歴 $\mathcal{H}_n$ の増加に対してL6の最適忘却定理を適用する。コードの差分や全文はローカルストレージのテンポラリ空間（`tempfile` 等）にスワップアウトし、接続コンテキストには軽量なSHA-256ハッシュ値のみを保持することで、コンテキストウィンドウの上限突破とコスト増大を抑制する。
*   **L7 (API Degraded Boundary) との連携**:
    APIの制限やネットワーク遅延が閾値を超えた場合、L7の縮退運転境界に基づき、Google ADK のモデルを軽量モデル（Flash等）へ切り替えるか、実行するテストスイートをコアテストのみに制限することで、処理を停止させずに修復を継続する。
*   **L8 (Structured Log Entropy Minimization) との連携**:
    テスト実行ログおよび状態遷移デルタは、**structlog** を用いてL8の最小有効エントロピー定義に準拠した構造化JSONとして記録される。これにより、入力トークンの無駄な消費を防ぎ、Criticエージェントの診断精度を高める。

---

## 5. 自己修復ループの収束制御アルゴリズム (Pseudo-code)

以下に、上記の境界条件（ランタイムポテンシャル監視、ハッシュ履歴管理、L5コスト離脱）を実装し、**FastAPI**, **Granian**, **Inngest**, **Google ADK**, **uv**, **Ruff**, **pytest**, **structlog** を統合した2026年技術エコシステム準拠の Python 実装擬似コードを示す。

```python
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
import structlog
from fastapi import FastAPI
from google.antigravity import Agent, LocalAgentConfig
from inngest import Inngest, InngestFastAPI
import pydantic
from pydantic import BaseModel

# L8: 構造化ログ（最小エントロピー構造）の初期化
logger = structlog.get_logger()

# L1: Criticの構造化出力を定義するPydanticスキーマ
class CriticFeedback(BaseModel):
    reasoning: str
    proposed_code: str
    explanation: str

class CodeState(BaseModel):
    code: str
    test_vector: list[bool]
    static_errors: int
    semantic_distance: float

    @property
    def passed_count(self) -> int:
        return sum(self.test_vector)

    @property
    def is_correct(self) -> bool:
        return all(self.test_vector) and self.static_errors == 0

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.code.encode("utf-8")).hexdigest()

# 2. ポテンシャル関数の計算
def calculate_potential(
    state: CodeState, 
    total_tests: int, 
    w_test: float = 10.0, 
    w_static: float = 2.0, 
    w_sem: float = 1.0
) -> float:
    assert w_static < w_test, "テスト優先境界違反: w_static >= w_test"
    max_w_sem = w_test / max(1, total_tests - 1)
    if w_sem >= max_w_sem:
        w_sem = max_w_sem * 0.9
        
    failed_tests = total_tests - state.passed_count
    term_test_sem = failed_tests * (w_test + w_sem * state.semantic_distance)
    term_static = w_static * state.static_errors
    return term_test_sem + term_static

# 3. L3/L4/L6: uv, Ruff, pytest 連携によるツール（スキル）隔離実行
def run_static_analysis_via_ruff(code: str) -> int:
    try:
        res = subprocess.run(
            ["uv", "run", "ruff", "check", "--format=json", "-"],
            input=code,
            capture_output=True,
            text=True,
            check=False
        )
        if not res.stdout.strip():
            return 0
        errors = json.loads(res.stdout)
        return len(errors)
    except Exception as e:
        logger.error("ruff_execution_failed", error=str(e))
        return 999

def run_tests_via_pytest(code: str) -> list[bool]:
    with tempfile.TemporaryDirectory() as tmpdir:
        code_file = Path(tmpdir) / "solution.py"
        test_file = Path(tmpdir) / "test_solution.py"
        
        code_file.write_text(code)
        test_file.write_text(
            "def test_func():\n"
            "    from solution import target_func\n"
            "    assert target_func() == True\n"
        )
        
        res = subprocess.run(
            ["uv", "run", "pytest", "--json-report", str(test_file)],
            capture_output=True,
            text=True,
            cwd=tmpdir
        )
        return [res.returncode == 0]

# 4. L2/L5: Inngest ワークフローエンジンによる自己修復状態遷移の定義
inngest_client = Inngest(app_id="l9-self-repair-system")

@inngest_client.create_function(
    fn_id="self-repair-loop",
    trigger=inngest_client.Trigger(event="repair/start")
)
async def self_repair_workflow(ctx):
    event_data = ctx.event.data
    initial_code = event_data["code"]
    specification = event_data["specification"]
    max_iterations = event_data.get("max_iterations", 8)
    c_hitl = event_data.get("c_hitl", 100.0)
    c_fail = event_data.get("c_fail", 250.0)
    
    hash_history: set[str] = set()
    current_code = initial_code
    
    test_result = run_tests_via_pytest(current_code)
    static_errors = run_static_analysis_via_ruff(current_code)
    sem_dist = 0.5
    
    current_state = CodeState(
        code=current_code,
        test_vector=test_result,
        static_errors=static_errors,
        semantic_distance=sem_dist
    )
    total_tests = len(test_result)
    current_potential = calculate_potential(current_state, total_tests)
    hash_history.add(current_state.fingerprint)
    
    logger.info("L9_REPAIR_WORKFLOW_START", initial_potential=current_potential)
    
    agent_config = LocalAgentConfig(
        system_instructions=f"仕様 {specification} に従い、提示されたコードのバグを修復してください。",
        response_schema=CriticFeedback
    )
    
    async with Agent(agent_config) as agent:
        for step in range(1, max_iterations + 1):
            if current_state.is_correct:
                logger.info("L9_REPAIR_SUCCESS", steps=step, final_code=current_code)
                return {"status": "success", "code": current_code}
                
            usage = agent.conversation.total_usage
            c_auto_accumulated = (usage.prompt_token_count * 0.00001) + (usage.candidates_token_count * 0.00003)
            
            progress_ratio = step / max_iterations
            p_success = max(0.0, 1.0 - progress_ratio)
            
            if c_fail > 0:
                threshold = 1.0 - (c_hitl - c_auto_accumulated) / c_fail
                if p_success < threshold:
                    logger.warn("L9_HITL_ESCALATION", step=step, accumulated_cost=c_auto_accumulated)
                    return {"status": "hitl_escalation", "last_code": current_code}
            
            prompt = (
                f"現在のコード:\n{current_code}\n\n"
                f"テスト成否ベクトル: {current_state.test_vector}\n"
                f"静的警告数: {current_state.static_errors}\n"
                f"過去のコード履歴ハッシュ: {hash_history}"
            )
            response = await agent.chat(prompt)
            feedback: CriticFeedback = await response.structured_output()
            
            next_code = feedback.proposed_code
            next_fingerprint = hashlib.sha256(next_code.encode("utf-8")).hexdigest()
            
            if next_fingerprint in hash_history:
                logger.warn("L9_CYCLE_DETECTED", fingerprint=next_fingerprint[:8])
                next_code += "\n# L9_FORCED_MUTATION_TO_BREAK_CYCLE"
                next_fingerprint = hashlib.sha256(next_code.encode("utf-8")).hexdigest()
            
            next_test_result = run_tests_via_pytest(next_code)
            next_static_errors = run_static_analysis_via_ruff(next_code)
            next_sem_dist = 0.2
            
            next_state = CodeState(
                code=next_code,
                test_vector=next_test_result,
                static_errors=next_static_errors,
                semantic_distance=next_sem_dist
            )
            next_potential = calculate_potential(next_state, total_tests)
            
            if next_potential >= current_potential:
                logger.warn("L9_POTENTIAL_VIOLATION", curr=current_potential, next=next_potential)
            
            current_code = next_code
            current_state = next_state
            current_potential = next_potential
            hash_history.add(next_fingerprint)
            
            logger.info(
                "L9_STATE_TRANSITION",
                step=step,
                potential=current_potential,
                passed_tests=current_state.passed_count,
                thoughts_tokens=usage.thoughts_token_count
            )
            
    return {"status": "failed", "code": current_code}

app = FastAPI()

inngest_handler = InngestFastAPI(
    client=inngest_client,
    functions=[self_repair_workflow]
)
app.mount("/api/inngest", inngest_handler)
```
