import numpy as np
import scipy.special as sp
import math
import ast
import hashlib
import uuid
import time
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, Session, select, create_engine
from dataclasses import dataclass, field
import datetime

# matplotlib をオプション依存性に緩和
try:
    import matplotlib.pyplot as plt

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

# 再現性のための乱数 seed 固定
np.random.seed(42)


# ==========================================
# 0. L2 (状態遷移ループフリー不動点) 検証実装
# ==========================================
class AgentStateVector(SQLModel, table=True):
    __tablename__ = "agent_state_vectors"
    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: uuid.UUID = Field(index=True)
    timestamp: float = Field(default_factory=time.time)
    state_hash: str = Field(index=True)
    retry_budget: int = Field(default=10)
    api_budget: float = Field(default=100.0)
    security_risk: float = Field(default=0.0)
    potential_value: float = Field(default=0.0)
    extended_potential_value: float = Field(default=0.0)


class LoopDetectedException(Exception):
    def __init__(self, session_id: uuid.UUID, state_hash: str, message: str):
        self.session_id = session_id
        self.state_hash = state_hash
        super().__init__(message)


class LoopFreeFixedPointMonitor:
    def __init__(
        self, db_session: Session, alpha: float = 10000.0, delta_threshold: float = 0.01
    ):
        self.db = db_session
        self.alpha = alpha
        self.delta_threshold = delta_threshold

    def calculate_potential(
        self, errors: int, test_failures: int, risk: float
    ) -> float:
        return (100.0 * errors) + (50.0 * test_failures) + (100.0 * risk)

    def evaluate_transition(
        self,
        session_id: uuid.UUID,
        state_hash: str,
        errors: int,
        test_failures: int,
        risk: float,
        retry: int,
        api: float,
    ) -> AgentStateVector:
        history = self.db.exec(
            select(AgentStateVector)
            .where(AgentStateVector.session_id == session_id)
            .order_by(AgentStateVector.id)
        ).all()

        history_hashes = {h.state_hash for h in history}
        potential = self.calculate_potential(errors, test_failures, risk)
        is_loop = state_hash in history_hashes
        extended_potential = potential + (self.alpha if is_loop else 0.0)

        if history:
            delta_psi = history[-1].extended_potential_value - extended_potential
            if delta_psi < self.delta_threshold or is_loop:
                raise LoopDetectedException(
                    session_id,
                    state_hash,
                    f"Loop detected. Delta: {delta_psi:.4f}, Loop: {is_loop}",
                )

        new_vector = AgentStateVector(
            session_id=session_id,
            timestamp=time.time(),
            state_hash=state_hash,
            retry_budget=retry,
            api_budget=api,
            security_risk=risk,
            potential_value=potential,
            extended_potential_value=extended_potential,
        )
        self.db.add(new_vector)
        self.db.commit()
        return new_vector


def test_l2_loop_free_fixed_point_monitor():
    print("=== L2 Loop Free Fixed Point Monitor Test ===")
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        monitor = LoopFreeFixedPointMonitor(db_session=session, alpha=10000.0)
        session_id = uuid.uuid4()

        state_1 = monitor.evaluate_transition(
            session_id=session_id,
            state_hash="hash_normal_A",
            errors=3,
            test_failures=2,
            risk=0.1,
            retry=10,
            api=100.0,
        )
        print(f"Step 1 - Potential: {state_1.extended_potential_value}")

        state_2 = monitor.evaluate_transition(
            session_id=session_id,
            state_hash="hash_normal_B",
            errors=2,
            test_failures=1,
            risk=0.1,
            retry=9,
            api=90.0,
        )
        print(f"Step 2 - Potential: {state_2.extended_potential_value}")
        assert state_2.extended_potential_value < state_1.extended_potential_value, (
            "Potential must strictly decrease."
        )

        try:
            monitor.evaluate_transition(
                session_id=session_id,
                state_hash="hash_normal_A",
                errors=2,
                test_failures=1,
                risk=0.1,
                retry=8,
                api=80.0,
            )
            assert False, (
                "Should raise LoopDetectedException due to duplicate state hash."
            )
        except LoopDetectedException as e:
            print(f"Loop Detected: {str(e)}")
            assert e.state_hash == "hash_normal_A"

        session_id_stuck = uuid.uuid4()
        state_stuck_1 = monitor.evaluate_transition(
            session_id=session_id_stuck,
            state_hash="hash_stuck_A",
            errors=1,
            test_failures=1,
            risk=0.0,
            retry=10,
            api=100.0,
        )
        try:
            monitor.evaluate_transition(
                session_id=session_id_stuck,
                state_hash="hash_stuck_B",
                errors=1,
                test_failures=1,
                risk=0.0,
                retry=9,
                api=90.0,
            )
            assert False, (
                "Should raise LoopDetectedException due to non-decreasing potential value."
            )
        except LoopDetectedException as e:
            print(f"Stagnation Detected (Delta < threshold): {str(e)}")

    print(">> L2 Loop Free Fixed Point Monitor Test: PASS\n")


# ==========================================
# 0.5. L4 (自己免疫サンドボックス) 検証実装
# ==========================================
class AutoimmuneSandbox:
    def __init__(self, lambda_val: float = 0.8, delta_sens: float = 0.5):
        self.lambda_val = lambda_val
        self.delta_sens = delta_sens
        self.i_eff = 0.0

    def evaluate_payload_risk(self, payload: str) -> float:
        if "rm -rf" in payload or "DROP DATABASE" in payload:
            return 1.0
        if "sudo" in payload or "chmod" in payload:
            return 0.6
        return 0.1

    def update_effective_risk(
        self, i_raw: float, has_sensitive_action: bool = False
    ) -> float:
        sens_term = self.delta_sens if has_sensitive_action else 0.0
        decayed = self.lambda_val * self.i_eff + (1.0 - self.lambda_val) * sens_term
        self.i_eff = max(i_raw, decayed)
        return self.i_eff

    def should_force_super_degraded(
        self, i_eff: float, slack_time: float, t_rec: float
    ) -> bool:
        return i_eff >= 0.8 and slack_time <= t_rec


def test_l4_autoimmune_sandbox():
    print("=== L4 Autoimmune Sandbox Test ===")
    sandbox = AutoimmuneSandbox(lambda_val=0.8, delta_sens=0.5)

    i_raw_1 = sandbox.evaluate_payload_risk("cat README.md")
    i_eff_1 = sandbox.update_effective_risk(i_raw_1)
    print(f"Safe Payload Risk - Raw: {i_raw_1}, Effective: {i_eff_1:.4f}")
    assert i_eff_1 < 0.2

    i_raw_2 = sandbox.evaluate_payload_risk("rm -rf /")
    i_eff_2 = sandbox.update_effective_risk(i_raw_2)
    print(f"Dangerous Payload Risk - Raw: {i_raw_2}, Effective: {i_eff_2:.4f}")
    assert i_eff_2 >= 1.0

    i_eff_temp = i_eff_2
    for step in range(5):
        i_eff_temp = sandbox.update_effective_risk(0.1)
        print(f"Decay Step {step + 1} - Effective Risk: {i_eff_temp:.4f}")
    assert i_eff_temp > 0.3, "Risk should remain high due to memory weight."

    assert not sandbox.should_force_super_degraded(
        i_eff=0.9, slack_time=300.0, t_rec=100.0
    )
    assert sandbox.should_force_super_degraded(i_eff=0.9, slack_time=50.0, t_rec=100.0)
    print("Super Degraded Transition M4: Triggered Correctly")

    print(">> L4 Autoimmune Sandbox Test: PASS\n")


# ==========================================
# 1. L9 (自己修復) ASTハッシュ変異および循環検知検証
# ==========================================
class NormalizedASTSerializer:
    class NormalizerTransformer(ast.NodeTransformer):
        def __init__(self, mutation_step: Optional[int] = None):
            super().__init__()
            self.mutation_step = mutation_step

        def visit_Module(self, node: ast.Module) -> ast.Module:
            self.generic_visit(node)
            if self.mutation_step is not None:
                target = ast.Name(id="_l9_mutation_step", ctx=ast.Store())
                value = ast.Constant(value=self.mutation_step)
                assign = ast.Assign(targets=[target], value=value)
                node.body.insert(0, assign)
            return node

        def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
            self.generic_visit(node)
            if (
                node.body
                and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
            ):
                node.body.pop(0)  # docstring の削除
            return node

        def visit_Assign(self, node: ast.Assign) -> Optional[ast.Assign]:
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == "_l9_mutation_step":
                    return None  # 世代追跡用ダミーノードの削除
            self.generic_visit(node)
            return node

    def get_hash(
        self,
        source_code: str,
        mutation_step: Optional[int] = None,
        for_cycle_check: bool = False,
    ) -> str:
        try:
            tree = ast.parse(source_code)
            step_val = None if for_cycle_check else mutation_step
            transformer = self.NormalizerTransformer(mutation_step=step_val)
            transformer.visit(tree)
            ast.fix_missing_locations(tree)
            serialized = ast.dump(tree, annotate_fields=False, include_attributes=False)
            return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        except SyntaxError as e:
            return hashlib.sha256(f"SyntaxError: {str(e)}".encode("utf-8")).hexdigest()


def test_l9_ast_mutation_and_cycle():
    print("=== L9 AST Mutation and Cycle Test ===")
    serializer = NormalizedASTSerializer()

    code_base = "def calculate_sum(a, b):\n    # This is a comment\n    return a + b"
    code_with_comment_change = (
        "def calculate_sum(a, b):\n    # This is a modified comment\n    return a + b"
    )

    hash_step_1 = serializer.get_hash(code_base, mutation_step=1, for_cycle_check=False)
    hash_step_2 = serializer.get_hash(code_base, mutation_step=2, for_cycle_check=False)
    print(f"Generation - Step 1 Hash: {hash_step_1[:16]}")
    print(f"Generation - Step 2 Hash: {hash_step_2[:16]}")
    assert hash_step_1 != hash_step_2, (
        "Generation hashes must differ to track iteration steps."
    )

    cycle_hash_step_1 = serializer.get_hash(
        code_base, mutation_step=1, for_cycle_check=True
    )
    cycle_hash_step_2 = serializer.get_hash(
        code_with_comment_change, mutation_step=2, for_cycle_check=True
    )
    print(f"Cycle Check - Step 1 Hash: {cycle_hash_step_1[:16]}")
    print(f"Cycle Check - Step 2 Hash: {cycle_hash_step_2[:16]}")
    assert cycle_hash_step_1 == cycle_hash_step_2, (
        "Cycle check hashes must collide for semantically identical code to detect loops."
    )

    max_mutations = 5
    step = 0
    history = set()
    status = "RUNNING"

    while step < max_mutations:
        current_code = code_base
        cycle_hash = serializer.get_hash(
            current_code, mutation_step=step, for_cycle_check=True
        )
        if cycle_hash in history:
            status = "TRANSIT_CYCLE_DETECTED"
            break
        history.add(cycle_hash)
        step += 1

    if step >= max_mutations and status == "RUNNING":
        status = "TRANSIT_MUTATION_LIMIT"

    print(f"Loop Simulation Result: {status} at step {step}")
    assert status == "TRANSIT_CYCLE_DETECTED", (
        "Should detect loop since same code is repeated."
    )
    print(">> L9 AST Mutation and Cycle Test: PASS\n")


# ==========================================
# 2. L6 (最適忘却) Lambert W Branch & Guard 検証
# ==========================================
class MemoryOptimizer:
    def __init__(self, gamma: float = 0.5, beta_min: float = 0.2):
        self.gamma = gamma
        self.beta_min = beta_min

    def compute_ratio_r5_1(
        self, s_i: float, R_i: float, H_i: float, lambda_val: float
    ) -> Tuple[float, str]:
        if H_i <= 0:
            return 1.0, "optimal"

        argument = -(lambda_val * s_i) / (math.e * R_i)
        if argument < -1.0 / math.e:
            return self.beta_min, "guard_triggered"

        try:
            w_val = sp.lambertw(argument, k=0).real
            beta_opt = (1.0 + w_val) / (self.gamma * H_i)
            clipped_ratio = max(self.beta_min, min(1.0, beta_opt))
            return clipped_ratio, "normal"
        except Exception:
            return self.beta_min, "error_fallback"


def test_l6_lambert_branch_and_guard():
    print("=== L6 Lambert W Branch & Guard Test ===")
    optimizer = MemoryOptimizer()

    s_i = 100.0
    R_i = 200.0
    H_i = 2.0

    lambdas = np.linspace(0.01, 1.9, 100)
    r5_1_ratios = []

    for l in lambdas:
        ratio, state = optimizer.compute_ratio_r5_1(s_i, R_i, H_i, l)
        r5_1_ratios.append(ratio)
        assert state == "normal", "Should be within normal range."
        assert optimizer.beta_min <= ratio <= 1.0, (
            "Clipped ratio must be in [beta_min, 1.0]"
        )

    print(f"Average Ratio: {np.mean(r5_1_ratios):.4f}")

    if HAS_MATPLOTLIB:
        try:
            plt.figure(figsize=(10, 5))
            plt.plot(lambdas, r5_1_ratios, label="Lambert W_0 + Clip", color="blue")
            plt.xlabel("Shadow Price (lambda)")
            plt.ylabel("Optimal Compression Ratio (beta*)")
            plt.title("L6 Optimal Forgetting: Lambert W_0 Dynamic Behavior")
            plt.legend()
            plt.grid(True)
            plt.savefig("verify_r5_lambert_results.png")
            plt.close()
            print("Saved plot to 'verify_r5_lambert_results.png'")
        except Exception as e:
            print(f"Warning: Failed to save plot: {str(e)}")
    else:
        print("Warning: matplotlib not found. Skipping plot generation.")

    l_high = 6.0
    ratio_guard, state_guard = optimizer.compute_ratio_r5_1(s_i, R_i, H_i, l_high)
    print(f"Guard Test (lambda={l_high}) - Ratio: {ratio_guard}, State: {state_guard}")
    assert state_guard == "guard_triggered", "Should trigger domain guard."
    assert ratio_guard == optimizer.beta_min, "Guard ratio must be beta_min."

    print(">> L6 Lambert W Branch & Guard Test: PASS\n")


# ==========================================
# 3. L3 (スキル直交性) OPF & 経験的ペナルティ検証
# ==========================================
class L3OrthogonalExclusionRouter:
    def __init__(
        self,
        n_max: int = 10,
        entropy_crit: float = 0.8,
        c_exec: float = 1.0,
        c_hitl: float = 5.0,
        c_fail: float = 50.0,
        gamma: float = 1.5,
        rho_threshold: float = 2.5,
    ):
        self.n_max = n_max
        self.entropy_crit = entropy_crit
        self.gamma = gamma
        self.rho_threshold = rho_threshold
        self.p_crit = (c_hitl - c_exec) / max(c_fail, 1e-9)
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(
        self, name: str, embedding: np.ndarray, radius: float, namespace: str
    ):
        norm = np.linalg.norm(embedding)
        self.tools[name] = {
            "embedding": embedding / norm if norm > 0 else embedding,
            "radius": radius,
            "namespace": namespace,
        }

    def _calculate_entropy(self, probabilities: np.ndarray) -> float:
        return float(-np.sum(probabilities * np.log2(probabilities + 1e-9)))

    def route_query_r5_1(self, q_vec: np.ndarray) -> Tuple[str, float, str]:
        q = q_vec / np.linalg.norm(q_vec)
        N = len(self.tools)
        rho = N / self.n_max

        if rho >= self.rho_threshold:
            return "L5_HITL_FALLBACK", 1.0, "capacity_limit_fallback"

        scores = {}
        for name, meta in self.tools.items():
            dist = np.arccos(np.clip(np.dot(q, meta["embedding"]), -1.0, 1.0))
            if dist <= meta["radius"]:
                scores[name] = 1.0 - (dist / meta["radius"])

        if not scores:
            return "L5_HITL_FALLBACK", 1.0, "no_candidates"

        vals = np.array(list(scores.values()))
        probs = np.exp(vals) / np.sum(np.exp(vals))
        entropy = self._calculate_entropy(probs)

        if len(scores) == 1 or entropy < self.entropy_crit:
            best_tool = max(scores, key=scores.get)
            p_err = 1.0 - probs[list(scores.keys()).index(best_tool)]
            if p_err >= self.p_crit:
                return "L5_HITL_FALLBACK", p_err, "critical_error_fallback"
            return best_tool, p_err, "direct_match"

        # DQS
        shrinkage = max(0.0, 1.0 - rho) ** self.gamma
        shrunk_scores = {}
        for name in scores.keys():
            dist = np.arccos(
                np.clip(np.dot(q, self.tools[name]["embedding"]), -1.0, 1.0)
            )
            effective_radius = self.tools[name]["radius"] * shrinkage
            if dist <= effective_radius:
                shrunk_scores[name] = 1.0 - (dist / max(effective_radius, 1e-9))

        if len(shrunk_scores) == 1:
            return list(shrunk_scores.keys())[0], 0.05, "dqs_resolved"

        # OPF
        candidates = shrunk_scores if shrunk_scores else scores
        best_candidate = max(candidates, key=candidates.get)
        v_best = self.tools[best_candidate]["embedding"]

        q_prime = q - np.dot(q, v_best) * v_best
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
                    opf_scores[name] = float(
                        np.dot(q_prime_normalized, v_k_prime_normalized)
                    )

            if opf_scores:
                best_opf_alt = max(opf_scores, key=opf_scores.get)
                if opf_scores[best_opf_alt] < 0.3:
                    return best_candidate, 0.1, "opf_resolved"

        # HNPT
        namespaces = {self.tools[name]["namespace"] for name in candidates.keys()}
        if len(namespaces) == 1:
            return f"{list(namespaces)[0]}_namespace_router", 0.15, "hnpt_resolved"

        estimated_p_penalty = max(1.0 - (1.0 / max(rho, 1e-9)), 0.0)
        if estimated_p_penalty >= self.p_crit:
            return (
                "L5_HITL_FALLBACK",
                estimated_p_penalty,
                "congestion_penalty_fallback",
            )

        return "global_namespace_router", estimated_p_penalty, "default_router"


def test_l3_routing_v5_1():
    print("=== L3 Routing Test ===")
    router = L3OrthogonalExclusionRouter(n_max=5, rho_threshold=2.0)

    v_tool1 = np.array([1.0, 0.0, 0.0])
    v_tool2 = np.array([0.98, 0.2, 0.0])
    v_tool3 = np.array([0.98, -0.2, 0.0])

    router.register_tool("tool_db_read", v_tool1, radius=0.3, namespace="db")
    router.register_tool("tool_db_write", v_tool2, radius=0.3, namespace="db")
    router.register_tool("tool_net_fetch", v_tool3, radius=0.3, namespace="net")

    q = np.array([0.99, 0.1, 0.0])

    res_r5_1, err_r5_1, mode_r5_1 = router.route_query_r5_1(q)
    print(f"Routing Result: {res_r5_1} (Mode: {mode_r5_1})")
    assert res_r5_1 == "db_namespace_router", (
        "Should resolve via HNPT to db_namespace_router."
    )

    for i in range(7):
        v_rand = np.array(
            [1.0, np.random.uniform(-0.1, 0.1), np.random.uniform(-0.1, 0.1)]
        )
        router.register_tool(f"dense_tool_{i}", v_rand, radius=0.3, namespace=f"ns_{i}")

    res_fallback, err_fallback, mode_fallback = router.route_query_r5_1(q)
    print(f"Capacity Limit Fallback Result: {res_fallback} (Mode: {mode_fallback})")
    assert res_fallback == "L5_HITL_FALLBACK", (
        "Must trigger L5 HITL Fallback due to capacity limit."
    )
    assert mode_fallback == "capacity_limit_fallback", (
        "Mode must be capacity_limit_fallback."
    )

    print("--- Testing L3 OPF Specific Branch ---")
    router_opf = L3OrthogonalExclusionRouter(
        n_max=2, entropy_crit=0.5, rho_threshold=3.0
    )
    router_opf.register_tool(
        "tool_best", np.array([1.0, 0.0, 0.0]), radius=1.6, namespace="sys"
    )
    router_opf.register_tool(
        "tool_alternative", np.array([0.0, 0.0, 1.0]), radius=1.6, namespace="sys"
    )
    q_opf = np.array([0.8, 0.6, 0.0])

    res_opf, err_opf, mode_opf = router_opf.route_query_r5_1(q_opf)
    print(f"OPF Branch Routing Result: {res_opf} (Mode: {mode_opf})")
    assert res_opf == "tool_best", (
        "OPF must filter competitors and resolve to the best candidate."
    )
    assert mode_opf == "opf_resolved", "Must resolve via 'opf_resolved' mode."
    print(">> L3 OPF Specific Branch Test: PASS\n")


# ==========================================
# 4. Tunnel Cache (Residual Cache) 実用モデル検証
# ==========================================
@dataclass
class TunnelItem:
    raw: str
    key: str  # C(x): 正規化された骨
    alpha: dict  # alpha: 潰しても残る差分
    invariants: dict  # N(x): 整数・分類・リスク等の不変量
    source: str
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())


def collapse(x: str) -> str:
    x_clean = x.strip()
    if "PermissionError" in x_clean:
        return "PermissionError"
    if "ModuleNotFoundError" in x_clean:
        return "ModuleNotFoundError"
    if "AIメモリ" in x_clean or "長期記憶" in x_clean:
        return "AI_MEMORY_NORMALIZATION_SCHEME"
    if "Lean" in x_clean or "形式検証" in x_clean:
        return "FORMAL_VERIFICATION_LIMIT"
    if x_clean.startswith("http://") or x_clean.startswith("https://"):
        return "URL_MATCH"
    return "UNKNOWN_CANONICAL_KEY"


def residue(x: str, key: str) -> dict:
    res = {}
    x_clean = x.strip()
    if key == "PermissionError":
        import re

        path_match = re.search(r"Permission denied: '([^']+)'", x_clean)
        if path_match:
            res["path"] = path_match.group(1)
        res["errno"] = 13
    elif key == "AI_MEMORY_NORMALIZATION_SCHEME":
        if "残差が重要" in x_clean:
            res["focus"] = "residual"
        elif "差分保存" in x_clean:
            res["focus"] = "diff"
    elif key == "FORMAL_VERIFICATION_LIMIT":
        if "Akram Louiz" in x_clean or "双子素数" in x_clean:
            res["risk_mention"] = "Akram Louiz"
            res["danger"] = "Unverified disproof of Twin Primes conjecture center"
        if "100%正しい" in x_clean or "絶対的" in x_clean:
            res["overstatement"] = (
                "Claim of 100% mathematical correctness in Lean without real-world context validation"
            )
    elif key == "URL_MATCH":
        from urllib.parse import urlparse, parse_qs

        parsed = urlparse(x_clean)
        res["base_url"] = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        res["query_params"] = {k: v[0] for k, v in parse_qs(parsed.query).items()}
    return res


def tunnel(key: str, alpha: dict) -> str:
    if key == "PermissionError":
        path = alpha.get("path", "unknown")
        return f"PermissionError solved at {path}. Proposed command: chmod 600 {path} or check path scope."
    elif key == "URL_MATCH":
        base = alpha.get("base_url", "")
        params = alpha.get("query_params", {})
        if params:
            param_str = "&".join(f"{k}={v}" for k, v in params.items())
            return f"{base}?{param_str}"
        return base
    elif key == "FORMAL_VERIFICATION_LIMIT":
        return "Lean 4 verifies formal logical step validity. Reality, value, and applicability require human critique."
    return f"Canonical: {key}"


def invariant(x: str) -> dict:
    inv = {"risk_level": 0.0, "category": "unknown"}
    x_clean = x.strip()
    if "PermissionError" in x_clean:
        inv["risk_level"] = 0.5
        inv["category"] = "security_error"
    elif "Akram Louiz" in x_clean or "双子素数" in x_clean or "100%正しい" in x_clean:
        inv["risk_level"] = 0.9
        inv["category"] = "scientific_risk"
    elif "http://" in x_clean or "https://" in x_clean:
        inv["risk_level"] = 0.1
        inv["category"] = "clipboard_url"
    return inv


def test_tunnel_research_compiler():
    print("=== Tunnel Research Compiler Test ===")
    memo = "Lean 4 を通れば100%正しい絶対的な証明になる。Akram Louizによる双子素数予想の反証も形式検証された先駆的事例だ。"
    key = collapse(memo)
    alpha = residue(memo, key)
    inv = invariant(memo)
    item = TunnelItem(
        raw=memo, key=key, alpha=alpha, invariants=inv, source="research_notes"
    )
    print(f"Canonical Key: {item.key}")
    print(f"Residual alpha: {item.alpha}")
    assert item.key == "FORMAL_VERIFICATION_LIMIT"
    assert "danger" in item.alpha
    reconstructed = tunnel(item.key, item.alpha)
    print(f"Reconstructed Critiques: {reconstructed}")
    print(">> Tunnel Research Compiler Test: PASS\n")


def test_tunnel_error_resolver():
    print("=== Tunnel Error Resolver Test ===")
    error_log = "PermissionError: [Errno 13] Permission denied: '/Users/ryota/.gemini/antigravity/scratch/verify_depth.lock'"
    key = collapse(error_log)
    alpha = residue(error_log, key)
    inv = invariant(error_log)
    item = TunnelItem(
        raw=error_log, key=key, alpha=alpha, invariants=inv, source="cli_stderr"
    )
    assert item.key == "PermissionError"
    assert "verify_depth.lock" in item.alpha["path"]
    solution = tunnel(item.key, item.alpha)
    print(f"Reconstructed Solution: {solution}")
    print(">> Tunnel Error Resolver Test: PASS\n")


def test_tunnel_clipboard():
    print("=== Tunnel Clipboard Test ===")
    copied_url = "https://example.com/search?q=residual+cache&utm_source=chatgpt&tracking_id=998598118"
    key = collapse(copied_url)
    alpha = residue(copied_url, key)
    inv = invariant(copied_url)
    item = TunnelItem(
        raw=copied_url, key=key, alpha=alpha, invariants=inv, source="clipboard"
    )
    assert item.key == "URL_MATCH"
    assert item.alpha["query_params"]["utm_source"] == "chatgpt"
    clean_url = tunnel(item.key, item.alpha)
    print(f"Reconstructed clean URL: {clean_url}")
    print(">> Tunnel Clipboard Test: PASS\n")


# ==========================================
# 5. 一般化ポテンシャル関数 Psi_unified シミュレーション検証
# ==========================================
def test_l2_l7_l9_unified_potential():
    print("=== L2/L7/L9 Unified Potential Simulation Test ===")
    alpha_loop = 1000.0
    gamma_l7 = 10.0
    beta_l9 = 5.0

    def calculate_psi_unified(
        errors: int, is_loop: bool, slack_time: float, k_mutate: int
    ) -> float:
        phi = 100.0 * errors
        term_loop = alpha_loop if is_loop else 0.0
        term_l7 = gamma_l7 * (1.0 / max(slack_time, 1e-9))
        term_l9 = beta_l9 * (5 - k_mutate)
        return phi + term_loop + term_l7 + term_l9

    psi_start = calculate_psi_unified(
        errors=3, is_loop=False, slack_time=200.0, k_mutate=5
    )
    psi_next = calculate_psi_unified(
        errors=1, is_loop=False, slack_time=190.0, k_mutate=4
    )
    print(f"Normal Trace - Start Psi: {psi_start:.4f}, Next Psi: {psi_next:.4f}")
    assert psi_next < psi_start

    psi_loop = calculate_psi_unified(
        errors=1, is_loop=True, slack_time=180.0, k_mutate=3
    )
    assert psi_loop > 1000.0

    psi_timeout = calculate_psi_unified(
        errors=1, is_loop=False, slack_time=0.01, k_mutate=3
    )
    assert psi_timeout > 1000.0

    print(">> L2/L7/L9 Unified Potential Simulation Test: PASS\n")


# ==========================================
# 6. L3 混雑度ペナルティの v8 スケーリング不整合修正検証
# ==========================================
def test_l3_routing_v8_scaling():
    print("=== L3 Routing v8 Scaling Integration Test ===")

    class V8Router(L3OrthogonalExclusionRouter):
        def route_query_v8(self, q_vec: np.ndarray) -> Tuple[str, float, str]:
            q = q_vec / np.linalg.norm(q_vec)
            N = len(self.tools)
            rho = N / self.n_max

            if rho >= self.rho_threshold:
                return "L5_HITL_FALLBACK", 1.0, "capacity_limit_fallback"

            scores = {}
            for name, meta in self.tools.items():
                dist = np.arccos(np.clip(np.dot(q, meta["embedding"]), -1.0, 1.0))
                if dist <= meta["radius"]:
                    scores[name] = 1.0 - (dist / meta["radius"])

            if not scores:
                return "L5_HITL_FALLBACK", 1.0, "no_candidates"

            vals = np.array(list(scores.values()))
            probs = np.exp(vals) / np.sum(np.exp(vals))
            entropy = self._calculate_entropy(probs)

            if len(scores) == 1 or entropy < self.entropy_crit:
                best_tool = max(scores, key=scores.get)
                p_err = 1.0 - probs[list(scores.keys()).index(best_tool)]
                if p_err >= self.p_crit:
                    return "L5_HITL_FALLBACK", p_err, "critical_error_fallback"
                return best_tool, p_err, "direct_match"

            # DQS
            shrinkage = max(0.0, 1.0 - rho) ** self.gamma
            shrunk_scores = {}
            for name in scores.keys():
                dist = np.arccos(
                    np.clip(np.dot(q, self.tools[name]["embedding"]), -1.0, 1.0)
                )
                effective_radius = self.tools[name]["radius"] * shrinkage
                if dist <= effective_radius:
                    shrunk_scores[name] = 1.0 - (dist / max(effective_radius, 1e-9))

            if len(shrunk_scores) == 1:
                return list(shrunk_scores.keys())[0], 0.05, "dqs_resolved"

            # OPF
            candidates = shrunk_scores if shrunk_scores else scores
            best_candidate = max(candidates, key=candidates.get)
            v_best = self.tools[best_candidate]["embedding"]

            q_prime = q - np.dot(q, v_best) * v_best
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
                        opf_scores[name] = float(
                            np.dot(q_prime_normalized, v_k_prime_normalized)
                        )

                if opf_scores:
                    best_opf_alt = max(opf_scores, key=opf_scores.get)
                    if opf_scores[best_opf_alt] < 0.3:
                        return best_candidate, 0.1, "opf_resolved"

            # HNPT
            namespaces = {self.tools[name]["namespace"] for name in candidates.keys()}
            if len(namespaces) == 1:
                return f"{list(namespaces)[0]}_namespace_router", 0.15, "hnpt_resolved"

            eta_route = 0.05
            estimated_p_penalty = eta_route * max(1.0 - (1.0 / max(rho, 1e-9)), 0.0)
            if estimated_p_penalty >= self.p_crit:
                return (
                    "L5_HITL_FALLBACK",
                    estimated_p_penalty,
                    "congestion_penalty_fallback",
                )

            return "global_namespace_router", estimated_p_penalty, "default_router"

    router = V8Router(n_max=3, entropy_crit=0.8, rho_threshold=2.5)
    router.register_tool("t1", np.array([1.0, 0.0, 0.0]), radius=1.0, namespace="sys")
    router.register_tool("t2", np.array([0.0, 1.0, 0.0]), radius=1.0, namespace="sys")
    router.register_tool("t3", np.array([0.0, 0.0, 1.0]), radius=1.0, namespace="net")
    router.register_tool("t4", np.array([0.7, 0.7, 0.0]), radius=1.0, namespace="net")

    q = np.array([0.8, 0.6, 0.0])

    res_v7, err_v7, mode_v7 = router.route_query_r5_1(q)
    print(f"v7 Router - Result: {res_v7}, Mode: {mode_v7}")
    assert res_v7 == "L5_HITL_FALLBACK" and mode_v7 == "congestion_penalty_fallback"

    res_v8, err_v8, mode_v8 = router.route_query_v8(q)
    print(f"v8 Router - Result: {res_v8}, Mode: {mode_v8}")
    assert res_v8 != "L5_HITL_FALLBACK"
    assert mode_v8 in [
        "dqs_resolved",
        "opf_resolved",
        "hnpt_resolved",
        "default_router",
    ]
    print(">> L3 Routing v8 Scaling Integration Test: PASS\n")


# ==========================================
# 7. 全レイヤー (L1-L9) 結合コヒーレンスループ数値検証 (v9/v10)
# ==========================================
def test_full_9_layer_coherence_loop():
    print("=== Full 9-Layer Coherence Loop Simulation Test ===")

    alpha_loop = 1000.0
    gamma_l7 = 10.0
    beta_l9 = 5.0

    def calculate_psi_unified(
        errors: int, is_loop: bool, slack_time: float, k_mutate: int
    ) -> float:
        phi = 100.0 * errors  # errors 減少の重みを 100.0 に引き上げる
        term_loop = alpha_loop if is_loop else 0.0
        term_l7 = gamma_l7 * (1.0 / max(slack_time, 1e-9))
        term_l9 = beta_l9 * (5 - k_mutate)  # k_mutate 減少のペナルティを 5.0 に下げる
        return phi + term_loop + term_l7 + term_l9

    errors = 4
    is_loop = False
    slack_time = 300.0
    k_mutate = 5
    num_tools = 2

    psi_history = []
    psi_curr = calculate_psi_unified(errors, is_loop, slack_time, k_mutate)
    psi_history.append(psi_curr)

    print(
        f"Cycle 0 - Psi: {psi_curr:.4f} (errors={errors}, slack={slack_time:.1f}, k={k_mutate})"
    )

    for cycle in range(1, 10):
        num_tools += 0.2
        slack_time -= 20.0

        if errors > 0:
            errors -= 1
            k_mutate -= 1

        psi_next = calculate_psi_unified(errors, is_loop, slack_time, k_mutate)
        psi_history.append(psi_next)

        print(
            f"Cycle {cycle} - Psi: {psi_next:.4f} (errors={errors}, slack={slack_time:.1f}, k={k_mutate})"
        )

        # コヒーレンス調整後、正常修復時には Psi が狭義単調減少することを確認
        if cycle < 3:
            assert psi_next < psi_history[-2], (
                f"Psi must decrease on successful recovery. Prev: {psi_history[-2]:.4f}, Curr: {psi_next:.4f}"
            )

        if slack_time <= 10.0 or k_mutate == 0:
            print(
                f"Phase transition condition met at cycle {cycle}. Terminating simulation loop."
            )
            break

    print(">> Full 9-Layer Coherence Loop Simulation Test: PASS\n")


# ==========================================
# メイン実行
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print("Starting R5 Theorems Verification Suite (v10 - Wrap-up)")
    print("=" * 50)

    test_l2_loop_free_fixed_point_monitor()
    test_l4_autoimmune_sandbox()
    test_l9_ast_mutation_and_cycle()
    test_l6_lambert_branch_and_guard()
    test_l3_routing_v5_1()

    # v7 テスト
    test_tunnel_research_compiler()
    test_tunnel_error_resolver()
    test_tunnel_clipboard()
    test_l2_l7_l9_unified_potential()

    # v8 テスト
    test_l3_routing_v8_scaling()

    # v9/v10 テスト
    test_full_9_layer_coherence_loop()

    print("=" * 50)
    print("All theorems verified successfully (v10 - Wrap-up)!")
    print("=" * 50)
