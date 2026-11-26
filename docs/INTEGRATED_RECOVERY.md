# Integrated legacy source recovery
2026-11-27 JST. Nine standalone historical sources recovered from Library and placed together under legacy/integrated_recovery. These are exact hash-pinned historical sources, not a verified extraction of R170. Readback from GitHub matched each recovered text.

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

Additional direct missing parents: R160 -> Chappy_Trading_Known_Market_Diagnostic_v0.1.py (cfbd00bfcefa91ec9bbdcf5fae9ec2f81b7d8daa1fc96a3df0255ad14fb7a589); R152 -> Chappy_Trading_OHLCV_Refresh_Study_v0.1.py (dd25cb1de68a2db67cfb9455d74ab7389561967fdc220eb7c912f35b868cf4d3). Resolve recursive parents without relaxing pins. No execution or full dependency closure verified. R170, Offline Lab and Splitter archives materialized but could not be inspected in this run. Do not claim R170 package SHA or archive CRC verified. No data archives were committed. Historical source only; not authorized for live use or use with restricted HF data. See research charter.
