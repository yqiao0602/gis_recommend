实验 4：看 set predictor 是否能给 reranker 提供额外帮助

(transformer) qy@mdzhang:~/system_redesign$ python scripts/evaluate_system.py --eval-mode dev --skip-qgis --checkpoint outputs/transformer_checkpoints_v4_6/best_model.pth --sp-checkpoint outputs/set_predictor_checkpoints_v3/best_model.pth --set-prior-mode soft --use-reranker
======================================================================
Transformer Configuration (L3 Embeddings + V4/V4.6 + Set Predictor)
======================================================================
  Device: cuda
  Model: d_model=256, n_heads=8, n_layers=6
  Vocabulary: 354 tokens (350 L3 + 4 special)
  Max sequence length: 100
  Batch size: 32, LR: 0.0001
  Training epochs: 50, Patience: 10
  L3 Embeddings: Enabled
  L3 Embeddings path: /home/qy/system_redesign/outputs/l3_embeddings.pt
======================================================================
======================================================================
  GIS Recommendation System Evaluation V3
======================================================================
  Device: cuda
  Eval mode: dev
  Effective max samples: 1000
  Effective soft prior threshold: 0.7
  Effective hard confidence threshold: 0.8

[1] Loading data ...
  Loaded 114401 workflows

[2] Building test set ...
  Loaded 11441 test indices from /home/qy/system_redesign/outputs/dataset_splits_v4.json
  Test samples: 1000
  Task types included: 66
  Task types excluded (<5 samples): 0
  Saved to /home/qy/system_redesign/outputs/evaluation_test_set.json

[3] Running L3 inference (beam search, deterministic) ...
  Loading inferencer from outputs/transformer_checkpoints_v4_6/best_model.pth ...
  [OK] Length stats loaded (60 task types)
[V4 Inferencer] Loading model: outputs/transformer_checkpoints_v4_6/best_model.pth
  Checkpoint info: epoch=14, val_loss=2.3495291346436615
  [OK] state_dict strict=True loaded successfully
  Model loaded on cuda
  Vocab loaded: 350 L3 codes, 350 with names
  Transition matrix: 99 states
/home/qy/miniconda3/envs/transformer/lib/python3.10/site-packages/torch/nn/modules/transformer.py:286: UserWarning: enable_nested_tensor is True, but self.use_nested_tensor is False because encoder_layer.norm_first was True
  warnings.warn(f"enable_nested_tensor is True, but self.use_nested_tensor is False because {why_not_sparsity_fast_path}")
  [OK] Set predictor loaded (77 active tokens)
  [Set Predictor] prior mode = soft
L3 inference: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [1:25:50<00:00,  5.15s/sample]
  Done in 5158s

[4] Computing L3 sequence metrics ...

[4a] Running reranker pipeline (N×M candidate pool) ...
Reranker: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [00:05<00:00, 183.20sample/s]
  Reranked 1000/1000 samples

[4b] Computing L3 sequence metrics ...

======================================================================
  Reranker Diagnostics
======================================================================
  Changed predictions: 301/1000 (30.10%)
  Effect counts: improved=160, degraded=127, unchanged=713
  Avg deltas: SetF1=+0.0025, LCS=+0.0021, LenRatio=+0.0247
  Candidate pool: avg=13.72, pool<=1=0, avg_l3_candidates=4.71

[5] Skipping QGIS evaluation (--skip-qgis)

======================================================================
  L3 Generation Evaluation (N=1000)
======================================================================
  Token Accuracy (Top-1):    6.67%   <- positional exact match
  Sequence Exact Match:      0.00%   <- full sequence match
  Set F1 (token overlap):   49.10%   <- token set overlap
  Soft Set Sim:            0.9964    <- avg best-match cosine
  L2-Set F1:                57.63%   <- L2 category overlap
  L2-Positional Accuracy:    7.80%   <- positional L2 match
  LCS Ratio:               0.3557    <- subsequence overlap
  Length Ratio (mean):      0.8161

======================================================================
  Breakdown by Task Type
======================================================================
  Task Type                                   N  SetF1  SoftSim   L2F1    LCS  TokAcc
  -----------------------------------------------------------------------------------
  Agricultural plant science                  1  66.7%   1.0000  80.0% 0.3750   25.0%
  Air quality                                13  50.9%   1.0000  60.9% 0.3856    8.5%
  Atmospheric gases                           1  54.5%   1.0000  66.7% 0.2857    0.0%
  Atmospheric radiation                       2  35.3%   1.0000  39.7% 0.2737    6.2%
  Atmospheric temperature                     9  56.6%   1.0000  67.6% 0.4677    4.3%
  Atmospheric water vapor                     2  54.2%   1.0000  65.6% 0.4471    0.0%
  Atmospheric winds                           2  60.3%   1.0000  72.0% 0.5059   20.0%
  Atmospheric/ocean indicators                2  29.6%   1.0000  33.3% 0.2213   16.2%
  Bathymetry                                  1  50.0%   1.0000  53.8% 0.2632    5.3%
  Biospheric indicators                      10  48.0%   1.0000  57.1% 0.3466    4.3%
  Boundaries                                  5  43.9%   0.9357  55.7% 0.3202    3.3%
  Carbon flux                                 5  36.1%   1.0000  42.6% 0.2429    7.4%
  Citizen science data integration            1  36.4%   1.0000  44.4% 0.2857    0.0%
  Climate feedbacks                           1  91.7%   1.0000 100.0% 0.8462    0.0%
  Climate indicators                          2  46.2%   1.0000  53.0% 0.2730    8.3%
  Cloud masking                               1  28.6%   1.0000  33.3% 0.2000   10.0%
  Clouds                                      8  45.9%   0.9416  57.3% 0.3500   11.5%
  Cryospheric indicators                      5  48.8%   1.0000  57.5% 0.3716   13.6%
  Distance to coast                           1  36.4%   1.0000  44.4% 0.2857    0.0%
  Drought monitoring                          1  12.5%   1.0000  20.0% 0.0370    0.0%
  Environmental governance/management         2  39.9%   1.0000  46.8% 0.2774    1.6%
  Erosion/sedimentation                       2  11.3%   1.0000  19.7% 0.0508    0.0%
  Forest science                              5  47.2%   1.0000  58.1% 0.3675   11.5%
  Frozen ground                               1  41.9%   1.0000  53.7% 0.2593    3.7%
  Geodetics                                   1  80.0%   1.0000 100.0% 0.5000    0.0%
  Geomorphic landforms/processes              5  33.1%   1.0000  39.0% 0.2288   13.2%
  Glaciers/ice sheets                         4  47.3%   1.0000  53.2% 0.3229    3.7%
  Ground water                                1  60.0%   1.0000  75.0% 0.5000    0.0%
  Habitat conversion/fragmentation           29  46.5%   0.9974  53.4% 0.3282    3.2%
  Human dimensions                            1  44.4%   1.0000  57.1% 0.4000   20.0%
  Human settlements                          20  49.7%   1.0000  57.0% 0.3673    8.4%
  Infrastructure                              3  28.7%   0.9587  33.6% 0.1702    4.8%
  Land ice/ocean classification               1  75.0%   1.0000  85.7% 0.7500    0.0%
  Land surface/agriculture indicators       134  49.7%   0.9960  58.6% 0.3621    6.5%
  Land surface/water classification           1  65.4%   1.0000  68.0% 0.3429    0.0%
  Land use/land cover                       307  52.0%   0.9986  60.1% 0.3737    7.1%
  Natural hazards                            28  46.5%   1.0000  56.3% 0.3379    7.2%
  Nighttime lights analysis                   1  50.0%   1.0000  60.0% 0.3333    0.0%
  None                                        1  48.0%   1.0000  52.2% 0.3158    0.0%
  Ocean color                                 1  53.3%   1.0000  61.5% 0.2727    9.1%
  Platform characteristics                    1  14.3%   1.0000  33.3% 0.1111    0.0%
  Population                                  4  43.9%   1.0000  52.7% 0.3098    0.7%
  Precipitation                              26  49.3%   0.9954  59.6% 0.3657    7.4%
  Regional climate levels                     1  58.3%   1.0000  63.6% 0.4667   13.3%
  Salinity/density                            2  52.7%   1.0000  63.2% 0.3972    2.1%
  Sea surface temperature                     1  60.0%   1.0000  66.7% 0.3333    0.0%
  Sea surface temperature anomaly             1  50.0%   1.0000  64.7% 0.3636    4.5%
  Sea surface topography                      2  57.1%   1.0000  68.5% 0.4559    2.9%
  Snow/ice                                    6  53.8%   1.0000  63.3% 0.4157   13.8%
  Soils                                       6  36.7%   1.0000  44.9% 0.2526    2.7%
  Spectral/Engineering                        1  40.0%   1.0000  50.0% 0.3333    0.0%
  Surface compositional properties            1  61.5%   1.0000  66.7% 0.4706    0.0%
  Surface mass                                1  85.7%   1.0000 100.0% 0.7500    0.0%
  Surface mineral composition                 1  20.0%   1.0000  25.0% 0.1667    0.0%
  Surface radiative properties               17  51.5%   0.9858  60.5% 0.3565    7.2%
  Surface reflectance properties              1  54.5%   1.0000  66.7% 0.3333   16.7%
  Surface thermal properties                 33  46.5%   1.0000  53.7% 0.3580    7.0%
  Surface water                               2  48.4%   1.0000  58.5% 0.2698    0.0%
  Temporal analysis                           1  30.8%   1.0000  36.4% 0.2222    0.0%
  Terrestrial hydrosphere indicators         63  45.7%   0.9964  54.5% 0.3317    6.7%
  Tides                                       1  30.0%   1.0000  44.4% 0.2727    0.0%
  Topography                                 24  47.1%   1.0000  57.7% 0.3417    4.6%
  Unknown                                     1   0.0%   1.0000   0.0% 0.0000    0.0%
  Vegetation                                172  48.6%   0.9964  56.8% 0.3482    6.6%
  Water quality                               9  45.0%   0.9543  55.0% 0.3104    4.9%
  Weather events                              1  42.1%   1.0000  47.1% 0.3636    0.0%

  Full report saved to /home/qy/system_redesign/outputs/evaluation_report.json