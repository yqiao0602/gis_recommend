(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_set_predictor_quality_gate.py --mrv-ablation-dir outputs_v2/v4_qg_mr_ablation --mrv-ablation-version mr_all_42
  Active tokens: 47 / 94
/home/qy/miniconda3/envs/transformer/lib/python3.10/site-packages/torch/nn/modules/transformer.py:286: UserWarning: enable_nested_tensor is True, but self.use_nested_tensor is False because encoder_layer.norm_first was True
  warnings.warn(f"enable_nested_tensor is True, but self.use_nested_tensor is False because {why_not_sparsity_fast_path}")
======================================================================
Set Predictor V3 Quality-Gate Training
======================================================================
  Workflows: 76926
  Train/Val/Test: 61537 / 7694 / 7695
  Task types: 47
  Active tokens: 47
  Checkpoint dir: /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6
  Balanced sampling task types: 47
  Checkpoint: latest epoch snapshot; metrics are recorded only
Epoch 1/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [11:46<00:00,  1.36it/s, loss=0.7971, bin=0.4944, cnt=0.6053]
  Epoch 1: loss=0.9904(bin=0.6329,cnt=0.7150), val_loss=0.8971, F1@0.50=0.6038, F1@0.70=0.6398
         Jaccard=0.453 ExactMatch=0.0% predSz=10.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=37.8% top3R=0.411 top5R=0.605 top8R=0.773 top10R=0.845
         Brier=0.0941 ECE=0.1163 LR=3.33e-06, Time=856.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 2/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:22<00:00,  1.30it/s, loss=0.5557, bin=0.3229, cnt=0.4655]
  Epoch 2: loss=0.6425(bin=0.3703,cnt=0.5445), val_loss=0.8500, F1@0.50=0.6092, F1@0.70=0.6543
         Jaccard=0.459 ExactMatch=0.3% predSz=11.6 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=42.2% top3R=0.438 top5R=0.632 top8R=0.798 top10R=0.867
         Brier=0.0998 ECE=0.1268 LR=6.67e-06, Time=878.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 3/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:25<00:00,  1.29it/s, loss=0.3479, bin=0.1843, cnt=0.3273]
  Epoch 3: loss=0.5028(bin=0.2891,cnt=0.4275), val_loss=0.8461, F1@0.50=0.6234, F1@0.70=0.6694
         Jaccard=0.475 ExactMatch=0.6% predSz=11.2 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=38.7% top3R=0.443 top5R=0.637 top8R=0.805 top10R=0.871
         Brier=0.0929 ECE=0.1152 LR=1.00e-05, Time=883.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 4/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:25<00:00,  1.29it/s, loss=0.3848, bin=0.1756, cnt=0.4183]
  Epoch 4: loss=0.4285(bin=0.2470,cnt=0.3630), val_loss=0.8246, F1@0.50=0.6331, F1@0.70=0.6801
         Jaccard=0.486 ExactMatch=0.8% predSz=11.0 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=37.1% top3R=0.454 top5R=0.651 top8R=0.816 top10R=0.879
         Brier=0.0940 ECE=0.1344 LR=9.97e-06, Time=884.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 5/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:24<00:00,  1.29it/s, loss=0.4959, bin=0.2913, cnt=0.4093]
  Epoch 5: loss=0.3888(bin=0.2234,cnt=0.3308), val_loss=0.8249, F1@0.50=0.6494, F1@0.70=0.6897
         Jaccard=0.505 ExactMatch=1.2% predSz=10.5 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=32.2% top3R=0.458 top5R=0.654 top8R=0.817 top10R=0.880
         Brier=0.0866 ECE=0.1117 LR=9.87e-06, Time=883.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 6/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:25<00:00,  1.29it/s, loss=0.1649, bin=0.0918, cnt=0.1463]
  Epoch 6: loss=0.3650(bin=0.2091,cnt=0.3118), val_loss=0.8318, F1@0.50=0.6413, F1@0.70=0.6862
         Jaccard=0.495 ExactMatch=1.1% predSz=10.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=35.2% top3R=0.459 top5R=0.656 top8R=0.819 top10R=0.882
         Brier=0.0886 ECE=0.1132 LR=9.70e-06, Time=884.1s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 7/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:50<00:00,  1.25it/s, loss=0.5465, bin=0.3369, cnt=0.4191]
  Epoch 7: loss=0.3404(bin=0.1953,cnt=0.2902), val_loss=0.8292, F1@0.50=0.6236, F1@0.70=0.6730
         Jaccard=0.475 ExactMatch=0.7% predSz=11.5 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=42.1% top3R=0.458 top5R=0.657 top8R=0.820 top10R=0.882
         Brier=0.0996 ECE=0.1379 LR=9.47e-06, Time=908.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 8/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:26<00:00,  1.29it/s, loss=0.3227, bin=0.1998, cnt=0.2458]
  Epoch 8: loss=0.3230(bin=0.1853,cnt=0.2753), val_loss=0.8274, F1@0.50=0.6478, F1@0.70=0.6940
         Jaccard=0.504 ExactMatch=1.4% predSz=10.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=34.5% top3R=0.463 top5R=0.660 top8R=0.821 top10R=0.882
         Brier=0.0860 ECE=0.1105 LR=9.18e-06, Time=885.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 9/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [13:19<00:00,  1.20it/s, loss=0.2662, bin=0.1625, cnt=0.2073]
  Epoch 9: loss=0.3099(bin=0.1772,cnt=0.2654), val_loss=0.8387, F1@0.50=0.6512, F1@0.70=0.6974
         Jaccard=0.508 ExactMatch=2.1% predSz=10.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=33.7% top3R=0.466 top5R=0.663 top8R=0.825 top10R=0.886
         Brier=0.0859 ECE=0.1085 LR=8.83e-06, Time=954.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 10/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:47<00:00,  1.25it/s, loss=0.1518, bin=0.0880, cnt=0.1276]
  Epoch 10: loss=0.2947(bin=0.1691,cnt=0.2513), val_loss=0.8412, F1@0.50=0.6456, F1@0.70=0.6908
         Jaccard=0.502 ExactMatch=1.9% predSz=11.0 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=35.3% top3R=0.468 top5R=0.662 top8R=0.824 top10R=0.886
         Brier=0.0912 ECE=0.1146 LR=8.43e-06, Time=905.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 11/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:25<00:00,  1.29it/s, loss=0.2540, bin=0.1594, cnt=0.1891]
  Epoch 11: loss=0.2836(bin=0.1626,cnt=0.2419), val_loss=0.8439, F1@0.50=0.6602, F1@0.70=0.7001
         Jaccard=0.518 ExactMatch=2.2% predSz=10.3 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=30.2% top3R=0.467 top5R=0.665 top8R=0.825 top10R=0.887
         Brier=0.0816 ECE=0.0971 LR=7.99e-06, Time=884.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 12/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:25<00:00,  1.29it/s, loss=0.3213, bin=0.1885, cnt=0.2654]
  Epoch 12: loss=0.2736(bin=0.1566,cnt=0.2340), val_loss=0.8463, F1@0.50=0.6336, F1@0.70=0.6874
         Jaccard=0.488 ExactMatch=1.6% predSz=11.5 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=39.4% top3R=0.464 top5R=0.661 top8R=0.825 top10R=0.886
         Brier=0.0958 ECE=0.1280 LR=7.50e-06, Time=885.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 13/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:25<00:00,  1.29it/s, loss=0.3481, bin=0.1867, cnt=0.3229]
  Epoch 13: loss=0.2639(bin=0.1506,cnt=0.2266), val_loss=0.8444, F1@0.50=0.6463, F1@0.70=0.6921
         Jaccard=0.502 ExactMatch=1.7% predSz=10.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=35.2% top3R=0.467 top5R=0.664 top8R=0.826 top10R=0.886
         Brier=0.0877 ECE=0.1052 LR=6.98e-06, Time=884.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 14/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:26<00:00,  1.29it/s, loss=0.1717, bin=0.1072, cnt=0.1289]
  Epoch 14: loss=0.2516(bin=0.1439,cnt=0.2153), val_loss=0.8556, F1@0.50=0.6636, F1@0.70=0.6968
         Jaccard=0.523 ExactMatch=2.4% predSz=10.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=29.9% top3R=0.468 top5R=0.666 top8R=0.826 top10R=0.888
         Brier=0.0828 ECE=0.0959 LR=6.43e-06, Time=884.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 15/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:25<00:00,  1.29it/s, loss=0.2561, bin=0.1414, cnt=0.2294]
  Epoch 15: loss=0.2412(bin=0.1387,cnt=0.2051), val_loss=0.8409, F1@0.50=0.6617, F1@0.70=0.7015
         Jaccard=0.521 ExactMatch=2.3% predSz=10.2 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=30.6% top3R=0.467 top5R=0.665 top8R=0.829 top10R=0.888
         Brier=0.0815 ECE=0.0981 LR=5.87e-06, Time=885.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 16/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [13:10<00:00,  1.22it/s, loss=0.2325, bin=0.1360, cnt=0.1929]
  Epoch 16: loss=0.2377(bin=0.1364,cnt=0.2026), val_loss=0.8591, F1@0.50=0.6605, F1@0.70=0.7002
         Jaccard=0.519 ExactMatch=2.1% predSz=10.3 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=31.4% top3R=0.470 top5R=0.665 top8R=0.829 top10R=0.889
         Brier=0.0825 ECE=0.1010 LR=5.29e-06, Time=929.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 17/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:25<00:00,  1.29it/s, loss=0.1508, bin=0.0878, cnt=0.1260]
  Epoch 17: loss=0.2301(bin=0.1326,cnt=0.1949), val_loss=0.8665, F1@0.50=0.6773, F1@0.70=0.7080
         Jaccard=0.540 ExactMatch=3.8% predSz=9.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=26.2% top3R=0.472 top5R=0.668 top8R=0.829 top10R=0.889
         Brier=0.0777 ECE=0.0911 LR=4.71e-06, Time=884.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 18/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:59<00:00,  1.23it/s, loss=0.2072, bin=0.1363, cnt=0.1418]
  Epoch 18: loss=0.2209(bin=0.1263,cnt=0.1893), val_loss=0.8716, F1@0.50=0.6535, F1@0.70=0.6965
         Jaccard=0.511 ExactMatch=2.2% predSz=10.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=33.7% top3R=0.471 top5R=0.668 top8R=0.828 top10R=0.889
         Brier=0.0877 ECE=0.1078 LR=4.13e-06, Time=936.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 19/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:56<00:00,  1.24it/s, loss=0.2124, bin=0.1452, cnt=0.1344]
  Epoch 19: loss=0.2154(bin=0.1240,cnt=0.1828), val_loss=0.8728, F1@0.50=0.6686, F1@0.70=0.7068
         Jaccard=0.529 ExactMatch=2.7% predSz=10.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=29.5% top3R=0.475 top5R=0.669 top8R=0.830 top10R=0.891
         Brier=0.0809 ECE=0.0971 LR=3.57e-06, Time=915.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 20/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:25<00:00,  1.29it/s, loss=0.1945, bin=0.1279, cnt=0.1333]
  Epoch 20: loss=0.2065(bin=0.1197,cnt=0.1736), val_loss=0.8869, F1@0.50=0.6680, F1@0.70=0.7069
         Jaccard=0.528 ExactMatch=2.5% predSz=10.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=29.2% top3R=0.473 top5R=0.670 top8R=0.832 top10R=0.891
         Brier=0.0797 ECE=0.0948 LR=3.02e-06, Time=884.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 21/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:27<00:00,  1.29it/s, loss=0.2626, bin=0.1272, cnt=0.2707]
  Epoch 21: loss=0.2033(bin=0.1174,cnt=0.1717), val_loss=0.8921, F1@0.50=0.6618, F1@0.70=0.7051
         Jaccard=0.521 ExactMatch=2.4% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=31.4% top3R=0.474 top5R=0.671 top8R=0.832 top10R=0.891
         Brier=0.0837 ECE=0.1038 LR=2.50e-06, Time=886.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 22/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:27<00:00,  1.29it/s, loss=0.0850, bin=0.0472, cnt=0.0757]
  Epoch 22: loss=0.1963(bin=0.1131,cnt=0.1663), val_loss=0.9183, F1@0.50=0.6755, F1@0.70=0.7082
         Jaccard=0.537 ExactMatch=3.1% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.1% top3R=0.475 top5R=0.672 top8R=0.832 top10R=0.892
         Brier=0.0775 ECE=0.0852 LR=2.01e-06, Time=886.1s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 23/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:26<00:00,  1.29it/s, loss=0.1308, bin=0.0690, cnt=0.1236]
  Epoch 23: loss=0.1909(bin=0.1102,cnt=0.1614), val_loss=0.9351, F1@0.50=0.6718, F1@0.70=0.7068
         Jaccard=0.533 ExactMatch=3.0% predSz=10.0 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=28.2% top3R=0.474 top5R=0.671 top8R=0.833 top10R=0.892
         Brier=0.0800 ECE=0.0922 LR=1.57e-06, Time=885.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 24/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:26<00:00,  1.29it/s, loss=0.2025, bin=0.1202, cnt=0.1646]
  Epoch 24: loss=0.1901(bin=0.1101,cnt=0.1600), val_loss=0.9151, F1@0.50=0.6650, F1@0.70=0.7056
         Jaccard=0.525 ExactMatch=2.7% predSz=10.3 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=30.5% top3R=0.476 top5R=0.672 top8R=0.833 top10R=0.892
         Brier=0.0832 ECE=0.1016 LR=1.17e-06, Time=885.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 25/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:56<00:00,  1.24it/s, loss=0.2369, bin=0.1078, cnt=0.2582]
  Epoch 25: loss=0.1845(bin=0.1072,cnt=0.1546), val_loss=0.9341, F1@0.50=0.6793, F1@0.70=0.7120
         Jaccard=0.542 ExactMatch=3.6% predSz=9.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=25.9% top3R=0.475 top5R=0.673 top8R=0.834 top10R=0.893
         Brier=0.0766 ECE=0.0878 LR=8.23e-07, Time=915.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 26/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:28<00:00,  1.28it/s, loss=0.1799, bin=0.0880, cnt=0.1839]
  Epoch 26: loss=0.1840(bin=0.1066,cnt=0.1549), val_loss=0.9390, F1@0.50=0.6745, F1@0.70=0.7103
         Jaccard=0.536 ExactMatch=3.2% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.7% top3R=0.476 top5R=0.673 top8R=0.834 top10R=0.893
         Brier=0.0780 ECE=0.0890 LR=5.32e-07, Time=887.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 27/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [13:00<00:00,  1.23it/s, loss=0.1153, bin=0.0757, cnt=0.0792]
  Epoch 27: loss=0.1807(bin=0.1054,cnt=0.1508), val_loss=0.9474, F1@0.50=0.6776, F1@0.70=0.7114
         Jaccard=0.540 ExactMatch=3.4% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=26.7% top3R=0.476 top5R=0.673 top8R=0.835 top10R=0.893
         Brier=0.0770 ECE=0.0868 LR=3.02e-07, Time=937.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 28/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [13:09<00:00,  1.22it/s, loss=0.1735, bin=0.1023, cnt=0.1423]
  Epoch 28: loss=0.1779(bin=0.1029,cnt=0.1500), val_loss=0.9468, F1@0.50=0.6769, F1@0.70=0.7118
         Jaccard=0.539 ExactMatch=3.3% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.2% over=27.1% top3R=0.476 top5R=0.673 top8R=0.835 top10R=0.893
         Brier=0.0775 ECE=0.0888 LR=1.35e-07, Time=929.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 29/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [12:29<00:00,  1.28it/s, loss=0.1586, bin=0.1160, cnt=0.0851]
  Epoch 29: loss=0.1783(bin=0.1034,cnt=0.1498), val_loss=0.9460, F1@0.50=0.6765, F1@0.70=0.7117
         Jaccard=0.539 ExactMatch=3.3% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.3% top3R=0.476 top5R=0.673 top8R=0.835 top10R=0.893
         Brier=0.0775 ECE=0.0889 LR=3.38e-08, Time=885.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 30/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 962/962 [11:19<00:00,  1.42it/s, loss=0.1291, bin=0.0668, cnt=0.1246]
  Epoch 30: loss=0.1788(bin=0.1038,cnt=0.1498), val_loss=0.9467, F1@0.50=0.6767, F1@0.70=0.7118
         Jaccard=0.539 ExactMatch=3.2% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.2% top3R=0.476 top5R=0.673 top8R=0.834 top10R=0.893
         Brier=0.0774 ECE=0.0885 LR=0.00e+00, Time=777.6s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Set Predictor quality-gate training launcher:
  trainer: SetPredictorV3
  set_predictor_contract: {'runtime_role': 'coverage_prior_only', 'not_responsible_for': ['candidate_ranking', 'sequence_generation', 'semantic_validation']}
  training_contract: {'system_role': 'coverage_prior_only', 'system_objective': 'predict which active L3 operators may appear in a workflow', 'known_limitations': ['single_reference_training_remains_the_base_case', 'count_buckets_are_coarse', 'planner_quality_is_post_training', 'semantic_constraints_are_not_encoded_as_runtime_authority'], 'required_post_training_validation': ['planner_set_coverage_score', 'planner_selected_top1_usable_rate', 'qgis_mapping_or_execution_diagnostics']}
  metric_contract: {'primary': ['planner_selected_set_coverage', 'planner_selected_top1_usable_rate', 'qgis_mapping'], 'supporting': ['topk_recall@5', 'topk_recall@8', 'topk_recall@10'], 'diagnostic_support': ['set_f1', 'set_jaccard', 'exact_set_match', 'brier_score', 'ece', 'zero_pred_rate', 'small_pred_rate_lt2', 'count_acc', 'count_mae']}
  checkpoint_policy: {'latest_snapshot': 'best_model.pth', 'recommended_checkpoint': 'best_topk_recall5_model.pth', 'selection_snapshots': {'set_f1': {'path': 'best_set_f1_model.pth', 'epoch': 25, 'value': 0.7119815349578857}, 'topk_recall@5': {'path': 'best_topk_recall5_model.pth', 'epoch': 25, 'value': 0.6732870936393738}}}
  mr_registry: {'status': 'disabled', 'path': None, 'task_groups': 0, 'matched_train_samples': 0, 'variant_active_tokens_added': []}
  mrv_training_dataset: {'status': 'enabled', 'version_name': 'mr_all_42', 'manifest_path': 'outputs_v2/v4_qg_mr_ablation/mrv_training_ablation_manifest.json', 'report_path': 'outputs_v2/v4_qg_mr_ablation/mr_all_42/mrv_training_ablation_report.json', 'data_path': 'outputs_v2/v4_qg_mr_ablation/mr_all_42/labeled_workflows_l3_v4_quality_gate.json', 'splits_path': 'outputs_v2/v4_qg_mr_ablation/mr_all_42/dataset_splits_v4_quality_gate.json', 'task_vocab_path': 'outputs_v2/v4_qg_mr_ablation/mr_all_42/task_type_vocabulary_v4_quality_gate.json', 'injected_variants': 42, 'available_verified_mr_variants': 42, 'train_injection_rate_vs_base_train': 0.00068298, 'equivalence_family_counts': {'filter_filter': 30, 'select_filter': 8, 'select_clip': 3, 'other': 1}, 'risk_level_counts': {'low': 31, 'medium': 10, 'unknown': 1}}
  data_path: outputs_v2/v4_qg_mr_ablation/mr_all_42/labeled_workflows_l3_v4_quality_gate.json
  splits_path: outputs_v2/v4_qg_mr_ablation/mr_all_42/dataset_splits_v4_quality_gate.json
  task_vocab_path: outputs_v2/v4_qg_mr_ablation/mr_all_42/task_type_vocabulary_v4_quality_gate.json
  active_tokens_path: /home/qy/system_redesign/outputs_v2/set_predictor_active_tokens_quality_gate.json
  checkpoint_dir: /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6
  workflows_total: 76926
  train: 61537
  val: 7694
  test: 7695
  num_task_types: 47
  num_active_tokens: 47
  batch_size: 64
  num_epochs: 30
  device: cuda
  dry_run: False
  history_epochs: 30
  latest_val_f1: 0.71175616979599