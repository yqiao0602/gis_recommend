(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_v4_6_quality_gate.py --data outputs_v2/v4_qg_mr_ablation/mr_all_42/labeled_workflows_l3_v4_quality_gate.json --splits outputs_v2/v4_qg_mr_ablation/mr_all_42/dataset_splits_v4_quality_gate.json --task-vocab outputs_v2/v4_qg_mr_ablation/mr_all_42/task_type_vocabulary_v4_quality_gate.json --checkpoint-dir outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42 --num-epochs 50
  [V4] Loaded L3 embeddings: 94 tokens from /home/qy/system_redesign/outputs_v2/l3_embeddings_v2.pt
  Params: 22.7M trainable, 117.4M total

  Training from scratch (TF phase: 10 epochs, total: 50 epochs)
  [V4.2] Using frequency-weighted CE loss (alpha=0.5)
  [V4.2] 转移矩阵: 48 states loaded
  [V4.5] task_cls_loss_weight overridden to 0.3

  Starting V4.6 Quality-Gate training...

================================================================================
V4.6 Training: Gradient Fix + Latest Snapshot Checkpointing
================================================================================
  Device: cuda, AMP: True
  Batch: 16 x 2 accum = 32 effective
  LR: BERT=2.0e-06, Other=5.0e-05
  AR max steps: 20
  Gen eval batches: 8
  Checkpoint: latest epoch snapshot; AR metrics are recorded only
================================================================================


Epoch 1/50
----------------------------------------------------------------------
Epoch 1/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [06:36<00:00,  9.69it/s, loss=8.7150, main=8.5686]

  Train: Loss=9.6967 (main=8.9213, len=0.425, tcls=1.646)
  Val:   Loss=3.6164 | PPL=37.2 | Top1=10.5% Top5=39.0% TF-SeqEM=0.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=7.9%
  TF=1.000, AR=0%, LR=0.000050
  [Diag] BERT gradient check moved to _train_step_autoregressive (after backward)
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 2/50
----------------------------------------------------------------------
Epoch 2/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [06:42<00:00,  9.56it/s, loss=8.5552, main=8.4483]

  Train: Loss=8.2797 (main=8.1335, len=0.152, tcls=0.034)
  Val:   Loss=3.2823 | PPL=26.6 | Top1=20.6% Top5=49.8% TF-SeqEM=0.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.5%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 3/50
----------------------------------------------------------------------
Epoch 3/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [06:41<00:00,  9.58it/s, loss=7.6422, main=7.5271]

  Train: Loss=7.9199 (main=7.7878, len=0.133, tcls=0.018)
  Val:   Loss=3.1095 | PPL=22.4 | Top1=26.3% Top5=55.6% TF-SeqEM=0.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.9%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 4/50
----------------------------------------------------------------------
Epoch 4/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [06:41<00:00,  9.58it/s, loss=7.4471, main=7.3423]

  Train: Loss=7.6166 (main=7.4910, len=0.123, tcls=0.012)
  Val:   Loss=2.9977 | PPL=20.0 | Top1=31.2% Top5=59.0% TF-SeqEM=1.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.5%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 5/50
----------------------------------------------------------------------
Epoch 5/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [07:04<00:00,  9.06it/s, loss=7.4141, main=7.3098]

  Train: Loss=7.3793 (main=7.2590, len=0.113, tcls=0.008)
  Val:   Loss=2.9815 | PPL=19.7 | Top1=31.0% Top5=58.7% TF-SeqEM=0.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.8%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 6/50
----------------------------------------------------------------------
Epoch 6/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [06:42<00:00,  9.57it/s, loss=7.4274, main=7.2527]

  Train: Loss=7.2237 (main=7.1066, len=0.108, tcls=0.007)
  Val:   Loss=2.9651 | PPL=19.4 | Top1=32.0% Top5=59.3% TF-SeqEM=0.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.1%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 7/50
----------------------------------------------------------------------
Epoch 7/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [06:42<00:00,  9.54it/s, loss=7.4538, main=7.3566]

  Train: Loss=7.0607 (main=6.9476, len=0.101, tcls=0.005)
  Val:   Loss=2.9062 | PPL=18.3 | Top1=35.0% Top5=62.4% TF-SeqEM=0.9%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 8/50
----------------------------------------------------------------------
Epoch 8/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [06:43<00:00,  9.54it/s, loss=7.4035, main=7.2919]

  Train: Loss=6.9979 (main=6.8873, len=0.096, tcls=0.004)
  Val:   Loss=2.9038 | PPL=18.2 | Top1=35.0% Top5=62.0% TF-SeqEM=1.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.6%
  TF=1.000, AR=0%, LR=0.000048
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 9/50
----------------------------------------------------------------------
Epoch 9/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [06:42<00:00,  9.57it/s, loss=7.6596, main=7.5576]

  Train: Loss=6.9036 (main=6.7950, len=0.092, tcls=0.003)
  Val:   Loss=2.8423 | PPL=17.2 | Top1=36.5% Top5=63.7% TF-SeqEM=1.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.3%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 10/50
----------------------------------------------------------------------
Epoch 10/50 [TF, n=61537]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [06:41<00:00,  9.58it/s, loss=7.3256, main=7.2250]

  Train: Loss=6.8551 (main=6.7479, len=0.089, tcls=0.003)
  Val:   Loss=2.8452 | PPL=17.2 | Top1=37.0% Top5=63.2% TF-SeqEM=1.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.4%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 11/50
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61537]:   0%|                                                                                                                               | 1/3846 [00:00<07:17,  8.78it/s, loss=7.4199, main=7.2621]
  [Diag] BERT top-layer gradients (after backward): OK ✓
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [23:29<00:00,  2.73it/s, loss=7.6838, main=7.5806]

  Train: Loss=inf (main=inf, len=0.105, tcls=0.004)
  Val:   Loss=2.8500 | PPL=17.3 | Top1=35.0% Top5=63.9% TF-SeqEM=1.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
  TF=0.417, AR=50%, LR=0.000046
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 12/50
----------------------------------------------------------------------
Epoch 12/50 [AR-SS(tf=0.41,ar=51%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [23:44<00:00,  2.70it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.104, tcls=0.004)
  Val:   Loss=2.8526 | PPL=17.3 | Top1=34.7% Top5=63.3% TF-SeqEM=0.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.5%
  TF=0.408, AR=51%, LR=0.000045
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 13/50
----------------------------------------------------------------------
Epoch 13/50 [AR-SS(tf=0.40,ar=52%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [24:14<00:00,  2.64it/s, loss=7.1630, main=7.0545]

  Train: Loss=inf (main=inf, len=0.103, tcls=0.005)
  Val:   Loss=2.8255 | PPL=16.9 | Top1=35.5% Top5=65.0% TF-SeqEM=0.7%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.3%
  TF=0.398, AR=52%, LR=0.000044
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 14/50
----------------------------------------------------------------------
Epoch 14/50 [AR-SS(tf=0.39,ar=54%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [24:21<00:00,  2.63it/s, loss=7.4091, main=7.3172]

  Train: Loss=inf (main=inf, len=0.102, tcls=0.004)
  Val:   Loss=2.8434 | PPL=17.2 | Top1=35.6% Top5=64.2% TF-SeqEM=0.7%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.9%
  TF=0.387, AR=54%, LR=0.000043
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 15/50
----------------------------------------------------------------------
Epoch 15/50 [AR-SS(tf=0.38,ar=55%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [24:28<00:00,  2.62it/s, loss=7.5509, main=7.4401]

  Train: Loss=inf (main=inf, len=0.099, tcls=0.004)
  Val:   Loss=2.8064 | PPL=16.6 | Top1=36.9% Top5=65.0% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
  TF=0.376, AR=55%, LR=0.000042
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 16/50
----------------------------------------------------------------------
Epoch 16/50 [AR-SS(tf=0.36,ar=56%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [25:18<00:00,  2.53it/s, loss=7.0773, main=6.9626]

  Train: Loss=inf (main=inf, len=0.099, tcls=0.003)
  Val:   Loss=2.8197 | PPL=16.8 | Top1=36.6% Top5=64.9% TF-SeqEM=1.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.9%
  TF=0.364, AR=56%, LR=0.000040
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 17/50
----------------------------------------------------------------------
Epoch 17/50 [AR-SS(tf=0.35,ar=57%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [25:49<00:00,  2.48it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.099, tcls=0.003)
  Val:   Loss=2.8344 | PPL=17.0 | Top1=35.9% Top5=63.8% TF-SeqEM=1.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.4%
  TF=0.351, AR=57%, LR=0.000039
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 18/50
----------------------------------------------------------------------
Epoch 18/50 [AR-SS(tf=0.34,ar=59%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [26:36<00:00,  2.41it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.100, tcls=0.003)
  Val:   Loss=2.8625 | PPL=17.5 | Top1=35.5% Top5=63.2% TF-SeqEM=0.9%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
  TF=0.338, AR=59%, LR=0.000038
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 19/50
----------------------------------------------------------------------
Epoch 19/50 [AR-SS(tf=0.32,ar=60%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [26:56<00:00,  2.38it/s, loss=6.6962, main=6.6079]

  Train: Loss=inf (main=inf, len=0.099, tcls=0.003)
  Val:   Loss=2.8266 | PPL=16.9 | Top1=36.1% Top5=64.0% TF-SeqEM=0.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.9%
  TF=0.324, AR=60%, LR=0.000036
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 20/50
----------------------------------------------------------------------
Epoch 20/50 [AR-SS(tf=0.31,ar=61%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [27:11<00:00,  2.36it/s, loss=7.3525, main=7.2566]

  Train: Loss=inf (main=inf, len=0.097, tcls=0.003)
  Val:   Loss=2.8215 | PPL=16.8 | Top1=36.9% Top5=64.4% TF-SeqEM=1.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.3%
  TF=0.309, AR=61%, LR=0.000035
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 21/50
----------------------------------------------------------------------
Epoch 21/50 [AR-SS(tf=0.29,ar=62%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [27:01<00:00,  2.37it/s, loss=7.7497, main=7.6243]

  Train: Loss=inf (main=inf, len=0.097, tcls=0.003)
  Val:   Loss=2.8348 | PPL=17.0 | Top1=36.7% Top5=63.8% TF-SeqEM=1.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
  TF=0.294, AR=62%, LR=0.000033
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 22/50
----------------------------------------------------------------------
Epoch 22/50 [AR-SS(tf=0.28,ar=64%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [27:50<00:00,  2.30it/s, loss=5.3735, main=5.2951]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.002)
  Val:   Loss=2.8420 | PPL=17.1 | Top1=36.2% Top5=64.2% TF-SeqEM=1.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.4%
  TF=0.279, AR=64%, LR=0.000032
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 23/50
----------------------------------------------------------------------
Epoch 23/50 [AR-SS(tf=0.26,ar=65%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [28:53<00:00,  2.22it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.096, tcls=0.002)
  Val:   Loss=2.8229 | PPL=16.8 | Top1=37.2% Top5=64.3% TF-SeqEM=1.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
  TF=0.264, AR=65%, LR=0.000030
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 24/50
----------------------------------------------------------------------
Epoch 24/50 [AR-SS(tf=0.25,ar=66%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [30:08<00:00,  2.13it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.002)
  Val:   Loss=2.8340 | PPL=17.0 | Top1=36.7% Top5=63.9% TF-SeqEM=1.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.6%
  TF=0.248, AR=66%, LR=0.000029
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 25/50
----------------------------------------------------------------------
Epoch 25/50 [AR-SS(tf=0.23,ar=68%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [30:56<00:00,  2.07it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.096, tcls=0.002)
  Val:   Loss=2.8389 | PPL=17.1 | Top1=36.4% Top5=63.9% TF-SeqEM=0.9%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.6%
  TF=0.232, AR=68%, LR=0.000027
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 26/50
----------------------------------------------------------------------
Epoch 26/50 [AR-SS(tf=0.22,ar=69%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [30:50<00:00,  2.08it/s, loss=7.6300, main=7.5258]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.002)
  Val:   Loss=2.8265 | PPL=16.9 | Top1=37.7% Top5=64.1% TF-SeqEM=1.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
  TF=0.217, AR=69%, LR=0.000026
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 27/50
----------------------------------------------------------------------
Epoch 27/50 [AR-SS(tf=0.20,ar=70%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [31:10<00:00,  2.06it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.094, tcls=0.002)
  Val:   Loss=2.8657 | PPL=17.6 | Top1=36.2% Top5=63.0% TF-SeqEM=1.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
  TF=0.202, AR=70%, LR=0.000024
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 28/50
----------------------------------------------------------------------
Epoch 28/50 [AR-SS(tf=0.19,ar=71%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [31:38<00:00,  2.03it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.096, tcls=0.002)
  Val:   Loss=2.8469 | PPL=17.2 | Top1=36.9% Top5=63.6% TF-SeqEM=1.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.9%
  TF=0.187, AR=71%, LR=0.000022
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 29/50
----------------------------------------------------------------------
Epoch 29/50 [AR-SS(tf=0.17,ar=72%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [40:16<00:00,  1.59it/s, loss=6.1193, main=6.0319]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.002)
  Val:   Loss=2.8417 | PPL=17.1 | Top1=36.5% Top5=63.8% TF-SeqEM=1.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
  TF=0.173, AR=72%, LR=0.000021
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 30/50
----------------------------------------------------------------------
Epoch 30/50 [AR-SS(tf=0.16,ar=74%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [41:12<00:00,  1.56it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.093, tcls=0.002)
  Val:   Loss=2.8549 | PPL=17.4 | Top1=36.9% Top5=63.1% TF-SeqEM=1.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=18.0%
  TF=0.159, AR=74%, LR=0.000019
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 31/50
----------------------------------------------------------------------
Epoch 31/50 [AR-SS(tf=0.15,ar=75%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [42:13<00:00,  1.52it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.094, tcls=0.002)
  Val:   Loss=2.8448 | PPL=17.2 | Top1=36.5% Top5=63.5% TF-SeqEM=1.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.0%
  TF=0.145, AR=75%, LR=0.000018
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 32/50
----------------------------------------------------------------------
Epoch 32/50 [AR-SS(tf=0.13,ar=76%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [38:49<00:00,  1.65it/s, loss=7.2268, main=7.1020]

  Train: Loss=inf (main=inf, len=0.096, tcls=0.002)
  Val:   Loss=2.8381 | PPL=17.1 | Top1=36.5% Top5=64.1% TF-SeqEM=1.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
  TF=0.133, AR=76%, LR=0.000016
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 33/50
----------------------------------------------------------------------
Epoch 33/50 [AR-SS(tf=0.12,ar=78%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [33:43<00:00,  1.90it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.002)
  Val:   Loss=2.8528 | PPL=17.3 | Top1=36.1% Top5=63.5% TF-SeqEM=1.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
  TF=0.121, AR=78%, LR=0.000015
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 34/50
----------------------------------------------------------------------
Epoch 34/50 [AR-SS(tf=0.11,ar=79%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [33:42<00:00,  1.90it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.092, tcls=0.002)
  Val:   Loss=2.8524 | PPL=17.3 | Top1=35.9% Top5=63.7% TF-SeqEM=1.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
  TF=0.110, AR=79%, LR=0.000013
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 35/50
----------------------------------------------------------------------
Epoch 35/50 [AR-SS(tf=0.10,ar=80%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [34:39<00:00,  1.85it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.002)
  Val:   Loss=2.8633 | PPL=17.5 | Top1=36.2% Top5=63.1% TF-SeqEM=1.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
  TF=0.100, AR=80%, LR=0.000012
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 36/50
----------------------------------------------------------------------
Epoch 36/50 [AR-SS(tf=0.09,ar=81%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [35:10<00:00,  1.82it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.094, tcls=0.002)
  Val:   Loss=2.8488 | PPL=17.3 | Top1=36.2% Top5=63.5% TF-SeqEM=1.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.0%
  TF=0.090, AR=81%, LR=0.000011
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 37/50
----------------------------------------------------------------------
Epoch 37/50 [AR-SS(tf=0.08,ar=82%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [35:29<00:00,  1.81it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.094, tcls=0.002)
  Val:   Loss=2.8587 | PPL=17.4 | Top1=36.6% Top5=63.1% TF-SeqEM=1.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.8%
  TF=0.081, AR=82%, LR=0.000009
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 38/50
----------------------------------------------------------------------
Epoch 38/50 [AR-SS(tf=0.07,ar=84%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [35:45<00:00,  1.79it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.094, tcls=0.002)
  Val:   Loss=2.8775 | PPL=17.8 | Top1=35.8% Top5=62.9% TF-SeqEM=1.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
  TF=0.073, AR=84%, LR=0.000008
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 39/50
----------------------------------------------------------------------
Epoch 39/50 [AR-SS(tf=0.07,ar=85%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [36:06<00:00,  1.78it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.096, tcls=0.002)
  Val:   Loss=2.8697 | PPL=17.6 | Top1=35.7% Top5=63.1% TF-SeqEM=1.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=18.0%
  TF=0.066, AR=85%, LR=0.000007
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 40/50
----------------------------------------------------------------------
Epoch 40/50 [AR-SS(tf=0.06,ar=86%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [36:23<00:00,  1.76it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.094, tcls=0.002)
  Val:   Loss=2.8745 | PPL=17.7 | Top1=35.8% Top5=63.3% TF-SeqEM=1.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
  TF=0.059, AR=86%, LR=0.000006
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 41/50
----------------------------------------------------------------------
Epoch 41/50 [AR-SS(tf=0.05,ar=88%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [37:14<00:00,  1.72it/s, loss=6.6378, main=6.5386]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.001)
  Val:   Loss=2.8846 | PPL=17.9 | Top1=35.3% Top5=62.8% TF-SeqEM=1.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
  TF=0.053, AR=88%, LR=0.000005
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 42/50
----------------------------------------------------------------------
Epoch 42/50 [AR-SS(tf=0.05,ar=89%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [37:15<00:00,  1.72it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.001)
  Val:   Loss=2.8903 | PPL=18.0 | Top1=35.3% Top5=62.8% TF-SeqEM=1.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
  TF=0.047, AR=89%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 43/50
----------------------------------------------------------------------
Epoch 43/50 [AR-SS(tf=0.04,ar=90%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [38:14<00:00,  1.68it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.096, tcls=0.002)
  Val:   Loss=2.9079 | PPL=18.3 | Top1=34.7% Top5=62.0% TF-SeqEM=1.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
  TF=0.042, AR=90%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 44/50
----------------------------------------------------------------------
Epoch 44/50 [AR-SS(tf=0.04,ar=91%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [38:21<00:00,  1.67it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.094, tcls=0.002)
  Val:   Loss=2.9045 | PPL=18.3 | Top1=34.6% Top5=62.7% TF-SeqEM=1.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
  TF=0.037, AR=91%, LR=0.000003
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 45/50
----------------------------------------------------------------------
Epoch 45/50 [AR-SS(tf=0.03,ar=92%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [38:35<00:00,  1.66it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.001)
  Val:   Loss=2.8961 | PPL=18.1 | Top1=34.9% Top5=63.0% TF-SeqEM=1.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
  TF=0.033, AR=92%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 46/50
----------------------------------------------------------------------
Epoch 46/50 [AR-SS(tf=0.03,ar=94%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [39:05<00:00,  1.64it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.096, tcls=0.001)
  Val:   Loss=2.9012 | PPL=18.2 | Top1=34.7% Top5=62.4% TF-SeqEM=1.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
  TF=0.030, AR=94%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 47/50
----------------------------------------------------------------------
Epoch 47/50 [AR-SS(tf=0.03,ar=95%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [39:39<00:00,  1.62it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.096, tcls=0.001)
  Val:   Loss=2.9210 | PPL=18.6 | Top1=34.0% Top5=62.0% TF-SeqEM=1.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.1%
  TF=0.026, AR=95%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 48/50
----------------------------------------------------------------------
Epoch 48/50 [AR-SS(tf=0.02,ar=96%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [40:10<00:00,  1.60it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.002)
  Val:   Loss=2.9327 | PPL=18.8 | Top1=33.6% Top5=61.7% TF-SeqEM=1.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
  TF=0.023, AR=96%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 49/50
----------------------------------------------------------------------
Epoch 49/50 [AR-SS(tf=0.02,ar=98%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [43:30<00:00,  1.47it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.096, tcls=0.002)
  Val:   Loss=2.9412 | PPL=18.9 | Top1=33.3% Top5=61.5% TF-SeqEM=1.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
  TF=0.021, AR=98%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

Epoch 50/50
----------------------------------------------------------------------
Epoch 50/50 [AR-SS(tf=0.02,ar=99%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [52:04<00:00,  1.23it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.095, tcls=0.001)
  Val:   Loss=2.9487 | PPL=19.1 | Top1=33.0% Top5=61.4% TF-SeqEM=1.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.9%
  TF=0.018, AR=99%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/best_model.pth

================================================================================
Training complete! Loading latest checkpoint for test evaluation...

Test Results:
  Loss=2.9974 PPL=20.0
  Top1=31.3% Top5=60.0%
  TF-SeqEM=0.6%
  AR-SeqEM=0.0% AR-TokenAcc=18.8%

History saved: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42/training_history_v4_6.json

V4.6 Quality-Gate training summary:
  trainer: V4.6
  mode: from_scratch
  data_path: outputs_v2/v4_qg_mr_ablation/mr_all_42/labeled_workflows_l3_v4_quality_gate.json
  splits_path: outputs_v2/v4_qg_mr_ablation/mr_all_42/dataset_splits_v4_quality_gate.json
  task_vocab_path: outputs_v2/v4_qg_mr_ablation/mr_all_42/task_type_vocabulary_v4_quality_gate.json
  warmstart_path: None
  checkpoint_dir: outputs_v2/transformer_checkpoints_v4_6_quality_gate_mr_all_42
  workflows_total: 76926
  train: 61537
  val: 7694
  test: 7695
  num_task_types: 47
  vocab_size: 98
  num_epochs: 50
  tf_phase_epochs: 10
  device: cuda
  dry_run: False
  history_epochs: 50