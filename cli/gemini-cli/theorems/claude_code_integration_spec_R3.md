# Claude Code 9レイヤー定理統合アーキテクチャ仕様書 (v4.0 - R3)

## 概要
本仕様書は、自律型AIコーディングエージェントである **Claude Code** に対し、本プロジェクトで確立した「エージェント工学 9レイヤー定理（L1〜L9）」を適用し、自律実行ループの信頼性、リソース効率、セキュリティ、およびエラー自己修復性能を極限まで高めるための統合アーキテクチャ設計を規定する。
特に第3ラウンド（R3）においては、各種パラメータ（リソース、時間、バジェット、意味空間）が臨界値に達した極限状態における、各レイヤー間の数理的コヒーレンスと相転移ダイナミクスを厳密化した。

---

## 1. 各レイヤー定理の Claude Code への適用設計

### [L1] プロンプトセマンティクス収束定理の適用 (R3)
*   **ユースケース**: Claude Code がユーザーからの曖昧な指示や大規模なファイル差分等のコンテキストを処理する際、情報の過圧縮による決定境界の崩壊（ハルシネーション）や、過希釈によるアテンション散逸（指示無視）を未然に防止する。
*   **適用モデル**:
    Claude Code が LLM を呼び出す直前に介入する **L1-Semantics-Interceptor** を配置。
    ローカル推論環境（Mac Studio 上の MLX-LM）によるアテンションマップから得られるアテンションエントロピーに基づき、アテンション散逸係数 $\chi(L)$ を算出：
    $$\chi(L) = \frac{\bar{H}(\mathcal{A})}{\log(L + c)}$$
    （ここで $\bar{H}(\mathcal{A}) = \frac{1}{L} \sum_{i=1}^L H_i(\mathcal{A})$ は平均アテンションエントロピー、$c > 1$ は正則化定数）。
    これを用いて、有効意味情報量 $I(P)$ および表現密度 $\mathcal{D}(P) = I(P)/L$ を動的に算出する：
    $$I(P) = (1 - \chi(L)) \sum_{t_i \in P_{concept}} - \log_2 P(t_i \mid t_{<i})$$
    *   **過圧縮領域 ($\mathcal{D}(P) > \mathcal{D}_c$)**:
        指示の詰め込みすぎによる解釈崩壊を防ぐため、コード差分の省略記法を完全展開し、AST構造と型制約（Type Assertions）を明示的に補強するテンプレート拡張を実行。
    *   **過希釈領域 ($\mathcal{D}(P) < \mathcal{D}_{opt}$)**:
        アテンション散逸を防ぐため、重複表現のパージ、ボイラープレートの削除、および Ruff AST パーサーを用いた不要コードブロック・冗長コメントの静的パージを実行。
    *   **極限境界条件での整合性**:
        *   **無限コンテキスト極限 ($L \to \infty$)**: $\chi(L) \to 1 \implies I(P) \to 0 \implies \mathcal{D}(P) \to 0$ となり、安定性 $\mathcal{S}(P) \to 0$ に収束する（Lost in the Middle 現象の数理的裏付け）。
        *   **単一トークン極限 ($L \to 1$)**: $\chi(1) = 0 \implies \mathcal{D}(P) = I(P)$ となるが、コンテキスト構造を欠くため、微小摂動で $\mathcal{S}(P) \to 0$ となり不安定化が正しくシミュレートされる。
    *   **一貫性と観測性 (structlog適合)**:
        監査結果は、キー値ペアで構造化されたログ（`structlog.get_logger().info("prompt_semantics_audited", token_length=length, attention_dissipation=chi, representation_density=d_p, measured_stability=s_p, status=status)`）を経て L8 構造化ログへ完全統合され、すべてのインターセプター実装は Ruff の厳格な型アノテーション・静的検査に準拠する。

### [L2] 状態遷移ループフリー不動点定理の適用 (R3)
*   **ユースケース**: Claude Code がテスト修正やコマンド試行を行う際、同一の状態を往復する循環ループ（有向閉路）を排除し、有限ステップで目標不動点（テスト通過、エラーゼロ）に収束させる。
*   **適用モデル**:
    統合多次元状態空間 $\mathcal{V}$ の状態ベクトル $v = (s, k, \Gamma, I)$ （$s$: 機能状態、$k$: リトライ制限、$\Gamma$: APIリミット残量、$I$: セキュリティリスク）を定義。
    目標不動点 $v^*$ への到達最小期待総コストに一致するポテンシャル関数 $\Phi(v) = w_e E(v) + w_t T(v) + w_r R(v)$ を導入（$E(v)$ はエラー局所性強度、$T(v)$ はテスト不合格数、$R(v)$ はリスク指数）。
    通常遷移 $T_p$ と縮退遷移 $T_{\text{deg}}$ 間の双方向循環ループ（チャタリング）を防止するため、過去の遷移履歴 $\mathcal{H}_t = \{v_0, \dots, v_{t-1}\}$ に基づくペナルティ項を加味した**拡張ポテンシャル関数 $\Psi(v_t, \mathcal{H}_t)$** を定義する：
    $$\Psi(v_t, \mathcal{H}_t) = \Phi(v_t) + \alpha \cdot \mathbb{I}(v_t \in \mathcal{H}_t)$$
    ここで $\alpha > \max_{v} \Phi(v)$ は極大定数、$\mathbb{I}$ は指示関数である。
    各ステップの遷移において、通常遷移の進捗がポテンシャル減少下限 $\delta_{\text{threshold}}$ 未満（$\Psi(v_t, \mathcal{H}_t) - \Psi(T_p(v_t, a_t), \mathcal{H}_t \cup \{v_t\}) < \delta_{\text{threshold}}$）となる場合、システムは**一様縮退遷移 $T_{\text{deg}}(v_t)$** へ相転移する：
    一様縮退遷移 $T_{\text{deg}}(v_t)$ は、以下のいずれかのアクションによって拡張ポテンシャル $\Psi$ の狭義単調減少を強制する：
    1. **ロールバック型縮退**: 状態を以前の安定状態 $v_{safe}$ に戻し、かつ探索空間の解解像度を粗くすることで状態数を縮小し、$\Phi(v_{t+1}) < \Phi(v_t)$ を達成。
    2. **モード退行**: クラウドAPIからローカルLLM（MLX-LM）によるテンプレート適用等の決定論的動作モード $M_{i+1}$ へ移行し、遷移確率を $1.0$ に固定。
    3. **エスカレーション**: 終端エスカレーション状態 $v_{esc}$ （$\Phi(v_{esc}) = 0$ とみなし、ワークフローを即座に停止）への強制遷移。
*   **2026年技術エコシステム適合**:
    *   Inngest ワークフロー統合：非同期ステップ実行時の状態変化監視ミドルウェアを実装し、Inngest の `step.run` に割り込んで状態ベクトルのハッシュ履歴から循環遷移を検知、即座にサイクルを破壊する。
    *   Next.js 15 & Granian 連携：`FastAPI (Granian)` からポテンシャル値 $\Phi(v)$ の推移データを Server Actions 経由で Next.js 15 のクライアント側ダッシュボードへストリーミング転送し、リアルタイム可視化。

### [L3] スキル記述の直交排他定理の適用 (R3)
*   **ユースケース**: Claude Code が持つツール群（ファイル編集、コマンド実行、リサーチ等）の説明文（Description）が類似・重複し、モデルが誤ったツールを選択して不要な処理を実行（衝突・チャタリング）するのを防止する。
*   **適用モデル**:
    意味空間を $D$ 次元単位球面 $\mathcal{V} = \mathbb{S}^{D-1}$ とする。各ツール $T_i$ について、機能説明文 $D_i$ の意味埋め込みベクトルを $\mathbf{v}_i = \text{Embed}(D_i) \in \mathcal{V}$ とする。
    異なるツールペア $T_i, T_j$ ($i \neq j$) において、決定境界の衝突を排除するための境界十分条件は、両者の活性化球帽（活性化半径 $\theta_i, \theta_j$）が互いに素であることである：
    $$d(\mathbf{v}_i, \mathbf{v}_j) > \theta_i + \theta_j = z_{1-\epsilon}(\sigma_i + \sigma_j)$$
    ここで $d(\mathbf{x}, \mathbf{y}) = \arccos(\mathbf{x} \cdot \mathbf{y})$ は球面上の角度距離、$\sigma_k = \sqrt{\sigma_{emb}^2 + \sigma_{q, k}^2}$ である（$z_{1-\epsilon}$ は信頼係数、$\sigma_{emb}^2$ は埋め込みノイズ分散、$\sigma_{q, k}^2$ はクエリセマンティクス多様性分散）。
    *   **球面パッキング限界境界 ($N \to N_{max}$)**:
        最小活性化半径 $\theta_{min}$ において配置可能な最大登録ツール数 $N_{max}$ を以下で画定する：
        $$N \le N_{max}(\theta_{min}) \approx \left( \frac{1}{\sin \theta_{min}} \right)^{D-1}$$
        $N \to N_{max}$ に近接する場合、静的境界は破綻し、動的信頼度圧縮（DQS）を強制発動する。
    *   **セマンティックマージン崩壊極限 ($\Delta_{ij} \ge d(\mathbf{v}_i, \mathbf{v}_j)$)**:
        ノイズまたは多様性の極大化によりマージンがツール間距離を超えた場合、最近傍ルーティングの分類誤り率 $P_{error}$ は以下のようにベイズ制限に拘束される：
        $$P_{error} = \frac{1}{2} \text{erfc}\left( \frac{d(\mathbf{v}_i, \mathbf{v}_j)}{2\sqrt{2}\bar{\sigma}} \right) \quad \left(\bar{\sigma} = \frac{\sigma_i + \sigma_j}{2}\right)$$
        このとき、重複領域での決定不能チャタリングを防ぐため、ADK フックにおいて直交射影フィルタリング（OPF）および階層的名前空間転移を実行する。
*   **直交排他を達成するツール説明文（Negative Constraints）の強制適用**:
    *   `view_file` の説明文: "Displays the contents of a file. Use ONLY when the exact file path is known and direct reading is required. DO NOT use if you need to find, search, or list files."
    *   `grep_search` の説明文: "Searches for patterns inside file contents. Use ONLY when performing pattern matching or locating specific strings. DO NOT use to read the full content of a known file path."
*   **2026年技術エコシステム適合**:
    *   Google ADK ライフサイクルフック統合：
        1. **登録時バリデーションフック (Register-time validation)**: `@tool` デコレータ実行時に直交境界違反および限界収容数オーバーを監査し、違反検知時は起動をブロックする。
        2. **動的衝突回避フック (ADK `pre_route`)**: クエリ $\mathbf{q}$ に対する判定エントロピー $\mathcal{H}$ が閾値 $\mathcal{H}_{crit}$ を超過した場合、以下のステップで制御ダイナミクスを収束させる：
            *   **Step 1: 動的信頼度圧縮 (DQS)**: 混雑度 $\rho = N / N_{max}$ に応じて信頼係数を縮小：$z'_{1-\epsilon} = z_{1-\epsilon} \cdot (1 - \rho)^\gamma$
            *   **Step 2: 直交射影フィルタリング (OPF)**: 最有力ツール以外の干渉ベクトル成分を射影排除し、再ルーティング：
                $$\mathbf{q}' = \mathbf{q} - \sum_{k \neq \text{argmax}(p)} (\mathbf{q} \cdot \mathbf{v}_k) \mathbf{v}_k, \quad \mathbf{q}'' = \frac{\mathbf{q}'}{\|\mathbf{q}'\|}$$
            *   **Step 3: 階層的名前空間相転移 (HNPT)**: 類似ツールを同一 Namespace にクラスタリングし、ルーティングを2段階（Global / Local Sub-Router）に分離する。
            *   **Step 4: L5 HITLエスカレーション**: すべての相転移レイヤーで決定不能な場合、L5定理の介入閾値 $\theta$ を強制的に下回らせ、自律ループから人間への介入要求をトリガーする。

### [L4] 自己免疫的サンドボックス隔離定理の適用 (R3)
*   **ユースケース**: Claude Code が任意のシェルコマンドを実行したりファイルを編集したりする際、インジェクション攻撃やホストシステムの破壊的命令を検知し、安全に実行制限・隔離を行う。
*   **適用モデル**:
    Claude Code のツール実行エンジンに動的サンドボックス **AutoimmuneSandbox** を結合し、実行環境の制御レベル（隔離レベル） $S(t) \in [0, 1]$ （0: 通常, 1: 完全隔離）を管理する。
    1.  **適応的感度調整モデル ($I_{eff}$)**:
        生の脅威検出スコアを $I_{raw}(t)$、過去のインシデント累積による感度増幅項を $\delta_{sens}(t)$ とし、実効リスク指数 $I_{eff}(t)$ を以下で定義する：
        $$I_{eff}(t) = \max\left( I_{raw}(t), \lambda \cdot I_{eff}(t-1) + (1 - \lambda) \cdot \delta_{sens}(t) \right)$$
        ここで $\lambda \in [0.8, 0.95]$ はリスク記憶の半減期を決定する減衰係数である。
    2.  **サンドボックス隔離の制御モデル**:
        隔離レベル $S(t)$ は以下の境界条件で即時かつ非対称に遷移する：
        $$S(t) = \begin{cases} 
        1.0 & \text{if } I_{eff}(t) \ge I_{crit} \\
        \max\left(0, S(t-1) - \Delta S_{recovery}(t)\right) & \text{if } I_{eff}(t) < I_{crit}
        \end{cases}$$
        得られた $S(t)$ に基づき、許容アクション境界 $\mathcal{B}(t)$ を動的に制限する：
        *   $S(t) \ge 0.8$ (最大隔離): `execute_command`, `write_file`, `network_write` を即時ブロックし、生存最小境界 $\mathcal{B}_{min}$（通知および安全なビューイングのみ）に制限。このときエージェントは「安全サスペンド状態 (Suspended Safe State)」へと自己縮退し、自己診断のための読込専用アクセスと人間監査エスカレーション（HITL）のみを実行する。
        *   $0.4 \le S(t) < 0.8$ (中等度隔離): シェルコマンド実行および外部ネットワーク送信をブロックし、サンドボックス内ファイルの読み書きのみを許可。
        *   $S(t) < 0.4$ (最小制限): 通常動作。
    3.  **ヒステリシス復元機構と遅延極限（L7結合）**:
        段階的復帰レート $\Delta S_{recovery}(t)$ を以下のように定義する：
        $$\Delta S_{recovery}(t) = \eta \cdot A(t) \cdot \mathbb{I}\left(k_{safe}(t) \ge K_{min}\right)$$
        ここで $\eta = 0.2$、人間による監査承認フラグ $A(t) \in \{0, 1\}$、および連続安全ステップ数 $k_{safe}(t)$ が最小基準 $K_{min}$ を超えた場合のみ段階的な権限復帰を許可する。
        完全隔離状態 $S(t_{emit}) = 1.0$ から通常動作境界（$S(t) < 0.4$）に復帰するために必要な最小ステップ数を $N_{rec} = K_{min} \cdot \left\lceil 0.6/\eta \right\rceil$ とし、人間監査応答レイテンシを $\tau_A$ 秒、1ステップの平均処理時間を $\delta_t$ 秒、システム制御・伝送オーバーヘッドを $\tau_{overhead}$ 秒としたとき、復帰所要時間 $t_{rec}$ は次式で決定される：
        $$t_{rec} = \tau_A + N_{rec} \cdot \delta_t + \tau_{overhead}$$
        この $t_{rec}$ が L7 の残り Slack Time $L(t)$ を超える極限状態（$L(t_{emit}) \le t_{rec}$）においては、人間監査の完了を待たずに即座に「超縮退運転モード」 $M^{(4)}$ (FAIL / 安全停止) へ強制遷移する。
*   **2026年技術エコシステム適合**:
    *   Granian & Google ADK 連携：ツール実行時に `execute_tool` ラッパーを介して権限をチェック。拒否時は `PermissionError` 例外を発行。
    *   Inngest ワークフロー：違反例外を `agent/security.violation` イベントとしてパブリッシュし、非同期で管理者への通知・HITLフローをトリガー。

### [L5] 有向タスクグラフ最小コスト定理の適用 (R3)
*   **ユースケース**: Claude Code が複雑なリファクタリングを自律的に継続するか、APIトークンやエラーペナルティの累積コストを懸念して人間に承認・指示（HITL）を求めるべきかの最適判断。
*   **適用モデル**:
    有向タスクグラフ上の現在ノード $u$ と残リトライバジェット $k$ からなる状態 $x = (u, k)$ を定義。
    期待遷移コストを最小化する Bellman 最適方程式は以下の通り：
    $$V^*(u, k) = \min \{ Q^*(u, k, \text{AUTO}), Q^*(u, k, \text{HITL}) \}$$
    ここで、AUTOがHITLよりも期待コストで優位となる（自律実行を選択する）必要十分条件は、自律成功確率 $P_a(u, v, k)$ が以下の安全クランプ付きエスカレーション閾値 $\theta(u, v, k)$ 以上であることである：
    $$\theta(u, v, k) = \begin{cases} 
    1.0 & \text{if } k \le 0 \text{ or } C_f(u) + V^*(u, k-1) - V^*(v, k) \le 0 \\
    \min\left(1.0, 1 - \frac{C_h(u, v) - C_a(u, v)}{C_f(u) + V^*(u, k-1) - V^*(v, k)}\right) & \text{otherwise}
    \end{cases}$$
    - $C_h(u, v)$: 人間の認知介入コスト。
    - $C_a(u, v)$: 自律実行コスト。
    - $C_f(u)$: 失敗時の修復コスト。
    - $V^*(u, k-1) - V^*(v, k)$: 失敗時の状態価値の損失（$V^*(u, 0) = C_{\text{fail}}$ はバジェット枯渇時の端末失敗ペナルティ）。
*   **数理的極限と境界**:
    1. **残リトライバジェット $k \to 0$ の極限**: バジェット枯渇に向かい、安全クリティカル環境における端末失敗ペナルティ $C_{\text{fail}} \to \infty$ となると、期待価値損失 $\Delta V^* \to \infty$ となり、閾値 $\theta \to 1.0$ となる。これにより自律実行条件 $P_a \ge \theta$ が崩壊し、確実にHITLへエスカレーションされる。
    2. **失敗修復コスト $C_f(u) \to \infty$ の極限**: 破壊的操作による修復不能リスク等で $C_f(u) \to \infty$ となる場合、同様に分母が発散するため $\theta \to 1.0$ となり、安全にHITLが選択される。
    3. **決定境界の連続性**: $C_h(u, v) \le C_a(u, v)$ のときは分子が $\le 0$ になるため $\theta = 1.0$ となり、決定境界は $[0, 1]$ 内で滑らかにクランプされ、不連続なジャンプや負の確率閾値の発生を完全に防止する。
*   **2026年技術エコシステム適合**:
    *   SQLModel永続化：コストパラメータを `SQLModel` で管理。
    *   Granian & FastAPI サービス：最適経路・ポリシーを後退帰納法で計算する `/optimize` エンドポイントを Granian 上でホスト。

### [L6] 記憶容量制限下の最適忘却定理の適用 (R3)
*   **ユースケース**: Claude Code のコンテキスト（会話履歴、リポジトリコード）がコンテキスト窓上限に近づき、API料金が急増したり、応答遅延が発生するのを防止する。
*   **適用モデル**:
    メモリ要素の集合を $\mathcal{M} = \{m_1, m_2, \dots, m_N\}$ とする。各要素 $m_i$ は、サイズ $s_i$、重要度 $R_i$（または時間減衰重要度 $P_i(t) = e^{-\gamma \Delta t_i}$）、エントロピー $H_i \ge 0$、圧縮率 $\beta_i \in [\beta_{min}, 1]$ を持つ。
    圧縮率 $\beta_i$ におけるメモリ要素の表現密度効用（二面性表現密度ユーティリティ関数） $U_{\text{comp}}(\beta_i, H_i, R_i)$ を以下のように定義する：
    $$U_{\text{comp}}(\beta_i, H_i, R_i) = R_i \left( \frac{2}{\gamma H_i} - \beta_i \right) e^{\gamma H_i \beta_i}$$
    - 指数項 $e^{\gamma H_i \beta_i}$ は、圧縮率の増加（緩和）に伴うセマンティクス情報の保持率を表し、エントロピー $H_i$ にスケールされる。
    - 線形項 $\left( \frac{2}{\gamma H_i} - \beta_i \right)$ は、情報の肥大化に伴う資源占有ペナルティを反映する。
    
    各要素に対するアクション $\mathbf{a}_i = [a_{keep}, a_{comp}, a_{swap}, a_{forget}]^T \in \{0, 1\}^4$ に対し、容量制限のシャドウプライス $\lambda$ とアクセス遅延制限のシャドウプライス $\mu$ を用いた以下のラグランジュ多目的最適化問題を最大化する：
    $$\max_{\mathbf{a}, \boldsymbol{\beta}} \sum_{i=1}^N \sum_{k} a_{i,k} U_k(m_i, \beta_i) - \lambda \left( \sum_{i=1}^N C(\mathbf{a}_i, \beta_i) - C_{max} \right) - \mu \left( \sum_{i=1}^N D(\mathbf{a}_i) - D_{max} \right)$$
    圧縮アクションが選択された際の最適な圧縮率 $\beta_i^*$ は、Lambert W 関数の下部枝 $W_{-1}$ を用いて以下のように算出される：
    $$\beta_i^* = \frac{1}{\gamma H_i} \left[ 1 + W_{-1}\left( - \frac{\lambda s_i}{e R_i} \right) \right]$$
    実数解が存在するための必要十分条件は $\lambda s_i \le R_i$ である。この条件が崩壊（$\lambda s_i > R_i$）した場合、内部最適解は消失し、圧縮率は最小値 $\beta_{min}$ に張り付くか、または `Swap` もしくは `Forget` へ強制遷移する。
*   **2026年技術エコシステム適合**:
    *   SQLModel永続化：メモリ要素の属性を `MemoryElementEntity` としてデータベース管理。
    *   pytest & httpx テスト：デュアルアセント最適化アルゴリズムが一意の最適忘却状態に収束することをテスト検証。

### [L7] API制約下の縮退運転境界定理の適用 (R3)
*   **ユースケース**: Claude Code 実行中に Anthropic API のレートリミット（429エラー）や接続遮断が発生した場合、または時間制約（デッドライン）が迫っている場合に、ハングアップを回避して動作を継続する。
*   **適用モデル**:
    動作モード $M(t) \in \{M^{(0)}, M^{(1)}, M^{(2)}, M^{(3)}, M^{(4)}\}$ （通常、ローカル推論 MLX-LM、ルールベース、HITL、FAIL）を定義。
    モード $M_i$ ごとに定義された期待計算コスト $W^{(i)}$、安全マージン $\tau^{(i), safe}$、および Slack Time $L(t) = T_{\text{deadline}} - T_{\text{elapsed}}(t) - T_{\text{est}}(t)$ から、以下の動的境界関数 $\Gamma_i(C(t), L(t))$ （$C(t) \in [0, C_{\max}]$ は瞬時APIキャパシティ）を評価する：
    $$\Gamma_i(C(t), L(t)) = W^{(i)} + \tau^{(i), safe} - L(t)$$
    *   **退行トリガー条件**:
        現在の動作モードが $M_i$ のとき、APIキャパシティが瞬時境界値を下回った時点で、直ちに下位モード $M_{i+1}$ への強制退行を行う：
        $$C(t) < \Gamma_i(C(t), L(t)) \implies M_i \to M_{i+1}$$
        ※ $L(t) \le 0$ （期限超過または残り時間ゼロ）の場合は、自動的にローカル最小保証モードへ相転移する。
    *   **チャタリング防止とZeno動作の完全排除の証明**:
        下位モード $M_{i+1}$ から上位モード $M_i$ への復帰（復元遷移）には、以下の「二重ヒステリシス条件」を課す：
        1. **容量回復条件 (容量ヒステリシス)**: $C(t) \ge \Gamma_i(C(t), L(t)) + \Delta_C \quad (\Delta_C > 0)$
        2. **時間的安定条件 (時間ヒステリシス)**: $t - t_{\text{last\_trans}} \ge T_{\text{dwell}} \quad (T_{dwell} > 0)$
        任意有限時間 $[0, T]$ における遷移回数を $N(T)$ とすると、各遷移間隔が下限 $T_{dwell}$ で抑えられるため、$N(T) \le \frac{T}{T_{dwell}} < \infty$ が成立し、Zeno動作（チャタリング極限での無限遷移）は数学的に完全に排除される。
    *   **リアプノフ関数による極限時安定性保証**:
        状態 $x(t) = [C(t), L(t)]^T$ に対するリアプノフ関数 $V(t) = \frac{1}{2} \max\left(0, \Gamma_{M(t)}(C(t), L(t)) - C(t)\right)^2 + \frac{1}{2} \max\left(0, -L(t)\right)^2$ を定義する。
        $C(t) \to 0$ または $L(t) \to 0$ （デッドライン極限）において、$C(t) < \Gamma_i$ となった瞬間にモード退行 $M^{(i)} \to M^{(i+1)}$ がトリガーされ、境界値が $\Gamma_{i+1} < \Gamma_i$ に不連続減少する。これにより、遷移前後で $V(t^+) < V(t^-)$ が保証され、システムは破綻せず安定な縮退状態へ収束する。
*   **2026年技術エコシステム適合**:
    *   Granian & FastAPI：非同期 ASGI トークンバケットおよび境界判定ロジックを Granian サーバー上で実行。
    *   Next.js 15 SSE 配信：エージェントのモード推移および残余許容時間を SSE 経由で Next.js 15 管理画面へストリーミング転送し、リアルタイム表示。

### [L8] 構造化ログのエントロピー最小化定理の適用 (R3)
*   **ユースケース**: Claude Code の詳細な推論プロセス（思考木、ツール実行）を出力する際、ログデータの肥大化を極小化しつつ、デバッグに必要なトレーサビリティを完全維持する。
*   **適用モデル**:
    動作ログ出力 $L_k$ を、最適チェックポイント周期 $T_c \in \mathbb{N}^+$、静的識別子（ASTハッシュ $ID_k$）、サブ状態ハッシュ $h_k^{(j)}$ を用いた以下のハイブリッド生成モデルとして定義する：
    $$L_k = \begin{cases}
    \langle ID_k, \text{Type}=\text{KEY}, s_k \rangle & \text{if } k \equiv 0 \pmod{T_c} \\
    \langle ID_k, \text{Type}=\text{DELTA}, \{ (j, \Delta s_k^{(j)}) \mid h_k^{(j)} \neq h_{k-1}^{(j)} \} \rangle & \text{if } k \not\equiv 0 \pmod{T_c}
    \end{cases}$$
    ここで、全体状態 $s_k$ は $M$ 個の独立サブ状態の直和 $s_k = \bigoplus_{j=1}^M s_k^{(j)}$ に分解され、$\Delta s_k^{(j)} = s_k^{(j)} \ominus s_{k-1}^{(j)}$ である。
    
    1. **最適チェックポイント周期 $T_c^*$ の決定境界**:
       単一ログの損失確率を $p$、許容される平均状態再構成エラー確率の上限を $\epsilon$、1ステップあたりの適用コストを $\alpha$、最大再構成コストを $C_{max}$ としたとき、最適周期 $T_c^*$ は以下で決定される：
       $$T_c^* = \min \left( \left\lfloor \frac{2 C_{max}}{\alpha} + 1 \right\rfloor, \left\lfloor \frac{2\epsilon}{p} - 1 \right\rfloor \right)$$
    2. **ハッシュDirty判定によるシリアライズ・比較オーバーヘッドの削減**:
       ハッシュ比較 $h_k^{(j)} \neq h_{k-1}^{(j)}$ により、Dirtyなサブ状態のみを特定して差分演算を行うことで、全体状態シリアライズの計算複雑度を $O(|S|)$ から $O(M) + O(\sum_{dirty} |s^{(j)}|)$ へと大幅に削減し、L6/L7の遅延制約への影響を排除する。
*   **2026年技術エコシステム適合**:
    *   structlog統合：`structlog.contextvars` を用いて、共通コンテキストをスレッドローカルにバインドし、エントリごとの冗長キー出力を排除。
    *   Google ADK ライフサイクルフック統合：`L8AgentObservabilityEngine` クラスを定義。`post_tool_call` などのフックで遷移差分 $\Delta s_k$ のみを構造化ログとして非同期出力。

### [L9] 自己修復ループの不動点収束定理の適用 (R3)
*   **ユースケース**: Claude Code が生成・修正したコードにエラーが検出された際、デバッグ修復ループを確実に終了（テスト合格の不動点へ収束）させる。
*   **適用モデル**:
    履歴追跡にはソースコードの生テキストではなく、抽象構文木（AST）を正規化シリアライズして得られる暗号学的ハッシュ $H(a_t)$ を用いる。履歴集合 $\mathcal{H}_t$ の保持上限を $M_{\text{limit}}$ とする。
    修復ポテンシャル関数を以下のように定義する：
    $$\Phi(a_t) = w_{test} \cdot (N_{test} - N_{pass}) + w_{static} \cdot N_{static}$$
    （静的エラーが存在する場合は、動的テストが実行不可能または不安定となるため $N_{pass} = 0$ と極小化する）。
    履歴ペナルティを加味した修正ポテンシャル関数 $\Psi(a_t, \mathcal{H}_t)$：
    $$\Psi(a_t, \mathcal{H}_t) = \Phi(a_t) + \alpha \cdot \mathbb{I}(H(a_t) \in \mathcal{H}_t)$$
    探索温度の上昇やプロンプト変更による突然変異試行回数を $k_{mut}(t)$ とし、最大許容値を $K_{mutate}$ とする。
    *   **相転移境界条件 (L9 $\to$ L7/L5)**:
        状態遷移インジケータ $P_{\text{transit}}(t)$ が 1 のとき、ループを即時脱出し、L7 縮退運転または L5 HITL エスカレーションへ自動相転移する：
        $$P_{\text{transit}}(t) = \mathbb{I}\left( (t \ge t_{max}(t)) \lor (|\mathcal{H}_t| \ge M_{limit}) \lor (k_{mut}(t) \ge K_{mutate}) \lor (H(a_t) \in \mathcal{H}_t) \right)$$
        ここで $t_{max}(t) = \lfloor L(t) / \Delta \tau \rfloor$ （L7 の Slack Time $L(t)$ およびステップ見積もり時間 $\Delta \tau$ から算出）。
*   **2026年技術エコシステム適合**:
    *   Google ADK 構造化出力：フィードバック時に Pydantic スキーマ（`proposed_code`, `reasoning`）による出力を強制。
    *   Inngest ワークフロー：修復ステップをべき等に管理し、不整合を排除。
    *   uv / Ruff / pytest 連携：`uv` 仮想環境下のサブプロセスで `Ruff`（静的解析）および `pytest`（動的テスト）を隔離実行。

---

## 2. 統合コヒーレンスの方程式系

各レイヤーの境界値は、以下の数理的結合方程式を通じて完全同期し、システム全体の調和的安定性を担保する。

1.  **ルーティングと成功確率 (L3 $\to$ L5)**:
    L3ルーティングの曖昧度誤差を $\epsilon(q)$ としたとき、L5における自律タスクの成功確率は以下のように制約される：
    $$P_{success} \le (1 - \epsilon(q)) P_{base}$$
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
