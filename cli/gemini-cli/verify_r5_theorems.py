import numpy as np
import scipy.special as sp
import math
import ast
import hashlib
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel

# 再現性のための乱数 seed 固定 (v5.1)
np.random.seed(42)

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
            # 世代追跡用ダミー変数の動的追加
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

        def visit_Assign(self, node: ast.Assign) -> Optional[ast.Assign]:
            # 循環検知用のハッシュ作成時、ダミー変数は AST から除外して正規化する (v5.1修正)
            if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                if node.targets[0].id == '_l9_mutation_step':
                    return None  # 世代追跡用ダミーノードの削除
            self.generic_visit(node)
            return node

    def get_hash(self, source_code: str, mutation_step: Optional[int] = None, for_cycle_check: bool = False) -> str:
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
    code_with_comment_change = "def calculate_sum(a, b):\n    # This is a modified comment\n    return a + b"
    
    # R5(v5.1)検証: 世代管理用としては、mutation_step を付与するとハッシュが異なる (世代の一意性)
    hash_step_1 = serializer.get_hash(code_base, mutation_step=1, for_cycle_check=False)
    hash_step_2 = serializer.get_hash(code_base, mutation_step=2, for_cycle_check=False)
    print(f"v5.1 Generation - Step 1 Hash: {hash_step_1[:16]}")
    print(f"v5.1 Generation - Step 2 Hash: {hash_step_2[:16]}")
    assert hash_step_1 != hash_step_2, "Generation hashes must differ to track iteration steps."

    # R5(v5.1)検証: 循環検知（for_cycle_check=True）をオンにすると、同じ意味のコードは衝突する (検知の正常化)
    cycle_hash_step_1 = serializer.get_hash(code_base, mutation_step=1, for_cycle_check=True)
    cycle_hash_step_2 = serializer.get_hash(code_with_comment_change, mutation_step=2, for_cycle_check=True)
    print(f"v5.1 Cycle Check - Step 1 Hash: {cycle_hash_step_1[:16]}")
    print(f"v5.1 Cycle Check - Step 2 Hash: {cycle_hash_step_2[:16]}")
    assert cycle_hash_step_1 == cycle_hash_step_2, "Cycle check hashes must collide for semantically identical code to detect loops."
    
    # MAX_L9_MUTATIONS イテレーション制限のシミュレーション
    max_mutations = 5
    step = 0
    history = set()
    status = "RUNNING"
    
    while step < max_mutations:
        current_code = code_base  # 同じコードが生成され続ける無限ループ状態
        # 循環検知用ハッシュで判定
        cycle_hash = serializer.get_hash(current_code, mutation_step=step, for_cycle_check=True)
        if cycle_hash in history:
            status = "TRANSIT_CYCLE_DETECTED"
            break
        history.add(cycle_hash)
        step += 1
        
    if step >= max_mutations and status == "RUNNING":
        status = "TRANSIT_MUTATION_LIMIT"
        
    print(f"Loop Simulation Result: {status} at step {step}")
    assert status == "TRANSIT_CYCLE_DETECTED", "Should detect loop since same code is repeated."
    print(">> L9 AST Mutation and Cycle Test: PASS\n")

# ==========================================
# 2. L6 (最適忘却) Lambert W Branch & Guard 検証
# ==========================================
class MemoryOptimizer:
    def __init__(self, gamma: float = 0.5, beta_min: float = 0.2):
        self.gamma = gamma
        self.beta_min = beta_min

    def compute_ratio_r5_1(self, s_i: float, R_i: float, H_i: float, lambda_val: float) -> Tuple[float, str]:
        # R5 v5.1: k=0 (主枝) を使用し、クリップと定義域ガードを実装
        if H_i <= 0: 
            return 1.0, "optimal"
        
        # 定義域ガード
        argument = - (lambda_val * s_i) / (math.e * R_i)
        if argument < -1.0 / math.e:
            # 定義域外 (NaN) ガード発火: 最小値クランプ
            return self.beta_min, "guard_triggered"
            
        try:
            # 主枝 k=0 を使用して正の物理的値を算出
            w_val = sp.lambertw(argument, k=0).real
            beta_opt = (1.0 + w_val) / (self.gamma * H_i)
            # 後段クリップによる [beta_min, 1.0] レンジの保証
            clipped_ratio = max(self.beta_min, min(1.0, beta_opt))
            return clipped_ratio, "normal"
        except Exception:
            return self.beta_min, "error_fallback"

def test_l6_lambert_branch_and_guard():
    print("=== L6 Lambert W Branch & Guard Test ===")
    optimizer = MemoryOptimizer()
    
    # 正常ケースでの Lambert W_0 挙動
    s_i = 100.0
    R_i = 200.0
    H_i = 2.0
    
    lambdas = np.linspace(0.01, 1.9, 100)
    r5_1_ratios = []
    
    for l in lambdas:
        ratio, state = optimizer.compute_ratio_r5_1(s_i, R_i, H_i, l)
        r5_1_ratios.append(ratio)
        # lambda * s_i <= R_i であるため正常に動作するはず
        assert state == "normal", "Should be within normal range."
        assert optimizer.beta_min <= ratio <= 1.0, "Clipped ratio must be in [beta_min, 1.0]"
        
    print(f"v5.1 Average Ratio: {np.mean(r5_1_ratios):.4f} (expected to vary dynamically in [0.2, 1.0])")
    
    # 可視化プロットの更新
    plt.figure(figsize=(10, 5))
    plt.plot(lambdas, r5_1_ratios, label='v5.1 (Lambert W_0 + Clip)', color='blue')
    plt.xlabel('Shadow Price (lambda)')
    plt.ylabel('Optimal Compression Ratio (beta*)')
    plt.title('L6 Optimal Forgetting: v5.1 Lambert W_0 Dynamic Behavior')
    plt.legend()
    plt.grid(True)
    plt.savefig('verify_r5_lambert_results.png')
    print("Saved plot to 'verify_r5_lambert_results.png'")
    
    # 定義域外ガードのテストケース
    # lambda * s_i > R_i * e を満たすように設定
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
        rho_threshold: float = 2.5
    ):
        self.n_max = n_max
        self.entropy_crit = entropy_crit
        self.gamma = gamma
        self.rho_threshold = rho_threshold
        self.p_crit = (c_hitl - c_exec) / max(c_fail, 1e-9)
        self.tools: Dict[str, Dict[str, Any]] = {}

    def register_tool(self, name: str, embedding: np.ndarray, radius: float, namespace: str):
        norm = np.linalg.norm(embedding)
        self.tools[name] = {
            "embedding": embedding / norm if norm > 0 else embedding,
            "radius": radius,
            "namespace": namespace
        }

    def _calculate_entropy(self, probabilities: np.ndarray) -> float:
        return float(-np.sum(probabilities * np.log2(probabilities + 1e-9)))

    def route_query_r5_1(self, q_vec: np.ndarray) -> Tuple[str, float, str]:
        # R5 v5.1: OPFの直交補空間上での類似度評価、および経験的ペナルティ閾値判定
        q = q_vec / np.linalg.norm(q_vec)
        N = len(self.tools)
        rho = N / self.n_max
        
        # 混雑度閾値によるエスカレーション (v5.1)
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
            dist = np.arccos(np.clip(np.dot(q, self.tools[name]["embedding"]), -1.0, 1.0))
            effective_radius = self.tools[name]["radius"] * shrinkage
            if dist <= effective_radius:
                shrunk_scores[name] = 1.0 - (dist / max(effective_radius, 1e-9))
                
        if len(shrunk_scores) == 1:
            return list(shrunk_scores.keys())[0], 0.05, "dqs_resolved"
            
        # OPF (直交補空間での類似度評価)
        candidates = shrunk_scores if shrunk_scores else scores
        best_candidate = max(candidates, key=candidates.get)
        v_best = self.tools[best_candidate]["embedding"]
        
        q_prime = q - np.dot(q, v_best) * v_best
        q_prime_norm = np.linalg.norm(q_prime)
        
        if q_prime_norm > 1e-5:
            q_prime_normalized = q_prime / q_prime_norm
            opf_scores = {}
            for name in candidates.keys():
                if name == best_candidate: continue
                v_k = self.tools[name]["embedding"]
                v_k_prime = v_k - np.dot(v_k, v_best) * v_best
                v_k_prime_norm = np.linalg.norm(v_k_prime)
                
                if v_k_prime_norm > 1e-5:
                    v_k_prime_normalized = v_k_prime / v_k_prime_norm
                    opf_scores[name] = float(np.dot(q_prime_normalized, v_k_prime_normalized))
            
            if opf_scores:
                best_opf_alt = max(opf_scores, key=opf_scores.get)
                if opf_scores[best_opf_alt] < 0.3: 
                    return best_candidate, 0.1, "opf_resolved"
                    
        # HNPT
        namespaces = {self.tools[name]["namespace"] for name in candidates.keys()}
        if len(namespaces) == 1:
            return f"{list(namespaces)[0]}_namespace_router", 0.15, "hnpt_resolved"
            
        # 経験的混雑度ペナルティによるフォールバック判定 (v5.1)
        estimated_p_penalty = max(1.0 - (1.0 / max(rho, 1e-9)), 0.0)
        if estimated_p_penalty >= self.p_crit:
            return "L5_HITL_FALLBACK", estimated_p_penalty, "congestion_penalty_fallback"
            
        return "global_namespace_router", estimated_p_penalty, "default_router"

def test_l3_routing_v5_1():
    print("=== L3 Routing v5.1 Test ===")
    router = L3OrthogonalExclusionRouter(n_max=5, rho_threshold=2.0)
    
    v_tool1 = np.array([1.0, 0.0, 0.0])
    v_tool2 = np.array([0.98, 0.2, 0.0])
    v_tool3 = np.array([0.98, -0.2, 0.0])
    
    router.register_tool("tool_db_read", v_tool1, radius=0.3, namespace="db")
    router.register_tool("tool_db_write", v_tool2, radius=0.3, namespace="db")
    router.register_tool("tool_net_fetch", v_tool3, radius=0.3, namespace="net")
    
    # 曖昧なクエリ
    q = np.array([0.99, 0.1, 0.0])
    
    # v5.1 OPFによる解決 (同一ネームスペース内解決)
    res_r5_1, err_r5_1, mode_r5_1 = router.route_query_r5_1(q)
    print(f"v5.1 Routing Result: {res_r5_1} (Mode: {mode_r5_1})")
    assert res_r5_1 == "db_namespace_router", "Should resolve via HNPT to db_namespace_router."
    
    # 経験的混雑度ペナルティによるフォールバック
    # rho_threshold=2.0 に対して、ツール登録数 10 (rho = 2.0 >= 2.0) とする
    for i in range(7):
        v_rand = np.array([1.0, np.random.uniform(-0.1, 0.1), np.random.uniform(-0.1, 0.1)])
        router.register_tool(f"dense_tool_{i}", v_rand, radius=0.3, namespace=f"ns_{i}")
        
    res_fallback, err_fallback, mode_fallback = router.route_query_r5_1(q)
    print(f"v5.1 Capacity Limit Fallback Result: {res_fallback} (Mode: {mode_fallback})")
    assert res_fallback == "L5_HITL_FALLBACK", "Must trigger L5 HITL Fallback due to capacity limit."
    assert mode_fallback == "capacity_limit_fallback", "Mode must be capacity_limit_fallback."
    
    print(">> L3 Routing v5.1 Test: PASS\n")

# ==========================================
# メイン実行
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print("Starting R5 Theorems Verification Suite (v5.1)")
    print("=" * 50)
    
    test_l9_ast_mutation_and_cycle()
    test_l6_lambert_branch_and_guard()
    test_l3_routing_v5_1()
    
    print("=" * 50)
    print("All R5 theorems (L3, L6, L9) verified successfully (v5.1)!")
    print("=" * 50)
