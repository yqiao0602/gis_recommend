(transformer) qy@mdzhang:~/system_redesign$ python -m gis_recommend.evaluation --eval-mode dev --use-reranker --reranker-v3 --executable-check --executable-strict --checkpoint outputs/transformer_checkpoints_v4_6/best_model.pth --sp-checkpoint outputs/set_predictor_checkpoints_v3/best_model.pth --report-tag v3-exec-dev
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
L3 inference: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [1:31:56<00:00,  5.52s/sample]
  Done in 5524s

[4] Computing L3 sequence metrics ...

[4a] Running reranker pipeline (N×M candidate pool) ...
  [OK] QueryChainEncoder loaded (sentence-transformers/all-MiniLM-L6-v2)
  [OK] Two-stage reranker v3 (semantic) initialized, set_threshold=0.70 (soft)
Reranker: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [00:31<00:00, 31.30sample/s]
  Reranked 1000/1000 samples

[4b] Computing L3 sequence metrics ...

======================================================================
  Reranker Diagnostics
======================================================================
  Changed predictions: 259/1000 (25.90%)
  Effect counts: improved=154, degraded=88, unchanged=758
  Avg deltas: SetF1=+0.0042, LCS=+0.0020, LenRatio=+0.0280
  Candidate pool: avg=13.84, pool<=1=0, avg_l3_candidates=4.71

[5] Running QGIS chain evaluation ...
  Initializing QGIS generator ...
  Connecting to Neo4j ...
[INFO] Neo4j GraphRAG Retriever Initialized
  - URI: bolt://localhost:7687
  - Mode: Real Neo4j
  QGIS evaluation:   6%|██████████▉                                                                                                                                                                      | 62/1000 [00:02<00:33, 28.15sample/s]/home/qy/miniconda3/envs/transformer/lib/python3.10/site-packages/neo4j/_sync/work/result.py:635: UserWarning: Expected a result with a single record, but found multiple.
    warn(
  QGIS evaluation: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1000/1000 [00:50<00:00, 19.80sample/s]
  [INFO] Neo4j connection closed
    Done in 51s

[5b] Computing executable-chain ratio ...
[INFO] Neo4j GraphRAG Retriever Initialized
  - URI: bolt://localhost:7687
  - Mode: Real Neo4j
    [OK] Neo4j validator ready for Level 2 check

======================================================================
  Executable Chain Analysis
======================================================================
  Total samples:   1000
  With chain:      1000  (100.00% of total)

  Level 1 (local io_types, strict):
    [WARN] qgis_operator_io_types.json missing — Level 1 not computed

  Level 2 (Neo4j KG validator, strict):
    overall:      50.20%  (502/1000)
    conditional:  50.20%  (502/1000)
[INFO] Neo4j connection closed

======================================================================
  L3 Generation Evaluation (N=1000)
======================================================================
  Token Accuracy (Top-1):    6.76%   <- positional exact match
  Sequence Exact Match:      0.00%   <- full sequence match
  Set F1 (token overlap):   49.27%   <- token set overlap
  Soft Set Sim:            0.9962    <- avg best-match cosine
  L2-Set F1:                57.77%   <- L2 category overlap
  L2-Positional Accuracy:    7.98%   <- positional L2 match
  LCS Ratio:               0.3556    <- subsequence overlap
  Length Ratio (mean):      0.8194

======================================================================
  QGIS Chain Evaluation (N=1000)
======================================================================
  Coverage Score:    0.9589    <- % non-UNKNOWN steps
  Validity Score:    0.8855    <- composite chain quality
  Exist. Validity:   1.0000    <- % non-UNKNOWN steps found in KG
  Struct. Validity:  0.7311    <- issue/critical-unknown penalty
  I/O Compatibility: 0.8979    <- % compatible pairs
  Chain Confidence:  0.8678    <- combined score

======================================================================
  Breakdown by Task Type
======================================================================
  Task Type                                   N  SetF1  SoftSim   L2F1    LCS  TokAcc    Cov    Val    Str    I/O
  ---------------------------------------------------------------------------------------------------------------
  Agricultural plant science                  1  66.7%   1.0000  80.0% 0.3750   25.0%  1.000  1.000  1.000  1.000
  Air quality                                13  49.2%   1.0000  57.6% 0.3660    8.0%  0.956  0.953  0.888  0.963
  Atmospheric gases                           1  54.5%   1.0000  66.7% 0.2857    0.0%  1.000  1.000  1.000  1.000
  Atmospheric radiation                       2  39.8%   1.0000  44.4% 0.2737   11.4%  0.944  0.858  0.675  0.857
  Atmospheric temperature                     9  52.3%   1.0000  64.1% 0.4122    5.1%  0.950  0.898  0.756  0.916
  Atmospheric water vapor                     2  51.5%   1.0000  62.9% 0.4176    0.0%  1.000  1.000  1.000  1.000
  Atmospheric winds                           2  56.9%   1.0000  66.7% 0.5059   10.0%  0.944  1.000  1.000  1.000
  Atmospheric/ocean indicators                2  29.6%   1.0000  33.3% 0.2213   16.2%  0.950  0.916  0.800  0.929
  Bathymetry                                  1  44.4%   1.0000  48.0% 0.3158    5.3%  0.875  0.820  0.600  0.800
  Biospheric indicators                      10  49.3%   1.0000  57.7% 0.3513    5.3%  0.937  0.811  0.555  0.832
  Boundaries                                  5  46.1%   1.0000  57.6% 0.3602    3.3%  0.950  0.804  0.630  0.667
  Carbon flux                                 5  39.5%   0.9517  46.3% 0.2611   11.0%  0.982  0.895  0.760  0.893
  Citizen science data integration            1  40.0%   1.0000  50.0% 0.2857    0.0%  1.000  1.000  1.000  1.000
  Climate feedbacks                           1  91.7%   1.0000 100.0% 0.8462    0.0%  0.909  0.723  0.350  0.750
  Climate indicators                          2  46.2%   1.0000  53.0% 0.2730    8.3%  0.955  0.715  0.350  0.713
  Cloud masking                               1  28.6%   1.0000  33.3% 0.2000   10.0%  1.000  1.000  1.000  1.000
  Clouds                                      8  53.3%   0.9403  64.2% 0.4083    9.2%  0.947  0.913  0.800  0.917
  Cryospheric indicators                      5  46.8%   1.0000  58.7% 0.3144   12.1%  0.969  0.824  0.580  0.855
  Distance to coast                           1  36.4%   1.0000  44.4% 0.2857    0.0%  1.000  0.793  0.600  0.667
  Drought monitoring                          1  12.5%   1.0000  20.0% 0.0370    0.0%  1.000  1.000  1.000  1.000
  Environmental governance/management         2  39.9%   1.0000  46.8% 0.2774    1.6%  1.000  0.921  0.800  0.955
  Erosion/sedimentation                       2  11.3%   1.0000  19.7% 0.0508    0.0%  1.000  0.842  0.600  0.909
  Forest science                              5  47.2%   1.0000  58.1% 0.3675   11.5%  0.933  0.775  0.560  0.646
  Frozen ground                               1  41.9%   1.0000  53.7% 0.2593    3.7%  1.000  1.000  1.000  1.000
  Geodetics                                   1  80.0%   1.0000 100.0% 0.5000    0.0%  1.000  1.000  1.000  1.000
  Geomorphic landforms/processes              5  33.1%   1.0000  39.0% 0.2288   13.2%  0.975  0.798  0.580  0.723
  Glaciers/ice sheets                         4  47.3%   1.0000  53.2% 0.3229    3.7%  1.000  0.868  0.675  0.907
  Ground water                                1  60.0%   1.0000  75.0% 0.5000    0.0%  1.000  0.793  0.600  0.667
  Habitat conversion/fragmentation           29  46.7%   0.9974  53.6% 0.3277    4.2%  0.953  0.772  0.466  0.794
  Human dimensions                            1  44.4%   1.0000  57.1% 0.4000   20.0%  1.000  1.000  1.000  1.000
  Human settlements                          20  48.8%   1.0000  56.5% 0.3559    7.2%  0.957  0.884  0.745  0.869
  Infrastructure                              3  28.7%   0.9587  33.6% 0.1702    4.8%  0.875  0.754  0.483  0.676
  Land ice/ocean classification               1  75.0%   1.0000  85.7% 0.7500    0.0%  0.750  1.000  1.000  1.000
  Land surface/agriculture indicators       134  50.2%   0.9948  59.2% 0.3636    6.7%  0.956  0.885  0.738  0.883
  Land surface/water classification           1  66.7%   1.0000  69.2% 0.4857    0.0%  0.947  0.848  0.600  0.938
  Land use/land cover                       307  51.8%   0.9978  59.8% 0.3729    7.4%  0.962  0.888  0.733  0.910
  Natural hazards                            28  47.4%   1.0000  56.8% 0.3295    4.4%  0.961  0.863  0.666  0.900
  Nighttime lights analysis                   1  50.0%   1.0000  60.0% 0.3333    0.0%  1.000  1.000  1.000  1.000
  None                                        1  48.0%   1.0000  52.2% 0.3158    0.0%  0.833  0.793  0.600  0.667
  Ocean color                                 1  53.3%   1.0000  61.5% 0.2727    9.1%  1.000  1.000  1.000  1.000
  Platform characteristics                    1  50.0%   1.0000  57.1% 0.3333   11.1%  1.000  0.827  0.600  0.833
  Population                                  4  43.9%   1.0000  52.7% 0.3098    0.7%  0.938  0.958  0.900  0.964
  Precipitation                              26  50.6%   0.9966  60.7% 0.3682    8.9%  0.959  0.855  0.667  0.857
  Regional climate levels                     1  58.3%   1.0000  63.6% 0.4667   13.3%  1.000  1.000  1.000  1.000
  Salinity/density                            2  32.7%   1.0000  38.2% 0.2305    2.1%  1.000  1.000  1.000  1.000
  Sea surface temperature                     1  60.0%   1.0000  66.7% 0.3333    0.0%  1.000  1.000  1.000  1.000
  Sea surface temperature anomaly             1  50.0%   1.0000  64.7% 0.3636    4.5%  0.857  0.574  0.100  0.444
  Sea surface topography                      2  57.1%   1.0000  68.5% 0.4559    2.9%  1.000  0.920  0.800  0.950
  Snow/ice                                    6  53.2%   1.0000  62.6% 0.4042   14.3%  0.952  0.857  0.650  0.897
  Soils                                       6  36.5%   1.0000  44.6% 0.2860    3.7%  0.956  0.939  0.867  0.929
  Spectral/Engineering                        1  60.0%   1.0000  75.0% 0.5000    0.0%  1.000  1.000  1.000  1.000
  Surface compositional properties            1  61.5%   1.0000  66.7% 0.4706    0.0%  0.889  1.000  1.000  1.000
  Surface mass                                1  85.7%   1.0000 100.0% 0.7500    0.0%  0.833  1.000  1.000  1.000
  Surface mineral composition                 1  18.2%   1.0000  22.2% 0.1667    0.0%  1.000  1.000  1.000  1.000
  Surface radiative properties               17  50.8%   0.9858  59.3% 0.3590    6.3%  0.929  0.914  0.812  0.899
  Surface reflectance properties              1  54.5%   1.0000  66.7% 0.3333   16.7%  1.000  1.000  1.000  1.000
  Surface thermal properties                 33  48.2%   1.0000  55.2% 0.3752    8.3%  0.978  0.928  0.826  0.943
  Surface water                               2  48.4%   1.0000  58.5% 0.2698    0.0%  1.000  0.864  0.675  0.889
  Temporal analysis                           1  15.4%   1.0000  18.2% 0.1111    0.0%  1.000  1.000  1.000  1.000
  Terrestrial hydrosphere indicators         63  46.1%   0.9970  54.9% 0.3305    6.3%  0.967  0.869  0.681  0.902
  Tides                                       1  26.7%   1.0000  46.2% 0.0909    0.0%  1.000  1.000  1.000  1.000
  Topography                                 24  47.6%   0.9901  59.1% 0.3532    4.8%  0.941  0.939  0.867  0.928
  Unknown                                     1   0.0%   1.0000   0.0% 0.0000    0.0%  1.000  0.810  0.600  0.750
  Vegetation                                172  48.5%   0.9980  56.7% 0.3468    6.5%  0.957  0.892  0.742  0.912
  Water quality                               9  49.0%   0.9543  59.7% 0.3104    7.1%  0.939  0.898  0.750  0.930
  Weather events                              1  42.1%   1.0000  47.1% 0.3636    0.0%  1.000  1.000  1.000  1.000

  Full report saved to /home/qy/system_redesign/outputs/evaluation_report.json
  Full report saved to /home/qy/system_redesign/outputs/evaluation_reports/evaluation-report-v3-exec-dev-20260418-122729.json