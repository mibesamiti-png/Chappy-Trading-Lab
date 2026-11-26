# Integrated legacy source recovery
2026-11-27 JST. Twenty-one standalone historical sources recovered from Library and placed together under legacy/integrated_recovery. These are exact hash-pinned historical sources, not a verified extraction of R170. Readback from GitHub matched each recovered text.

| Round | Source | SHA-256 verified against historical record or parent pin |
|---|---|---|
| R169 | Chappy_Trading_Integrated_Lab_v0.1.py | 06da1cbe4799b1a7f6468756c5af5fd0b0f3a79ecc8b99c2e0bd2798ee87b313 |
| R168 | Chappy_Trading_Data_Safety_Adapter_v0.1.py | 7f60c306ccfc648570e6cdce4914fb70c88f6a1c3c24b16c7648451e11faedf9 |
| R166 | Chappy_Trading_Capital_Lifecycle_Study_v0.1.py | fe0a70707e9f75fa2974bc9f7c8c61cdbc5282fe079f492ccb1da75b5db9c94b |
| R165 | Chappy_Trading_Capital_Aware_Learning_v0.1.py | 97b24c62808f609a5cfeac525d1779e179ba71c9d6e10c0b5c6f93486cd2dbce |
| R162 | Chappy_Trading_Multi_Horizon_Learning_Study_v0.1.py | 4e92b34c34ddbda5fca8bfb77efc43b653f50944e2f16e1e70755d772f57eb49 |
| R161 | Chappy_Trading_Multi_Horizon_Adapter_v0.1.py | 7aa917e673e3d289c58d2da30c09380d67d70d25e1d3b541b86666c008c0654b |
| R153 | Chappy_Trading_Configured_Lifecycle_Study_v0.1.py | 8279536d239361f54e9f0e167af1105caa0c56b7159011b2d8a1bf4188735b09 |

| R160 | Chappy_Trading_Market_Context_Adapter_v0.1.py | 14d2affe89176df07d784780add75d0bf08b91f96759f9d99de0f92973af0677 |
| R152 | Chappy_Trading_CSV_Input_Guard_v0.1.py | c4a4ad009a8c4cf87c2fce344525bf8dc1d38971a4d734ac1fa2bdd46d4fe0ec |
| R158 | Chappy_Trading_Known_Market_Diagnostic_v0.1.py | cfbd00bfcefa91ec9bbdcf5fae9ec2f81b7d8daa1fc96a3df0255ad14fb7a589 |
| R151 | Chappy_Trading_OHLCV_Refresh_Study_v0.1.py | dd25cb1de68a2db67cfb9455d74ab7389561967fdc220eb7c912f35b868cf4d3 |
| R157 | Chappy_Trading_CTRL_Evaluation_v0.1.py | ec13774a49d1cf106df85ab04bbe01977d32c5058b497daacc33cb35a9eaf41d |
| R150 | Chappy_Trading_OHLCV_Capital_Study_v0.1.py | 4583053b7c6a1cd82f9537372a43eb77adc6bce91c6b13f085446b3842108a61 |
| R82 | Chappy_Trading_Economic_Monitor_Study_v0.1.py | e3e830034f1e13382232ebe6d5658ff38722e36570ab0e34210ab294abe919d4 |
| R156 | Chappy_Trading_CTRL_Intake_v0.1.py | 51a72c0dd6b961a654fbc67438dcf123aa5c9a22221229aee55ed7e69c505ad5 |
| R149 | Chappy_Trading_Variable_Payoff_Core_Study_v0.1.py | a5a4d5189f338382e67c1ff572daf4dfabc9a8ca308cdfdec78937a459492103 |
| R81 | Chappy_Trading_Knowledge_Refresh_Study_v0.1.py | 620529a8bd827e567e6cb30a45575cf46b206b27b70f6e7cbdf27598279de707 |
| R148 | Chappy_Trading_OHLCV_Input_Study_v0.1.py | 58542626c20308885b0257483ff955db6838c431280ef52aafea1f8d2d103d12 |
| R99 | Chappy_Trading_Selective_Hypothesis_Study_v0.1.py | da45cbba59a269bc24379e0fffa7060562fdd1e0ed5e3c0681552cecb8dd1854 |
| R80 | Chappy_Trading_Applicability_Study_v0.1.py | a68f670dcc6e13ab0d54f7de34f1908c41878dc7ecf1318aa94a6caa1de759c3 |
| R74 | Chappy_Trading_Expected_Value_Study_v0.1.py | d2bfc1892be0a1893ddc9e86956c8d9654834728782b08b679dbf71e6ad2fa95 |

Remaining direct source parents: R148 -> R68 Price Response (1b9e2634cdfaeaa15b6d11446e187cfaa90a3d6daa89f64dc1e670a0685511a3), R69 Volume Baseline (719a82912c9fc817b03fc26755124b74bb641630673c7526a846fd47b06bb265); R99 -> R98 Observation Imbalance (426709b3d3ded3dfb7c760883abbede4f44e0bf18b54094ea0b0de3ef0575a61); R80 -> R79 Observation Coverage (7b99b2893770cabee0d84b02c6a9d0f700fce72587554ca41e33e2f141f872db); R74 -> R73 Economic Value (8ad5370ca7d1341f5df9bc845b2a97a64bb03526952bb3fe0800a73c3666b85e). R156 has no direct source parent observed. R158 diagnostic reads a prior result file, which stays local pending rights review; do not invent a replacement. Resolve recursive parents without relaxing pins. No execution or full dependency closure verified. R170, Offline Lab and Splitter archive inspection remains pending. Do not claim R170 package SHA or archive CRC verified. No data archives committed. Historical source only; not authorized for live use or use with restricted HF data. See research charter.
