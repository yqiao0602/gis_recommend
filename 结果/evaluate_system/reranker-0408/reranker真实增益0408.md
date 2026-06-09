实验 2：看 reranker 真实增益

(transformer) qy@mdzhang:~/system_redesign$ python scripts/evaluate_system.py --eval-mode dev --skip-qgis --checkpoint outputs/transformer_checkpoints_v4_6/best_model.pth --set-prior-mode off --use-reranker
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
  [Set Predictor] prior mode = off
L3 inference: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [1:19:02<00:00,  4.74s/sample]
  Done in 4749s

[4] Computing L3 sequence metrics ...

[4a] Running reranker pipeline (N×M candidate pool) ...
Reranker: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [00:04<00:00, 209.07sample/s]
  Reranked 999/1000 samples

[4b] Computing L3 sequence metrics ...

======================================================================
  Reranker Diagnostics
======================================================================
  Changed predictions: 254/1000 (25.40%)
  Effect counts: improved=110, degraded=132, unchanged=758
  Avg deltas: SetF1=-0.0018, LCS=-0.0009, LenRatio=+0.0013
  Candidate pool: avg=13.60, pool<=1=1, avg_l3_candidates=4.68

[5] Skipping QGIS evaluation (--skip-qgis)

======================================================================
  L3 Generation Evaluation (N=1000)
======================================================================
  Token Accuracy (Top-1):    6.32%   <- positional exact match
  Sequence Exact Match:      0.00%   <- full sequence match
  Set F1 (token overlap):   48.07%   <- token set overlap
  Soft Set Sim:            0.9948    <- avg best-match cosine
  L2-Set F1:                56.82%   <- L2 category overlap
  L2-Positional Accuracy:    7.59%   <- positional L2 match
  LCS Ratio:               0.3487    <- subsequence overlap
  Length Ratio (mean):      0.7521

======================================================================
  Breakdown by Task Type
======================================================================
  Task Type                                   N  SetF1  SoftSim   L2F1    LCS  TokAcc
  -----------------------------------------------------------------------------------
  Agricultural plant science                  1  50.0%   1.0000  60.0% 0.2500    0.0%
  Air quality                                13  47.9%   1.0000  57.7% 0.3614    8.2%
  Atmospheric gases                           1  60.0%   1.0000  75.0% 0.4286    0.0%
  Atmospheric radiation                       2  37.0%   1.0000  42.0% 0.3005    7.1%
  Atmospheric temperature                     9  52.1%   1.0000  64.3% 0.4136    4.3%
  Atmospheric water vapor                     2  50.7%   1.0000  61.9% 0.4176    0.0%
  Atmospheric winds                           2  63.0%   1.0000  74.9% 0.5059   22.9%
  Atmospheric/ocean indicators                2  29.8%   1.0000  33.6% 0.2213   16.2%
  Bathymetry                                  1  57.1%   1.0000  61.5% 0.3158    5.3%
  Biospheric indicators                      10  47.9%   1.0000  58.3% 0.3461    5.2%
  Boundaries                                  5  46.7%   0.9026  58.1% 0.3565   11.0%
  Carbon flux                                 5  28.0%   1.0000  34.7% 0.1839    8.4%
  Citizen science data integration            1  36.4%   1.0000  44.4% 0.2857    0.0%
  Climate feedbacks                           1  91.7%   1.0000 100.0% 0.8462    0.0%
  Climate indicators                          2  23.0%   1.0000  26.0% 0.1745    0.0%
  Cloud masking                               1  28.6%   1.0000  33.3% 0.2000   10.0%
  Clouds                                      8  47.6%   0.9438  58.7% 0.3619    8.8%
  Cryospheric indicators                      5  47.1%   1.0000  57.5% 0.3382   12.3%
  Distance to coast                           1  20.0%   1.0000  25.0% 0.1429    0.0%
  Drought monitoring                          1  12.5%   1.0000  20.0% 0.0370    0.0%
  Environmental governance/management         2  35.6%   1.0000  39.3% 0.2774    1.6%
  Erosion/sedimentation                       2   4.8%   1.0000  12.1% 0.0169    0.0%
  Forest science                              5  40.8%   1.0000  53.5% 0.3126    2.6%
  Frozen ground                               1  41.9%   1.0000  53.7% 0.2593    3.7%
  Geodetics                                   1  80.0%   1.0000 100.0% 0.5000    0.0%
  Geomorphic landforms/processes              5  28.1%   1.0000  37.2% 0.1871    9.0%
  Glaciers/ice sheets                         4  41.1%   1.0000  49.5% 0.3061    1.8%
  Ground water                                1  60.0%   1.0000  75.0% 0.5000    0.0%
  Habitat conversion/fragmentation           29  45.5%   0.9895  51.8% 0.3086    4.8%
  Human dimensions                            1  50.0%   1.0000  66.7% 0.4000    0.0%
  Human settlements                          20  48.1%   1.0000  55.3% 0.3434    6.3%
  Infrastructure                              3  31.8%   0.9528  40.7% 0.2104    4.8%
  Land ice/ocean classification               1  47.1%   1.0000  66.7% 0.3333   22.2%
  Land surface/agriculture indicators       134  49.0%   0.9921  58.5% 0.3579    5.6%
  Land surface/water classification           1  66.7%   1.0000  69.2% 0.4857    0.0%
  Land use/land cover                       307  51.3%   0.9979  59.8% 0.3692    6.3%
  Natural hazards                            28  46.0%   0.9969  54.8% 0.3504    8.0%
  Nighttime lights analysis                   1  36.4%   1.0000  44.4% 0.1667    0.0%
  None                                        1  34.8%   1.0000  38.1% 0.2105    0.0%
  Ocean color                                 1  53.3%   1.0000  61.5% 0.2727    9.1%
  Platform characteristics                    1  50.0%   1.0000  57.1% 0.3333   11.1%
  Population                                  4  42.0%   1.0000  50.5% 0.3275    0.0%
  Precipitation                              26  46.6%   0.9947  56.6% 0.3489    6.6%
  Regional climate levels                     1  60.9%   1.0000  66.7% 0.3333    6.7%
  Salinity/density                            2  55.8%   1.0000  66.4% 0.4184    1.1%
  Sea surface temperature                     1  60.0%   1.0000  66.7% 0.3333    0.0%
  Sea surface temperature anomaly             1  57.1%   1.0000  66.7% 0.4545    0.0%
  Sea surface topography                      2  54.2%   1.0000  66.7% 0.4265    0.0%
  Snow/ice                                    6  49.9%   1.0000  56.4% 0.3421   10.3%
  Soils                                       6  32.3%   1.0000  41.8% 0.2203    3.0%
  Spectral/Engineering                        1  40.0%   1.0000  50.0% 0.3333    0.0%
  Surface compositional properties            1  50.0%   1.0000  54.5% 0.3529    0.0%
  Surface mass                                1  85.7%   1.0000 100.0% 0.7500    0.0%
  Surface mineral composition                 1  40.0%   1.0000  50.0% 0.3333    0.0%
  Surface radiative properties               17  47.2%   0.9858  55.9% 0.3312    5.6%
  Surface reflectance properties              1  66.7%   1.0000  85.7% 0.4000   20.0%
  Surface thermal properties                 33  45.1%   1.0000  52.3% 0.3381    8.9%
  Surface water                               2  37.3%   1.0000  44.3% 0.2698   10.0%
  Temporal analysis                           1  30.8%   1.0000  36.4% 0.2222    0.0%
  Terrestrial hydrosphere indicators         63  45.8%   0.9913  54.8% 0.3369    6.2%
  Tides                                       1  50.0%   1.0000  66.7% 0.3636   18.2%
  Topography                                 24  43.7%   0.9951  53.2% 0.3227    3.5%
  Unknown                                     1   0.0%   1.0000   0.0% 0.0000    0.0%
  Vegetation                                172  48.4%   0.9964  57.0% 0.3490    7.3%
  Water quality                               9  38.8%   0.9616  47.1% 0.2702    3.5%
  Weather events                              1  40.0%   1.0000  44.4% 0.3636    0.0%

  Full report saved to /home/qy/system_redesign/outputs/evaluation_report.json