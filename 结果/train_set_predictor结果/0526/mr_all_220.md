(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_set_predictor_quality_gate.py --mrv-ablation-dir outputs_v2/v4_qg_mr_ablation_from_multisolution --mrv-ablation-version mr_all_220
  Active tokens: 47 / 94
/home/qy/miniconda3/envs/transformer/lib/python3.10/site-packages/torch/nn/modules/transformer.py:286: UserWarning: enable_nested_tensor is True, but self.use_nested_tensor is False because encoder_layer.norm_first was True
  warnings.warn(f"enable_nested_tensor is True, but self.use_nested_tensor is False because {why_not_sparsity_fast_path}")
======================================================================
Set Predictor V3 Quality-Gate Training
======================================================================
  Workflows: 77104
  Train/Val/Test: 61715 / 7694 / 7695
  Task types: 47
  Active tokens: 47
  Checkpoint dir: /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6
  Balanced sampling task types: 47
  Checkpoint: latest epoch snapshot; metrics are recorded only
Epoch 1/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:27<00:00,  1.29it/s, loss=0.7256, bin=0.4621, cnt=0.5269]
  Epoch 1: loss=0.9882(bin=0.6332,cnt=0.7101), val_loss=0.8898, F1@0.50=0.5782, F1@0.70=0.6289
         Jaccard=0.426 ExactMatch=0.0% predSz=12.3 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=49.7% top3R=0.409 top5R=0.597 top8R=0.771 top10R=0.842
         Brier=0.1089 ECE=0.1474 LR=3.33e-06, Time=897.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 2/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:29<00:00,  1.29it/s, loss=0.5896, bin=0.3649, cnt=0.4495]
  Epoch 2: loss=0.6427(bin=0.3719,cnt=0.5416), val_loss=0.8459, F1@0.50=0.6243, F1@0.70=0.6620
         Jaccard=0.476 ExactMatch=0.5% predSz=10.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=37.7% top3R=0.442 top5R=0.638 top8R=0.801 top10R=0.869
         Brier=0.0918 ECE=0.1077 LR=6.67e-06, Time=885.6s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 3/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:28<00:00,  1.29it/s, loss=0.5196, bin=0.2891, cnt=0.4609]
  Epoch 3: loss=0.5068(bin=0.2898,cnt=0.4340), val_loss=0.8550, F1@0.50=0.6060, F1@0.70=0.6545
         Jaccard=0.456 ExactMatch=0.5% predSz=12.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=46.8% top3R=0.444 top5R=0.639 top8R=0.806 top10R=0.872
         Brier=0.1056 ECE=0.1355 LR=1.00e-05, Time=885.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 4/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:28<00:00,  1.29it/s, loss=0.4086, bin=0.2664, cnt=0.2844]
  Epoch 4: loss=0.4380(bin=0.2524,cnt=0.3712), val_loss=0.8342, F1@0.50=0.6276, F1@0.70=0.6711
         Jaccard=0.479 ExactMatch=0.5% predSz=11.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=38.8% top3R=0.451 top5R=0.653 top8R=0.815 top10R=0.877
         Brier=0.0952 ECE=0.1240 LR=9.97e-06, Time=885.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 5/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:28<00:00,  1.29it/s, loss=0.5360, bin=0.2956, cnt=0.4808]
  Epoch 5: loss=0.3919(bin=0.2264,cnt=0.3310), val_loss=0.8297, F1@0.50=0.6386, F1@0.70=0.6872
         Jaccard=0.492 ExactMatch=1.2% predSz=10.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=36.5% top3R=0.457 top5R=0.652 top8R=0.815 top10R=0.876
         Brier=0.0882 ECE=0.1132 LR=9.87e-06, Time=886.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 6/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:28<00:00,  1.29it/s, loss=0.2874, bin=0.1465, cnt=0.2818]
  Epoch 6: loss=0.3652(bin=0.2101,cnt=0.3100), val_loss=0.8321, F1@0.50=0.6511, F1@0.70=0.6847
         Jaccard=0.508 ExactMatch=1.9% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=32.6% top3R=0.461 top5R=0.654 top8R=0.819 top10R=0.882
         Brier=0.0867 ECE=0.1034 LR=9.70e-06, Time=886.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 7/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:52<00:00,  1.25it/s, loss=0.3029, bin=0.1672, cnt=0.2714]
  Epoch 7: loss=0.3442(bin=0.1974,cnt=0.2936), val_loss=0.8300, F1@0.50=0.6534, F1@0.70=0.6917
         Jaccard=0.510 ExactMatch=1.5% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=31.3% top3R=0.459 top5R=0.655 top8R=0.818 top10R=0.882
         Brier=0.0855 ECE=0.1068 LR=9.47e-06, Time=911.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 8/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:28<00:00,  1.29it/s, loss=0.2425, bin=0.1761, cnt=0.1329]
  Epoch 8: loss=0.3251(bin=0.1867,cnt=0.2768), val_loss=0.8412, F1@0.50=0.6375, F1@0.70=0.6833
         Jaccard=0.491 ExactMatch=0.8% predSz=11.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=36.8% top3R=0.460 top5R=0.659 top8R=0.822 top10R=0.884
         Brier=0.0916 ECE=0.1151 LR=9.18e-06, Time=886.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 9/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [13:38<00:00,  1.18it/s, loss=0.4196, bin=0.2514, cnt=0.3365]
  Epoch 9: loss=0.3116(bin=0.1785,cnt=0.2661), val_loss=0.8355, F1@0.50=0.6394, F1@0.70=0.6890
         Jaccard=0.493 ExactMatch=0.9% predSz=10.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=36.1% top3R=0.468 top5R=0.663 top8R=0.821 top10R=0.883
         Brier=0.0864 ECE=0.1083 LR=8.83e-06, Time=974.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 10/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:32<00:00,  1.28it/s, loss=0.3047, bin=0.1704, cnt=0.2686]
  Epoch 10: loss=0.2991(bin=0.1712,cnt=0.2559), val_loss=0.8306, F1@0.50=0.6544, F1@0.70=0.6962
         Jaccard=0.511 ExactMatch=1.6% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=31.3% top3R=0.468 top5R=0.664 top8R=0.825 top10R=0.886
         Brier=0.0836 ECE=0.1040 LR=8.43e-06, Time=892.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 11/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:27<00:00,  1.29it/s, loss=0.3021, bin=0.2454, cnt=0.1135]
  Epoch 11: loss=0.2873(bin=0.1640,cnt=0.2466), val_loss=0.8319, F1@0.50=0.6400, F1@0.70=0.6896
         Jaccard=0.495 ExactMatch=1.4% predSz=11.2 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=37.4% top3R=0.469 top5R=0.663 top8R=0.824 top10R=0.886
         Brier=0.0928 ECE=0.1222 LR=7.99e-06, Time=886.6s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 12/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:28<00:00,  1.29it/s, loss=0.2409, bin=0.1007, cnt=0.2805]
  Epoch 12: loss=0.2782(bin=0.1592,cnt=0.2380), val_loss=0.8432, F1@0.50=0.6676, F1@0.70=0.6999
         Jaccard=0.527 ExactMatch=2.1% predSz=10.0 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.6% top3R=0.468 top5R=0.666 top8R=0.826 top10R=0.886
         Brier=0.0804 ECE=0.0952 LR=7.50e-06, Time=887.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 13/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:28<00:00,  1.29it/s, loss=0.3281, bin=0.2049, cnt=0.2463]
  Epoch 13: loss=0.2673(bin=0.1527,cnt=0.2293), val_loss=0.8446, F1@0.50=0.6501, F1@0.70=0.6949
         Jaccard=0.507 ExactMatch=1.9% predSz=10.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=34.0% top3R=0.468 top5R=0.666 top8R=0.827 top10R=0.887
         Brier=0.0880 ECE=0.1099 LR=6.98e-06, Time=887.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 14/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:26<00:00,  1.29it/s, loss=0.2432, bin=0.1387, cnt=0.2090]
  Epoch 14: loss=0.2550(bin=0.1463,cnt=0.2176), val_loss=0.8481, F1@0.50=0.6445, F1@0.70=0.6907
         Jaccard=0.500 ExactMatch=1.5% predSz=11.0 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=35.9% top3R=0.466 top5R=0.663 top8R=0.826 top10R=0.885
         Brier=0.0902 ECE=0.1114 LR=6.43e-06, Time=886.1s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 15/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:29<00:00,  1.29it/s, loss=0.2252, bin=0.1215, cnt=0.2074]
  Epoch 15: loss=0.2477(bin=0.1425,cnt=0.2105), val_loss=0.8524, F1@0.50=0.6637, F1@0.70=0.7020
         Jaccard=0.523 ExactMatch=2.8% predSz=10.3 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=30.1% top3R=0.471 top5R=0.669 top8R=0.828 top10R=0.888
         Brier=0.0829 ECE=0.1007 LR=5.87e-06, Time=896.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 16/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [13:03<00:00,  1.23it/s, loss=0.3308, bin=0.1149, cnt=0.4318]
  Epoch 16: loss=0.2395(bin=0.1376,cnt=0.2038), val_loss=0.8532, F1@0.50=0.6781, F1@0.70=0.7094
         Jaccard=0.539 ExactMatch=2.8% predSz=9.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=25.9% top3R=0.471 top5R=0.669 top8R=0.830 top10R=0.891
         Brier=0.0762 ECE=0.0882 LR=5.29e-06, Time=922.6s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 17/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:27<00:00,  1.29it/s, loss=0.2555, bin=0.1015, cnt=0.3080]
  Epoch 17: loss=0.2309(bin=0.1329,cnt=0.1959), val_loss=0.8697, F1@0.50=0.6697, F1@0.70=0.7054
         Jaccard=0.530 ExactMatch=2.7% predSz=10.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=28.6% top3R=0.470 top5R=0.669 top8R=0.832 top10R=0.890
         Brier=0.0803 ECE=0.0952 LR=4.71e-06, Time=886.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 18/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [13:23<00:00,  1.20it/s, loss=0.2210, bin=0.1230, cnt=0.1960]
  Epoch 18: loss=0.2243(bin=0.1287,cnt=0.1912), val_loss=0.8720, F1@0.50=0.6636, F1@0.70=0.7045
         Jaccard=0.523 ExactMatch=2.8% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=30.6% top3R=0.473 top5R=0.670 top8R=0.830 top10R=0.889
         Brier=0.0839 ECE=0.1023 LR=4.13e-06, Time=962.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 19/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:34<00:00,  1.28it/s, loss=0.2733, bin=0.1713, cnt=0.2040]
  Epoch 19: loss=0.2191(bin=0.1264,cnt=0.1854), val_loss=0.8568, F1@0.50=0.6604, F1@0.70=0.7031
         Jaccard=0.519 ExactMatch=2.4% predSz=10.5 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=31.9% top3R=0.473 top5R=0.671 top8R=0.832 top10R=0.891
         Brier=0.0855 ECE=0.1096 LR=3.57e-06, Time=893.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 20/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:27<00:00,  1.29it/s, loss=0.1389, bin=0.1004, cnt=0.0770]
  Epoch 20: loss=0.2109(bin=0.1215,cnt=0.1787), val_loss=0.8807, F1@0.50=0.6640, F1@0.70=0.7056
         Jaccard=0.523 ExactMatch=2.4% predSz=10.3 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=30.7% top3R=0.475 top5R=0.670 top8R=0.833 top10R=0.892
         Brier=0.0827 ECE=0.1018 LR=3.02e-06, Time=887.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 21/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:29<00:00,  1.29it/s, loss=0.0690, bin=0.0369, cnt=0.0642]
  Epoch 21: loss=0.2029(bin=0.1171,cnt=0.1716), val_loss=0.9085, F1@0.50=0.6737, F1@0.70=0.7075
         Jaccard=0.535 ExactMatch=3.0% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.7% top3R=0.475 top5R=0.671 top8R=0.832 top10R=0.892
         Brier=0.0788 ECE=0.0906 LR=2.50e-06, Time=889.6s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 22/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:28<00:00,  1.29it/s, loss=0.1469, bin=0.0786, cnt=0.1366]
  Epoch 22: loss=0.1999(bin=0.1151,cnt=0.1696), val_loss=0.9033, F1@0.50=0.6784, F1@0.70=0.7126
         Jaccard=0.541 ExactMatch=3.4% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=26.4% top3R=0.474 top5R=0.673 top8R=0.833 top10R=0.892
         Brier=0.0773 ECE=0.0927 LR=2.01e-06, Time=889.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 23/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:28<00:00,  1.29it/s, loss=0.2171, bin=0.1347, cnt=0.1647]
  Epoch 23: loss=0.1938(bin=0.1119,cnt=0.1638), val_loss=0.9237, F1@0.50=0.6821, F1@0.70=0.7135
         Jaccard=0.545 ExactMatch=3.7% predSz=9.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=25.3% top3R=0.472 top5R=0.674 top8R=0.834 top10R=0.892
         Brier=0.0764 ECE=0.0884 LR=1.57e-06, Time=888.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 24/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:29<00:00,  1.29it/s, loss=0.2402, bin=0.1374, cnt=0.2056]
  Epoch 24: loss=0.1906(bin=0.1106,cnt=0.1599), val_loss=0.9252, F1@0.50=0.6723, F1@0.70=0.7110
         Jaccard=0.533 ExactMatch=3.1% predSz=10.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=28.4% top3R=0.476 top5R=0.675 top8R=0.835 top10R=0.893
         Brier=0.0797 ECE=0.0952 LR=1.17e-06, Time=892.6s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 25/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:54<00:00,  1.25it/s, loss=0.2325, bin=0.1357, cnt=0.1936]
  Epoch 25: loss=0.1863(bin=0.1082,cnt=0.1564), val_loss=0.9367, F1@0.50=0.6792, F1@0.70=0.7118
         Jaccard=0.541 ExactMatch=3.4% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=26.1% top3R=0.476 top5R=0.673 top8R=0.835 top10R=0.892
         Brier=0.0768 ECE=0.0868 LR=8.23e-07, Time=915.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 26/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:30<00:00,  1.29it/s, loss=0.0475, bin=0.0414, cnt=0.0122]
  Epoch 26: loss=0.1874(bin=0.1082,cnt=0.1585), val_loss=0.9485, F1@0.50=0.6843, F1@0.70=0.7150
         Jaccard=0.548 ExactMatch=3.6% predSz=9.6 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.2% over=24.4% top3R=0.476 top5R=0.675 top8R=0.836 top10R=0.892
         Brier=0.0750 ECE=0.0844 LR=5.32e-07, Time=891.1s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 27/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [13:30<00:00,  1.19it/s, loss=0.1066, bin=0.0762, cnt=0.0607]
  Epoch 27: loss=0.1825(bin=0.1062,cnt=0.1525), val_loss=0.9441, F1@0.50=0.6785, F1@0.70=0.7129
         Jaccard=0.541 ExactMatch=3.3% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=26.7% top3R=0.475 top5R=0.674 top8R=0.835 top10R=0.893
         Brier=0.0777 ECE=0.0899 LR=3.02e-07, Time=969.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 28/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:42<00:00,  1.26it/s, loss=0.1297, bin=0.0751, cnt=0.1093]
  Epoch 28: loss=0.1800(bin=0.1042,cnt=0.1517), val_loss=0.9464, F1@0.50=0.6769, F1@0.70=0.7117
         Jaccard=0.539 ExactMatch=3.3% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.1% top3R=0.475 top5R=0.675 top8R=0.836 top10R=0.892
         Brier=0.0784 ECE=0.0907 LR=1.35e-07, Time=902.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 29/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [12:24<00:00,  1.30it/s, loss=0.0801, bin=0.0435, cnt=0.0733]
  Epoch 29: loss=0.1834(bin=0.1062,cnt=0.1545), val_loss=0.9481, F1@0.50=0.6774, F1@0.70=0.7125
         Jaccard=0.540 ExactMatch=3.4% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.0% top3R=0.476 top5R=0.675 top8R=0.836 top10R=0.893
         Brier=0.0781 ECE=0.0901 LR=3.38e-08, Time=885.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 30/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 965/965 [10:14<00:00,  1.57it/s, loss=0.0972, bin=0.0661, cnt=0.0621]
  Epoch 30: loss=0.1809(bin=0.1048,cnt=0.1522), val_loss=0.9486, F1@0.50=0.6778, F1@0.70=0.7127
         Jaccard=0.540 ExactMatch=3.5% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=26.9% top3R=0.476 top5R=0.675 top8R=0.836 top10R=0.893
         Brier=0.0779 ECE=0.0897 LR=0.00e+00, Time=707.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Set Predictor quality-gate training launcher:
  trainer: SetPredictorV3
  set_predictor_contract: {'runtime_role': 'coverage_prior_only', 'not_responsible_for': ['candidate_ranking', 'sequence_generation', 'semantic_validation']}
  training_contract: {'system_role': 'coverage_prior_only', 'system_objective': 'predict which active L3 operators may appear in a workflow', 'known_limitations': ['single_reference_training_remains_the_base_case', 'count_buckets_are_coarse', 'planner_quality_is_post_training', 'semantic_constraints_are_not_encoded_as_runtime_authority'], 'required_post_training_validation': ['planner_set_coverage_score', 'planner_selected_top1_usable_rate', 'qgis_mapping_or_execution_diagnostics']}
  metric_contract: {'primary': ['planner_selected_set_coverage', 'planner_selected_top1_usable_rate', 'qgis_mapping'], 'supporting': ['topk_recall@5', 'topk_recall@8', 'topk_recall@10'], 'diagnostic_support': ['set_f1', 'set_jaccard', 'exact_set_match', 'brier_score', 'ece', 'zero_pred_rate', 'small_pred_rate_lt2', 'count_acc', 'count_mae']}
  checkpoint_policy: {'latest_snapshot': 'best_model.pth', 'recommended_checkpoint': 'best_topk_recall5_model.pth', 'selection_snapshots': {'set_f1': {'path': 'best_set_f1_model.pth', 'epoch': 26, 'value': 0.7150136232376099}, 'topk_recall@5': {'path': 'best_topk_recall5_model.pth', 'epoch': 26, 'value': 0.6752742528915405}}}
  mr_registry: {'status': 'disabled', 'path': None, 'task_groups': 0, 'matched_train_samples': 0, 'variant_active_tokens_added': []}
  mrv_training_dataset: {'status': 'enabled', 'version_name': 'mr_all_220', 'manifest_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mrv_training_ablation_manifest.json', 'report_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/mrv_training_ablation_report.json', 'data_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/labeled_workflows_l3_v4_quality_gate.json', 'splits_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/dataset_splits_v4_quality_gate.json', 'task_vocab_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/task_type_vocabulary_v4_quality_gate.json', 'injected_variants': 220, 'available_verified_mr_variants': 220, 'train_injection_rate_vs_base_train': 0.00357753, 'equivalence_family_counts': {'filter_filter': 30, 'select_filter': 8, 'select_clip': 3, 'boundary_review_candidate': 175, 'high_precision_review_candidate': 3, 'other': 1}, 'risk_level_counts': {'low': 31, 'medium': 10, 'reviewed': 178, 'unknown': 1}}
  data_path: outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/labeled_workflows_l3_v4_quality_gate.json
  splits_path: outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/dataset_splits_v4_quality_gate.json
  task_vocab_path: outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/task_type_vocabulary_v4_quality_gate.json
  active_tokens_path: /home/qy/system_redesign/outputs_v2/set_predictor_active_tokens_quality_gate.json
  checkpoint_dir: /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6
  workflows_total: 77104
  train: 61715
  val: 7694
  test: 7695
  num_task_types: 47
  num_active_tokens: 47
  batch_size: 64
  num_epochs: 30
  device: cuda
  dry_run: False
  history_epochs: 30
  latest_val_f1: 0.7127166390419006