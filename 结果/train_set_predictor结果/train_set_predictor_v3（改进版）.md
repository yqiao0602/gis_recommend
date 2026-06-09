(transformer) qy@mdzhang:~/system_redesign/src$ python -m gis_recommend.training.train_set_predictor_v3
======================================================================
Transformer Configuration (V2.0 - With L3 Embeddings + V4/V4.1 Extension)
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
Set Predictor V2 Training (Binary + Count, Per-token Attention)
======================================================================

[1] Loading data...
  Loaded 114401 workflows
  Task types: 132

[2] Discovering active tokens...
  Active tokens: 77 / 350
  Saved active tokens to /home/qy/system_redesign/outputs/set_predictor_active_tokens.json

[3] Splitting data...
  Loaded existing splits from /home/qy/system_redesign/outputs/dataset_splits_v4.json
  Train: 91520, Val: 11440, Test: 11441

[4] Building datasets...

[5] Computing pos_weight...
  pos_weight (absent/present ratio): 8.85

[6] Building model...
/home/qy/miniconda3/envs/transformer/lib/python3.10/site-packages/torch/nn/modules/transformer.py:286: UserWarning: enable_nested_tensor is True, but self.use_nested_tensor is False because encoder_layer.norm_first was True
  warnings.warn(f"enable_nested_tensor is True, but self.use_nested_tensor is False because {why_not_sparsity_fast_path}")
  Total params: 111,314,948
  Trainable params: 16,599,044

[7] Training for 30 epochs...
  Device: cuda
  Batch size: 64
  LR: BERT=1e-05, Other=0.0005
  pos_weight: 8.85, count_weight: 0.5
Epoch 1/30: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [07:24<00:00,  3.22it/s, loss=1.0039, bin=0.6344, cnt=0.7389]
  Epoch 1: loss=1.1503(bin=0.7540,cnt=0.7926), val_loss=0.9927, F1=0.4903, P=0.3581, R=0.8703, AvgSize=18.8, CntAcc=0.6653, CntMAE=0.4385, LR=3.33e-06, Time=489.2s
  ** Best model saved (F1=0.4903) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 2/30: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:12<00:00,  4.58it/s, loss=0.9520, bin=0.6054, cnt=0.6933]
  Epoch 2: loss=0.9825(bin=0.6128,cnt=0.7393), val_loss=0.9366, F1=0.5136, P=0.3785, R=0.8930, AvgSize=18.5, CntAcc=0.6708, CntMAE=0.4300, LR=6.67e-06, Time=341.6s
  ** Best model saved (F1=0.5136) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 3/30: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.62it/s, loss=1.0314, bin=0.6106, cnt=0.8415]
  Epoch 3: loss=0.9415(bin=0.5774,cnt=0.7282), val_loss=0.9007, F1=0.5312, P=0.3969, R=0.8962, AvgSize=17.6, CntAcc=0.6759, CntMAE=0.4197, LR=1.00e-05, Time=339.1s
  ** Best model saved (F1=0.5312) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 4/30: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.61it/s, loss=0.9349, bin=0.5740, cnt=0.7219]
  Epoch 4: loss=0.9151(bin=0.5552,cnt=0.7198), val_loss=0.8827, F1=0.5513, P=0.4210, R=0.8939, AvgSize=16.7, CntAcc=0.6789, CntMAE=0.4159, LR=9.97e-06, Time=338.9s
  ** Best model saved (F1=0.5513) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 5/30: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:10<00:00,  4.61it/s, loss=0.8090, bin=0.4911, cnt=0.6359]
  Epoch 5: loss=0.8946(bin=0.5384,cnt=0.7124), val_loss=0.8637, F1=0.5474, P=0.4132, R=0.9110, AvgSize=17.5, CntAcc=0.6860, CntMAE=0.4017, LR=9.87e-06, Time=339.4s
Epoch 6/30: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:08<00:00,  4.63it/s, loss=0.9220, bin=0.5294, cnt=0.7851]
  Epoch 6: loss=0.8781(bin=0.5254,cnt=0.7054), val_loss=0.8533, F1=0.5510, P=0.4152, R=0.9090, AvgSize=17.2, CntAcc=0.6862, CntMAE=0.3996, LR=9.70e-06, Time=337.5s
Epoch 7/30: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.63it/s, loss=0.8084, bin=0.4785, cnt=0.6597]
  Epoch 7: loss=0.8654(bin=0.5155,cnt=0.6999), val_loss=0.8423, F1=0.5606, P=0.4260, R=0.9106, AvgSize=16.9, CntAcc=0.6892, CntMAE=0.3945, LR=9.47e-06, Time=338.2s
  ** Best model saved (F1=0.5606) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 8/30: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.62it/s, loss=0.8806, bin=0.5261, cnt=0.7091]
  Epoch 8: loss=0.8554(bin=0.5077,cnt=0.6955), val_loss=0.8334, F1=0.5645, P=0.4299, R=0.9110, AvgSize=16.7, CntAcc=0.6913, CntMAE=0.3943, LR=9.18e-06, Time=338.9s
  ** Best model saved (F1=0.5645) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 9/30: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.62it/s, loss=0.8636, bin=0.5265, cnt=0.6743]
  Epoch 9: loss=0.8453(bin=0.5000,cnt=0.6906), val_loss=0.8258, F1=0.5675, P=0.4326, R=0.9106, AvgSize=16.6, CntAcc=0.6925, CntMAE=0.3928, LR=8.83e-06, Time=338.3s
  ** Best model saved (F1=0.5675) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 10/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:07<00:00,  4.64it/s, loss=0.8500, bin=0.4854, cnt=0.7291]
  Epoch 10: loss=0.8371(bin=0.4938,cnt=0.6866), val_loss=0.8210, F1=0.5758, P=0.4423, R=0.9085, AvgSize=16.2, CntAcc=0.6938, CntMAE=0.3875, LR=8.43e-06, Time=336.9s
  ** Best model saved (F1=0.5758) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 11/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:11<00:00,  4.59it/s, loss=0.9068, bin=0.5339, cnt=0.7457]
  Epoch 11: loss=0.8290(bin=0.4877,cnt=0.6827), val_loss=0.8143, F1=0.5885, P=0.4594, R=0.9015, AvgSize=15.6, CntAcc=0.6958, CntMAE=0.3860, LR=7.99e-06, Time=340.7s
  ** Best model saved (F1=0.5885) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 12/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.62it/s, loss=0.8234, bin=0.4832, cnt=0.6804]
  Epoch 12: loss=0.8217(bin=0.4826,cnt=0.6782), val_loss=0.8110, F1=0.5899, P=0.4614, R=0.9035, AvgSize=15.8, CntAcc=0.6966, CntMAE=0.3837, LR=7.50e-06, Time=338.6s
  ** Best model saved (F1=0.5899) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 13/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:08<00:00,  4.63it/s, loss=0.8903, bin=0.5188, cnt=0.7429]
  Epoch 13: loss=0.8152(bin=0.4777,cnt=0.6750), val_loss=0.8046, F1=0.5786, P=0.4446, R=0.9166, AvgSize=16.4, CntAcc=0.6983, CntMAE=0.3806, LR=6.98e-06, Time=337.8s
Epoch 14/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:07<00:00,  4.65it/s, loss=0.8079, bin=0.4673, cnt=0.6811]
  Epoch 14: loss=0.8086(bin=0.4726,cnt=0.6720), val_loss=0.7977, F1=0.5914, P=0.4613, R=0.9100, AvgSize=15.8, CntAcc=0.6996, CntMAE=0.3768, LR=6.43e-06, Time=336.7s
  ** Best model saved (F1=0.5914) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 15/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:08<00:00,  4.64it/s, loss=0.8229, bin=0.4678, cnt=0.7103]
  Epoch 15: loss=0.8024(bin=0.4684,cnt=0.6681), val_loss=0.7951, F1=0.5895, P=0.4581, R=0.9127, AvgSize=15.9, CntAcc=0.7006, CntMAE=0.3764, LR=5.87e-06, Time=337.6s
Epoch 16/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.62it/s, loss=0.7837, bin=0.4527, cnt=0.6619]
  Epoch 16: loss=0.7964(bin=0.4641,cnt=0.6647), val_loss=0.7917, F1=0.5943, P=0.4637, R=0.9113, AvgSize=15.7, CntAcc=0.7023, CntMAE=0.3767, LR=5.29e-06, Time=338.3s
  ** Best model saved (F1=0.5943) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 17/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:07<00:00,  4.65it/s, loss=0.7648, bin=0.4502, cnt=0.6292]
  Epoch 17: loss=0.7908(bin=0.4602,cnt=0.6613), val_loss=0.7906, F1=0.5932, P=0.4622, R=0.9121, AvgSize=15.7, CntAcc=0.7020, CntMAE=0.3743, LR=4.71e-06, Time=336.0s
Epoch 18/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:07<00:00,  4.65it/s, loss=0.7648, bin=0.4373, cnt=0.6549]
  Epoch 18: loss=0.7856(bin=0.4565,cnt=0.6583), val_loss=0.7853, F1=0.5965, P=0.4658, R=0.9129, AvgSize=15.6, CntAcc=0.7050, CntMAE=0.3708, LR=4.13e-06, Time=336.7s
  ** Best model saved (F1=0.5965) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 19/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.63it/s, loss=0.7978, bin=0.4870, cnt=0.6216]
  Epoch 19: loss=0.7811(bin=0.4534,cnt=0.6554), val_loss=0.7830, F1=0.5984, P=0.4678, R=0.9134, AvgSize=15.6, CntAcc=0.7055, CntMAE=0.3699, LR=3.57e-06, Time=338.0s
  ** Best model saved (F1=0.5984) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 20/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.62it/s, loss=0.8100, bin=0.4879, cnt=0.6443]
  Epoch 20: loss=0.7765(bin=0.4501,cnt=0.6530), val_loss=0.7823, F1=0.5972, P=0.4664, R=0.9150, AvgSize=15.7, CntAcc=0.7059, CntMAE=0.3677, LR=3.02e-06, Time=338.5s
Epoch 21/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:07<00:00,  4.65it/s, loss=0.8457, bin=0.4774, cnt=0.7366]
  Epoch 21: loss=0.7724(bin=0.4473,cnt=0.6502), val_loss=0.7784, F1=0.5981, P=0.4672, R=0.9152, AvgSize=15.7, CntAcc=0.7080, CntMAE=0.3654, LR=2.50e-06, Time=336.6s
Epoch 22/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:08<00:00,  4.64it/s, loss=0.7504, bin=0.4390, cnt=0.6228]
  Epoch 22: loss=0.7694(bin=0.4450,cnt=0.6486), val_loss=0.7769, F1=0.5994, P=0.4687, R=0.9161, AvgSize=15.6, CntAcc=0.7092, CntMAE=0.3637, LR=2.01e-06, Time=337.4s
  ** Best model saved (F1=0.5994) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 23/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.62it/s, loss=0.7409, bin=0.4471, cnt=0.5877]
  Epoch 23: loss=0.7653(bin=0.4423,cnt=0.6461), val_loss=0.7764, F1=0.6039, P=0.4752, R=0.9124, AvgSize=15.4, CntAcc=0.7083, CntMAE=0.3650, LR=1.57e-06, Time=338.4s
  ** Best model saved (F1=0.6039) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 24/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.63it/s, loss=0.7787, bin=0.4968, cnt=0.5638]
  Epoch 24: loss=0.7625(bin=0.4403,cnt=0.6444), val_loss=0.7778, F1=0.6025, P=0.4729, R=0.9147, AvgSize=15.5, CntAcc=0.7092, CntMAE=0.3639, LR=1.17e-06, Time=338.0s
Epoch 25/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:07<00:00,  4.65it/s, loss=0.7186, bin=0.4246, cnt=0.5879]
  Epoch 25: loss=0.7606(bin=0.4391,cnt=0.6430), val_loss=0.7733, F1=0.5994, P=0.4680, R=0.9175, AvgSize=15.7, CntAcc=0.7092, CntMAE=0.3629, LR=8.23e-07, Time=336.7s
Epoch 26/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:08<00:00,  4.63it/s, loss=0.7427, bin=0.4158, cnt=0.6537]
  Epoch 26: loss=0.7585(bin=0.4376,cnt=0.6418), val_loss=0.7735, F1=0.6013, P=0.4708, R=0.9170, AvgSize=15.6, CntAcc=0.7099, CntMAE=0.3626, LR=5.32e-07, Time=337.9s
Epoch 27/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.62it/s, loss=0.8413, bin=0.4659, cnt=0.7506]
  Epoch 27: loss=0.7566(bin=0.4361,cnt=0.6409), val_loss=0.7731, F1=0.6026, P=0.4724, R=0.9167, AvgSize=15.5, CntAcc=0.7101, CntMAE=0.3620, LR=3.02e-07, Time=338.6s
Epoch 28/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:08<00:00,  4.64it/s, loss=0.7612, bin=0.4402, cnt=0.6420]
  Epoch 28: loss=0.7552(bin=0.4353,cnt=0.6397), val_loss=0.7732, F1=0.6041, P=0.4744, R=0.9155, AvgSize=15.4, CntAcc=0.7098, CntMAE=0.3623, LR=1.35e-07, Time=337.1s
  ** Best model saved (F1=0.6041) → /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/best_model.pth
Epoch 29/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:07<00:00,  4.64it/s, loss=0.7592, bin=0.4330, cnt=0.6522]
  Epoch 29: loss=0.7552(bin=0.4355,cnt=0.6395), val_loss=0.7730, F1=0.6036, P=0.4739, R=0.9159, AvgSize=15.5, CntAcc=0.7103, CntMAE=0.3616, LR=3.38e-08, Time=336.9s
Epoch 30/30: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1430/1430 [05:09<00:00,  4.63it/s, loss=0.7329, bin=0.4050, cnt=0.6558]
  Epoch 30: loss=0.7544(bin=0.4349,cnt=0.6391), val_loss=0.7732, F1=0.6040, P=0.4743, R=0.9157, AvgSize=15.5, CntAcc=0.7100, CntMAE=0.3621, LR=0.00e+00, Time=338.1s

[8] Test evaluation (best val F1=0.6041)...
Testing: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 179/179 [00:44<00:00,  4.03it/s]

======================================================================
  Test Results (multi-threshold):
    thr=0.3: F1=0.5377, P=0.3934, R=0.9557, AvgSize=19.7, CntAcc=0.7177
    thr=0.4: F1=0.5724, P=0.4336, R=0.9372, AvgSize=17.5, CntAcc=0.7149
    thr=0.5: F1=0.6043, P=0.4750, R=0.9142, AvgSize=15.5, CntAcc=0.7116 ← default
    thr=0.6: F1=0.6348, P=0.5219, R=0.8822, AvgSize=13.5, CntAcc=0.7072
    thr=0.7: F1=0.6624, P=0.5773, R=0.8361, AvgSize=11.4, CntAcc=0.7026
======================================================================
  History saved to /home/qy/system_redesign/outputs/set_predictor_checkpoints_v3/training_history.json