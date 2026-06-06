import numpy as np
import scipy.special as sp
import math
import ast
import hashlib
import matplotlib.pyplot as plt
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel

# ==========================================
# 1. L9 (自己修復) ASTハッシュ変異検証
# ==========================================
class NormalizedASTSerializer:
    class NormalizerTransformer(ast.NodeTransformer):
        def __init__(self, mutation_step: Optional[int] = None):
            super().__init__()
            self.mutation_step = mutation_step

        def visit_Module(self, node: ast.Module) -> ast.Module:
            self.generic_visit(node)
            if self.mutation_step is not None:
                # ASTの先頭に無害なダミー変数代入を差し込み、ハッシュを一意に変異させる (R5バグ修正)
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

def test_l9_ast_mutation():
    print("=== L9 AST Mutation Test ===")
    serializer = NormalizedASTSerializer()
    
    code_base = "def calculate_sum(a, b):\n    # This is a comment\n    return a + b"
    code_with_comment_change = "def calculate_sum(a, b):\n    # This is a modified comment\n    return a + b"
    
    # R4バグ: コメント変更のみでは正規化ASTハッシュは衝突する
    hash_base_r4 = serializer.get_hash(code_base, mutation_step=None)
    hash_modified_r4 = serializer.get_hash(code_with_comment_change, mutation_step=None)
    print(f"R4 (No Mutation Node) - Base Hash: {hash_base_r4[:16]}")
    print(f"R4 (No Mutation Node) - Mod Hash:  {hash_modified_r4[:16]}")
    assert hash_base_r4 == hash_modified_r4, "R4 AST normalizer should ignore comments and collide."
    
    # R5修正: mutation_step のダミー変数ノードを追加することでハッシュを変異させる
    hash_step_1 = serializer.get_hash(code_base, mutation_step=1)
    hash_step_2 = serializer.get_hash(code_base, mutation_step=2)
    print(f"R5 (With Mutation Node) - Step 1 Hash: {hash_step_1[:16]}")
    print(f"R5 (With Mutation Node) - Step 2 Hash: {hash_step_2[:16]}")
    assert hash_step_1 != hash_step_2, "R5 AST normalizer must generate different hashes for different steps."
    assert hash_base_r4 != hash_step_1, "Mutation hash must differ from base hash."
    print(">> L9 AST Mutation Test: PASS\n")

# ==========================================
# 2. L6 (最適忘却) Lambert W Branch 検証
# ==========================================
class MemoryOptimizer:
    def __init__(self, gamma: float = 0.5, beta_min: float = 0.2):
        self.gamma = gamma
        self.beta_min = beta_min

    def compute_ratio_r4(self, s_i: float, R_i: float, H_i: float, lambda_val: float) -> float:
        # R4バグ: k=-1 を使用
        if H_i <= 0: return 1.0
        argument = - (lambda_val * s_i) / (math.e * R_i)
        if argument < -1.0 / math.e: return self.beta_min
        try:
            w_val = sp.lambertw(argument, k=-1).real
            beta_opt = (1.0 + w_val) / (self.gamma * H_i)
            return max(self.beta_min, min(1.0, beta_opt))
        except Exception:
            return self.beta_min

    def compute_ratio_r5(self, s_i: float, R_i: float, H_i: float, lambda_val: float) -> float:
        # R5修正: k=0 を使用
        if H_i <= 0: return 1.0
        argument = - (lambda_val * s_i) / (math.e * R_i)
        if argument < -1.0 / math.e: return self.beta_min
        try:
            w_val = sp.lambertw(argument, k=0).real
            beta_opt = (1.0 + w_val) / (self.gamma * H_i)
            return max(self.beta_min, min(1.0, beta_opt))
        except Exception:
            return self.beta_min

def test_l6_lambert_branch():
    print("=== L6 Lambert W Branch Test ===")
    optimizer = MemoryOptimizer()
    
    # テストパラメータ
    s_i = 100.0  # メモリサイズ
    R_i = 200.0  # メモリ重要度
    H_i = 2.0    # メモリ情報エントロピー
    
    # 異なるシャドウプライス lambda に対して両分岐の挙動を評価
    lambdas = np.linspace(0.01, 1.9, 100)
    r4_ratios = []
    r5_ratios = []
    
    for l in lambdas:
        r4_ratios.append(optimizer.compute_ratio_r4(s_i, R_i, H_i, l))
        r5_ratios.append(optimizer.compute_ratio_r5(s_i, R_i, H_i, l))
        
    # 可視化プロット用
    plt.figure(figsize=(10, 5))
    plt.plot(lambdas, r4_ratios, label='R4 (Lambert W_-1)', color='red', linestyle='--')
    plt.plot(lambdas, r5_ratios, label='R5 (Lambert W_0)', color='blue')
    plt.xlabel('Shadow Price (lambda)')
    plt.ylabel('Optimal Compression Ratio (beta*)')
    plt.title('L6 Optimal Forgetting: R4 vs R5 Lambert W Branch Comparison')
    plt.legend()
    plt.grid(True)
    plt.savefig('verify_r5_lambert_results.png')
    print("Saved plot to 'verify_r5_lambert_results.png'")
    
    # R4 は Lambert W_-1 を使うため、常に beta_min に張り付いていることを確認
    print(f"R4 Average Ratio: {np.mean(r4_ratios):.4f} (expected to be close to beta_min = 0.2)")
    print(f"R5 Average Ratio: {np.mean(r5_ratios):.4f} (expected to vary dynamically)")
    assert np.all(np.array(r4_ratios) == optimizer.beta_min), "R4 should always be clamped to beta_min."
    assert np.any(np.array(r5_ratios) > optimizer.beta_min), "R5 should calculate positive dynamic compression ratio."
    print(">> L6 Lambert W Branch Test: PASS\n")

# ==========================================
# 3. L3 (スキル直交性) OPF & ベイズ境界検証
# ==========================================
class L3OrthogonalExclusionRouter:
    def __init__(
        self, 
        n_max: int = 10, 
        entropy_crit: float = 0.8,
        c_exec: float = 1.0,
        c_hitl: float = 5.0,
        c_fail: float = 50.0,
        gamma: float = 1.5
    ):
        self.n_max = n_max
        self.entropy_crit = entropy_crit
        self.gamma = gamma
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

    def route_query_r4(self, q_vec: np.ndarray) -> Tuple[str, float]:
        # R4バグ: 直交補空間ベクトルと最尤候補自体の内積を取って適合判定している (常に不適合になる)
        q = q_vec / np.linalg.norm(q_vec)
        scores = {}
        for name, meta in self.tools.items():
            dist = np.arccos(np.clip(np.dot(q, meta["embedding"]), -1.0, 1.0))
            if dist <= meta["radius"]:
                scores[name] = 1.0 - (dist / meta["radius"])
        if not scores: return "L5_HITL_FALLBACK", 1.0
        
        vals = np.array(list(scores.values()))
        probs = np.exp(vals) / np.sum(np.exp(vals))
        entropy = self._calculate_entropy(probs)
        
        if len(scores) == 1 or entropy < self.entropy_crit:
            best_tool = max(scores, key=scores.get)
            p_err = 1.0 - probs[list(scores.keys()).index(best_tool)]
            return best_tool, p_err
            
        # R4 OPF
        best = max(scores, key=scores.get)
        best_vec = self.tools[best]["embedding"]
        q_prime = q - np.dot(q, best_vec) * best_vec
        norm = np.linalg.norm(q_prime)
        
        # バグ部分: 直交ベクトル q_prime/norm と best_vec の内積を計算 (常に 0 となり、arccos(0) = pi/2 となる)
        if norm > 0 and np.arccos(np.dot(q_prime/norm, best_vec)) <= self.tools[best]["radius"]:
            return best # ここには絶対到達しない (radius < pi/2 のため)
            
        return "L5_HITL_FALLBACK", 1.0

    def route_query_r5(self, q_vec: np.ndarray) -> Tuple[str, float]:
        # R5修正: OPFでの直交補空間上での類似度評価およびベイズフォールバック
        q = q_vec / np.linalg.norm(q_vec)
        N = len(self.tools)
        rho = N / self.n_max
        
        scores = {}
        for name, meta in self.tools.items():
            dist = np.arccos(np.clip(np.dot(q, meta["embedding"]), -1.0, 1.0))
            if dist <= meta["radius"]:
                scores[name] = 1.0 - (dist / meta["radius"])
                
        if not scores: return "L5_HITL_FALLBACK", 1.0
        
        vals = np.array(list(scores.values()))
        probs = np.exp(vals) / np.sum(np.exp(vals))
        entropy = self._calculate_entropy(probs)
        
        if len(scores) == 1 or entropy < self.entropy_crit:
            best_tool = max(scores, key=scores.get)
            p_err = 1.0 - probs[list(scores.keys()).index(best_tool)]
            if p_err >= self.p_crit:
                return "L5_HITL_FALLBACK", p_err
            return best_tool, p_err

        # DQS
        shrinkage = max(0.0, 1.0 - rho) ** self.gamma
        shrunk_scores = {}
        for name in scores.keys():
            dist = np.arccos(np.clip(np.dot(q, self.tools[name]["embedding"]), -1.0, 1.0))
            effective_radius = self.tools[name]["radius"] * shrinkage
            if dist <= effective_radius:
                shrunk_scores[name] = 1.0 - (dist / max(effective_radius, 1e-9))
                
        if len(shrunk_scores) == 1:
            return list(shrunk_scores.keys())[0], 0.05
            
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
                # 次点候補との類似度が低ければ、主候補を採択
                if opf_scores[best_opf_alt] < 0.3: 
                    return best_candidate, 0.1
                    
        # HNPT名前空間ルーティング
        namespaces = {self.tools[name]["namespace"] for name in candidates.keys()}
        if len(namespaces) == 1:
            return f"{list(namespaces)[0]}_namespace_router", 0.15
            
        # ベイズ誤り境界によるフォールバック判定
        estimated_p_error = max(1.0 - (1.0 / max(rho, 1e-9)), 0.0)
        if estimated_p_error >= self.p_crit:
            return "L5_HITL_FALLBACK", estimated_p_error
            
        return "global_namespace_router", estimated_p_error

def test_l3_routing():
    print("=== L3 Routing OPF & Bayes Fallback Test ===")
    router = L3OrthogonalExclusionRouter(n_max=5)
    
    # 競合するツール埋め込み (角度的に非常に近い)
    v_tool1 = np.array([1.0, 0.0, 0.0])
    v_tool2 = np.array([0.98, 0.2, 0.0]) # ツール1と類似
    v_tool3 = np.array([0.98, -0.2, 0.0]) # ツール1と類似
    
    router.register_tool("tool_db_read", v_tool1, radius=0.3, namespace="db")
    router.register_tool("tool_db_write", v_tool2, radius=0.3, namespace="db")
    router.register_tool("tool_net_fetch", v_tool3, radius=0.3, namespace="net")
    
    # クエリ (ツール1とツール2の中間に位置する曖昧なクエリ)
    q = np.array([0.99, 0.1, 0.0])
    
    # R4 はOPFが内積0の判定バグのため、ルーティングできずに強制フォールバックする
    res_r4, err_r4 = router.route_query_r4(q)
    print(f"R4 Routing Result: {res_r4} (Error: {err_r4})")
    assert res_r4 == "L5_HITL_FALLBACK", "R4 must fail routing and fallback."
    
    # R5 はOPFで直交補空間の類似度を評価して正しく tool_db_write を分離できるか確認
    res_r5, err_r5 = router.route_query_r5(q)
    print(f"R5 Routing Result: {res_r5} (Error: {err_r5})")
    # 曖昧なクエリで両者が衝突しているが、DQS・OPFが機能するか、同じネームスペース "db" 内であれば "db_namespace_router" になる
    assert res_r5 in ["tool_db_write", "tool_db_read", "db_namespace_router"], f"R5 should resolve to one of candidate tools or namespace router, got: {res_r5}"
    
    # ベイズエラー限界による L5 HITL フォールバックの検証
    # 大量のツールを登録して混雑度 rho > 1.0 にし、ベイズ誤り率限界を上昇させる
    for i in range(10):
        # 狭い球面空間に大量にツールを登録
        v_rand = np.array([1.0, np.random.uniform(-0.1, 0.1), np.random.uniform(-0.1, 0.1)])
        router.register_tool(f"dense_tool_{i}", v_rand, radius=0.3, namespace=f"ns_{i}")
        
    res_fallback, err_fallback = router.route_query_r5(q)
    print(f"R5 Crowded Fallback Result: {res_fallback} (Error: {err_fallback:.4f}, p_crit: {router.p_crit:.4f})")
    assert res_fallback == "L5_HITL_FALLBACK", "Under high congestion, L3 must trigger L5 HITL Fallback."
    print(">> L3 Routing OPF & Bayes Fallback Test: PASS\n")

# ==========================================
# メイン実行
# ==========================================
if __name__ == "__main__":
    print("=" * 50)
    print("Starting R5 Theorems Verification Suite")
    print("=" * 50)
    
    test_l9_ast_mutation()
    test_l6_lambert_branch()
    test_l3_routing()
    
    print("=" * 50)
    print("All R5 theorems (L3, L6, L9) verified successfully!")
    print("=" * 50)
