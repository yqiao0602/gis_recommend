(transformer) qy@mdzhang:~/system_redesign$ python ./scripts/evaluate_system.py --eval-mode dev --checkpoint ./outputs/transformer_checkpoints_v4_6/best_model.pth --sp-checkpoint ./outputs/set_predictor_checkpoints_v3/best_model.pth --use-reranker   --oracle --report-tag reranker-oracle-dev
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
L3 inference: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [1:58:21<00:00,  7.10s/sample]
  Done in 7108s

[4] Computing L3 sequence metrics ...

[4a] Running reranker pipeline (N×M candidate pool) ...
Reranker: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [00:05<00:00, 171.07sample/s]
  Reranked 1000/1000 samples

[4b] Computing L3 sequence metrics ...

======================================================================
  Reranker Diagnostics
======================================================================
  Changed predictions: 696/1000 (69.60%)
  Effect counts: improved=407, degraded=264, unchanged=329
  Avg deltas: SetF1=+0.0031, LCS=+0.0053, LenRatio=+0.1217
  Candidate pool: avg=13.72, pool<=1=0, avg_l3_candidates=4.71

[4b] Computing oracle metrics (best from top-N candidates) ...

======================================================================
  Oracle Analysis (max 5 candidates per sample)
======================================================================
     Label |   Set F1 |      gap |      LCS |      gap |  LenRatio |      gap
-----------------------------------------------------------------
  reranked |   49.16% |   +0.00% |   0.3589 |  +0.0000 |    0.9131 |  +0.0000
  raw-top1 |   48.85% |   -0.31% |   0.3536 |  -0.0053 |    0.7914 |  -0.1217
  oracle@3 |   53.31% |   +4.15% |   0.3969 |  +0.0380 |    0.7973 |  -0.1158
  oracle@5 |   54.53% |   +5.37% |   0.4085 |  +0.0496 |    0.7807 |  -0.1323

  QGIS Pool Oracle (reranker candidate pool):
  pool oracle Set F1: 54.43% (gap: +5.27%)
  pool oracle LCS:    0.4068 (gap: +0.0479)

[5] Running QGIS chain evaluation ...
  Initializing QGIS generator ...
  Connecting to Neo4j ...
[INFO] Neo4j GraphRAG Retriever Initialized
  - URI: bolt://localhost:7687
  - Mode: Real Neo4j
  QGIS evaluation:   6%|██████████▊                                                                                                                                                                      | 61/1000 [00:02<00:37, 24.82sample/s]/home/qy/miniconda3/envs/transformer/lib/python3.10/site-packages/neo4j/_sync/work/result.py:635: UserWarning: Expected a result with a single record, but found multiple.
    warn(
  QGIS evaluation: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [00:55<00:00, 18.10sample/s]
  [INFO] Neo4j connection closed
    Done in 56s

======================================================================
  L3 Generation Evaluation (N=1000)
======================================================================
  Token Accuracy (Top-1):    7.44%   <- positional exact match
  Sequence Exact Match:      0.00%   <- full sequence match
  Set F1 (token overlap):   49.16%   <- token set overlap
  Soft Set Sim:            0.9957    <- avg best-match cosine
  L2-Set F1:                57.45%   <- L2 category overlap
  L2-Positional Accuracy:    8.64%   <- positional L2 match
  LCS Ratio:               0.3589    <- subsequence overlap
  Length Ratio (mean):      0.9131

======================================================================
  QGIS Chain Evaluation (N=1000)
======================================================================
  Coverage Score:    0.9668    <- % non-UNKNOWN steps
  Validity Score:    1.0000    <- composite chain quality
  Exist. Validity:   1.0000    <- % non-UNKNOWN steps found in KG
  Struct. Validity:  1.0000    <- issue/critical-unknown penalty
  I/O Compatibility: 0.8921    <- % compatible pairs
  Chain Confidence:  0.8492    <- combined score

======================================================================
  Breakdown by Task Type
======================================================================
  Task Type                                   N  SetF1  SoftSim   L2F1    LCS  TokAcc    Cov    Val    Str    I/O
  ---------------------------------------------------------------------------------------------------------------
  Agricultural plant science                  1  66.7%   1.0000  80.0% 0.3750   25.0%  1.000  1.000  1.000  1.000
  Air quality                                13  47.7%   1.0000  55.4% 0.3628    8.0%  0.982  1.000  1.000  0.905
  Atmospheric gases                           1  50.0%   1.0000  60.0% 0.2857    0.0%  1.000  1.000  1.000  0.750
  Atmospheric radiation                       2  44.8%   1.0000  50.5% 0.2737   14.2%  1.000  1.000  1.000  0.929
  Atmospheric temperature                     9  53.6%   1.0000  64.3% 0.4322    8.1%  0.967  1.000  1.000  0.909
  Atmospheric water vapor                     2  54.2%   1.0000  65.6% 0.4471    0.0%  1.000  1.000  1.000  0.900
  Atmospheric winds                           2  52.2%   1.0000  61.5% 0.4765   12.9%  0.950  1.000  1.000  1.000
  Atmospheric/ocean indicators                2  29.6%   1.0000  33.3% 0.2213   16.2%  0.950  1.000  1.000  0.929
  Bathymetry                                  1  50.0%   1.0000  53.8% 0.2632    5.3%  1.000  1.000  1.000  0.750
  Biospheric indicators                      10  51.2%   1.0000  59.9% 0.3553    5.2%  0.959  1.000  1.000  0.834
  Boundaries                                  5  41.5%   0.9357  51.8% 0.2868    4.0%  0.967  1.000  1.000  0.700
  Carbon flux                                 5  41.3%   1.0000  45.5% 0.2793    9.2%  1.000  1.000  1.000  0.860
  Citizen science data integration            1  36.4%   1.0000  44.4% 0.2857    0.0%  1.000  1.000  1.000  0.667
  Climate feedbacks                           1  91.7%   1.0000 100.0% 0.8462    0.0%  0.909  1.000  1.000  0.750
  Climate indicators                          2  46.2%   1.0000  53.0% 0.2730    8.3%  0.955  1.000  1.000  0.713
  Cloud masking                               1  26.7%   1.0000  30.8% 0.2000   10.0%  1.000  1.000  1.000  0.500
  Clouds                                      8  49.8%   0.9588  61.7% 0.3831   12.6%  0.972  1.000  1.000  0.901
  Cryospheric indicators                      5  47.5%   1.0000  55.3% 0.3716    9.6%  0.986  1.000  1.000  0.861
  Distance to coast                           1  36.4%   1.0000  44.4% 0.2857    0.0%  1.000  1.000  1.000  0.667
  Drought monitoring                          1  37.2%   1.0000  43.9% 0.1852    0.0%  0.938  1.000  1.000  0.923
  Environmental governance/management         2  38.4%   1.0000  42.9% 0.2935    1.6%  1.000  1.000  1.000  0.958
  Erosion/sedimentation                       2  16.0%   1.0000  23.6% 0.0821    0.0%  1.000  1.000  1.000  0.919
  Forest science                              5  47.2%   1.0000  58.1% 0.3675   11.5%  0.933  1.000  1.000  0.646
  Frozen ground                               1  45.5%   1.0000  57.1% 0.2963    3.7%  1.000  1.000  1.000  0.938
  Geodetics                                   1  80.0%   1.0000 100.0% 0.5000    0.0%  1.000  1.000  1.000  1.000
  Geomorphic landforms/processes              5  41.8%   1.0000  50.8% 0.2871   15.7%  0.978  1.000  1.000  0.697
  Glaciers/ice sheets                         4  40.5%   1.0000  51.1% 0.3204    8.6%  1.000  1.000  1.000  0.856
  Ground water                                1  60.0%   0.7521  75.0% 0.5000    0.0%  1.000  1.000  1.000  0.333
  Habitat conversion/fragmentation           29  45.9%   0.9974  52.9% 0.3161    3.2%  0.966  1.000  1.000  0.835
  Human dimensions                            1  44.4%   1.0000  57.1% 0.4000   20.0%  1.000  1.000  1.000  1.000
  Human settlements                          20  49.2%   1.0000  56.3% 0.3752    7.6%  0.972  1.000  1.000  0.887
  Infrastructure                              3  28.7%   0.9587  33.6% 0.1702    4.8%  0.875  1.000  1.000  0.676
  Land ice/ocean classification               1  47.1%   1.0000  66.7% 0.3333   22.2%  0.889  1.000  1.000  0.833
  Land surface/agriculture indicators       134  49.7%   0.9930  58.9% 0.3590    8.5%  0.962  1.000  1.000  0.904
  Land surface/water classification           1  66.7%   1.0000  69.2% 0.4857    0.0%  0.947  1.000  1.000  0.938
  Land use/land cover                       307  52.1%   0.9982  59.8% 0.3828    7.9%  0.969  1.000  1.000  0.906
  Natural hazards                            28  46.7%   0.9969  56.2% 0.3489    9.4%  0.970  1.000  1.000  0.890
  Nighttime lights analysis                   1  57.1%   1.0000  66.7% 0.3750    0.0%  1.000  1.000  1.000  1.000
  None                                        1  34.8%   1.0000  38.1% 0.2105    0.0%  1.000  1.000  1.000  0.333
  Ocean color                                 1  66.7%   1.0000  75.0% 0.1818    0.0%  1.000  1.000  1.000  0.833
  Platform characteristics                    1  50.0%   1.0000  57.1% 0.3333   11.1%  1.000  1.000  1.000  0.833
  Population                                  4  30.1%   1.0000  34.6% 0.2431    9.9%  0.950  1.000  1.000  0.839
  Precipitation                              26  46.0%   0.9966  55.0% 0.3338    8.7%  0.959  1.000  1.000  0.818
  Regional climate levels                     1  58.3%   1.0000  63.6% 0.4667   13.3%  1.000  1.000  1.000  1.000
  Salinity/density                            2  55.5%   1.0000  66.1% 0.4184    0.0%  1.000  1.000  1.000  1.000
  Sea surface temperature                     1  57.1%   1.0000  63.2% 0.4167    0.0%  1.000  1.000  1.000  1.000
  Sea surface temperature anomaly             1  51.4%   1.0000  60.6% 0.3636    0.0%  0.923  1.000  1.000  0.600
  Sea surface topography                      2  59.5%   1.0000  70.7% 0.4853    5.9%  1.000  1.000  1.000  0.818
  Snow/ice                                    6  49.3%   1.0000  59.7% 0.3725   14.3%  0.956  1.000  1.000  0.898
  Soils                                       6  29.5%   1.0000  36.4% 0.1983    2.1%  0.965  1.000  1.000  0.819
  Spectral/Engineering                        1  40.0%   0.7553  50.0% 0.3333    0.0%  1.000  1.000  1.000  1.000
  Surface compositional properties            1  59.3%   0.9009  64.0% 0.4706    0.0%  1.000  1.000  1.000  0.889
  Surface mass                                1  85.7%   1.0000 100.0% 0.7500    0.0%  0.833  1.000  1.000  1.000
  Surface mineral composition                 1  18.2%   1.0000  22.2% 0.1667    0.0%  1.000  1.000  1.000  1.000
  Surface radiative properties               17  52.5%   0.9905  61.0% 0.4101    7.6%  0.933  1.000  1.000  0.936
  Surface reflectance properties              1  54.5%   1.0000  66.7% 0.3333   16.7%  1.000  1.000  1.000  1.000
  Surface thermal properties                 33  47.0%   1.0000  53.5% 0.3533    7.4%  0.977  1.000  1.000  0.932
  Surface water                               2  53.3%   1.0000  63.6% 0.3047    1.2%  1.000  1.000  1.000  0.955
  Temporal analysis                           1  30.8%   1.0000  36.4% 0.2222    0.0%  1.000  1.000  1.000  1.000
  Terrestrial hydrosphere indicators         63  46.2%   0.9961  54.8% 0.3380    6.7%  0.972  1.000  1.000  0.897
  Tides                                       1  30.0%   1.0000  44.4% 0.2727    0.0%  1.000  1.000  1.000  1.000
  Topography                                 24  49.2%   1.0000  59.0% 0.3413    5.5%  0.964  1.000  1.000  0.920
  Unknown                                     1  26.1%   1.0000  28.6% 0.1538    7.7%  1.000  1.000  1.000  0.917
  Vegetation                                172  48.9%   0.9974  57.0% 0.3533    6.5%  0.963  1.000  1.000  0.897
  Water quality                               9  46.2%   0.9662  55.8% 0.2979    8.7%  0.942  1.000  1.000  0.926
  Weather events                              1  42.1%   1.0000  47.1% 0.3636    0.0%  1.000  1.000  1.000  1.000

  Full report saved to /home/qy/system_redesign/outputs/evaluation_report.json
  Full report saved to /home/qy/system_redesign/outputs/evaluation_reports/evaluation-report-reranker-oracle-dev-20260412-112346.json