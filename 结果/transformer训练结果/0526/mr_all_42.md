(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_v4_6_quality_gate.py --mrv-ablation-dir outputs_v2/v4_qg_mr_ablation --mrv-ablation-version mr_all_42
  [V4] Loaded L3 embeddings: 94 tokens from /home/qy/system_redesign/outputs_v2/l3_embeddings_v2.pt
  Params: 22.7M trainable, 117.4M total

  Training from scratch (TF phase: 10 epochs, total: 50 epochs)
  [V4.2] Using frequency-weighted CE loss (alpha=0.5)
  [V4.2] 转移矩阵: 48 states loaded
  [V4.5] task_cls_loss_weight overridden to 0.3
  [V4.6] task_type length bucket auxiliary loss enabled (weight=0.1)

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
Epoch 1/50 [TF, n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:59:41<00:00,  1.87s/it, loss=8.7140, main=8.5679]

  Train: Loss=9.6968 (main=8.9213, len=0.425, tcls=1.646)
  Val:   Loss=3.6154 | PPL=37.2 | Top1=10.5% Top5=39.1% TF-SeqEM=0.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.0%
         AR-LCS=0.104 AR-SetF1=0.154
         len(pred)=56.9 len(ref)=7.8 |lenErr|=49.5 earlyEOS=3.1% empty=0.0%
         rep=88.4% dup=0.0% badTrans=58.1%
  TF=1.000, AR=0%, LR=0.000050
  [Diag] BERT gradient check moved to _train_step_autoregressive (after backward)
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth
  [SNAPSHOT] Saved best Gen SetF1: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_gen_set_f1_model.pth
  [SNAPSHOT] Saved best Gen LCS: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_gen_lcs_model.pth

Epoch 2/50
----------------------------------------------------------------------
Epoch 2/50 [TF, n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [2:00:26<00:00,  1.88s/it, loss=8.5534, main=8.4469]

  Train: Loss=8.2798 (main=8.1336, len=0.152, tcls=0.034)
  Val:   Loss=3.2834 | PPL=26.7 | Top1=20.5% Top5=49.7% TF-SeqEM=0.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.7%
         AR-LCS=0.264 AR-SetF1=0.352
         len(pred)=16.6 len(ref)=7.8 |lenErr|=10.9 earlyEOS=13.3% empty=0.0%
         rep=65.6% dup=0.3% badTrans=56.6%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 3/50
----------------------------------------------------------------------
Epoch 3/50 [TF, n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [2:00:18<00:00,  1.88s/it, loss=7.6429, main=7.5284]

  Train: Loss=7.9191 (main=7.7870, len=0.133, tcls=0.018)
  Val:   Loss=3.1120 | PPL=22.5 | Top1=26.3% Top5=55.6% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.9%
         AR-LCS=0.309 AR-SetF1=0.418
         len(pred)=14.4 len(ref)=7.8 |lenErr|=10.2 earlyEOS=22.7% empty=0.0%
         rep=60.1% dup=0.1% badTrans=46.4%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 4/50
----------------------------------------------------------------------
Epoch 4/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [50:48<00:00,  1.26it/s, loss=7.4407, main=7.3350]

  Train: Loss=7.6159 (main=7.4903, len=0.123, tcls=0.012)
  Val:   Loss=2.9949 | PPL=20.0 | Top1=31.2% Top5=59.0% TF-SeqEM=1.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.6%
         AR-LCS=0.354 AR-SetF1=0.486
         len(pred)=5.9 len(ref)=7.8 |lenErr|=3.6 earlyEOS=32.0% empty=0.0%
         rep=10.5% dup=0.0% badTrans=20.7%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 5/50
----------------------------------------------------------------------
Epoch 5/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [14:21<00:00,  4.47it/s, loss=7.4212, main=7.3179]

  Train: Loss=7.3780 (main=7.2577, len=0.113, tcls=0.008)
  Val:   Loss=2.9737 | PPL=19.6 | Top1=31.4% Top5=59.0% TF-SeqEM=0.9% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.3%
         AR-LCS=0.353 AR-SetF1=0.488
         len(pred)=9.8 len(ref)=7.8 |lenErr|=4.8 earlyEOS=14.1% empty=0.0%
         rep=30.9% dup=0.1% badTrans=28.9%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 6/50
----------------------------------------------------------------------
Epoch 6/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [14:35<00:00,  4.39it/s, loss=7.4301, main=7.2544]

  Train: Loss=7.2231 (main=7.1061, len=0.108, tcls=0.007)
  Val:   Loss=2.9672 | PPL=19.4 | Top1=32.0% Top5=59.3% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.7%
         AR-LCS=0.349 AR-SetF1=0.484
         len(pred)=8.2 len(ref)=7.8 |lenErr|=4.2 earlyEOS=20.3% empty=0.0%
         rep=23.7% dup=0.2% badTrans=25.8%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 7/50
----------------------------------------------------------------------
Epoch 7/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [14:02<00:00,  4.57it/s, loss=7.4548, main=7.3569]

  Train: Loss=7.0601 (main=6.9470, len=0.101, tcls=0.005)
  Val:   Loss=2.9098 | PPL=18.4 | Top1=35.0% Top5=62.3% TF-SeqEM=0.9% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.2%
         AR-LCS=0.367 AR-SetF1=0.503
         len(pred)=8.6 len(ref)=7.8 |lenErr|=4.0 earlyEOS=16.4% empty=0.0%
         rep=24.7% dup=0.2% badTrans=23.2%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 8/50
----------------------------------------------------------------------
Epoch 8/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [17:20<00:00,  3.70it/s, loss=7.3941, main=7.2846]

  Train: Loss=6.9972 (main=6.8866, len=0.096, tcls=0.004)
  Val:   Loss=2.9086 | PPL=18.3 | Top1=34.8% Top5=62.0% TF-SeqEM=0.9% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.1%
         AR-LCS=0.368 AR-SetF1=0.510
         len(pred)=6.9 len(ref)=7.8 |lenErr|=2.9 earlyEOS=15.6% empty=0.0%
         rep=9.9% dup=0.5% badTrans=16.1%
  TF=1.000, AR=0%, LR=0.000048
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 9/50
----------------------------------------------------------------------
Epoch 9/50 [TF, n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [49:02<00:00,  1.31it/s, loss=7.6493, main=7.5496]

  Train: Loss=6.9027 (main=6.7940, len=0.092, tcls=0.003)
  Val:   Loss=2.8489 | PPL=17.3 | Top1=36.3% Top5=63.5% TF-SeqEM=1.7% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.0%
         AR-LCS=0.382 AR-SetF1=0.516
         len(pred)=6.0 len(ref)=7.8 |lenErr|=3.0 earlyEOS=24.2% empty=0.0%
         rep=3.8% dup=0.8% badTrans=7.9%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 10/50
----------------------------------------------------------------------
Epoch 10/50 [TF, n=61537]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [51:52<00:00,  1.24it/s, loss=7.3238, main=7.2224]

  Train: Loss=6.8543 (main=6.7472, len=0.089, tcls=0.003)
  Val:   Loss=2.8490 | PPL=17.3 | Top1=37.0% Top5=63.1% TF-SeqEM=1.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.2%
         AR-LCS=0.387 AR-SetF1=0.528
         len(pred)=6.7 len(ref)=7.8 |lenErr|=2.9 earlyEOS=19.5% empty=0.0%
         rep=6.8% dup=1.1% badTrans=12.2%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 11/50
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61537]:   0%|                                                                                                                               | 1/3846 [00:00<56:18,  1.14it/s, loss=7.4129, main=7.2533]
  [Diag] BERT top-layer gradients (after backward): OK ✓
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:21:01<00:00,  1.26s/it, loss=7.7542, main=7.6528]

  Train: Loss=9.9839 (main=7.2553, len=0.121, tcls=0.004)
  Val:   Loss=2.8545 | PPL=17.4 | Top1=34.4% Top5=63.5% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.9%
         AR-LCS=0.388 AR-SetF1=0.525
         len(pred)=10.2 len(ref)=7.8 |lenErr|=4.4 earlyEOS=6.2% empty=0.0%
         rep=31.7% dup=0.3% badTrans=18.2%
  TF=0.417, AR=50%, LR=0.000046
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 12/50
----------------------------------------------------------------------
Epoch 12/50 [AR-SS(tf=0.41,ar=51%), n=61537]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [44:24<00:00,  1.44it/s, loss=13.7846, main=8.0567]

  Train: Loss=9.5470 (main=7.2368, len=0.120, tcls=0.004)
  Val:   Loss=2.8142 | PPL=16.7 | Top1=35.5% Top5=64.5% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.6%
         AR-LCS=0.393 AR-SetF1=0.543
         len(pred)=7.0 len(ref)=7.8 |lenErr|=2.9 earlyEOS=14.1% empty=0.0%
         rep=10.1% dup=0.4% badTrans=13.2%
  TF=0.408, AR=51%, LR=0.000045
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 13/50
----------------------------------------------------------------------
Epoch 13/50 [AR-SS(tf=0.40,ar=52%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [43:33<00:00,  1.47it/s, loss=7.1442, main=7.0231]

  Train: Loss=9.3790 (main=7.2439, len=0.120, tcls=0.005)
  Val:   Loss=2.8465 | PPL=17.2 | Top1=34.1% Top5=63.9% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.0%
         AR-LCS=0.393 AR-SetF1=0.547
         len(pred)=9.2 len(ref)=7.8 |lenErr|=3.9 earlyEOS=9.4% empty=0.0%
         rep=24.8% dup=0.3% badTrans=14.3%
  TF=0.398, AR=52%, LR=0.000044
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 14/50
----------------------------------------------------------------------
Epoch 14/50 [AR-SS(tf=0.39,ar=54%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [43:26<00:00,  1.48it/s, loss=7.4537, main=7.3669]

  Train: Loss=9.2042 (main=7.2065, len=0.119, tcls=0.004)
  Val:   Loss=2.8345 | PPL=17.0 | Top1=35.8% Top5=64.7% TF-SeqEM=0.8% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.6%
         AR-LCS=0.386 AR-SetF1=0.533
         len(pred)=7.6 len(ref)=7.8 |lenErr|=3.1 earlyEOS=14.8% empty=0.0%
         rep=17.3% dup=0.4% badTrans=14.6%
  TF=0.387, AR=54%, LR=0.000043
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 15/50
----------------------------------------------------------------------
Epoch 15/50 [AR-SS(tf=0.38,ar=55%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [47:15<00:00,  1.36it/s, loss=7.5830, main=7.4714]

  Train: Loss=9.1255 (main=7.1721, len=0.117, tcls=0.004)
  Val:   Loss=2.7942 | PPL=16.3 | Top1=36.2% Top5=65.9% TF-SeqEM=1.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.0%
         AR-LCS=0.412 AR-SetF1=0.541
         len(pred)=7.2 len(ref)=7.8 |lenErr|=2.7 earlyEOS=12.5% empty=0.0%
         rep=12.2% dup=0.6% badTrans=13.2%
  TF=0.376, AR=55%, LR=0.000042
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 16/50
----------------------------------------------------------------------
Epoch 16/50 [AR-SS(tf=0.36,ar=56%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [50:14<00:00,  1.28it/s, loss=7.0828, main=6.9740]

  Train: Loss=9.1225 (main=7.1786, len=0.116, tcls=0.004)
  Val:   Loss=2.8294 | PPL=16.9 | Top1=35.8% Top5=64.6% TF-SeqEM=0.8% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.399 AR-SetF1=0.535
         len(pred)=8.8 len(ref)=7.8 |lenErr|=3.3 earlyEOS=7.8% empty=0.0%
         rep=19.4% dup=0.4% badTrans=13.4%
  TF=0.364, AR=56%, LR=0.000040
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 17/50
----------------------------------------------------------------------
Epoch 17/50 [AR-SS(tf=0.35,ar=57%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [47:45<00:00,  1.34it/s, loss=8.0099, main=7.7137]

  Train: Loss=9.1920 (main=7.1903, len=0.118, tcls=0.003)
  Val:   Loss=2.8210 | PPL=16.8 | Top1=35.9% Top5=64.6% TF-SeqEM=1.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.401 AR-SetF1=0.543
         len(pred)=8.4 len(ref)=7.8 |lenErr|=3.3 earlyEOS=10.2% empty=0.0%
         rep=18.4% dup=0.3% badTrans=15.5%
  TF=0.351, AR=57%, LR=0.000039
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 18/50
----------------------------------------------------------------------
Epoch 18/50 [AR-SS(tf=0.34,ar=59%), n=61537]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [50:09<00:00,  1.28it/s, loss=12.0039, main=7.4161]

  Train: Loss=9.0567 (main=7.1902, len=0.119, tcls=0.003)
  Val:   Loss=2.8573 | PPL=17.4 | Top1=34.7% Top5=63.6% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.3%
         AR-LCS=0.386 AR-SetF1=0.529
         len(pred)=10.6 len(ref)=7.8 |lenErr|=4.5 earlyEOS=7.0% empty=0.0%
         rep=36.9% dup=0.6% badTrans=26.9%
  TF=0.338, AR=59%, LR=0.000038
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 19/50
----------------------------------------------------------------------
Epoch 19/50 [AR-SS(tf=0.32,ar=60%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [49:37<00:00,  1.29it/s, loss=6.7276, main=6.6392]

  Train: Loss=9.0004 (main=7.1576, len=0.120, tcls=0.003)
  Val:   Loss=2.8314 | PPL=17.0 | Top1=35.4% Top5=64.2% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.393 AR-SetF1=0.541
         len(pred)=9.4 len(ref)=7.8 |lenErr|=3.4 earlyEOS=0.8% empty=0.0%
         rep=23.4% dup=0.5% badTrans=17.4%
  TF=0.324, AR=60%, LR=0.000036
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 20/50
----------------------------------------------------------------------
Epoch 20/50 [AR-SS(tf=0.31,ar=61%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [50:15<00:00,  1.28it/s, loss=7.3638, main=7.2705]

  Train: Loss=8.9819 (main=7.1781, len=0.118, tcls=0.002)
  Val:   Loss=2.8553 | PPL=17.4 | Top1=35.0% Top5=63.4% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
         AR-LCS=0.411 AR-SetF1=0.552
         len(pred)=8.0 len(ref)=7.8 |lenErr|=2.9 earlyEOS=10.9% empty=0.0%
         rep=15.4% dup=0.4% badTrans=13.7%
  TF=0.309, AR=61%, LR=0.000035
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 21/50
----------------------------------------------------------------------
Epoch 21/50 [AR-SS(tf=0.29,ar=62%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [50:14<00:00,  1.28it/s, loss=7.6740, main=7.5477]

  Train: Loss=8.9593 (main=7.1370, len=0.117, tcls=0.003)
  Val:   Loss=2.8546 | PPL=17.4 | Top1=35.5% Top5=63.1% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.1%
         AR-LCS=0.383 AR-SetF1=0.522
         len(pred)=8.4 len(ref)=7.8 |lenErr|=3.3 earlyEOS=4.7% empty=0.0%
         rep=18.1% dup=0.4% badTrans=17.0%
  TF=0.294, AR=62%, LR=0.000033
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 22/50
----------------------------------------------------------------------
Epoch 22/50 [AR-SS(tf=0.28,ar=64%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [52:42<00:00,  1.22it/s, loss=5.4518, main=5.3697]

  Train: Loss=8.9264 (main=7.1337, len=0.117, tcls=0.002)
  Val:   Loss=2.8455 | PPL=17.2 | Top1=35.3% Top5=63.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.1%
         AR-LCS=0.411 AR-SetF1=0.547
         len(pred)=7.7 len(ref)=7.8 |lenErr|=2.6 earlyEOS=10.2% empty=0.0%
         rep=16.4% dup=0.7% badTrans=18.4%
  TF=0.279, AR=64%, LR=0.000032
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 23/50
----------------------------------------------------------------------
Epoch 23/50 [AR-SS(tf=0.26,ar=65%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [54:14<00:00,  1.18it/s, loss=7.9551, main=7.7179]

  Train: Loss=8.9939 (main=7.1545, len=0.118, tcls=0.002)
  Val:   Loss=2.8090 | PPL=16.6 | Top1=36.6% Top5=65.0% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.4%
         AR-LCS=0.404 AR-SetF1=0.548
         len(pred)=7.4 len(ref)=7.8 |lenErr|=2.9 earlyEOS=11.7% empty=0.0%
         rep=12.9% dup=0.4% badTrans=14.9%
  TF=0.264, AR=65%, LR=0.000030
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 24/50
----------------------------------------------------------------------
Epoch 24/50 [AR-SS(tf=0.25,ar=66%), n=61537]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [57:14<00:00,  1.12it/s, loss=13.1155, main=7.1208]

  Train: Loss=8.9539 (main=7.1333, len=0.118, tcls=0.002)
  Val:   Loss=2.8019 | PPL=16.5 | Top1=36.8% Top5=65.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.9%
         AR-LCS=0.416 AR-SetF1=0.563
         len(pred)=7.0 len(ref)=7.8 |lenErr|=3.0 earlyEOS=16.4% empty=0.0%
         rep=10.0% dup=0.4% badTrans=11.7%
  TF=0.248, AR=66%, LR=0.000029
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 25/50
----------------------------------------------------------------------
Epoch 25/50 [AR-SS(tf=0.23,ar=68%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [56:44<00:00,  1.13it/s, loss=9.1515, main=8.8297]

  Train: Loss=8.9151 (main=7.1508, len=0.118, tcls=0.002)
  Val:   Loss=2.8143 | PPL=16.7 | Top1=36.0% Top5=64.8% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
         AR-LCS=0.421 AR-SetF1=0.560
         len(pred)=7.6 len(ref)=7.8 |lenErr|=2.9 earlyEOS=10.9% empty=0.0%
         rep=14.1% dup=0.9% badTrans=11.8%
  TF=0.232, AR=68%, LR=0.000027
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 26/50
----------------------------------------------------------------------
Epoch 26/50 [AR-SS(tf=0.22,ar=69%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [55:19<00:00,  1.16it/s, loss=7.6797, main=7.5722]

  Train: Loss=8.8295 (main=7.1311, len=0.119, tcls=0.002)
  Val:   Loss=2.8415 | PPL=17.1 | Top1=36.0% Top5=64.2% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.4%
         AR-LCS=0.394 AR-SetF1=0.536
         len(pred)=7.3 len(ref)=7.8 |lenErr|=2.9 earlyEOS=11.7% empty=0.0%
         rep=12.3% dup=0.4% badTrans=16.1%
  TF=0.217, AR=69%, LR=0.000026
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 27/50
----------------------------------------------------------------------
Epoch 27/50 [AR-SS(tf=0.20,ar=70%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [57:25<00:00,  1.12it/s, loss=6.8769, main=6.7232]

  Train: Loss=8.8864 (main=7.1543, len=0.118, tcls=0.002)
  Val:   Loss=2.8595 | PPL=17.5 | Top1=35.1% Top5=63.4% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
         AR-LCS=0.407 AR-SetF1=0.548
         len(pred)=8.1 len(ref)=7.8 |lenErr|=2.8 earlyEOS=8.6% empty=0.0%
         rep=17.3% dup=0.4% badTrans=18.2%
  TF=0.202, AR=70%, LR=0.000024
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 28/50
----------------------------------------------------------------------
Epoch 28/50 [AR-SS(tf=0.19,ar=71%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [56:58<00:00,  1.13it/s, loss=6.9406, main=6.6921]

  Train: Loss=8.7687 (main=7.1237, len=0.120, tcls=0.002)
  Val:   Loss=2.8507 | PPL=17.3 | Top1=35.7% Top5=63.5% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.5%
         AR-LCS=0.408 AR-SetF1=0.548
         len(pred)=8.2 len(ref)=7.8 |lenErr|=2.7 earlyEOS=6.2% empty=0.0%
         rep=17.7% dup=0.7% badTrans=18.7%
  TF=0.187, AR=71%, LR=0.000022
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 29/50
----------------------------------------------------------------------
Epoch 29/50 [AR-SS(tf=0.17,ar=72%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [59:15<00:00,  1.08it/s, loss=6.1466, main=6.0658]

  Train: Loss=8.8140 (main=7.1345, len=0.120, tcls=0.002)
  Val:   Loss=2.8547 | PPL=17.4 | Top1=35.8% Top5=63.4% TF-SeqEM=0.7% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
         AR-LCS=0.417 AR-SetF1=0.556
         len(pred)=7.7 len(ref)=7.8 |lenErr|=2.4 earlyEOS=5.5% empty=0.0%
         rep=15.7% dup=1.4% badTrans=18.0%
  TF=0.173, AR=72%, LR=0.000021
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 30/50
----------------------------------------------------------------------
Epoch 30/50 [AR-SS(tf=0.16,ar=74%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [59:04<00:00,  1.09it/s, loss=8.0378, main=7.9107]

  Train: Loss=8.8118 (main=7.1476, len=0.118, tcls=0.002)
  Val:   Loss=2.8354 | PPL=17.0 | Top1=36.2% Top5=64.4% TF-SeqEM=0.8% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.1%
         AR-LCS=0.413 AR-SetF1=0.561
         len(pred)=7.5 len(ref)=7.8 |lenErr|=2.6 earlyEOS=9.4% empty=0.0%
         rep=13.1% dup=0.6% badTrans=15.0%
  TF=0.159, AR=74%, LR=0.000019
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 31/50
----------------------------------------------------------------------
Epoch 31/50 [AR-SS(tf=0.15,ar=75%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [59:29<00:00,  1.08it/s, loss=7.3606, main=7.2540]

  Train: Loss=8.7964 (main=7.1420, len=0.119, tcls=0.002)
  Val:   Loss=2.8438 | PPL=17.2 | Top1=36.0% Top5=64.6% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
         AR-LCS=0.417 AR-SetF1=0.560
         len(pred)=7.7 len(ref)=7.8 |lenErr|=2.6 earlyEOS=7.0% empty=0.0%
         rep=16.0% dup=0.6% badTrans=15.1%
  TF=0.145, AR=75%, LR=0.000018
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 32/50
----------------------------------------------------------------------
Epoch 32/50 [AR-SS(tf=0.13,ar=76%), n=61537]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [59:03<00:00,  1.09it/s, loss=7.2513, main=7.1306]

  Train: Loss=8.8326 (main=7.1677, len=0.121, tcls=0.002)
  Val:   Loss=2.8566 | PPL=17.4 | Top1=35.1% Top5=63.7% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
         AR-LCS=0.413 AR-SetF1=0.544
         len(pred)=8.6 len(ref)=7.8 |lenErr|=3.1 earlyEOS=5.5% empty=0.0%
         rep=22.6% dup=0.8% badTrans=17.5%
  TF=0.133, AR=76%, LR=0.000016
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 33/50
----------------------------------------------------------------------
Epoch 33/50 [AR-SS(tf=0.12,ar=78%), n=61537]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [59:24<00:00,  1.08it/s, loss=13.5327, main=7.2661]

  Train: Loss=8.7568 (main=7.1434, len=0.121, tcls=0.001)
  Val:   Loss=2.8599 | PPL=17.5 | Top1=35.3% Top5=63.6% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.3%
         AR-LCS=0.402 AR-SetF1=0.549
         len(pred)=8.1 len(ref)=7.8 |lenErr|=2.9 earlyEOS=8.6% empty=0.0%
         rep=16.9% dup=1.0% badTrans=16.2%
  TF=0.121, AR=78%, LR=0.000015
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 34/50
----------------------------------------------------------------------
Epoch 34/50 [AR-SS(tf=0.11,ar=79%), n=61537]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [59:15<00:00,  1.08it/s, loss=13.6522, main=7.5747]

  Train: Loss=8.7399 (main=7.1517, len=0.118, tcls=0.001)
  Val:   Loss=2.8485 | PPL=17.3 | Top1=35.2% Top5=64.2% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.1%
         AR-LCS=0.421 AR-SetF1=0.569
         len(pred)=8.0 len(ref)=7.8 |lenErr|=2.6 earlyEOS=7.0% empty=0.0%
         rep=17.1% dup=0.7% badTrans=13.4%
  TF=0.110, AR=79%, LR=0.000013
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 35/50
----------------------------------------------------------------------
Epoch 35/50 [AR-SS(tf=0.10,ar=80%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:00:27<00:00,  1.06it/s, loss=7.5727, main=7.4574]

  Train: Loss=8.6949 (main=7.1333, len=0.122, tcls=0.001)
  Val:   Loss=2.8685 | PPL=17.6 | Top1=35.1% Top5=63.5% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.1%
         AR-LCS=0.410 AR-SetF1=0.549
         len(pred)=7.8 len(ref)=7.8 |lenErr|=2.5 earlyEOS=4.7% empty=0.0%
         rep=15.3% dup=0.8% badTrans=15.0%
  TF=0.100, AR=80%, LR=0.000012
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 36/50
----------------------------------------------------------------------
Epoch 36/50 [AR-SS(tf=0.09,ar=81%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:01:21<00:00,  1.04it/s, loss=6.3978, main=6.1867]

  Train: Loss=8.6900 (main=7.1368, len=0.121, tcls=0.001)
  Val:   Loss=2.8476 | PPL=17.2 | Top1=35.3% Top5=64.1% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.6%
         AR-LCS=0.402 AR-SetF1=0.541
         len(pred)=8.6 len(ref)=7.8 |lenErr|=2.9 earlyEOS=7.8% empty=0.0%
         rep=21.9% dup=0.9% badTrans=22.0%
  TF=0.090, AR=81%, LR=0.000011
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 37/50
----------------------------------------------------------------------
Epoch 37/50 [AR-SS(tf=0.08,ar=82%), n=61537]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:02:05<00:00,  1.03it/s, loss=11.1041, main=7.5466]

  Train: Loss=8.7255 (main=7.1604, len=0.122, tcls=0.001)
  Val:   Loss=2.8649 | PPL=17.5 | Top1=35.6% Top5=63.4% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
         AR-LCS=0.397 AR-SetF1=0.544
         len(pred)=8.4 len(ref)=7.8 |lenErr|=3.0 earlyEOS=8.6% empty=0.0%
         rep=20.9% dup=0.7% badTrans=23.0%
  TF=0.081, AR=82%, LR=0.000009
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 38/50
----------------------------------------------------------------------
Epoch 38/50 [AR-SS(tf=0.07,ar=84%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:02:19<00:00,  1.03it/s, loss=6.8990, main=6.6940]

  Train: Loss=8.7514 (main=7.1674, len=0.122, tcls=0.001)
  Val:   Loss=2.8788 | PPL=17.8 | Top1=34.6% Top5=63.3% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.1%
         AR-LCS=0.407 AR-SetF1=0.547
         len(pred)=9.7 len(ref)=7.8 |lenErr|=3.9 earlyEOS=7.0% empty=0.0%
         rep=32.1% dup=0.6% badTrans=29.2%
  TF=0.073, AR=84%, LR=0.000008
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 39/50
----------------------------------------------------------------------
Epoch 39/50 [AR-SS(tf=0.07,ar=85%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:02:59<00:00,  1.02it/s, loss=8.3211, main=8.1843]

  Train: Loss=8.6396 (main=7.1393, len=0.124, tcls=0.001)
  Val:   Loss=2.8684 | PPL=17.6 | Top1=34.6% Top5=63.3% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
         AR-LCS=0.412 AR-SetF1=0.553
         len(pred)=9.1 len(ref)=7.8 |lenErr|=3.4 earlyEOS=7.0% empty=0.0%
         rep=27.3% dup=0.7% badTrans=25.4%
  TF=0.066, AR=85%, LR=0.000007
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 40/50
----------------------------------------------------------------------
Epoch 40/50 [AR-SS(tf=0.06,ar=86%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:03:22<00:00,  1.01it/s, loss=6.1620, main=6.0964]

  Train: Loss=8.6679 (main=7.1568, len=0.122, tcls=0.001)
  Val:   Loss=2.8741 | PPL=17.7 | Top1=35.1% Top5=63.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.9%
         AR-LCS=0.401 AR-SetF1=0.546
         len(pred)=7.5 len(ref)=7.8 |lenErr|=2.7 earlyEOS=7.8% empty=0.0%
         rep=14.4% dup=1.2% badTrans=20.5%
  TF=0.059, AR=86%, LR=0.000006
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 41/50
----------------------------------------------------------------------
Epoch 41/50 [AR-SS(tf=0.05,ar=88%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:04:37<00:00,  1.01s/it, loss=6.6773, main=6.5802]

  Train: Loss=8.7058 (main=7.1676, len=0.124, tcls=0.001)
  Val:   Loss=2.8932 | PPL=18.1 | Top1=34.4% Top5=62.9% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
         AR-LCS=0.406 AR-SetF1=0.546
         len(pred)=9.8 len(ref)=7.8 |lenErr|=3.8 earlyEOS=4.7% empty=0.0%
         rep=30.3% dup=0.8% badTrans=29.7%
  TF=0.053, AR=88%, LR=0.000005
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 42/50
----------------------------------------------------------------------
Epoch 42/50 [AR-SS(tf=0.05,ar=89%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:05:16<00:00,  1.02s/it, loss=7.3707, main=7.2670]

  Train: Loss=8.6671 (main=7.1689, len=0.124, tcls=0.001)
  Val:   Loss=2.8904 | PPL=18.0 | Top1=34.0% Top5=63.2% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.8%
         AR-LCS=0.405 AR-SetF1=0.546
         len(pred)=9.0 len(ref)=7.8 |lenErr|=3.3 earlyEOS=7.8% empty=0.0%
         rep=28.0% dup=0.9% badTrans=28.9%
  TF=0.047, AR=89%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 43/50
----------------------------------------------------------------------
Epoch 43/50 [AR-SS(tf=0.04,ar=90%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:06:38<00:00,  1.04s/it, loss=7.0195, main=6.7385]

  Train: Loss=8.6235 (main=7.1801, len=0.126, tcls=0.001)
  Val:   Loss=2.9151 | PPL=18.5 | Top1=33.5% Top5=62.2% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.413 AR-SetF1=0.553
         len(pred)=9.4 len(ref)=7.8 |lenErr|=3.5 earlyEOS=4.7% empty=0.0%
         rep=29.1% dup=0.7% badTrans=31.5%
  TF=0.042, AR=90%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 44/50
----------------------------------------------------------------------
Epoch 44/50 [AR-SS(tf=0.04,ar=91%), n=61537]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:06:29<00:00,  1.04s/it, loss=15.6429, main=6.8579]

  Train: Loss=8.6489 (main=7.1600, len=0.124, tcls=0.001)
  Val:   Loss=2.9048 | PPL=18.3 | Top1=33.7% Top5=62.9% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
         AR-LCS=0.403 AR-SetF1=0.542
         len(pred)=9.8 len(ref)=7.8 |lenErr|=3.9 earlyEOS=6.2% empty=0.0%
         rep=31.0% dup=0.9% badTrans=31.2%
  TF=0.037, AR=91%, LR=0.000003
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 45/50
----------------------------------------------------------------------
Epoch 45/50 [AR-SS(tf=0.03,ar=92%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:05:00<00:00,  1.01s/it, loss=7.5162, main=7.4330]

  Train: Loss=8.7380 (main=7.1977, len=0.125, tcls=0.001)
  Val:   Loss=2.9000 | PPL=18.2 | Top1=33.6% Top5=63.1% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.414 AR-SetF1=0.553
         len(pred)=7.8 len(ref)=7.8 |lenErr|=2.4 earlyEOS=7.0% empty=0.0%
         rep=16.8% dup=1.0% badTrans=20.7%
  TF=0.033, AR=92%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 46/50
----------------------------------------------------------------------
Epoch 46/50 [AR-SS(tf=0.03,ar=94%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:05:19<00:00,  1.02s/it, loss=7.5479, main=7.3910]

  Train: Loss=8.6512 (main=7.1815, len=0.126, tcls=0.001)
  Val:   Loss=2.9157 | PPL=18.5 | Top1=33.4% Top5=62.3% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
         AR-LCS=0.404 AR-SetF1=0.541
         len(pred)=9.1 len(ref)=7.8 |lenErr|=3.4 earlyEOS=7.0% empty=0.0%
         rep=27.8% dup=0.9% badTrans=30.6%
  TF=0.030, AR=94%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 47/50
----------------------------------------------------------------------
Epoch 47/50 [AR-SS(tf=0.03,ar=95%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:08:15<00:00,  1.06s/it, loss=9.2565, main=8.9845]

  Train: Loss=8.6894 (main=7.2020, len=0.127, tcls=0.001)
  Val:   Loss=2.9278 | PPL=18.7 | Top1=32.8% Top5=62.1% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
         AR-LCS=0.409 AR-SetF1=0.542
         len(pred)=8.7 len(ref)=7.8 |lenErr|=3.0 earlyEOS=7.0% empty=0.0%
         rep=24.9% dup=0.9% badTrans=29.0%
  TF=0.026, AR=95%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 48/50
----------------------------------------------------------------------
Epoch 48/50 [AR-SS(tf=0.02,ar=96%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:09:44<00:00,  1.09s/it, loss=6.3056, main=6.2438]

  Train: Loss=8.6820 (main=7.2071, len=0.127, tcls=0.001)
  Val:   Loss=2.9397 | PPL=18.9 | Top1=32.5% Top5=61.7% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
         AR-LCS=0.402 AR-SetF1=0.541
         len(pred)=9.2 len(ref)=7.8 |lenErr|=3.5 earlyEOS=6.2% empty=0.0%
         rep=29.1% dup=0.9% badTrans=32.9%
  TF=0.023, AR=96%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 49/50
----------------------------------------------------------------------
Epoch 49/50 [AR-SS(tf=0.02,ar=98%), n=61537]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:10:57<00:00,  1.11s/it, loss=11.7310, main=6.5199]

  Train: Loss=8.7232 (main=7.1850, len=0.129, tcls=0.001)
  Val:   Loss=2.9414 | PPL=18.9 | Top1=32.3% Top5=61.9% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
         AR-LCS=0.404 AR-SetF1=0.545
         len(pred)=9.1 len(ref)=7.8 |lenErr|=3.4 earlyEOS=7.0% empty=0.0%
         rep=29.1% dup=0.9% badTrans=31.1%
  TF=0.021, AR=98%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 50/50
----------------------------------------------------------------------
Epoch 50/50 [AR-SS(tf=0.02,ar=99%), n=61537]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3846/3846 [1:10:22<00:00,  1.10s/it, loss=8.1380, main=8.0530]

  Train: Loss=8.6957 (main=7.2084, len=0.128, tcls=0.001)
  Val:   Loss=2.9601 | PPL=19.3 | Top1=31.6% Top5=61.2% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
         AR-LCS=0.400 AR-SetF1=0.536
         len(pred)=9.8 len(ref)=7.8 |lenErr|=3.7 earlyEOS=3.9% empty=0.0%
         rep=32.7% dup=0.8% badTrans=35.6%
  TF=0.018, AR=99%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

================================================================================
Training complete! Loading latest checkpoint for test evaluation...

Test Results:
  Loss=3.0089 PPL=20.3
  Top1=30.1% Top5=59.8%
  TF-SeqEM=0.1% avglen(ref)=9.5
  AR-SeqEM=0.0% AR-TokenAcc=18.4%
  AR-LCS=0.423 AR-SetF1=0.544
  len(pred)=12.1 len(ref)=7.0 |lenErr|=6.4
  earlyEOS=4.7% empty=0.0%
  rep=50.1% dup=0.0% badTrans=37.0%

History saved: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/training_history_v4_6.json
Checkpoint selection manifest saved: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/checkpoint_selection_manifest_v4_6.json

V4.6 Quality-Gate training summary:
  trainer: V4.6
  mode: from_scratch
  mr_registry: {'status': 'disabled', 'path': None, 'ratio': 0.0, 'task_groups': 0, 'matched_train_samples': 0}
  mrv_training_dataset: {'status': 'enabled', 'version_name': 'mr_all_42', 'manifest_path': 'outputs_v2/v4_qg_mr_ablation/mrv_training_ablation_manifest.json', 'report_path': 'outputs_v2/v4_qg_mr_ablation/mr_all_42/mrv_training_ablation_report.json', 'data_path': 'outputs_v2/v4_qg_mr_ablation/mr_all_42/labeled_workflows_l3_v4_quality_gate.json', 'splits_path': 'outputs_v2/v4_qg_mr_ablation/mr_all_42/dataset_splits_v4_quality_gate.json', 'task_vocab_path': 'outputs_v2/v4_qg_mr_ablation/mr_all_42/task_type_vocabulary_v4_quality_gate.json', 'injected_variants': 42, 'available_verified_mr_variants': 42, 'train_injection_rate_vs_base_train': 0.00068298, 'equivalence_family_counts': {'filter_filter': 30, 'select_filter': 8, 'select_clip': 3, 'other': 1}, 'risk_level_counts': {'low': 31, 'medium': 10, 'unknown': 1}}
  length_bucket_training: {'status': 'enabled', 'path': '/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json', 'loss_weight': 0.1, 'target': 'task_type_bucket_expected_length', 'splits': {'train': {'samples': 61537, 'bucket_counts': {'medium': 38297, 'long': 22791, 'short': 449}}, 'val': {'samples': 7694, 'bucket_counts': {'long': 2846, 'medium': 4791, 'short': 57}}, 'test': {'samples': 7695, 'bucket_counts': {'medium': 4793, 'short': 57, 'long': 2845}}}, 'expected_length_by_bucket': {'short': 3, 'medium': 5, 'long': 8, 'very_long': 13}}
  training_contract: {'system_objective': 'increase usable/executable multi-solution GIS operator chains', 'known_limitations': ['token_ce_is_single_reference_supervision', 'ranking_is_post_training_not_a_training_objective', 'semantic_constraints_are_evaluated_outside_the_loss', 'inference_beam_constraints_are_not_fully_mirrored_in_ar_sampling'], 'required_post_training_validation': ['p0_evidence_aware_ranking_calibration', 'workflow_usability_evaluation', 'qgis_mapping_or_execution_diagnostics']}
  metric_contract: {'primary': ['set_f1', 'usable', 'executable', 'qgis_mapping'], 'supporting': ['lcs'], 'diagnostic_only': ['token_acc', 'sequence_em', 'loss', 'perplexity', 'top1', 'top5'], 'multi_solution_policy': 'TokenAcc and exact sequence match are diagnostic only for GIS workflow quality.'}
  checkpoint_policy: {'latest_snapshot': 'best_model.pth', 'latest_snapshot_note': 'historical compatibility name; overwritten each epoch', 'additional_selection_snapshots': ['best_gen_set_f1_model.pth', 'best_gen_lcs_model.pth'], 'selection_snapshot_note': 'post-training comparison aids; does not change training objective'}
  data_path: outputs_v2/v4_qg_mr_ablation/mr_all_42/labeled_workflows_l3_v4_quality_gate.json
  splits_path: outputs_v2/v4_qg_mr_ablation/mr_all_42/dataset_splits_v4_quality_gate.json
  task_vocab_path: outputs_v2/v4_qg_mr_ablation/mr_all_42/task_type_vocabulary_v4_quality_gate.json
  warmstart_path: None
  checkpoint_dir: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate
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