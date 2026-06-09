(base) qy@mdzhang:~/system_redesign$ conda activate transformer
(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_set_predictor_quality_gate.py
  Active tokens: 47 / 94
/home/qy/miniconda3/envs/transformer/lib/python3.10/site-packages/torch/nn/modules/transformer.py:286: UserWarning: enable_nested_tensor is True, but self.use_nested_tensor is False because encoder_layer.norm_first was True
  warnings.warn(f"enable_nested_tensor is True, but self.use_nested_tensor is False because {why_not_sparsity_fast_path}")
======================================================================
Set Predictor V3 Quality-Gate Training
======================================================================
  Workflows: 76884
  Train/Val/Test: 61495 / 7694 / 7695
  Task types: 47
  Active tokens: 47
  Checkpoint dir: /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6
  Balanced sampling task types: 47
  Checkpoint: latest epoch snapshot; metrics are recorded only
Epoch 1/30: 100%|█| 961/961 [04:41<00:00,  3.42it/s, loss=0.7917, bin=0.5049, cn
  Epoch 1: loss=0.9916(bin=0.6333,cnt=0.7167), val_loss=0.8956, F1@0.50=0.5732, F1@0.70=0.6269
         Jaccard=0.420 ExactMatch=0.0% predSz=12.3 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=51.5% top3R=0.412 top5R=0.608 top8R=0.777 top10R=0.847
         Brier=0.1105 ECE=0.1512 LR=3.33e-06, Time=346.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 2/30: 100%|█| 961/961 [11:21<00:00,  1.41it/s, loss=0.5717, bin=0.2989, cn
  Epoch 2: loss=0.6427(bin=0.3684,cnt=0.5486), val_loss=0.8489, F1@0.50=0.5962, F1@0.70=0.6538
         Jaccard=0.445 ExactMatch=0.2% predSz=12.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=48.2% top3R=0.437 top5R=0.639 top8R=0.803 top10R=0.869
         Brier=0.1074 ECE=0.1453 LR=6.67e-06, Time=812.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 3/30: 100%|█| 961/961 [12:15<00:00,  1.31it/s, loss=0.4446, bin=0.2607, cn
  Epoch 3: loss=0.5047(bin=0.2890,cnt=0.4312), val_loss=0.8279, F1@0.50=0.6194, F1@0.70=0.6676
         Jaccard=0.470 ExactMatch=0.3% predSz=11.5 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=41.1% top3R=0.444 top5R=0.646 top8R=0.809 top10R=0.875
         Brier=0.0976 ECE=0.1283 LR=1.00e-05, Time=874.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 4/30: 100%|█| 961/961 [12:22<00:00,  1.29it/s, loss=0.2960, bin=0.1808, cn
  Epoch 4: loss=0.4345(bin=0.2506,cnt=0.3680), val_loss=0.8326, F1@0.50=0.6300, F1@0.70=0.6705
         Jaccard=0.482 ExactMatch=0.9% predSz=11.3 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=38.7% top3R=0.452 top5R=0.649 top8R=0.817 top10R=0.880
         Brier=0.0968 ECE=0.1199 LR=9.97e-06, Time=880.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 5/30: 100%|█| 961/961 [12:23<00:00,  1.29it/s, loss=0.4334, bin=0.2479, cn
  Epoch 5: loss=0.3910(bin=0.2254,cnt=0.3312), val_loss=0.8353, F1@0.50=0.6225, F1@0.70=0.6747
         Jaccard=0.473 ExactMatch=0.6% predSz=11.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=40.9% top3R=0.454 top5R=0.652 top8R=0.817 top10R=0.881
         Brier=0.0953 ECE=0.1193 LR=9.87e-06, Time=881.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 6/30: 100%|█| 961/961 [12:22<00:00,  1.29it/s, loss=0.4780, bin=0.3084, cn
  Epoch 6: loss=0.3640(bin=0.2092,cnt=0.3097), val_loss=0.8235, F1@0.50=0.6396, F1@0.70=0.6867
         Jaccard=0.493 ExactMatch=1.0% predSz=10.8 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.1% over=35.0% top3R=0.455 top5R=0.655 top8R=0.819 top10R=0.882
         Brier=0.0882 ECE=0.1124 LR=9.70e-06, Time=880.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 7/30: 100%|█| 961/961 [12:24<00:00,  1.29it/s, loss=0.3007, bin=0.1770, cn
  Epoch 7: loss=0.3435(bin=0.1971,cnt=0.2928), val_loss=0.8273, F1@0.50=0.6514, F1@0.70=0.6915
         Jaccard=0.508 ExactMatch=1.4% predSz=10.5 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=32.6% top3R=0.461 top5R=0.658 top8R=0.820 top10R=0.883
         Brier=0.0851 ECE=0.1052 LR=9.47e-06, Time=883.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 8/30: 100%|█| 961/961 [12:50<00:00,  1.25it/s, loss=0.3606, bin=0.2027, cn
  Epoch 8: loss=0.3242(bin=0.1860,cnt=0.2764), val_loss=0.8276, F1@0.50=0.6418, F1@0.70=0.6883
         Jaccard=0.497 ExactMatch=1.5% predSz=11.0 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=36.4% top3R=0.461 top5R=0.658 top8R=0.820 top10R=0.883
         Brier=0.0919 ECE=0.1196 LR=9.18e-06, Time=908.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 9/30: 100%|█| 961/961 [12:24<00:00,  1.29it/s, loss=0.2325, bin=0.1163, cn
  Epoch 9: loss=0.3095(bin=0.1771,cnt=0.2649), val_loss=0.8735, F1@0.50=0.6565, F1@0.70=0.6872
         Jaccard=0.513 ExactMatch=1.7% predSz=10.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=29.7% top3R=0.461 top5R=0.657 top8R=0.821 top10R=0.883
         Brier=0.0843 ECE=0.0914 LR=8.83e-06, Time=883.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 10/30: 100%|█| 961/961 [13:11<00:00,  1.21it/s, loss=0.3172, bin=0.1588, c
  Epoch 10: loss=0.2958(bin=0.1694,cnt=0.2526), val_loss=0.8490, F1@0.50=0.6564, F1@0.70=0.6967
         Jaccard=0.514 ExactMatch=2.3% predSz=10.5 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=31.9% top3R=0.465 top5R=0.658 top8R=0.822 top10R=0.886
         Brier=0.0831 ECE=0.0989 LR=8.43e-06, Time=947.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 11/30: 100%|█| 961/961 [12:51<00:00,  1.25it/s, loss=0.2187, bin=0.1260, c
  Epoch 11: loss=0.2877(bin=0.1642,cnt=0.2470), val_loss=0.8224, F1@0.50=0.6578, F1@0.70=0.6991
         Jaccard=0.515 ExactMatch=2.3% predSz=10.5 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=31.5% top3R=0.466 top5R=0.665 top8R=0.825 top10R=0.887
         Brier=0.0846 ECE=0.1045 LR=7.99e-06, Time=912.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 12/30: 100%|█| 961/961 [12:24<00:00,  1.29it/s, loss=0.2873, bin=0.1416, c
  Epoch 12: loss=0.2734(bin=0.1568,cnt=0.2331), val_loss=0.8466, F1@0.50=0.6536, F1@0.70=0.6962
         Jaccard=0.510 ExactMatch=1.7% predSz=10.6 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=32.6% top3R=0.467 top5R=0.665 top8R=0.827 top10R=0.887
         Brier=0.0850 ECE=0.1012 LR=7.50e-06, Time=884.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 13/30: 100%|█| 961/961 [12:24<00:00,  1.29it/s, loss=0.2677, bin=0.1696, c
  Epoch 13: loss=0.2632(bin=0.1503,cnt=0.2258), val_loss=0.8487, F1@0.50=0.6500, F1@0.70=0.6956
         Jaccard=0.507 ExactMatch=1.7% predSz=10.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=34.1% top3R=0.468 top5R=0.661 top8R=0.825 top10R=0.886
         Brier=0.0867 ECE=0.1057 LR=6.98e-06, Time=883.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 14/30: 100%|█| 961/961 [12:24<00:00,  1.29it/s, loss=0.2604, bin=0.1493, c
  Epoch 14: loss=0.2560(bin=0.1468,cnt=0.2183), val_loss=0.8476, F1@0.50=0.6668, F1@0.70=0.7057
         Jaccard=0.527 ExactMatch=2.7% predSz=10.1 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.1% over=28.8% top3R=0.469 top5R=0.666 top8R=0.827 top10R=0.889
         Brier=0.0803 ECE=0.0976 LR=6.43e-06, Time=883.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 15/30: 100%|█| 961/961 [12:24<00:00,  1.29it/s, loss=0.1730, bin=0.1108, c
  Epoch 15: loss=0.2485(bin=0.1428,cnt=0.2114), val_loss=0.8625, F1@0.50=0.6752, F1@0.70=0.7075
         Jaccard=0.536 ExactMatch=2.8% predSz=9.6 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=26.2% top3R=0.469 top5R=0.666 top8R=0.828 top10R=0.890
         Brier=0.0751 ECE=0.0832 LR=5.87e-06, Time=885.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 16/30: 100%|█| 961/961 [12:24<00:00,  1.29it/s, loss=0.2210, bin=0.1356, c
  Epoch 16: loss=0.2365(bin=0.1358,cnt=0.2014), val_loss=0.8604, F1@0.50=0.6599, F1@0.70=0.7007
         Jaccard=0.517 ExactMatch=1.8% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=30.5% top3R=0.473 top5R=0.668 top8R=0.830 top10R=0.891
         Brier=0.0835 ECE=0.1015 LR=5.29e-06, Time=884.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 17/30: 100%|█| 961/961 [13:06<00:00,  1.22it/s, loss=0.2855, bin=0.1781, c
  Epoch 17: loss=0.2322(bin=0.1333,cnt=0.1978), val_loss=0.8721, F1@0.50=0.6695, F1@0.70=0.7066
         Jaccard=0.529 ExactMatch=2.4% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.2% over=27.8% top3R=0.473 top5R=0.667 top8R=0.829 top10R=0.890
         Brier=0.0781 ECE=0.0915 LR=4.71e-06, Time=931.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 18/30: 100%|█| 961/961 [12:22<00:00,  1.29it/s, loss=0.2622, bin=0.1303, c
  Epoch 18: loss=0.2245(bin=0.1295,cnt=0.1900), val_loss=0.8746, F1@0.50=0.6705, F1@0.70=0.7059
         Jaccard=0.531 ExactMatch=2.9% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=27.8% top3R=0.471 top5R=0.670 top8R=0.831 top10R=0.891
         Brier=0.0792 ECE=0.0947 LR=4.13e-06, Time=881.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 19/30: 100%|█| 961/961 [12:52<00:00,  1.24it/s, loss=0.2388, bin=0.1531, c
  Epoch 19: loss=0.2175(bin=0.1254,cnt=0.1843), val_loss=0.8681, F1@0.50=0.6616, F1@0.70=0.7027
         Jaccard=0.520 ExactMatch=2.4% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.1% over=31.3% top3R=0.469 top5R=0.668 top8R=0.831 top10R=0.891
         Brier=0.0845 ECE=0.1051 LR=3.57e-06, Time=928.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 20/30: 100%|█| 961/961 [13:02<00:00,  1.23it/s, loss=0.2261, bin=0.1227, c
  Epoch 20: loss=0.2092(bin=0.1205,cnt=0.1774), val_loss=0.8885, F1@0.50=0.6625, F1@0.70=0.7044
         Jaccard=0.521 ExactMatch=2.2% predSz=10.3 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.2% over=30.5% top3R=0.473 top5R=0.670 top8R=0.831 top10R=0.891
         Brier=0.0832 ECE=0.1011 LR=3.02e-06, Time=922.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 21/30: 100%|█| 961/961 [12:24<00:00,  1.29it/s, loss=0.2893, bin=0.1557, c
  Epoch 21: loss=0.2060(bin=0.1186,cnt=0.1749), val_loss=0.9104, F1@0.50=0.6761, F1@0.70=0.7108
         Jaccard=0.538 ExactMatch=3.4% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.2% over=26.6% top3R=0.472 top5R=0.669 top8R=0.833 top10R=0.892
         Brier=0.0777 ECE=0.0886 LR=2.50e-06, Time=885.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 22/30: 100%|█| 961/961 [12:25<00:00,  1.29it/s, loss=0.1994, bin=0.1237, c
  Epoch 22: loss=0.2007(bin=0.1158,cnt=0.1698), val_loss=0.9184, F1@0.50=0.6744, F1@0.70=0.7100
         Jaccard=0.536 ExactMatch=3.1% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.2% over=27.5% top3R=0.473 top5R=0.669 top8R=0.833 top10R=0.891
         Brier=0.0777 ECE=0.0888 LR=2.01e-06, Time=885.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 23/30: 100%|█| 961/961 [12:25<00:00,  1.29it/s, loss=0.1672, bin=0.0902, c
  Epoch 23: loss=0.1925(bin=0.1114,cnt=0.1621), val_loss=0.9224, F1@0.50=0.6740, F1@0.70=0.7105
         Jaccard=0.536 ExactMatch=3.2% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=27.4% top3R=0.473 top5R=0.670 top8R=0.833 top10R=0.892
         Brier=0.0786 ECE=0.0905 LR=1.57e-06, Time=886.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 24/30: 100%|█| 961/961 [12:24<00:00,  1.29it/s, loss=0.1096, bin=0.0745, c
  Epoch 24: loss=0.1908(bin=0.1105,cnt=0.1606), val_loss=0.9358, F1@0.50=0.6743, F1@0.70=0.7087
         Jaccard=0.536 ExactMatch=3.2% predSz=10.0 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=27.5% top3R=0.472 top5R=0.671 top8R=0.833 top10R=0.892
         Brier=0.0793 ECE=0.0905 LR=1.17e-06, Time=884.6s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 25/30: 100%|█| 961/961 [12:25<00:00,  1.29it/s, loss=0.1933, bin=0.1051, c
  Epoch 25: loss=0.1878(bin=0.1088,cnt=0.1581), val_loss=0.9424, F1@0.50=0.6794, F1@0.70=0.7130
         Jaccard=0.542 ExactMatch=3.7% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=26.2% top3R=0.476 top5R=0.673 top8R=0.835 top10R=0.895
         Brier=0.0767 ECE=0.0885 LR=8.23e-07, Time=885.1s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 26/30: 100%|█| 961/961 [12:56<00:00,  1.24it/s, loss=0.1685, bin=0.0932, c
  Epoch 26: loss=0.1838(bin=0.1064,cnt=0.1548), val_loss=0.9483, F1@0.50=0.6765, F1@0.70=0.7114
         Jaccard=0.539 ExactMatch=3.4% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=26.8% top3R=0.474 top5R=0.671 top8R=0.834 top10R=0.893
         Brier=0.0781 ECE=0.0898 LR=5.32e-07, Time=915.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 27/30: 100%|█| 961/961 [12:27<00:00,  1.29it/s, loss=0.2496, bin=0.1454, c
  Epoch 27: loss=0.1809(bin=0.1054,cnt=0.1511), val_loss=0.9489, F1@0.50=0.6775, F1@0.70=0.7127
         Jaccard=0.540 ExactMatch=3.5% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.3% over=26.5% top3R=0.475 top5R=0.672 top8R=0.834 top10R=0.894
         Brier=0.0770 ECE=0.0887 LR=3.02e-07, Time=888.1s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 28/30: 100%|█| 961/961 [12:54<00:00,  1.24it/s, loss=0.2374, bin=0.1342, c
  Epoch 28: loss=0.1802(bin=0.1047,cnt=0.1510), val_loss=0.9565, F1@0.50=0.6783, F1@0.70=0.7126
         Jaccard=0.541 ExactMatch=3.6% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.3% over=26.6% top3R=0.475 top5R=0.672 top8R=0.835 top10R=0.894
         Brier=0.0775 ECE=0.0887 LR=1.35e-07, Time=931.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 29/30: 100%|█| 961/961 [13:16<00:00,  1.21it/s, loss=0.1863, bin=0.1171, c
  Epoch 29: loss=0.1801(bin=0.1045,cnt=0.1512), val_loss=0.9557, F1@0.50=0.6774, F1@0.70=0.7123
         Jaccard=0.540 ExactMatch=3.5% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.3% over=26.9% top3R=0.475 top5R=0.672 top8R=0.835 top10R=0.894
         Brier=0.0778 ECE=0.0893 LR=3.38e-08, Time=937.1s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 30/30: 100%|█| 961/961 [12:28<00:00,  1.28it/s, loss=0.1399, bin=0.0749, c
  Epoch 30: loss=0.1797(bin=0.1043,cnt=0.1508), val_loss=0.9560, F1@0.50=0.6778, F1@0.70=0.7124
         Jaccard=0.540 ExactMatch=3.6% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.3% over=26.8% top3R=0.475 top5R=0.672 top8R=0.835 top10R=0.894
         Brier=0.0776 ECE=0.0890 LR=0.00e+00, Time=888.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Set Predictor quality-gate training launcher:
  trainer: SetPredictorV3
  set_predictor_contract: {'runtime_role': 'coverage_prior_only', 'not_responsible_for': ['candidate_ranking', 'sequence_generation', 'semantic_validation']}
  training_contract: {'system_role': 'coverage_prior_only', 'system_objective': 'predict which active L3 operators may appear in a workflow', 'known_limitations': ['single_reference_training_remains_the_base_case', 'count_buckets_are_coarse', 'planner_quality_is_post_training', 'semantic_constraints_are_not_encoded_as_runtime_authority'], 'required_post_training_validation': ['planner_set_coverage_score', 'planner_selected_top1_usable_rate', 'qgis_mapping_or_execution_diagnostics']}
  metric_contract: {'primary': ['planner_selected_set_coverage', 'planner_selected_top1_usable_rate', 'qgis_mapping'], 'supporting': ['topk_recall@5', 'topk_recall@8', 'topk_recall@10'], 'diagnostic_support': ['set_f1', 'set_jaccard', 'exact_set_match', 'brier_score', 'ece', 'zero_pred_rate', 'small_pred_rate_lt2', 'count_acc', 'count_mae']}
  checkpoint_policy: {'latest_snapshot': 'best_model.pth', 'recommended_checkpoint': 'best_topk_recall5_model.pth', 'selection_snapshots': {'set_f1': {'path': 'best_set_f1_model.pth', 'epoch': 25, 'value': 0.7129688262939453}, 'topk_recall@5': {'path': 'best_topk_recall5_model.pth', 'epoch': 25, 'value': 0.6728180646896362}}}
  mr_registry: {'status': 'disabled', 'path': None, 'task_groups': 0, 'matched_train_samples': 0, 'variant_active_tokens_added': []}
  mrv_training_dataset: {'status': 'disabled', 'version_name': None, 'injected_variants': 0}
  data_path: /home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json
  splits_path: /home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json
  task_vocab_path: /home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json
  active_tokens_path: /home/qy/system_redesign/outputs_v2/set_predictor_active_tokens_quality_gate.json
  checkpoint_dir: /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6
  workflows_total: 76884
  train: 61495
  val: 7694
  test: 7695
  num_task_types: 47
  num_active_tokens: 47
  batch_size: 64
  num_epochs: 30
  device: cuda
  dry_run: False
  history_epochs: 30
  latest_val_f1: 0.7124443054199219