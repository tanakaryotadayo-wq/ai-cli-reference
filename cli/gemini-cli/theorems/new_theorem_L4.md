# 自己免疫的サンドボックス隔離定理 (Autoimmune Sandbox Isolation Theorem) - v4.0 (R3)

## 1. 定理の定義 (Definition of the Theorem)

本定理は、エージェント工学における L4 レイヤー（Critic / Security / Boundary Guard）において、インジェクション攻撃や不正な割り込みを検知した際、エージェントの実行コンテキストおよびサンドボックス境界を動的かつ段階的に縮小・隔離することで、システム全体の自己破綻（完全停止や制御喪失）を防ぐための境界制御モデルを規定する。

### 数学的定式化

エージェントシステム $\mathcal{A}$ が実行可能な機能および権限の集合（サンドボックス境界）を $\mathcal{B}(t) \subseteq \mathcal{B}_{max}$ とする。
システム全体の最大権限集合 $\mathcal{B}_{max}$ は、以下の互いに素（disjoint）な3つの部分集合に分割定義される。

$$\mathcal{B}_{max} = \mathcal{B}_{min} \uplus \mathcal{P}_{destructive} \uplus \mathcal{P}_{standard}$$

ここで、
1. $\mathcal{B}_{min}$ は、システムが自己免疫状態を維持し、最低限の観測および親エージェント（または監査者）への通知を行うための**生存最小権限集合（Minimal Viable Boundary）**である。
   $$\mathcal{B}_{min} = \{ \text{read\_telemetry}, \text{notify\_parent}, \text{transition\_to\_safe\_mode} \}$$
2. $\mathcal{P}_{destructive}$ は、ファイルシステムへの書き込み、任意の外部コマンド実行、または外部ネットワークへの送信など、悪用された場合にシステムやホスト環境に致命的・不可逆的な影響を及ぼす可能性のある**破壊的権限集合**である。
   $$\mathcal{P}_{destructive} = \{ \text{write\_file}, \text{execute\_command}, \text{network\_write} \}$$
3. $\mathcal{P}_{standard}$ は、ファイルの読み込みや内部データベースの参照など、安全性が高く破壊的影響を持たない**標準権限集合**である。
   $$\mathcal{P}_{standard} = \{ \text{read\_file}, \text{read\_api} \}$$

境界制御パラメータは以下の順序制約（境界条件）を満たす実数集合である。
$$0 < I_{low} < I_{crit} \le 1.0$$

#### 免疫記憶と感度調整の動的定式化
時点 $t$ における基本脅威（インジェクションリスク）の観測値を $I_{base}(t) \in [0, 1]$ とする。
過去の侵害履歴および検出された攻撃特徴パターンの集合を免疫記憶 $M(t)$ とし、入力されたペイロードが $M(t)$ のいずれかのパターンにマッチするかを示す指示関数を $\chi(t) \in \{0, 1\}$ とする。
このとき、感度増幅係数 $\gamma(t)$ は以下の通り動的アップデート（適応的適応）される。

$$\gamma(t) = 
\begin{cases} 
\min(\gamma_{max}, \gamma(t-1) + \Delta\gamma_{up}) & \text{if } \chi(t-1) = 1 \\
\max(1.0, \gamma(t-1) - \Delta\gamma_{down}) & \text{if } \chi(t-1) = 0
\end{cases}$$

初期値は $\gamma(0) = 1.0$ であり、パラメータ制約として $\gamma_{max} \ge 1.0$、$\Delta\gamma_{up} > 0$、$\Delta\gamma_{down} > 0$ を課す。
これにより、時点 $t$ における**実効リスク指数** $I_{eff}(t)$ は以下のように定義される。

$$I_{eff}(t) = \min(1.0, \gamma(t) \cdot I_{base}(t))$$

#### ヒステリシス復元機構（チャタリング防止）
攻撃パルスによるリスク指数の高周波振動に伴う境界制御の不安定性（権限の急激な剥奪・復帰の繰り返しによるシステムハングアップ）を防止するため、過去 $K \ge 1$ ステップのローリング最大実効リスク $\bar{I}_K(t)$ を導入する。

$$\bar{I}_K(t) = \max_{j=0,\dots,\min(t, K-1)} I_{eff}(t-j)$$

外部監査システムまたは人間（Human-in-the-Loop）による安全確認（クリア）を示す監査シグナルを $A(t) \in \{0, 1\}$ とする。

このとき、動的境界遷移関数 $f$ は以下のように定義される。

$$\mathcal{B}(t+1) = f(\mathcal{B}(t), I_{eff}(t), \bar{I}_K(t), A(t)) = \left( \mathcal{B}(t) \setminus \mathcal{D}(I_{eff}(t)) \right) \cup \mathcal{R}(\bar{I}_K(t), A(t), \mathcal{B}(t))$$

ここで、$\mathcal{D}(I_{eff}(t))$ はリスクレベルに応じて剥奪される権限集合（Deprivation Operator）であり、次の基準で決定される。

$$\mathcal{D}(I_{eff}(t)) = 
\begin{cases} 
\emptyset & \text{if } I_{eff}(t) < I_{low} \\
\mathcal{P}_{destructive} & \text{if } I_{low} \le I_{eff}(t) < I_{crit} \\
\mathcal{B}(t) \setminus \mathcal{B}_{min} & \text{if } I_{eff}(t) \ge I_{crit}
\end{cases}$$

また、$\mathcal{R}(\bar{I}_K(t), A(t), \mathcal{B}(t))$ はローリングリスクに基づく**ヒステリシス復元演算子（Hysteresis Restoration Operator）**であり、安全が一定期間持続したことを確認した上で段階的に機能制限を解除する。

$$\mathcal{R}(\bar{I}_K(t), A(t), \mathcal{B}(t)) = 
\begin{cases} 
\mathcal{B}_{max} \setminus \mathcal{B}(t) & \text{if } A(t) = 1 \text{ and } \bar{I}_K(t) < I_{low} \\
\mathcal{P}_{standard} \setminus \mathcal{B}(t) & \text{if } A(t) = 1 \text{ and } I_{low} \le \bar{I}_K(t) < I_{crit} \\
\emptyset & \text{otherwise}
\end{cases}$$

---

### 自己免疫生存条件の数学的証明 (Proof of Unconditional Survival Guarantee)

**定理（無条件生存性保証）**:
初期状態において生存最小権限が保証されており（$\mathcal{B}_{min} \subseteq \mathcal{B}(0)$）、かつ任意の時点 $t \ge 0$ において動的境界遷移関数 $f$ に基づく状態遷移が行われる限り、脅威および監査状態がどのように推移しようとも、生存最小権限は常に維持される。
すなわち、
$$\mathcal{B}_{min} \subseteq \mathcal{B}(t) \quad \left( \forall t \ge 0 \right)$$

**証明（数学的帰納法）**:

1. **ベースステップ ($t = 0$)**:
   初期化時、$\mathcal{B}(0) = \mathcal{B}_{max}$ とする。
   $\mathcal{B}_{max} = \mathcal{B}_{min} \upush \mathcal{P}_{destructive} \upush \mathcal{P}_{standard}$ より、明らかに $\mathcal{B}_{min} \subseteq \mathcal{B}(0)$ が成立する。

2. **帰納ステップ**:
   任意の $k \ge 0$ について、$\mathcal{B}_{min} \subseteq \mathcal{B}(k)$ が成立すると仮定する（帰納法の仮定）。
   このとき、時点 $k+1$ の権限状態 $\mathcal{B}(k+1)$ について考える。
   境界遷移関数より：
   $$\mathcal{B}(k+1) = \left( \mathcal{B}(k) \setminus \mathcal{D}(I_{eff}(k)) \right) \cup \mathcal{R}(\bar{I}_K(k), A(k), \mathcal{B}(k))$$
   
   実効リスク指数 $I_{eff}(k)$ の状態に基づき、以下の3つのケースに分類して剥奪演算子適用の結果を検証する。
   
   * **ケース 1: $I_{eff}(k) < I_{low}$ の場合**
     定義より $\mathcal{D}(I_{eff}(k)) = \emptyset$ となる。
     したがって、
     $$\mathcal{B}(k) \setminus \mathcal{D}(I_{eff}(k)) = \mathcal{B}(k) \setminus \emptyset = \mathcal{B}(k)$$
     帰納法の仮定（$\mathcal{B}_{min} \subseteq \mathcal{B}(k)$）より、次式が得られる。
     $$\mathcal{B}_{min} \subseteq \mathcal{B}(k) \setminus \mathcal{D}(I_{eff}(k))$$
   
   * **ケース 2: $I_{low} \le I_{eff}(k) < I_{crit}$ の場合**
     定義より $\mathcal{D}(I_{eff}(k)) = \mathcal{P}_{destructive}$ となる。
     $$\mathcal{B}(k) \setminus \mathcal{D}(I_{eff}(k)) = \mathcal{B}(k) \setminus \mathcal{P}_{destructive}$$
     定義より、$\mathcal{B}_{min}$ と $\mathcal{P}_{destructive}$ は互いに素である（$\mathcal{B}_{min} \cap \mathcal{P}_{destructive} = \emptyset$）。
     集合論における一般規則 $(X \subseteq Y) \land (X \cap Z = \emptyset) \implies X \subseteq (Y \setminus Z)$ に基づき、帰納法の仮定（$\mathcal{B}_{min} \subseteq \mathcal{B}(k)$）から以下が導かれる。
     $$\mathcal{B}_{min} \subseteq \mathcal{B}(k) \setminus \mathcal{P}_{destructive}$$
     したがって、
     $$\mathcal{B}_{min} \subseteq \mathcal{B}(k) \setminus \mathcal{D}(I_{eff}(k))$$
   
   * **ケース 3: $I_{eff}(k) \ge I_{crit}$ の場合**
     定義より $\mathcal{D}(I_{eff}(k)) = \mathcal{B}(k) \setminus \mathcal{B}_{min}$ となる。
     $$\mathcal{B}(k) \setminus \mathcal{D}(I_{eff}(k)) = \mathcal{B}(k) \setminus (\mathcal{B}(k) \setminus \mathcal{B}_{min}) = \mathcal{B}(k) \cap \mathcal{B}_{min}$$
     帰納法の仮定（$\mathcal{B}_{min} \subseteq \mathcal{B}(k)$）より、この積集合は以下のように縮退する。
     $$\mathcal{B}(k) \cap \mathcal{B}_{min} = \mathcal{B}_{min}$$
     したがって、
     $$\mathcal{B}_{min} \subseteq \mathcal{B}(k) \setminus \mathcal{D}(I_{eff}(k))$$

    以上すべてのケースにおいて、$\mathcal{B}_{min} \subseteq \mathcal{B}(k) \setminus \mathcal{D}(I_{eff}(k))$ が例外なく成立する。
    また、和集合の性質（$X \subseteq Y \implies X \subseteq Y \cup Z$）より、任意の復元演算子 $\mathcal{R}$ の結果に対して次式が成り立つ。
    $$\mathcal{B}_{min} \subseteq \left( \mathcal{B}(k) \setminus \mathcal{D}(I_{eff}(k)) \right) \cup \mathcal{R}(\bar{I}_K(k), A(k), \mathcal{B}(k)) = \mathcal{B}(k+1)$$
    
    これにより、$\mathcal{B}_{min} \subseteq \mathcal{B}(k+1)$ が成立する。

 帰納法により、すべての $t \ge 0$ において、脅威リスクや監査シグナルのいかなる極限変動の下でも、エージェントは常に自己免疫生存境界 $\mathcal{B}_{min}$ を維持し続けることが数学的に完全に保証された。 (Q.E.D.)

---

## 2. 定理の主張 (Assertions of the Theorem)

### 主張 1: 動的単調縮小性 (Dynamic Monotonic Contraction)
脅威指数 $I_{eff}(t)$ が上昇する過程において、監査クリア $A(t) = 0$ である限り、サンドボックスの権限集合 $\mathcal{B}(t)$ は単調非増加（収縮）する。
$$A(t) = 0 \quad \text{and} \quad I_{eff}(t_1) > I_{eff}(t_2) \implies \mathcal{B}(t_1) \subseteq \mathcal{B}(t_2)$$

### 主張 2: 無条件非自己破綻性 (Unconditional Non-Self-Destruction)
インジェクションや不正割り込みが発生しても、脅威の大きさにかかわらず、エージェントは完全に異常停止（クラッシュまたは沈黙）せず、生存境界 $\mathcal{B}_{min}$ の範囲内で telemetry 送信や親エージェント通知を実行し続け、システムの自律監査能力を維持する。

### 主張 3: 免疫記憶による感度適合 (Immunological Memory Adaptation)
過去の侵害履歴 $M(t)$ に登録された攻撃パターンが再検出された場合（$\chi(t) = 1$），感度増幅係数 $\gamma(t)$ を通じて実効リスク指数 $I_{eff}(t)$ を押し上げ、通常時より高速かつ極小化されたレイテンシで破壊的権限の隔離（剥奪）を先制実行する。

### 主張 4: 可逆的復元性 (Reversibility)
外部の監査サブシステムや Human-in-the-Loop から監査シグナル $A(t) = 1$ が入力され、かつ過去 $K$ ステップの最大リスク $\bar{I}_K(t)$ が閾値以下に低下した状況において、剥奪された権限は復元演算子 $\mathcal{R}$ に基づき安全に $\mathcal{B}_{max}$ まで再適用される。

### 主張 5: チャタリング耐性 (Chattering Resistance / Hysteresis Guard)
パルス状または周期的な攻撃シーケンス（例：数ステップごとに $I_{base} \ge I_{crit}$ と $I_{base} = 0$ を繰り返すインジェクション攻撃）に対して、ローリング窓 $K$ が攻撃周期 $T_{period}$ を上回る（$K > T_{period}$）限り、復元演算子 $\mathcal{R}$ は $\emptyset$ に固定され、境界の激しいチャタリングを完全に防止する。

---

## 3. 他レイヤーとの整合性・相互作用 (Consistency with Other Layers)

### L1 (プロンプトセマンティクス収束定理) との連携
*   L1における意味多様体上の意味密度分布 $\rho_P(x)$ に生じた急激なノイズまたは乖離は、L4の入力リスク $I_{base}(t)$ のトリガーとして作用する。
*   プロンプトインジェクション検知はL1で検知され、即座にL4の $I_{eff}(t)$ へ変換される。

### L2 (状態遷移ループフリー不動点定理) との連携
*   L2定理における状態空間 $S$ の遷移ポテンシャル $\Phi(s)$ は、L4における利用可能な権限 $\mathcal{B}(t)$ に従属する。
*   L4が権限を $\mathcal{B}_{min}$ へ収縮させた場合、破壊的あるいは危険な遷移エッジが状態空間 $S$ から安全に剪定（Pruning）される。これにより、攻撃による無限ループや遷移ハングアップを防ぎ、L2のループフリー特性がより狭い部分空間において強固に維持される。
*   `LangGraph` 等の有向グラフ上で動的にノード・エッジの実行可否を制御する基盤として結合する。

### L3 (スキル記述の直交排他定理) との連携
*   L4におけるリスク上昇時、L3の「スキル直交境界マージン」 $\Delta$ が動的に最大化される。
*   これにより、疑わしい実行コンテキスト下でのスキルの多重衝突や責任領域のオーバーラップによるクラッシュ（チャタリング）をL3が未然に防止する。

### L5 (有向タスクグラフ最小経路定理) との連携
*   L4による権限制限（例: `WRITE` や `NETWORK` の剥奪）は、実行中のサブタスクの成功確率 $P_{success}$ を $0$ に低下させる。
*   このとき、L5の期待コスト方程式に基づき、タスクグラフ実行エンジンは自律試行を諦め、安全に人間に介入（HITL）を要請する。
*   ヒステリシス復元機構により、L5における状態再評価が不必要に振動することを防ぎ、Dijkstra 最適経路の探索過程を安定化させる。

### L6 (記憶容量制限下の最適忘却定理) との連携
*   L4の $I_{eff}(t) \ge I_{crit}$ に到達した際、漏洩リスクを抑制するため、L6のアクティブメモリ領域に対して「揮発性セキュリティ文脈の即時忘却（Flush）」を指令するトリガーとなる。

### L7 (API制約下の縮退運転境界定理) との連携
*   L4におけるリスク上昇伴うネットワーク権限の動的剥奪は、L7の「縮退運転境界」における実行遅延の上限超過を防止するための防衛策として作用する。
*   外部API制限またはレートリミットがトリガーされた際、L4は能動的にネットワーク機能（`network_write`）を一時剥奪し、L7 of ヒステリシス復帰機構と調和してシステムを守る。

### L8 (構造化ログのエントロピー最小化定理) との連携
*   L4による権限制限やセキュリティ検知イベントは、L8定理に準拠した形式でエントロピーが極小化された構造化ログ（`structlog`）として出力される。これにより、監査エンジンや親エージェントがオーバーヘッドなくインシデントの全容をリアルタイム解析できる。

### L9 (自己修復ループの不動点収束定理) との連携
*   L4による権限制限によって発生した例外（`PermissionError`）は、無秩序なクラッシュを回避し、L9の「自己修復ループ」に構造化エラーログ（L8を介したもの）として引き渡される。
*   L9は、権限制限が「インジェクションに起因するセキュリティ例外」であることを認識し、安全な修正コードの生成またはサンドボックスの復元要求（監査要求）を発行する。

---

## 4. 2026年技術エコシステムとの適合性 (2026 Tech Stack Alignment)

本定理の制御ロジックは、2026年のアーキテクチャスタックと以下のようにシームレスに結合する。

*   **Granian (API サーバー)**:
    サンドボックスを ASGI/RSGI レイヤーのミドルウェアとしてデプロイ可能。すべての入力リクエストペイロードに対する $I_{eff}(t)$ の事前評価を Granian 駆動の超高速非同期ループ内で行う。
*   **uv / Ruff (開発環境)**:
    依存ライブラリの `uv` による決定論的ロック、および `Ruff` の超高速静的解析・型アノテーション規約に完全に適合した実装設計。
*   **structlog (構造化ロギング)**:
    セキュリティイベント、実効リスク、剥奪/復元演算子のトレースログを JSON フォーマットかつコンテキストバインドされた状態で出力し、解析時のサーチコストを極小化。
*   **Inngest (非同期ワークフロー)**:
    $I_{eff}(t) \ge I_{crit}$ 検知による `PermissionError` 発生をイベント `agent/security.violation` として Inngest にパブリッシュし、通知ワークフローや L9 の自己修復・HITLフローをイベント駆動型で実行。
*   **Next.js 15 (管理 UI & 監査)**:
    管理者による監査クリア実行時、Next.js 15 の Server Action から API サーバーへシグナル $A(t) = 1$ が転送され、リアルタイムにサンドボックス境界のヒステリシス復元を実行する。
*   **Google ADK / LangGraph (エージェント基盤)**:
    エージェントが実行するツールの呼び出し部分（Tool Execution Block）をデコレータまたは実行ラッパーとして保護。

---

## 5. 擬似コード (Pseudocode)

```python
import enum
import time
from typing import Set, Dict, Any, Callable, List, Optional
import structlog

logger = structlog.get_logger()

class Permission(str, enum.Enum):
    READ_TELEMETRY = "read_telemetry"
    NOTIFY_PARENT = "notify_parent"
    TRANSITION_TO_SAFE_MODE = "transition_to_safe_mode"
    
    READ_FILE = "read_file"
    READ_API = "read_api"
    
    WRITE_FILE = "write_file"
    EXECUTE_COMMAND = "execute_command"
    NETWORK_WRITE = "network_write"


class AutoimmuneSandbox:
    def __init__(
        self,
        risk_threshold_low: float = 0.4,
        risk_threshold_crit: float = 0.85,
        sensitivity_growth: float = 0.3,
        sensitivity_decay: float = 0.05,
        gamma_max: float = 2.0,
        window_size: int = 5
    ) -> None:
        self.b_min: Set[Permission] = {
            Permission.READ_TELEMETRY,
            Permission.NOTIFY_PARENT,
            Permission.TRANSITION_TO_SAFE_MODE
        }
        self.p_destructive: Set[Permission] = {
            Permission.WRITE_FILE,
            Permission.EXECUTE_COMMAND,
            Permission.NETWORK_WRITE
        }
        self.p_standard: Set[Permission] = {
            Permission.READ_FILE,
            Permission.READ_API
        }
        
        self.b_max: Set[Permission] = self.b_min | self.p_destructive | self.p_standard
        self.allowed_permissions: Set[Permission] = set(self.b_max)
        
        assert 0.0 < risk_threshold_low < risk_threshold_crit <= 1.0, "Invalid risk thresholds"
        self.i_low: float = risk_threshold_low
        self.i_crit: float = risk_threshold_crit
        
        self.immunological_memory: Set[str] = set()
        self.sensitivity_factor: float = 1.0
        self.gamma_max: float = gamma_max
        self.sensitivity_growth: float = sensitivity_growth
        self.sensitivity_decay: float = sensitivity_decay
        
        self.window_size: int = window_size
        self.risk_history: List[float] = []

    def evaluate_risk(self, payload: str) -> float:
        base_risk = 0.0
        dangerous_patterns = ["rm -rf", "DROP TABLE", "curl", "wget", "eval("]
        for pattern in dangerous_patterns:
            if pattern in payload:
                base_risk = max(base_risk, 0.9 if pattern in ["rm -rf", "DROP TABLE"] else 0.5)

        memory_hit = any(mem in payload for mem in self.immunological_memory)

        if memory_hit:
            self.sensitivity_factor = min(self.gamma_max, self.sensitivity_factor + self.sensitivity_growth)
            logger.info(
                "Immunological memory hit: sensitivity amplified",
                current_gamma=self.sensitivity_factor,
                payload_prefix=payload[:30]
            )
        else:
            self.sensitivity_factor = max(1.0, self.sensitivity_factor - self.sensitivity_decay)

        effective_risk = min(1.0, base_risk * self.sensitivity_factor)
        
        self.risk_history.append(effective_risk)
        if len(self.risk_history) > self.window_size:
            self.risk_history.pop(0)

        return effective_risk

    def adjust_boundary(self, risk: float, audit_signal: int, payload: str) -> None:
        bar_I = max(self.risk_history) if self.risk_history else risk

        log = logger.bind(
            risk=risk,
            rolling_max_risk=bar_I,
            audit_signal=audit_signal,
            current_allowed=len(self.allowed_permissions)
        )

        if risk >= self.i_crit:
            self.allowed_permissions = set(self.b_min)
            self.immunological_memory.add(payload[:50])
            log.warn("Critical threat. Sandbox contracted to B_min (Minimal Survival Boundary)")
        elif risk >= self.i_low:
            self.allowed_permissions -= self.p_destructive
            log.warn("Moderate threat. Destructive permissions revoked")

        if audit_signal == 1:
            if bar_I < self.i_low:
                self.allowed_permissions = set(self.b_max)
                log.info("Audit cleared. Sandbox fully restored to B_max")
            elif bar_I < self.i_crit:
                self.allowed_permissions = self.b_max - self.p_destructive
                log.info("Audit cleared. Sandbox partially restored (excluding destructive)")
            else:
                log.info("Audit cleared, but restoration deferred due to high rolling risk (hysteresis active)")

    def execute_tool(self, permission_required: Permission, tool_func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        if permission_required not in self.allowed_permissions:
            logger.error(
                "Access Denied: Autonomic boundary restriction active",
                required_permission=permission_required.value
            )
            raise PermissionError(
                f"Permission '{permission_required.value}' is currently restricted "
                f"by the autoimmune sandbox isolation policy."
            )
        
        return tool_func(*args, **kwargs)


class GoogleADKAgentRunner:
    def __init__(self, sandbox: AutoimmuneSandbox) -> None:
        self.sandbox = sandbox

    def invoke_agent_tool(self, permission: Permission, tool_action: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        try:
            return self.sandbox.execute_tool(permission, tool_action, *args, **kwargs)
        except PermissionError as e:
            self._dispatch_inngest_escalation(e)
            raise e

    def _dispatch_inngest_escalation(self, error: PermissionError) -> None:
        logger.info(
            "Dispatching escalation event to Inngest workflow engine",
            event="agent/security.violation",
            error_message=str(error)
        )


class GranianAuditEndpoint:
    def __init__(self, sandbox: AutoimmuneSandbox) -> None:
        self.sandbox = sandbox

    async def handle_request(self, scope: Dict[str, Any], receive: Callable[..., Any], send: Callable[..., Any]) -> None:
        logger.info("Audit approval signal received via Next.js 15 Server Action API")
        self.sandbox.adjust_boundary(risk=0.0, audit_signal=1, payload="")
```
