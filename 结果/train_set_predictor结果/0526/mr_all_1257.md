(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_set_predictor_quality_gate.py --mrv-ablation-dir outputs_v2/v4_qg_mr_ablation_from_multisolution_unified --mrv-ablation-version mr_all_1257
  Active tokens: 47 / 94
/home/qy/miniconda3/envs/transformer/lib/python3.10/site-packages/torch/nn/modules/transformer.py:286: UserWarning: enable_nested_tensor is True, but self.use_nested_tensor is False because encoder_layer.norm_first was True
  warnings.warn(f"enable_nested_tensor is True, but self.use_nested_tensor is False because {why_not_sparsity_fast_path}")
======================================================================
Set Predictor V3 Quality-Gate Training
======================================================================
  Workflows: 78141
  Train/Val/Test: 62752 / 7694 / 7695
  Task types: 47
  Active tokens: 47
  Checkpoint dir: /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6
  Balanced sampling task types: 47
  Checkpoint: latest epoch snapshot; metrics are recorded only
Epoch 1/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:07<00:00,  2.67it/s, loss=0.7474, bin=0.4869, cnt=0.5210]
  Epoch 1: loss=0.9795(bin=0.6280,cnt=0.7032), val_loss=0.9029, F1@0.50=0.5702, F1@0.70=0.6147
         Jaccard=0.417 ExactMatch=0.1% predSz=12.6 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=51.7% top3R=0.412 top5R=0.599 top8R=0.768 top10R=0.842
         Brier=0.1176 ECE=0.1520 LR=3.33e-06, Time=451.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 2/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:37<00:00,  2.91it/s, loss=0.5575, bin=0.3069, cnt=0.5011]
  Epoch 2: loss=0.6366(bin=0.3680,cnt=0.5373), val_loss=0.8380, F1@0.50=0.6040, F1@0.70=0.6586
         Jaccard=0.453 ExactMatch=0.2% predSz=12.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=46.0% top3R=0.439 top5R=0.639 top8R=0.801 top10R=0.866
         Brier=0.1040 ECE=0.1427 LR=6.67e-06, Time=397.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 3/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:35<00:00,  2.92it/s, loss=0.4517, bin=0.2325, cnt=0.4384]
  Epoch 3: loss=0.5148(bin=0.2947,cnt=0.4402), val_loss=0.8427, F1@0.50=0.6206, F1@0.70=0.6723
         Jaccard=0.472 ExactMatch=0.5% predSz=11.6 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=40.8% top3R=0.450 top5R=0.647 top8R=0.809 top10R=0.873
         Brier=0.0969 ECE=0.1281 LR=1.00e-05, Time=395.6s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 4/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:31<00:00,  2.96it/s, loss=0.3717, bin=0.2534, cnt=0.2366]
  Epoch 4: loss=0.4449(bin=0.2559,cnt=0.3778), val_loss=0.8327, F1@0.50=0.6429, F1@0.70=0.6822
         Jaccard=0.496 ExactMatch=0.7% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=32.5% top3R=0.453 top5R=0.651 top8R=0.812 top10R=0.878
         Brier=0.0839 ECE=0.0993 LR=9.97e-06, Time=391.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 5/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:29<00:00,  2.98it/s, loss=0.3932, bin=0.1805, cnt=0.4253]
  Epoch 5: loss=0.4068(bin=0.2342,cnt=0.3454), val_loss=0.8258, F1@0.50=0.6360, F1@0.70=0.6783
         Jaccard=0.489 ExactMatch=0.7% predSz=10.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=36.6% top3R=0.454 top5R=0.652 top8R=0.815 top10R=0.878
         Brier=0.0894 ECE=0.1089 LR=9.87e-06, Time=389.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 6/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:28<00:00,  2.99it/s, loss=0.2614, bin=0.1463, cnt=0.2302]
  Epoch 6: loss=0.3755(bin=0.2152,cnt=0.3206), val_loss=0.8253, F1@0.50=0.6301, F1@0.70=0.6834
         Jaccard=0.482 ExactMatch=0.7% predSz=11.2 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=39.2% top3R=0.459 top5R=0.657 top8R=0.820 top10R=0.882
         Brier=0.0900 ECE=0.1135 LR=9.70e-06, Time=395.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 7/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:30<00:00,  2.97it/s, loss=0.3344, bin=0.1370, cnt=0.3948]
  Epoch 7: loss=0.3560(bin=0.2037,cnt=0.3046), val_loss=0.8257, F1@0.50=0.6519, F1@0.70=0.6943
         Jaccard=0.508 ExactMatch=1.8% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=31.7% top3R=0.460 top5R=0.658 top8R=0.820 top10R=0.882
         Brier=0.0847 ECE=0.1062 LR=9.47e-06, Time=391.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 8/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:01<00:00,  2.71it/s, loss=0.4706, bin=0.2414, cnt=0.4585]
  Epoch 8: loss=0.3409(bin=0.1947,cnt=0.2923), val_loss=0.8357, F1@0.50=0.6537, F1@0.70=0.6885
         Jaccard=0.510 ExactMatch=2.1% predSz=10.5 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=31.7% top3R=0.459 top5R=0.659 top8R=0.819 top10R=0.882
         Brier=0.0873 ECE=0.1031 LR=9.18e-06, Time=439.5s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 9/30: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:32<00:00,  2.95it/s, loss=0.2277, bin=0.1245, cnt=0.2063]
  Epoch 9: loss=0.3262(bin=0.1868,cnt=0.2790), val_loss=0.8335, F1@0.50=0.6594, F1@0.70=0.6977
         Jaccard=0.517 ExactMatch=1.7% predSz=10.2 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.1% over=29.8% top3R=0.468 top5R=0.663 top8R=0.824 top10R=0.885
         Brier=0.0820 ECE=0.1036 LR=8.83e-06, Time=399.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 10/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:20<00:00,  3.06it/s, loss=0.3018, bin=0.1683, cnt=0.2668]
  Epoch 10: loss=0.3170(bin=0.1809,cnt=0.2723), val_loss=0.8337, F1@0.50=0.6697, F1@0.70=0.7013
         Jaccard=0.529 ExactMatch=2.4% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=27.2% top3R=0.466 top5R=0.664 top8R=0.827 top10R=0.886
         Brier=0.0775 ECE=0.0877 LR=8.43e-06, Time=381.1s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 11/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:22<00:00,  3.04it/s, loss=0.2762, bin=0.1929, cnt=0.1666]
  Epoch 11: loss=0.3004(bin=0.1711,cnt=0.2585), val_loss=0.8445, F1@0.50=0.6726, F1@0.70=0.7036
         Jaccard=0.533 ExactMatch=2.8% predSz=9.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=26.1% top3R=0.469 top5R=0.666 top8R=0.826 top10R=0.887
         Brier=0.0774 ECE=0.0904 LR=7.99e-06, Time=383.1s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 12/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:21<00:00,  3.05it/s, loss=0.2590, bin=0.1734, cnt=0.1712]
  Epoch 12: loss=0.2921(bin=0.1668,cnt=0.2505), val_loss=0.8284, F1@0.50=0.6541, F1@0.70=0.6935
         Jaccard=0.512 ExactMatch=2.3% predSz=10.6 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=33.0% top3R=0.467 top5R=0.663 top8R=0.825 top10R=0.886
         Brier=0.0881 ECE=0.1094 LR=7.50e-06, Time=381.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 13/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:21<00:00,  3.05it/s, loss=0.2697, bin=0.1489, cnt=0.2416]
  Epoch 13: loss=0.2807(bin=0.1603,cnt=0.2408), val_loss=0.8465, F1@0.50=0.6755, F1@0.70=0.7054
         Jaccard=0.537 ExactMatch=3.0% predSz=9.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=25.9% top3R=0.468 top5R=0.665 top8R=0.829 top10R=0.888
         Brier=0.0759 ECE=0.0829 LR=6.98e-06, Time=381.8s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 14/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:21<00:00,  3.05it/s, loss=0.2700, bin=0.1484, cnt=0.2432]
  Epoch 14: loss=0.2727(bin=0.1555,cnt=0.2345), val_loss=0.8328, F1@0.50=0.6705, F1@0.70=0.7050
         Jaccard=0.531 ExactMatch=2.9% predSz=10.0 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=28.1% top3R=0.472 top5R=0.668 top8R=0.830 top10R=0.890
         Brier=0.0793 ECE=0.0952 LR=6.43e-06, Time=381.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 15/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:39<00:00,  2.89it/s, loss=0.2509, bin=0.1857, cnt=0.1303]
  Epoch 15: loss=0.2652(bin=0.1508,cnt=0.2286), val_loss=0.8560, F1@0.50=0.6511, F1@0.70=0.6939
         Jaccard=0.507 ExactMatch=1.9% predSz=10.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.0% over=34.3% top3R=0.471 top5R=0.666 top8R=0.826 top10R=0.888
         Brier=0.0892 ECE=0.1093 LR=5.87e-06, Time=398.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 16/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [05:34<00:00,  2.94it/s, loss=0.2321, bin=0.1492, cnt=0.1659]
  Epoch 16: loss=0.2566(bin=0.1464,cnt=0.2205), val_loss=0.8548, F1@0.50=0.6620, F1@0.70=0.7012
         Jaccard=0.521 ExactMatch=2.6% predSz=10.4 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=31.6% top3R=0.471 top5R=0.668 top8R=0.831 top10R=0.891
         Brier=0.0854 ECE=0.1067 LR=5.29e-06, Time=397.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 17/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:09<00:00,  2.66it/s, loss=0.1500, bin=0.0755, cnt=0.1492]
  Epoch 17: loss=0.2474(bin=0.1417,cnt=0.2113), val_loss=0.8659, F1@0.50=0.6602, F1@0.70=0.6987
         Jaccard=0.519 ExactMatch=2.9% predSz=10.6 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=31.8% top3R=0.472 top5R=0.667 top8R=0.831 top10R=0.891
         Brier=0.0861 ECE=0.1038 LR=4.71e-06, Time=442.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 18/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:25<00:00,  2.55it/s, loss=0.2545, bin=0.1645, cnt=0.1800]
  Epoch 18: loss=0.2414(bin=0.1374,cnt=0.2079), val_loss=0.8873, F1@0.50=0.6786, F1@0.70=0.7081
         Jaccard=0.541 ExactMatch=3.5% predSz=9.6 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=25.3% top3R=0.472 top5R=0.668 top8R=0.831 top10R=0.890
         Brier=0.0759 ECE=0.0842 LR=4.13e-06, Time=448.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 19/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:04<00:00,  2.69it/s, loss=0.1328, bin=0.0800, cnt=0.1056]
  Epoch 19: loss=0.2374(bin=0.1358,cnt=0.2032), val_loss=0.8911, F1@0.50=0.6753, F1@0.70=0.7085
         Jaccard=0.537 ExactMatch=3.0% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=26.7% top3R=0.471 top5R=0.667 top8R=0.831 top10R=0.890
         Brier=0.0775 ECE=0.0910 LR=3.57e-06, Time=431.9s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 20/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:00<00:00,  2.72it/s, loss=0.2284, bin=0.1323, cnt=0.1921]
  Epoch 20: loss=0.2294(bin=0.1315,cnt=0.1957), val_loss=0.8880, F1@0.50=0.6703, F1@0.70=0.7084
         Jaccard=0.530 ExactMatch=2.9% predSz=10.1 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=28.6% top3R=0.474 top5R=0.672 top8R=0.833 top10R=0.892
         Brier=0.0795 ECE=0.0943 LR=3.02e-06, Time=428.7s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 21/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:02<00:00,  2.71it/s, loss=0.3386, bin=0.1914, cnt=0.2944]
  Epoch 21: loss=0.2237(bin=0.1282,cnt=0.1911), val_loss=0.8953, F1@0.50=0.6745, F1@0.70=0.7081
         Jaccard=0.536 ExactMatch=3.0% predSz=10.0 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.1% over=27.4% top3R=0.475 top5R=0.671 top8R=0.833 top10R=0.892
         Brier=0.0790 ECE=0.0917 LR=2.50e-06, Time=430.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 22/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:01<00:00,  2.72it/s, loss=0.2067, bin=0.0900, cnt=0.2335]
  Epoch 22: loss=0.2170(bin=0.1244,cnt=0.1850), val_loss=0.9002, F1@0.50=0.6566, F1@0.70=0.7013
         Jaccard=0.514 ExactMatch=2.1% predSz=10.6 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=33.1% top3R=0.476 top5R=0.671 top8R=0.833 top10R=0.892
         Brier=0.0857 ECE=0.1068 LR=2.01e-06, Time=429.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 23/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:00<00:00,  2.72it/s, loss=0.2998, bin=0.1425, cnt=0.3146]
  Epoch 23: loss=0.2151(bin=0.1234,cnt=0.1834), val_loss=0.9146, F1@0.50=0.6812, F1@0.70=0.7133
         Jaccard=0.544 ExactMatch=3.4% predSz=9.6 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=25.5% top3R=0.476 top5R=0.672 top8R=0.834 top10R=0.893
         Brier=0.0759 ECE=0.0893 LR=1.57e-06, Time=429.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 24/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:02<00:00,  2.71it/s, loss=0.2733, bin=0.1374, cnt=0.2718]
  Epoch 24: loss=0.2088(bin=0.1198,cnt=0.1781), val_loss=0.9264, F1@0.50=0.6774, F1@0.70=0.7113
         Jaccard=0.540 ExactMatch=3.4% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.1%
         under=0.2% over=27.0% top3R=0.475 top5R=0.673 top8R=0.834 top10R=0.893
         Brier=0.0783 ECE=0.0908 LR=1.17e-06, Time=431.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 25/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:00<00:00,  2.72it/s, loss=0.1244, bin=0.0702, cnt=0.1085]
  Epoch 25: loss=0.2033(bin=0.1173,cnt=0.1720), val_loss=0.9328, F1@0.50=0.6808, F1@0.70=0.7130
         Jaccard=0.543 ExactMatch=3.3% predSz=9.7 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=25.9% top3R=0.477 top5R=0.674 top8R=0.835 top10R=0.894
         Brier=0.0757 ECE=0.0852 LR=8.23e-07, Time=428.2s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 26/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:00<00:00,  2.72it/s, loss=0.2223, bin=0.0965, cnt=0.2516]
  Epoch 26: loss=0.2038(bin=0.1175,cnt=0.1726), val_loss=0.9377, F1@0.50=0.6744, F1@0.70=0.7103
         Jaccard=0.536 ExactMatch=3.4% predSz=10.0 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=28.2% top3R=0.476 top5R=0.673 top8R=0.834 top10R=0.894
         Brier=0.0791 ECE=0.0916 LR=5.32e-07, Time=436.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 27/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:42<00:00,  2.44it/s, loss=0.1798, bin=0.0941, cnt=0.1714]
  Epoch 27: loss=0.1987(bin=0.1151,cnt=0.1671), val_loss=0.9429, F1@0.50=0.6785, F1@0.70=0.7123
         Jaccard=0.541 ExactMatch=3.4% predSz=9.8 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=26.7% top3R=0.476 top5R=0.674 top8R=0.835 top10R=0.894
         Brier=0.0771 ECE=0.0886 LR=3.02e-07, Time=465.4s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 28/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:00<00:00,  2.72it/s, loss=0.1717, bin=0.0660, cnt=0.2115]
  Epoch 28: loss=0.1984(bin=0.1143,cnt=0.1682), val_loss=0.9476, F1@0.50=0.6759, F1@0.70=0.7109
         Jaccard=0.538 ExactMatch=3.3% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.4% top3R=0.477 top5R=0.674 top8R=0.835 top10R=0.894
         Brier=0.0786 ECE=0.0906 LR=1.35e-07, Time=430.3s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 29/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:06<00:00,  2.68it/s, loss=0.1091, bin=0.0684, cnt=0.0813]
  Epoch 29: loss=0.1997(bin=0.1152,cnt=0.1689), val_loss=0.9491, F1@0.50=0.6769, F1@0.70=0.7118
         Jaccard=0.539 ExactMatch=3.3% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.0% top3R=0.476 top5R=0.674 top8R=0.836 top10R=0.894
         Brier=0.0779 ECE=0.0896 LR=3.38e-08, Time=434.0s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Epoch 30/30: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 981/981 [06:14<00:00,  2.62it/s, loss=0.2061, bin=0.0928, cnt=0.2266]
  Epoch 30: loss=0.1979(bin=0.1141,cnt=0.1675), val_loss=0.9478, F1@0.50=0.6767, F1@0.70=0.7118
         Jaccard=0.538 ExactMatch=3.3% predSz=9.9 trueSz=6.0 zero=0.0% lt2=0.0%
         under=0.1% over=27.2% top3R=0.476 top5R=0.674 top8R=0.835 top10R=0.894
         Brier=0.0780 ECE=0.0900 LR=0.00e+00, Time=437.6s
  ** Latest snapshot saved -> /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6/best_model.pth
Set Predictor quality-gate training launcher:
  trainer: SetPredictorV3
  set_predictor_contract: {'runtime_role': 'coverage_prior_only', 'not_responsible_for': ['candidate_ranking', 'sequence_generation', 'semantic_validation']}
  training_contract: {'system_role': 'coverage_prior_only', 'system_objective': 'predict which active L3 operators may appear in a workflow', 'known_limitations': ['single_reference_training_remains_the_base_case', 'count_buckets_are_coarse', 'planner_quality_is_post_training', 'semantic_constraints_are_not_encoded_as_runtime_authority'], 'required_post_training_validation': ['planner_set_coverage_score', 'planner_selected_top1_usable_rate', 'qgis_mapping_or_execution_diagnostics']}
  metric_contract: {'primary': ['planner_selected_set_coverage', 'planner_selected_top1_usable_rate', 'qgis_mapping'], 'supporting': ['topk_recall@5', 'topk_recall@8', 'topk_recall@10'], 'diagnostic_support': ['set_f1', 'set_jaccard', 'exact_set_match', 'brier_score', 'ece', 'zero_pred_rate', 'small_pred_rate_lt2', 'count_acc', 'count_mae']}
  checkpoint_policy: {'latest_snapshot': 'best_model.pth', 'recommended_checkpoint': 'best_topk_recall5_model.pth', 'selection_snapshots': {'set_f1': {'path': 'best_set_f1_model.pth', 'epoch': 23, 'value': 0.7132522463798523}, 'topk_recall@5': {'path': 'best_topk_recall5_model.pth', 'epoch': 30, 'value': 0.6740149855613708}}}
  mr_registry: {'status': 'disabled', 'path': None, 'task_groups': 0, 'matched_train_samples': 0, 'variant_active_tokens_added': []}
  mrv_training_dataset: {'status': 'enabled', 'version_name': 'mr_all_1257', 'manifest_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mrv_training_ablation_manifest.json', 'report_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/mrv_training_ablation_report.json', 'data_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/labeled_workflows_l3_v4_quality_gate.json', 'splits_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/dataset_splits_v4_quality_gate.json', 'task_vocab_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/task_type_vocabulary_v4_quality_gate.json', 'injected_variants': 1257, 'available_verified_mr_variants': 1257, 'train_injection_rate_vs_base_train': 0.02044069, 'equivalence_family_counts': {'filter_filter': 661, 'select_filter': 8, 'select_clip': 3, 'other': 1, 'structural_equivalence_conservative': 178, 'structural_equivalence_relaxed': 406}, 'risk_level_counts': {'low': 31, 'medium': 10, 'sampled_low': 631, 'unknown': 1, 'reviewed': 584}}
  data_path: outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/labeled_workflows_l3_v4_quality_gate.json
  splits_path: outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/dataset_splits_v4_quality_gate.json
  task_vocab_path: outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/task_type_vocabulary_v4_quality_gate.json
  active_tokens_path: /home/qy/system_redesign/outputs_v2/set_predictor_active_tokens_quality_gate.json
  checkpoint_dir: /home/qy/system_redesign/outputs_v2/set_predictor_checkpoints_v3_quality_gate_v4_6
  workflows_total: 78141
  train: 62752
  val: 7694
  test: 7695
  num_task_types: 47
  num_active_tokens: 47
  batch_size: 64
  num_epochs: 30
  device: cuda
  dry_run: False
  history_epochs: 30
  latest_val_f1: 0.7117571234703064