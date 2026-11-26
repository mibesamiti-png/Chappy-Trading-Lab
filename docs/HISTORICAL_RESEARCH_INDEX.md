# Historical research index / 過去研究索引

Source: historical Notion page 「Chappy Trading Lab｜v1.1.0 開発仕様書・ロードマップ」, snapshot inspected 2026-11-27 JST. This is a source-derived index and selected methodological lessons, not a copy of the private notebook, a fresh replication or an assertion that all sources were recovered. No private URLs, original market records, per-symbol results, historical profit figures, or HF-derived outputs are included. The Notion page describes earlier Japanese-market and artificial-fixture work; it is not evidence about HF academic research.

## Reusable lessons / 再利用できる研究上の教訓

| Historical rounds | Lesson and limitation |
|---|---|
| Early B research, R6–11 | Exploratory apparent advantages can concentrate in a few days; rerun from initial capital when removing days, do not merely subtract observed profits. Known-market findings are for hypothesis formation, not prospective acceptance. |
| R12–18 | Separate synchronized observation, decision expiry, execution evidence and durable state. Synthetic process termination tests are not evidence of physical power-loss or Windows robustness. |
| R23–44 | Distinguish publication time, observed receipt time, corrected versions, original evidence and retrospective explanation. Multiple simultaneous disclosures and corporate actions confound attribution. A digest alone does not authenticate the source. |
| R46–58 | Freeze observation and hypothesis before outcome; keep abstention, unavailable evidence, risk constraints and independent review explicit. Calibration of resolved cases is not an estimate for missing outcomes. Monitor correlated strategies without treating each warning as independent. |
| R59–66 | Integrate existing components before adding new mechanisms. SQLite replay and external checkpoint tests have limited scope; historical R66 accepted offline research only and blocked execution. |
| R67–79 | OHLCV cannot reconstruct order-flow imbalance. Separate direction accuracy, payoff magnitude, net value and unresolved outcomes. Correlated observations or replicated sources are not independent evidence; row weighting and source weighting estimate different quantities. Sensitivity deletion does not prove independence. |
| R80–88 | Feature support does not rule out a reversal of outcome distribution. Compare against null and no-action controls. Costs and delay may eliminate economic value; a one-shot test needs its independence assumptions. Repeated unadjusted looks inflate false acceptance. |
| R89–100 | A failed candidate pool is not proof of a universally unpredictable market. Expressive candidates can overfit small training samples. Include abstention in fixed candidate comparisons, separate selection and audit, and account for eligible observations, elapsed time and observation cost. |
| R101–119 | Separate temporary pause, retraining, requalification and switching. A prior approval does not guarantee future usefulness; monitor absolute economic deterioration separately from relative comparison. These are bounded artificial studies, not adopted universal policies. |
| R120–129 | Count evidence and review budget explicitly; keep candidate generations distinct. Freshness and depth trade off; sparse review and recovery consume the same finite budget. No general guarantee under nonstationarity. |
| R130–137 | Distinguish no eligible opportunities, no received outcomes, delayed reports, corrections and economic deterioration. Outcome-dependent missingness biases observed-only statistics. Identical observed histories can hide different underlying outcomes; bounds do not establish future economic value. |
| R138–140 | Additional evidence has value only within cost, deadline, quality and provenance constraints. Duplicate observations must not be counted as independent; complementary coverage is distinct from independent confirmation. Matching reports can share common errors. This research was deferred until a real need. |
| R141–155 | Completion-first decision: freeze comparison contract and common accounting; include abstention and simple baselines; distinguish synthetic fixed payoffs from variable returns. R155 frozen artificial offline candidate; no production claim. |
| R156–164 | Known development data may be used only within its authorized scope. Retrospective feature evaluation does not establish prospective performance. Distinguish hypothetical intentions from capital-constrained accepted actions, with strict label maturity and independent accounting. |
| R165–170 | Capital-aware evaluation, bounded refresh and terminal DATA authority; no automatic recovery after data stop. Historical R170 offline package accepted, but not Windows, clean environment, full regression, live fills or independent profitability. Fresh R169 synthetic CI has separate exact-head evidence in INTEGRATED_RECOVERY.md. |
| R171–173 | Storage integrity, provider contract and authorized offline import are separate layers. Synthetic fixtures do not prove provider authenticity, valid real calendar, actual network collection, or data rights. Declared receipt time is not authenticated receipt. |

## Earlier records

The page begins with desktop v1.1.0 development and Windows acceptance, then Batch A Research Lab v0.1.0, Batch B preparation v0.2.0, first known-data evaluation, second-generation v0.3.0, third-generation v0.4.0, fourth-generation concentration audit, and fifth-stage fixed prospective pilot preparation v0.5.0. These entries use mixed batch/generation numbering. Do not assign an exact R1–R5 filename mapping without verifying the original record. The earlier Japanese-market prospective protocol remains separate from the HF academic holdout; this historical record is not authorization to run either.

## Indexed stages

All 168 numbered headings from R6 through R173 are present in order. Titles are retained from the notebook, with internal hyperlinks and repeated date suffixes removed. An indexed heading is not evidence of successful source recovery or current test status. See INTEGRATED_RECOVERY.md and LEGACY_INTAKE.md for that distinction.

| Round | Original research title |
|---|---|
| R6 | 前兆イベント研究（Signal Study v0.1、探索専用） |
| R7 | 相対リターン研究（Relative Study v0.1、探索専用） |
| R8 | 単一資金口座の銘柄選択研究（Portfolio Study v0.1、探索専用） |
| R9 | 買い／空売り／両建て研究（LongShort Study v0.1） |
| R10 | 空売り専用条件と方向選択（Short Study v0.1） |
| R11 | 機会費用とポジション乗り換え（Opportunity Study v0.1） |
| R12 | 複数銘柄同期と通信異常（FeedSafety Study v0.1） |
| R13 | 統合リプレイと永続化（Integrated Replay v0.1、人工試験） |
| R14 | 強制終了と永続化障害（Durability Study v0.1） |
| R15 | 確定足から仮想約定までの統合（Pipeline Study v0.1） |
| R16 | 監視GUI（Chappy Trading Monitor v0.1） |
| R17 | 判断根拠の詳細診断（Pipeline v0.2 / Diagnostic Monitor v0.2） |
| R18 | 詳細診断付き統合パイプラインの強制終了試験 |
| R19 | 既知市場の時刻付きリプレイ（Market Replay v0.1） |
| R20 | 反発戦略と情報遅延（Latency Study v0.1） |
| R21 | 指標履歴の保持方式比較（History Study v0.1） |
| R22 | 相場環境の診断（Regime Study v0.1） |
| R23 | 決算イベントと既存取引の照合（Event Study v0.1） |
| R24 | イベント回避と発表後反応（Event Policy Study v0.1） |
| R25 | 引け後決算と翌営業日の反応（NextDay Study v0.1） |
| R26 | 市場期待との差と取得基盤（Consensus Study v0.1） |
| R27 | 矛盾する情報と時点整合性（Evidence Gate v0.1） |
| R28 | 受信証拠の追記保存と訂正履歴（Evidence Journal v0.1） |
| R29 | 外部情報取込と原本再生（Ingest Study v0.1） |
| R30 | 企業資料の数値抽出候補と根拠照合（Text Extraction Study v0.1） |
| R31 | 文書位置の特定と業績予想表の検証（Document Study v0.1） |
| R32 | 共通文書証拠形式（Common Document Study v0.1） |
| R33 | 提案と独立審査の分離（Review Workflow v0.1） |
| R34 | 受信原本と審査台帳の統合（Document Integration v0.1） |
| R35 | 情報採用ゲート（Adoption Gate v0.1） |
| R36 | 情報採用と仮想売買の接続（Evidence Paper Bridge v0.1） |
| R37 | 追加6社の日足イベント研究（Daily Event Study v0.1） |
| R38 | 市場/業界相対反応と外部要因（Market Context Study v0.1） |
| R39 | 決算日を除外した同業比較（Peer Context Study v0.1） |
| R40 | 基礎監査（Foundation Audit v0.1） |
| R41 | 原入力結合と同時刻の平常時対照（Baseline Audit v0.1） |
| R42 | 権利落ちと市場感応度の基礎監査（Beta Audit v0.1） |
| R43 | 複数開示のイベント束（Event Bundle Study v0.1） |
| R44 | 異業種の期待差と初回反応（Cross Sector Study v0.1） |
| R45 | 実際のデイトレーダーの意思決定研究（2026-11-26 JST） |
| R46 | 観測能力と判断品質（Decision Quality v0.1） |
| R47 | 構造化仮説と反証・資金制約（Decision Quality v0.2） |
| R48 | 判断時点固定と訂正履歴（Decision Journal v0.1） |
| R49 | 判断の事後診断と訂正感度（Decision Review v0.1） |
| R50 | 改善候補の固定比較と見送り診断（Improvement Study v0.1） |
| R51 | 共有資金と組み合わせ・乗換え判断（Portfolio Decision v0.1） |
| R52 | 共通ショックと期待スコア不確実性（Portfolio Stress v0.1） |
| R53 | 予測確率の校正と環境変化（Calibration Study v0.1） |
| R54 | 逐次校正監視と停止・復帰（Sequential Monitor v0.1） |
| R55 | 初回停止方式の確率比較と系列依存（Alarm Study v0.1） |
| R56 | 複数戦略監視と異常範囲（Multi Monitor v0.1） |
| R57 | 依存グラフと新規/保有監視/退出の分離（Dependency Study v0.1） |
| R58 | 復旧照合と段階的再開（Recovery Study v0.1） |
| R59 | 最小統合経路（Integration Study v0.1） |
| R60 | 仮想約定と口座のイベント再生（Event Replay v0.1） |
| R61 | SQLite永続化とプロセス中断（Durable Replay v0.1） |
| R62 | 統合事後監査（Integrated Review v0.1） |
| R63 | 統合改善案審査（Integrated Improvement v0.1） |
| R64 | 統合予測確率校正（Integrated Calibration v0.1） |
| R65 | 統合精度監視と復帰ゲート（Integrated Monitor v0.1） |
| R66 | 統合受入判定（Acceptance Study v0.1） |
| R67 | 市場判断研究再開：注文フローと価格反応（Order Flow Study v0.1） |
| R68 | 5分足の出来高と価格反応（Price Response Study v0.1） |
| R69 | 出来高の時間帯別基準（Volume Baseline Study v0.1） |
| R70 | 出来高の横断比較と短期/長期基準（Volume Context Study v0.1） |
| R71 | 複合仮説の人工比較（Composite Hypothesis Study v0.1） |
| R72 | 過去結果による逐次予測方式選択（Regime Selection Study v0.1） |
| R73 | 方向予測の経済的価値とコスト（Economic Value Study v0.1） |
| R74 | 期待損益推定と感度審査（Expected Value Study v0.1） |
| R75 | 共通証拠による推定方式比較（Estimation Comparison v0.1） |
| R76 | 証拠の依存と重複（Evidence Dependency Study v0.1） |
| R77 | 期待値と発生源別感度の分離（Evidence Sensitivity Study v0.1） |
| R78 | 判断機会と観測行の分離（Opportunity Study v0.1） |
| R79 | 観測範囲と一般化（Observation Coverage Study v0.1） |
| R80 | 知識の適用範囲と分布変化（Applicability Study v0.1） |
| R81 | 既知条件の知識更新（Knowledge Refresh Study v0.1） |
| R82 | 経済的価値の監視と診断（Economic Monitor Study v0.1） |
| R83 | 診断に応じた対応の比較（Diagnostic Response Study v0.1） |
| R84 | 受信遅延と市場変化周期（Latency Phase Study v0.1） |
| R85 | 予測不能市場と対照実験（Random Market Study v0.1） |
| R86 | 予測上/経済上の優位性の一回審査（Statistical Gate Study v0.1） |
| R87 | 証拠の必要時間と市場環境の寿命（Evidence Lifetime Study v0.1） |
| R88 | 早期審査と誤採用率配分（Sequential Gate Study v0.1） |
| R89 | 文脈別の条件付き予測可能性（Conditional Edge Study v0.1） |
| R90 | 特徴量の相互作用（Feature Interaction Study v0.1） |
| R91 | 固定候補選択と独立審査（Candidate Selection Study v0.1） |
| R92 | 分布変化と固定候補の限界（Candidate Limit Study v0.1） |
| R93 | 限定的な構造操作による仮説生成（Hypothesis Generation Study v0.1） |
| R94 | 条件分岐による限定仮説生成（Conditional Hypothesis Study v0.1） |
| R95 | 仮説表現力と学習量（Hypothesis Capacity Study v0.1） |
| R96 | 構造の複雑さに対する固定罰則（Hypothesis Penalty Study v0.1） |
| R97 | 固定学習予算での候補群選択（Hypothesis Pool Study v0.1） |
| R98 | 観測頻度の偏り（Observation Imbalance Study v0.1） |
| R99 | 状態限定仮説と観測予算（Selective Hypothesis Study v0.1） |
| R100 | 稀少事象の証拠時計と市場寿命（Rare Evidence Study v0.1） |
| R101 | 仮説選択・審査・運用の共通時計統合（Integrated Hypothesis Study v0.1） |
| R102 | 有限予算での自律再学習（Integrated Refresh Study v0.1） |
| R103 | 短期見送りと再学習発動の分離（Refresh Trigger Study v0.1） |
| R104 | 再学習方式の別条件頑健性（Refresh Robustness Study v0.1） |
| R105 | 旧仮説の保存と独立再審査（Knowledge Archive Study v0.1） |
| R106 | 審査順序と経済的価値（Archive Race Study v0.1） |
| R107 | 運用と並行審査（Parallel Review Study v0.1） |
| R108 | 乗換え差の不確実性（Switch Evidence Study v0.1） |
| R109 | 対応差の分散に基づく審査（Paired Variance Study v0.1） |
| R110 | 比較証拠の陳腐化（Comparison Drift Study v0.1） |
| R111 | 切替後の対応差監視と有限復帰（Post Switch Study v0.1） |
| R112 | 相対監視と絶対的経済価値監視（Dual Monitor Study v0.1） |
| R113 | 絶対停止後の有限再資格審査（Recovery Requalification Study v0.1） |
| R114 | 統合ライフサイクル監査（Lifecycle Audit Study v0.1） |
| R115 | 判断競合と最終境界監査（Lifecycle Priority Study v0.1） |
| R116 | 候補別監視証拠の保持（Monitor Evidence Study v0.1） |
| R117 | 資格世代と候補別絶対監視の統合（Qualification Generation Study v0.1） |
| R118 | 運用中の有限再資格審査（Parallel Requalification Study v0.1） |
| R119 | 再資格後の復帰と共通審査台帳（Requalification Budget Study v0.1） |
| R120 | 採用審査の証拠台帳（Admission Evidence Ledger Study v0.1） |
| R121 | 有限採用予算の固定/柔軟配分（Admission Allocation Study v0.1） |
| R122 | 有限審査予算と観測深度（Admission Depth Study v0.1） |
| R123 | 審査中の分布変化と証拠鮮度（Admission Drift Study v0.1） |
| R124 | 有限予算と疎審査/鮮度の接続（Admission Integration Study v0.1） |
| R125 | 疎審査採用後の絶対監視（Admission Monitor Study v0.1） |
| R126 | 短期見送りと残予算内の有限再資格（Admission Recovery Study v0.1） |
| R127 | 疎審査/末尾窓/残予算再資格の証拠台帳接続試験（Admission Ledger Integration Study v0.1） |
| R128 | 適格観測時計と疎審査の一般化（Eligible Evidence Study v0.1） |
| R129 | 適格時計による資格/監視/再資格接続（Eligible Lifecycle Study v0.1） |
| R130 | 観測カバレッジと監視遅延（Coverage Monitor Study v0.1） |
| R131 | 遅延受信と確定済み証拠の訂正（Delayed Coverage Study v0.1） |
| R132 | 停止理由別復旧（Stop Reason Study v0.1） |
| R133 | 通信復旧後の短期運用ゲート（Data Recovery Gate Study v0.1） |
| R134 | 成熟観測と鮮度制限（Mature Evidence Study v0.1） |
| R135 | 勝敗依存の受信偏り（Receipt Bias Study v0.1） |
| R136 | 固定窓の部分受信上下限ゲート（Bounded Receipt Gate Study v0.1） |
| R137 | 観測同一性と独立完全観測（Observation Identity Study v0.1） |
| R138 | 追加観測の費用・納期・品質（Audit Value Study v0.1） |
| R139 | 外部証拠台帳接続（External Audit Ledger Study v0.1） |
| R140 | 外注先の相互補完と共通障害（Supplier Complement Study v0.1） |
| R141 | 最小中核の比較パイロット（Core Comparison v0.1） |
| R142 | 資金制約と共通比較基準（Capital Comparison v0.1） |
| R143 | 中核AIの弱点診断（Core Diagnostic Study v0.1） |
| R144 | 短期見送り機構の中核比較（Core Pause Comparison v0.1） |
| R145 | 中核AIの早期採用審査比較（Core Admission Comparison v0.1） |
| R146 | 取引費用整合比較（Core Cost Comparison v0.1） |
| R147 | 費用整合審査の検出力・残存機会診断（Core Evidence Diagnostic v0.1） |
| R148 | OHLCV入力契約の人工検証（OHLCV Input Study v0.1） |
| R149 | 可変損益中核接続（Variable Payoff Core Study v0.1） |
| R150 | OHLCV可変損益と資金拘束の接続（OHLCV Capital Study v0.1） |
| R151 | OHLCV可変損益の停止・再学習接続（OHLCV Refresh Study v0.1） |
| R152 | 正規化CSV入力と開発期間保護（CSV Input Guard v0.1） |
| R153 | 日数・銘柄・期間設定化（Configured Lifecycle Study v0.1） |
| R154 | オフライン評価CLIの一体化（Offline Evaluation CLI v0.1） |
| R155 | 人工市場評価パッケージ凍結（Offline Lab v0.1） |
| R156 | CTRL.zip再受領と既知市場データ受付（CTRL Intake v0.1） |
| R157 | 既知実市場のOHLCV統合評価（CTRL Evaluation v0.1） |
| R158 | 既知市場の費用・過去反発研究照合（Known Market Diagnostic v0.1） |
| R159 | 既存市場研究の棚卸し（2026-11-26 JST） |
| R160 | 既存市場特徴の再接続（Market Context Adapter v0.1） |
| R161 | 複数保有時間の成熟と資金拘束（Multi-Horizon Adapter v0.1） |
| R162 | 観測方式と複数時間の仮説選択統合（Multi-Horizon Learning Study v0.1） |
| R163 | 複数時間・市場特徴の既知実市場比較（Multi-Horizon CTRL Evaluation v0.1） |
| R164 | 固定仮説の資金・費用・期間診断（Capital Diagnostic v0.1） |
| R165 | 学習審査の資金制約統合（Capital-Aware Learning v0.1） |
| R166 | 資金制約付き学習と劣化監視・再学習の統合（Capital Lifecycle Study v0.1） |
| R167 | 統合受入監査（Integration Audit v0.1） |
| R168 | 入力時刻とデータ安全権限の接続（Data Safety Adapter v0.1） |
| R169 | 統合オフラインCLI受入（Integrated Lab v0.1） |
| R170 | 統合オフライン比較基準の配布受入（Integrated Lab v0.1 R170） |
| R171 | 市場データ収集の保存基盤（Chappy Market Data Collector v0.1） |
| R172 | 取得契約と原本保存（Market Data Provider v0.1） |
| R173 | 利用許諾確認と実データ形式の受入（Market Data Import v0.1） |

## Missing or separately owned material

- R174–187: no numbered entries in this Notion snapshot. Exact scope and outcomes remain unverified; do not invent missing rounds or assume the original numbering continued without changes.
- R188–192: separate Work academic study, governed by the current charter and publication gate; no duplication or publication of restricted derived artifacts.
- Historical report files and market archives remain outside this public index. The remaining source inventory, archive inspection and rights review are independent of the knowledge index.
- Historical notes are not equivalent to fresh tests; exact CI success at head 759979d8603b499989269b095aa6ecb3d97dbbfc (run 45877584785) covered 53 hashes/compilation, 63 named source references (62 embedded pins and one historical filename import), R68 185, R169 17158, R154 725, R171 1647, R172 41 and R173 436 internal synthetic checks. These are heterogeneous internal checks, not independent market samples.
