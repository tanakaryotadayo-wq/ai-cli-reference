# Tunnel Calculus: A Formal Framework for Residual Information under Collapse Maps (v5.5 - R5_v9)

## 概要
本仕様書は、自律型AIコーディングエージェントおよびPC上の情報システムに対し、「崩壊写像（Collapse Map）」によって情報を正規化・圧縮しつつ、失われる差分を「残差（Residual）」として保持・復元する計算形式である **「トンネル計算（Tunnel Calculus）」** の数理的定式化およびPC向け応用設計を規定する。

第9周目 (v9) においては、全レイヤー（L1〜L9）の結合方程式（コヒーレンス）が、一般化ポテンシャル $\Psi_{unified}$ の狭義単調減少によって完全に閉じるための **「ポテンシャル重みコヒーレンス条件」** を数理的に明文化し、数値シミュレーションによりその安定収束性を実証する。

---

## 1. トンネル計算 (Tunnel Calculus) の 5大数学コンポーネント

トンネル計算は、情報損失と復元のメタ幾何学を記述するため、以下の5つの数理的構成要素によって定義される。

### A. 局所回転骨格 (Local Rotation Skeleton)
$$J = \begin{pmatrix} 0 & -1 \\ 1 & 0 \end{pmatrix}, \qquad J^2 = -I, \qquad e^{\theta J}$$

### B. 崩壊写像 (Collapse Map)
$$C: A \to B$$

### C. トンネル・セクション (Tunnel Section)
$$t_\alpha: B \to A, \qquad C \circ t_\alpha = \operatorname{id}_B$$

### D. 留数作用素 (Residue Operator)
$$T(f) = \frac{1}{2\pi i} \oint_\gamma f(z) \, dz$$

### E. 整数不変量 (Integer Invariant)
$$N(f) = \frac{1}{2\pi i} \oint_\gamma \frac{f'(z)}{f(z)} \, dz \in \mathbb{Z}$$

---

## 2. PC上での実用プロダクト設計と優先度

$$x \mapsto (C(x), \alpha)$$
*   $C(x)$: 正規化された骨 (`canonical key`)
*   $\alpha$: 潰しても残る差分・例外・署名 (`residual branch`)
*   $t_\alpha(C(x))$: 必要な文脈を復元 (`reconstructor`)

### 優先プロダクト設計
1.  **Tunnel Research Compiler (思考・研究メモの論文化支援)**: メモの学術構造分類と過大評価・未検証事例の残差抽出。
2.  **Tunnel Error Resolver (エラー解決エンジン)**: エラーの標準形と環境固有の残差による動的解決。
3.  **Tunnel Clipboard (クリップボード履歴の意味化)**: コピー種別自動分類と差分統合。

---

## 3. 統合コヒーレンスの方程式系 (v5.5最終定式)

### A. 一般化ポテンシャル関数
L2（ループ履歴）、L7（残余時間 $L(t)$）、L9（自己修復限界 $k$）を統合した一般化ポテンシャル関数 $\Psi_{unified}$ は以下のように定義される。
$$\Psi_{unified}(v_t, \mathcal{H}_t, L(t), k) = \Phi(v_t) + \alpha_{loop} \cdot \mathbb{I}(v_t \in \mathcal{H}_t) + \gamma_{L7} \cdot \left( \frac{1}{\max(L(t), 1e-9)} \right) + \beta_{L9} \cdot (5 - k)$$
ここで、 $\Phi(v_t) = \Phi_{weight} \cdot \text{errors}$ はコアタスクのポテンシャル値（エラー数）である。

### B. ポテンシャル重みコヒーレンス条件 (v9追加)
エージェントが正常な修復プロセスを進めている段階（$\Delta \text{errors} > 0$）において、ポテンシャルが狭義単調減少（$\Psi_{unified}(t+1) < \Psi_{unified}(t)$）してループフリー判定を通過し、誤検知による早期エスカレーション（Zeno動作）を防ぐためには、各重みパラメータが以下の **「ポテンシャル重みコヒーレンス不等式」** を満たさなければならない。
$$\Phi_{weight} \cdot \Delta \text{errors} > \beta_{L9} \cdot \Delta k + \gamma_{L7} \cdot \Delta \left( \frac{1}{L(t)} \right)$$

*   **物理的意味**: エラー解決によって得られる「正の進捗（減衰効用）」が、変異リトライ制限の減少に伴う「負のペナルティ増加」および時間経過による「時間枯渇ペナルティ上昇」の総和を常に上回る必要がある。
*   **不整合時の挙動**: $\Phi_{weight}$ が不十分な場合、エラーが減少しているにもかかわらずバジェット消費と時間経過のペナルティが勝ち、全体のポテンシャルが上昇（$\Psi_{next} > \Psi_{prev}$）してしまうため、システムは「膠着・ループが発生した」と誤検知して実行を強制遮断する。
*   **キャリブレーション値**: シミュレーション検証に基づき、以下の重み設定を標準とする。
    $$\Phi_{weight} = 100.0, \qquad \beta_{L9} = 5.0, \qquad \gamma_{L7} = 10.0$$

---

## 4. Lean 4 検証の限界定義と科学的誠実性

### A. Lean 4 の役割の適正化
Lean 4 は「定義された型システムと公理系内における論理的ステップの整合性（バグ排除）」を保証するが、理論自体の「新規性」「物理的妥当性」「数学的重要度」は保証しない。人間による批評と数学的評価を必須とする。

### B. 未検証事例の引用制限
Mathlib公式等で広く承認されていないプレプリント（双子素数予想の反証等）は排除し、独立研究者は「論文、形式検証コード、再現可能な環境」を同時に公開することを信頼の要件とする。

---

## 5. 実行エンジン実装検証 (verify_r5_theorems_v9.py)

本仕様のポテンシャル重みコヒーレンス不等式を適用した統合テスト `test_full_9_layer_coherence_loop()` を `verify_r5_theorems_v9.py` に実装し、実行検証を行った。

### 検証結果
*   **コヒーレンスループの単調減少実証**:
    *   初期状態 ($\Psi_{Cycle0} = 400.0333$) からエラーの減少に伴い、ポテンシャルが $\Psi_{Cycle1} = 305.0357 \to 210.0385 \to 115.0417 \to 20.0455$ と狭義単調減少して正常に収束に向かうことを実証。
    *   エラーが0に収束した後はポテンシャルが低位安定し、余計な Zeno 動作（早期遮断）を起こさないことを確認。
*   **L3 スケーリング不整合修正およびその他の全定理**: 100% PASS。
