(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_v4_6_quality_gate.py --data outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json --splits outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json --task-vocab outputs_v2/pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json --checkpoint-dir outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix --num-epochs 50
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
Epoch 1/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [07:36<00:00,  8.42it/s, loss=7.7533, main=7.5980]

  Train: Loss=9.7804 (main=8.9336, len=0.442, tcls=1.854)
  Val:   Loss=3.4241 | PPL=30.7 | Top1=15.6% Top5=45.4% TF-SeqEM=0.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.4%
  TF=1.000, AR=0%, LR=0.000050
  [Diag] BERT gradient check moved to _train_step_autoregressive (after backward)
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 2/50
----------------------------------------------------------------------
Epoch 2/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [08:20<00:00,  7.68it/s, loss=6.3974, main=6.2653]

  Train: Loss=8.3215 (main=8.1716, len=0.157, tcls=0.038)
  Val:   Loss=3.3078 | PPL=27.3 | Top1=17.5% Top5=47.8% TF-SeqEM=0.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.8%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 3/50
----------------------------------------------------------------------
Epoch 3/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [08:24<00:00,  7.62it/s, loss=7.6041, main=7.4774]

  Train: Loss=7.9229 (main=7.7899, len=0.135, tcls=0.018)
  Val:   Loss=3.1322 | PPL=22.9 | Top1=25.1% Top5=53.8% TF-SeqEM=0.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.2%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 4/50
----------------------------------------------------------------------
Epoch 4/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [08:21<00:00,  7.67it/s, loss=7.7019, main=7.5383]

  Train: Loss=7.6337 (main=7.5069, len=0.125, tcls=0.011)
  Val:   Loss=3.0199 | PPL=20.5 | Top1=29.4% Top5=57.4% TF-SeqEM=0.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.7%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 5/50
----------------------------------------------------------------------
Epoch 5/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [08:20<00:00,  7.68it/s, loss=6.0320, main=5.9369]

  Train: Loss=7.3950 (main=7.2743, len=0.115, tcls=0.008)
  Val:   Loss=2.9244 | PPL=18.6 | Top1=32.5% Top5=60.3% TF-SeqEM=0.9%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.8%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 6/50
----------------------------------------------------------------------
Epoch 6/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [08:20<00:00,  7.68it/s, loss=6.9314, main=6.8396]

  Train: Loss=7.2172 (main=7.0999, len=0.109, tcls=0.006)
  Val:   Loss=2.8944 | PPL=18.1 | Top1=34.2% Top5=61.6% TF-SeqEM=0.9%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.1%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 7/50
----------------------------------------------------------------------
Epoch 7/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [08:04<00:00,  7.93it/s, loss=7.8422, main=7.7377]

  Train: Loss=7.0973 (main=6.9839, len=0.101, tcls=0.005)
  Val:   Loss=2.8557 | PPL=17.4 | Top1=35.1% Top5=62.8% TF-SeqEM=0.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.1%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 8/50
----------------------------------------------------------------------
Epoch 8/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [09:26<00:00,  6.78it/s, loss=7.2289, main=7.1182]

  Train: Loss=6.9990 (main=6.8882, len=0.097, tcls=0.003)
  Val:   Loss=2.8358 | PPL=17.0 | Top1=35.7% Top5=63.6% TF-SeqEM=1.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.6%
  TF=1.000, AR=0%, LR=0.000048
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 9/50
----------------------------------------------------------------------
Epoch 9/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [09:28<00:00,  6.76it/s, loss=5.0976, main=4.9607]

  Train: Loss=6.9295 (main=6.8204, len=0.093, tcls=0.003)
  Val:   Loss=2.8603 | PPL=17.5 | Top1=36.0% Top5=62.8% TF-SeqEM=0.9%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=15.7%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 10/50
----------------------------------------------------------------------
Epoch 10/50 [TF, n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [10:03<00:00,  6.36it/s, loss=7.2244, main=7.0986]

  Train: Loss=6.8459 (main=6.7387, len=0.089, tcls=0.003)
  Val:   Loss=2.8238 | PPL=16.8 | Top1=37.0% Top5=64.3% TF-SeqEM=1.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.6%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 11/50
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61495]:   0%|                                                                                                                               | 1/3843 [00:00<06:35,  9.72it/s, loss=6.5187, main=6.3977]
  [Diag] BERT top-layer gradients (after backward): OK ✓
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [28:05<00:00,  2.28it/s, loss=7.5865, main=6.7395]

  Train: Loss=10.0113 (main=7.2869, len=0.106, tcls=0.003)
  Val:   Loss=2.8146 | PPL=16.7 | Top1=35.2% Top5=64.8% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
  TF=0.417, AR=50%, LR=0.000046
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 12/50
----------------------------------------------------------------------
Epoch 12/50 [AR-SS(tf=0.41,ar=51%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [27:37<00:00,  2.32it/s, loss=6.9427, main=6.8249]

  Train: Loss=9.5405 (main=7.2292, len=0.104, tcls=0.004)
  Val:   Loss=2.8344 | PPL=17.0 | Top1=34.5% Top5=64.2% TF-SeqEM=0.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
  TF=0.408, AR=51%, LR=0.000045
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 13/50
----------------------------------------------------------------------
Epoch 13/50 [AR-SS(tf=0.40,ar=52%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [29:03<00:00,  2.20it/s, loss=6.9635, main=6.8871]

  Train: Loss=9.3559 (main=7.2390, len=0.105, tcls=0.004)
  Val:   Loss=2.8256 | PPL=16.9 | Top1=35.1% Top5=65.4% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=18.8%
  TF=0.398, AR=52%, LR=0.000044
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 14/50
----------------------------------------------------------------------
Epoch 14/50 [AR-SS(tf=0.39,ar=54%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [26:11<00:00,  2.45it/s, loss=6.6093, main=6.5331]

  Train: Loss=9.2403 (main=7.1968, len=0.102, tcls=0.004)
  Val:   Loss=2.8356 | PPL=17.0 | Top1=35.5% Top5=63.8% TF-SeqEM=0.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.4%
  TF=0.387, AR=54%, LR=0.000043
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 15/50
----------------------------------------------------------------------
Epoch 15/50 [AR-SS(tf=0.38,ar=55%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [36:01<00:00,  1.78it/s, loss=7.7338, main=7.5954]

  Train: Loss=9.0971 (main=7.1670, len=0.101, tcls=0.003)
  Val:   Loss=2.8485 | PPL=17.3 | Top1=34.5% Top5=63.3% TF-SeqEM=0.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
  TF=0.376, AR=55%, LR=0.000042
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 16/50
----------------------------------------------------------------------
Epoch 16/50 [AR-SS(tf=0.36,ar=56%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [39:28<00:00,  1.62it/s, loss=6.0755, main=5.9818]

  Train: Loss=9.1496 (main=7.1869, len=0.103, tcls=0.003)
  Val:   Loss=2.8341 | PPL=17.0 | Top1=35.3% Top5=64.5% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
  TF=0.364, AR=56%, LR=0.000040
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 17/50
----------------------------------------------------------------------
Epoch 17/50 [AR-SS(tf=0.35,ar=57%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [37:04<00:00,  1.73it/s, loss=12.3784, main=8.0882]

  Train: Loss=9.1511 (main=7.2074, len=0.099, tcls=0.003)
  Val:   Loss=2.8551 | PPL=17.4 | Top1=35.2% Top5=63.1% TF-SeqEM=0.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=19.2%
  TF=0.351, AR=57%, LR=0.000039
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 18/50
----------------------------------------------------------------------
Epoch 18/50 [AR-SS(tf=0.34,ar=59%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [38:16<00:00,  1.67it/s, loss=7.3028, main=7.0612]

  Train: Loss=9.0270 (main=7.1709, len=0.101, tcls=0.003)
  Val:   Loss=2.8417 | PPL=17.1 | Top1=35.9% Top5=64.1% TF-SeqEM=0.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.0%
  TF=0.338, AR=59%, LR=0.000038
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 19/50
----------------------------------------------------------------------
Epoch 19/50 [AR-SS(tf=0.32,ar=60%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [39:30<00:00,  1.62it/s, loss=12.7428, main=8.7549]

  Train: Loss=9.0556 (main=7.1744, len=0.099, tcls=0.003)
  Val:   Loss=2.8211 | PPL=16.8 | Top1=35.8% Top5=64.0% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=20.1%
  TF=0.324, AR=60%, LR=0.000036
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 20/50
----------------------------------------------------------------------
Epoch 20/50 [AR-SS(tf=0.31,ar=61%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [39:14<00:00,  1.63it/s, loss=7.3203, main=7.2073]

  Train: Loss=9.0100 (main=7.1674, len=0.100, tcls=0.002)
  Val:   Loss=2.8421 | PPL=17.2 | Top1=35.7% Top5=63.9% TF-SeqEM=0.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
  TF=0.309, AR=61%, LR=0.000035
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 21/50
----------------------------------------------------------------------
Epoch 21/50 [AR-SS(tf=0.29,ar=62%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [39:28<00:00,  1.62it/s, loss=6.6665, main=6.5086]

  Train: Loss=8.9218 (main=7.1667, len=0.099, tcls=0.002)
  Val:   Loss=2.8075 | PPL=16.6 | Top1=35.9% Top5=65.5% TF-SeqEM=0.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
  TF=0.294, AR=62%, LR=0.000033
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 22/50
----------------------------------------------------------------------
Epoch 22/50 [AR-SS(tf=0.28,ar=64%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [42:28<00:00,  1.51it/s, loss=15.1573, main=6.9389]

  Train: Loss=8.9672 (main=7.1549, len=0.100, tcls=0.002)
  Val:   Loss=2.8428 | PPL=17.2 | Top1=35.4% Top5=64.6% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
  TF=0.279, AR=64%, LR=0.000032
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 23/50
----------------------------------------------------------------------
Epoch 23/50 [AR-SS(tf=0.26,ar=65%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [38:58<00:00,  1.64it/s, loss=6.6480, main=6.5253]

  Train: Loss=8.9495 (main=7.1575, len=0.097, tcls=0.002)
  Val:   Loss=2.8306 | PPL=17.0 | Top1=35.4% Top5=64.0% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.4%
  TF=0.264, AR=65%, LR=0.000030
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 24/50
----------------------------------------------------------------------
Epoch 24/50 [AR-SS(tf=0.25,ar=66%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [37:43<00:00,  1.70it/s, loss=6.7288, main=6.6328]

  Train: Loss=8.9077 (main=7.1538, len=0.099, tcls=0.002)
  Val:   Loss=2.8479 | PPL=17.3 | Top1=35.8% Top5=63.8% TF-SeqEM=0.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
  TF=0.248, AR=66%, LR=0.000029
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 25/50
----------------------------------------------------------------------
Epoch 25/50 [AR-SS(tf=0.23,ar=68%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [38:21<00:00,  1.67it/s, loss=8.1546, main=7.8994]

  Train: Loss=8.8957 (main=7.1575, len=0.099, tcls=0.002)
  Val:   Loss=2.8274 | PPL=16.9 | Top1=36.0% Top5=65.0% TF-SeqEM=0.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=18.9%
  TF=0.232, AR=68%, LR=0.000027
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 26/50
----------------------------------------------------------------------
Epoch 26/50 [AR-SS(tf=0.22,ar=69%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [38:51<00:00,  1.65it/s, loss=7.3675, main=7.2566]

  Train: Loss=8.8013 (main=7.1404, len=0.098, tcls=0.002)
  Val:   Loss=2.8072 | PPL=16.6 | Top1=35.8% Top5=64.7% TF-SeqEM=0.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
  TF=0.217, AR=69%, LR=0.000026
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 27/50
----------------------------------------------------------------------
Epoch 27/50 [AR-SS(tf=0.20,ar=70%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [38:26<00:00,  1.67it/s, loss=6.9683, main=6.8685]

  Train: Loss=8.8236 (main=7.1259, len=0.095, tcls=0.002)
  Val:   Loss=2.8222 | PPL=16.8 | Top1=36.2% Top5=64.5% TF-SeqEM=0.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
  TF=0.202, AR=70%, LR=0.000024
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 28/50
----------------------------------------------------------------------
Epoch 28/50 [AR-SS(tf=0.19,ar=71%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [39:40<00:00,  1.61it/s, loss=9.8486, main=5.8408]

  Train: Loss=8.7480 (main=7.1332, len=0.098, tcls=0.002)
  Val:   Loss=2.8509 | PPL=17.3 | Top1=35.2% Top5=63.5% TF-SeqEM=0.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
  TF=0.187, AR=71%, LR=0.000022
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 29/50
----------------------------------------------------------------------
Epoch 29/50 [AR-SS(tf=0.17,ar=72%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [40:55<00:00,  1.57it/s, loss=12.6147, main=6.9054]

  Train: Loss=8.7913 (main=7.1550, len=0.097, tcls=0.002)
  Val:   Loss=2.8324 | PPL=17.0 | Top1=35.8% Top5=64.6% TF-SeqEM=0.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.2%
  TF=0.173, AR=72%, LR=0.000021
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 30/50
----------------------------------------------------------------------
Epoch 30/50 [AR-SS(tf=0.16,ar=74%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [41:15<00:00,  1.55it/s, loss=15.1430, main=7.2178]

  Train: Loss=8.7818 (main=7.1353, len=0.095, tcls=0.002)
  Val:   Loss=2.8618 | PPL=17.5 | Top1=34.8% Top5=63.6% TF-SeqEM=0.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.5%
  TF=0.159, AR=74%, LR=0.000019
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 31/50
----------------------------------------------------------------------
Epoch 31/50 [AR-SS(tf=0.15,ar=75%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [42:16<00:00,  1.52it/s, loss=7.6548, main=7.4992]

  Train: Loss=8.7455 (main=7.1312, len=0.097, tcls=0.002)
  Val:   Loss=2.8464 | PPL=17.2 | Top1=35.1% Top5=64.5% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
  TF=0.145, AR=75%, LR=0.000018
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 32/50
----------------------------------------------------------------------
Epoch 32/50 [AR-SS(tf=0.13,ar=76%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [42:23<00:00,  1.51it/s, loss=14.3384, main=7.1394]

  Train: Loss=8.7360 (main=7.1383, len=0.097, tcls=0.001)
  Val:   Loss=2.8586 | PPL=17.4 | Top1=35.1% Top5=63.8% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.8%
  TF=0.133, AR=76%, LR=0.000016
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 33/50
----------------------------------------------------------------------
Epoch 33/50 [AR-SS(tf=0.12,ar=78%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [42:14<00:00,  1.52it/s, loss=8.2700, main=8.0690]

  Train: Loss=8.6865 (main=7.1451, len=0.096, tcls=0.001)
  Val:   Loss=2.8400 | PPL=17.1 | Top1=35.8% Top5=64.3% TF-SeqEM=0.7%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
  TF=0.121, AR=78%, LR=0.000015
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 34/50
----------------------------------------------------------------------
Epoch 34/50 [AR-SS(tf=0.11,ar=79%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [43:39<00:00,  1.47it/s, loss=7.4541, main=7.2606]

  Train: Loss=8.7083 (main=7.1464, len=0.096, tcls=0.001)
  Val:   Loss=2.8458 | PPL=17.2 | Top1=35.2% Top5=64.3% TF-SeqEM=0.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
  TF=0.110, AR=79%, LR=0.000013
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 35/50
----------------------------------------------------------------------
Epoch 35/50 [AR-SS(tf=0.10,ar=80%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [43:42<00:00,  1.47it/s, loss=13.4973, main=7.1823]

  Train: Loss=8.7012 (main=7.1416, len=0.096, tcls=0.001)
  Val:   Loss=2.8472 | PPL=17.2 | Top1=35.2% Top5=64.1% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
  TF=0.100, AR=80%, LR=0.000012
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 36/50
----------------------------------------------------------------------
Epoch 36/50 [AR-SS(tf=0.09,ar=81%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [44:00<00:00,  1.46it/s, loss=8.6498, main=8.4441]

  Train: Loss=8.6852 (main=7.1542, len=0.095, tcls=0.001)
  Val:   Loss=2.8574 | PPL=17.4 | Top1=35.4% Top5=64.3% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
  TF=0.090, AR=81%, LR=0.000011
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 37/50
----------------------------------------------------------------------
Epoch 37/50 [AR-SS(tf=0.08,ar=82%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [43:07<00:00,  1.49it/s, loss=6.1632, main=6.0113]

  Train: Loss=8.6795 (main=7.1545, len=0.096, tcls=0.001)
  Val:   Loss=2.8733 | PPL=17.7 | Top1=34.5% Top5=63.5% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
  TF=0.081, AR=82%, LR=0.000009
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 38/50
----------------------------------------------------------------------
Epoch 38/50 [AR-SS(tf=0.07,ar=84%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [40:56<00:00,  1.56it/s, loss=7.4173, main=7.2933]

  Train: Loss=8.7094 (main=7.1458, len=0.094, tcls=0.001)
  Val:   Loss=2.8656 | PPL=17.6 | Top1=34.5% Top5=64.0% TF-SeqEM=0.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
  TF=0.073, AR=84%, LR=0.000008
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 39/50
----------------------------------------------------------------------
Epoch 39/50 [AR-SS(tf=0.07,ar=85%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [41:45<00:00,  1.53it/s, loss=15.5613, main=7.5460]

  Train: Loss=8.6864 (main=7.1394, len=0.097, tcls=0.001)
  Val:   Loss=2.8708 | PPL=17.7 | Top1=35.0% Top5=63.9% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.3%
  TF=0.066, AR=85%, LR=0.000007
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 40/50
----------------------------------------------------------------------
Epoch 40/50 [AR-SS(tf=0.06,ar=86%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [41:58<00:00,  1.53it/s, loss=7.0332, main=6.8675]

  Train: Loss=8.7232 (main=7.1545, len=0.095, tcls=0.001)
  Val:   Loss=2.8659 | PPL=17.6 | Top1=34.8% Top5=64.2% TF-SeqEM=0.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
  TF=0.059, AR=86%, LR=0.000006
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 41/50
----------------------------------------------------------------------
Epoch 41/50 [AR-SS(tf=0.05,ar=88%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [42:33<00:00,  1.50it/s, loss=6.6095, main=6.5334]

  Train: Loss=8.6026 (main=7.1507, len=0.096, tcls=0.001)
  Val:   Loss=2.8917 | PPL=18.0 | Top1=34.0% Top5=63.2% TF-SeqEM=0.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
  TF=0.053, AR=88%, LR=0.000005
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 42/50
----------------------------------------------------------------------
Epoch 42/50 [AR-SS(tf=0.05,ar=89%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [43:43<00:00,  1.46it/s, loss=7.9035, main=7.7717]

  Train: Loss=8.6369 (main=7.1837, len=0.096, tcls=0.001)
  Val:   Loss=2.8976 | PPL=18.1 | Top1=33.9% Top5=63.2% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.5%
  TF=0.047, AR=89%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 43/50
----------------------------------------------------------------------
Epoch 43/50 [AR-SS(tf=0.04,ar=90%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [43:27<00:00,  1.47it/s, loss=7.1448, main=6.9356]

  Train: Loss=8.6327 (main=7.1642, len=0.097, tcls=0.001)
  Val:   Loss=2.8891 | PPL=18.0 | Top1=34.2% Top5=63.3% TF-SeqEM=0.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
  TF=0.042, AR=90%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 44/50
----------------------------------------------------------------------
Epoch 44/50 [AR-SS(tf=0.04,ar=91%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [43:07<00:00,  1.49it/s, loss=7.4362, main=7.1649]

  Train: Loss=8.6274 (main=7.1818, len=0.097, tcls=0.001)
  Val:   Loss=2.9022 | PPL=18.2 | Top1=33.4% Top5=63.0% TF-SeqEM=0.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.9%
  TF=0.037, AR=91%, LR=0.000003
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 45/50
----------------------------------------------------------------------
Epoch 45/50 [AR-SS(tf=0.03,ar=92%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [43:25<00:00,  1.47it/s, loss=7.6145, main=7.5286]

  Train: Loss=8.6650 (main=7.1921, len=0.096, tcls=0.001)
  Val:   Loss=2.9119 | PPL=18.4 | Top1=33.1% Top5=62.9% TF-SeqEM=0.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.6%
  TF=0.033, AR=92%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 46/50
----------------------------------------------------------------------
Epoch 46/50 [AR-SS(tf=0.03,ar=94%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [43:52<00:00,  1.46it/s, loss=7.3925, main=7.2710]

  Train: Loss=8.6599 (main=7.1825, len=0.097, tcls=0.001)
  Val:   Loss=2.9140 | PPL=18.4 | Top1=32.9% Top5=62.6% TF-SeqEM=0.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.1%
  TF=0.030, AR=94%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 47/50
----------------------------------------------------------------------
Epoch 47/50 [AR-SS(tf=0.03,ar=95%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [44:49<00:00,  1.43it/s, loss=12.1760, main=8.1206]

  Train: Loss=8.6388 (main=7.1726, len=0.097, tcls=0.001)
  Val:   Loss=2.9110 | PPL=18.4 | Top1=33.1% Top5=62.8% TF-SeqEM=0.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
  TF=0.026, AR=95%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 48/50
----------------------------------------------------------------------
Epoch 48/50 [AR-SS(tf=0.02,ar=96%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [45:00<00:00,  1.42it/s, loss=7.4726, main=7.3522]

  Train: Loss=8.6772 (main=7.2013, len=0.097, tcls=0.001)
  Val:   Loss=2.9279 | PPL=18.7 | Top1=32.6% Top5=62.3% TF-SeqEM=0.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
  TF=0.023, AR=96%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 49/50
----------------------------------------------------------------------
Epoch 49/50 [AR-SS(tf=0.02,ar=98%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [45:41<00:00,  1.40it/s, loss=14.4612, main=7.9440]

  Train: Loss=8.6809 (main=7.2032, len=0.099, tcls=0.001)
  Val:   Loss=2.9340 | PPL=18.8 | Top1=32.3% Top5=62.1% TF-SeqEM=0.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.8%
  TF=0.021, AR=98%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

Epoch 50/50
----------------------------------------------------------------------
Epoch 50/50 [AR-SS(tf=0.02,ar=99%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [46:10<00:00,  1.39it/s, loss=7.5152, main=7.3364]

  Train: Loss=8.6363 (main=7.2008, len=0.098, tcls=0.001)
  Val:   Loss=2.9424 | PPL=19.0 | Top1=31.9% Top5=61.9% TF-SeqEM=0.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
  TF=0.018, AR=99%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/best_model.pth

================================================================================
Training complete! Loading latest checkpoint for test evaluation...

Test Results:
  Loss=2.9926 PPL=19.9
  Top1=30.3% Top5=60.4%
  TF-SeqEM=0.1%
  AR-SeqEM=1.6% AR-TokenAcc=19.5%

History saved: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix/training_history_v4_6.json

V4.6 Quality-Gate training summary:
  trainer: V4.6
  mode: from_scratch
  data_path: outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json
  splits_path: outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json
  task_vocab_path: outputs_v2/pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json
  warmstart_path: None
  checkpoint_dir: outputs_v2/transformer_checkpoints_v4_6_quality_gate_baseline_0517_arss_fix
  workflows_total: 76884
  train: 61495
  val: 7694
  test: 7695
  num_task_types: 47
  vocab_size: 98
  num_epochs: 50
  tf_phase_epochs: 10
  device: cuda
  dry_run: False
  history_epochs: 50