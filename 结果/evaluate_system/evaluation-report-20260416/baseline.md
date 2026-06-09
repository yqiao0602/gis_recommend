(transformer) qy@mdzhang:~/system_redesign$ python scripts/evaluate_system.py --eval-mode dev --checkpoint outputs/transformer_checkpoints_v4_6/best_model.pth --sp-checkpoint outputs/set_predictor_checkpoints_v3/best_model.pth --report-tag baseline-dev
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
L3 inference: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [1:58:58<00:00,  7.14s/sample]
  Done in 7161s

[4] Computing L3 sequence metrics ...

[4b] Computing L3 sequence metrics ...

[5] Running QGIS chain evaluation ...
  Initializing QGIS generator ...
  Connecting to Neo4j ...
[INFO] Neo4j GraphRAG Retriever Initialized
  - URI: bolt://localhost:7687
  - Mode: Real Neo4j
  QGIS evaluation:   6%|██████████▌                                                                                                                                                                      | 60/1000 [00:03<00:47, 19.98sample/s]/home/qy/miniconda3/envs/transformer/lib/python3.10/site-packages/neo4j/_sync/work/result.py:635: UserWarning: Expected a result with a single record, but found multiple.
    warn(
  QGIS evaluation: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [00:52<00:00, 19.19sample/s]
  [INFO] Neo4j connection closed
    Done in 57s

======================================================================
  L3 Generation Evaluation (N=1000)
======================================================================
  Token Accuracy (Top-1):    6.37%   <- positional exact match
  Sequence Exact Match:      0.00%   <- full sequence match
  Set F1 (token overlap):   48.85%   <- token set overlap
  Soft Set Sim:            0.9965    <- avg best-match cosine
  L2-Set F1:                57.44%   <- L2 category overlap
  L2-Positional Accuracy:    7.57%   <- positional L2 match
  LCS Ratio:               0.3536    <- subsequence overlap
  Length Ratio (mean):      0.7914

======================================================================
  QGIS Chain Evaluation (N=977)
======================================================================
  Coverage Score:    0.9592    <- % non-UNKNOWN steps
  Validity Score:    1.0000    <- composite chain quality
  Exist. Validity:   1.0000    <- % non-UNKNOWN steps found in KG
  Struct. Validity:  1.0000    <- issue/critical-unknown penalty
  I/O Compatibility: 0.8957    <- % compatible pairs
  Chain Confidence:  0.8709    <- combined score

======================================================================
  Breakdown by Task Type
======================================================================
  Task Type                                   N  SetF1  SoftSim   L2F1    LCS  TokAcc    Cov    Val    Str    I/O
  ---------------------------------------------------------------------------------------------------------------
  Agricultural plant science                  1  50.0%   1.0000  60.0% 0.3750    0.0%  1.000  1.000  1.000  0.667
  Air quality                                13  49.9%   1.0000  57.8% 0.3720    6.4%  0.986  1.000  1.000  0.937
  Atmospheric gases                           1  60.0%   1.0000  75.0% 0.4286    0.0%  1.000  1.000  1.000  1.000
  Atmospheric radiation                       2  39.8%   1.0000  44.4% 0.2737   11.4%  0.944  1.000  1.000  0.857
  Atmospheric temperature                     9  52.9%   1.0000  65.1% 0.4122   12.5%  0.950  1.000  1.000  0.916
  Atmospheric water vapor                     2  51.5%   1.0000  62.9% 0.4176    0.0%  1.000  1.000  1.000  1.000
  Atmospheric winds                           2  60.3%   1.0000  72.0% 0.5059   22.9%  0.944  1.000  1.000  0.917
  Atmospheric/ocean indicators                2  29.6%   1.0000  33.3% 0.2213   16.2%  0.950  1.000  1.000  0.929
  Bathymetry                                  1  44.4%   1.0000  48.0% 0.3158    5.3%  0.875  1.000  1.000  0.800
  Biospheric indicators                      10  49.1%   1.0000  57.4% 0.3395    5.2%  0.947  1.000  1.000  0.841
  Boundaries                                  5  47.2%   1.0000  59.5% 0.3602    3.3%  0.950  1.000  1.000  0.733
  Carbon flux                                 5  36.4%   1.0000  42.9% 0.2429    7.4%  0.982  1.000  1.000  0.797
  Citizen science data integration            1  36.4%   1.0000  44.4% 0.2857    0.0%  1.000  1.000  1.000  0.667
  Climate feedbacks                           1  91.7%   1.0000 100.0% 0.8462    0.0%  0.909  1.000  1.000  0.750
  Climate indicators                          2  39.0%   1.0000  44.6% 0.3064    0.0%  0.955  1.000  1.000  0.688
  Cloud masking                               1  28.6%   1.0000  33.3% 0.2000   10.0%  1.000  1.000  1.000  0.667
  Clouds                                      8  47.9%   0.9416  57.9% 0.3667    9.2%  0.947  1.000  1.000  0.901
  Cryospheric indicators                      5  50.4%   1.0000  63.0% 0.3366   12.1%  0.969  1.000  1.000  0.872
  Distance to coast                           1  20.0%   1.0000  25.0% 0.1429    0.0%  1.000  1.000  1.000  1.000
  Drought monitoring                          1  12.5%   1.0000  20.0% 0.0370    0.0%  1.000  1.000  1.000  1.000
  Environmental governance/management         2  39.9%   1.0000  46.8% 0.2774    1.6%  1.000  1.000  1.000  0.955
  Erosion/sedimentation                       2   6.3%   1.0000  12.4% 0.0254    0.0%  1.000  1.000  1.000  0.962
  Forest science                              5  47.2%   1.0000  58.1% 0.3675   11.5%  0.933  1.000  1.000  0.646
  Frozen ground                               1  41.9%   1.0000  53.7% 0.2593    3.7%  1.000  1.000  1.000  1.000
  Geodetics                                   1  80.0%   1.0000 100.0% 0.5000    0.0%  1.000  1.000  1.000  1.000
  Geomorphic landforms/processes              5  33.1%   1.0000  39.0% 0.2288    9.2%  0.975  1.000  1.000  0.657
  Glaciers/ice sheets                         4  46.8%   1.0000  53.7% 0.3288    3.7%  0.975  1.000  1.000  0.939
  Ground water                                1  60.0%   1.0000  75.0% 0.5000    0.0%  1.000  1.000  1.000  0.667
  Habitat conversion/fragmentation           29  46.6%   0.9958  53.5% 0.3197    3.6%  0.951  1.000  1.000  0.779
  Human dimensions                            1  50.0%   1.0000  66.7% 0.4000    0.0%  1.000  1.000  1.000  1.000
  Human settlements                          20  49.2%   1.0000  57.2% 0.3551    7.2%  0.956  1.000  1.000  0.849
  Infrastructure                              3  28.7%   0.9587  33.6% 0.1702    4.8%  0.875  1.000  1.000  0.676
  Land ice/ocean classification               1  75.0%   1.0000  85.7% 0.7500    0.0%  0.750  1.000  1.000  1.000
  Land surface/agriculture indicators       134  49.2%   0.9953  58.2% 0.3642    7.0%  0.954  1.000  1.000  0.880
  Land surface/water classification           1  66.7%   1.0000  69.2% 0.4857    0.0%  0.947  1.000  1.000  0.938
  Land use/land cover                       307  52.0%   0.9980  60.2% 0.3717    6.6%  0.961  1.000  1.000  0.915
  Natural hazards                            28  48.3%   1.0000  58.1% 0.3426    5.0%  0.966  1.000  1.000  0.908
  Nighttime lights analysis                   1  50.0%   1.0000  60.0% 0.3333    0.0%  1.000  1.000  1.000  1.000
  None                                        1  48.0%   1.0000  52.2% 0.3158    0.0%  0.833  1.000  1.000  0.667
  Ocean color                                 1  53.3%   1.0000  61.5% 0.3636    0.0%  1.000  1.000  1.000  1.000
  Platform characteristics                    1  50.0%   1.0000  57.1% 0.3333   11.1%  1.000  1.000  1.000  0.833
  Population                                  4  43.1%   1.0000  51.9% 0.3025    0.0%  0.938  1.000  1.000  1.000
  Precipitation                              26  49.1%   0.9954  59.3% 0.3791    8.2%  0.962  1.000  1.000  0.840
  Regional climate levels                     1  58.3%   1.0000  63.6% 0.4667   13.3%  1.000  1.000  1.000  1.000
  Salinity/density                            2  52.7%   1.0000  63.2% 0.3972    2.1%  1.000  1.000  1.000  1.000
  Sea surface temperature                     1  60.0%   1.0000  66.7% 0.3333    0.0%  1.000  1.000  1.000  1.000
  Sea surface temperature anomaly             1  50.0%   1.0000  64.7% 0.3636    4.5%  0.857  1.000  1.000  0.444
  Sea surface topography                      2  57.1%   1.0000  68.5% 0.4559    2.9%  1.000  1.000  1.000  0.950
  Snow/ice                                    6  50.0%   1.0000  56.3% 0.3661   10.5%  0.982  1.000  1.000  0.877
  Soils                                       6  37.0%   1.0000  45.1% 0.2559    3.0%  0.980  1.000  1.000  0.915
  Spectral/Engineering                        1  40.0%   1.0000  50.0% 0.3333    0.0%  1.000  1.000  1.000  1.000
  Surface compositional properties            1  61.5%   1.0000  66.7% 0.4706    0.0%  0.889  1.000  1.000  1.000
  Surface mass                                1  85.7%   1.0000 100.0% 0.7500    0.0%  0.833  1.000  1.000  1.000
  Surface mineral composition                 1  20.0%   1.0000  25.0% 0.1667    0.0%  1.000  1.000  1.000  1.000
  Surface radiative properties               17  48.4%   0.9858  56.7% 0.3495    6.8%  0.933  1.000  1.000  0.873
  Surface reflectance properties              1  66.7%   1.0000  85.7% 0.4000   20.0%  1.000  1.000  1.000  1.000
  Surface thermal properties                 33  47.6%   1.0000  54.8% 0.3674    6.6%  0.976  1.000  1.000  0.938
  Surface water                               2  48.4%   1.0000  58.5% 0.2698    0.0%  1.000  1.000  1.000  0.889
  Temporal analysis                           1  30.8%   1.0000  36.4% 0.2222    0.0%  1.000  1.000  1.000  1.000
  Terrestrial hydrosphere indicators         63  43.9%   0.9964  52.9% 0.3228    6.4%  0.963  1.000  1.000  0.906
  Tides                                       1  26.7%   1.0000  46.2% 0.0909    0.0%  1.000  1.000  1.000  1.000
  Topography                                 24  47.6%   0.9838  59.0% 0.3537    4.2%  0.955  1.000  1.000  0.904
  Unknown                                     1   0.0%   1.0000   0.0% 0.0000    0.0%  1.000  1.000  1.000  0.750
  Vegetation                                172  48.3%   0.9973  56.7% 0.3427    6.4%  0.955  1.000  1.000  0.911
  Water quality                               9  42.4%   0.9838  52.4% 0.2873    2.6%  0.944  1.000  1.000  0.888
  Weather events                              1  42.1%   1.0000  47.1% 0.3636    0.0%  1.000  1.000  1.000  1.000

  Full report saved to /home/qy/system_redesign/outputs/evaluation_report.json