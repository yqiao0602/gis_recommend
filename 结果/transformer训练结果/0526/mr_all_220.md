(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_v4_6_quality_gate.py --mrv-ablation-dir outputs_v2/v4_qg_mr_ablation_from_multisolution --mrv-ablation-version mr_all_220
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
Epoch 1/50 [TF, n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:58:59<00:00,  1.85s/it, loss=7.4953, main=7.3103]

  Train: Loss=9.7620 (main=8.9045, len=0.430, tcls=1.912)
  Val:   Loss=3.5358 | PPL=34.3 | Top1=9.6% Top5=39.6% TF-SeqEM=0.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.1%
         AR-LCS=0.139 AR-SetF1=0.189
         len(pred)=39.2 len(ref)=7.8 |lenErr|=33.0 earlyEOS=8.6% empty=0.0%
         rep=84.3% dup=0.0% badTrans=70.9%
  TF=1.000, AR=0%, LR=0.000050
  [Diag] BERT gradient check moved to _train_step_autoregressive (after backward)
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth
  [SNAPSHOT] Saved best Gen SetF1: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_gen_set_f1_model.pth
  [SNAPSHOT] Saved best Gen LCS: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_gen_lcs_model.pth

Epoch 2/50
----------------------------------------------------------------------
Epoch 2/50 [TF, n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [2:00:44<00:00,  1.88s/it, loss=7.5905, main=7.4757]

  Train: Loss=8.2763 (main=8.1259, len=0.158, tcls=0.038)
  Val:   Loss=3.2293 | PPL=25.3 | Top1=20.6% Top5=51.3% TF-SeqEM=0.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.3%
         AR-LCS=0.271 AR-SetF1=0.372
         len(pred)=12.5 len(ref)=7.8 |lenErr|=8.0 earlyEOS=18.8% empty=0.0%
         rep=54.6% dup=0.0% badTrans=46.9%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 3/50
----------------------------------------------------------------------
Epoch 3/50 [TF, n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [2:00:05<00:00,  1.87s/it, loss=6.7625, main=6.6779]

  Train: Loss=7.9204 (main=7.7868, len=0.135, tcls=0.018)
  Val:   Loss=3.0744 | PPL=21.6 | Top1=27.1% Top5=56.9% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.7%
         AR-LCS=0.275 AR-SetF1=0.364
         len(pred)=14.7 len(ref)=7.8 |lenErr|=10.1 earlyEOS=20.3% empty=0.0%
         rep=59.7% dup=0.0% badTrans=46.8%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 4/50
----------------------------------------------------------------------
Epoch 4/50 [TF, n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [52:16<00:00,  1.23it/s, loss=7.5857, main=7.4920]

  Train: Loss=7.6138 (main=7.4865, len=0.126, tcls=0.012)
  Val:   Loss=2.9881 | PPL=19.8 | Top1=30.4% Top5=59.7% TF-SeqEM=0.7% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.4%
         AR-LCS=0.355 AR-SetF1=0.483
         len(pred)=6.5 len(ref)=7.8 |lenErr|=3.4 earlyEOS=25.8% empty=0.0%
         rep=7.9% dup=0.0% badTrans=15.8%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 5/50
----------------------------------------------------------------------
Epoch 5/50 [TF, n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [14:16<00:00,  4.50it/s, loss=7.9755, main=7.8283]

  Train: Loss=7.3834 (main=7.2622, len=0.116, tcls=0.008)
  Val:   Loss=2.9579 | PPL=19.3 | Top1=32.0% Top5=59.6% TF-SeqEM=0.9% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.9%
         AR-LCS=0.348 AR-SetF1=0.476
         len(pred)=8.6 len(ref)=7.8 |lenErr|=5.0 earlyEOS=20.3% empty=0.0%
         rep=29.3% dup=0.3% badTrans=28.5%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 6/50
----------------------------------------------------------------------
Epoch 6/50 [TF, n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [13:28<00:00,  4.77it/s, loss=5.9769, main=5.8120]

  Train: Loss=7.2298 (main=7.1119, len=0.110, tcls=0.006)
  Val:   Loss=2.9200 | PPL=18.5 | Top1=33.8% Top5=62.0% TF-SeqEM=1.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.5%
         AR-LCS=0.378 AR-SetF1=0.506
         len(pred)=7.0 len(ref)=7.8 |lenErr|=3.2 earlyEOS=13.3% empty=0.0%
         rep=8.9% dup=0.3% badTrans=17.2%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 7/50
----------------------------------------------------------------------
Epoch 7/50 [TF, n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [13:34<00:00,  4.74it/s, loss=6.4832, main=6.3858]

  Train: Loss=7.1131 (main=6.9992, len=0.102, tcls=0.004)
  Val:   Loss=2.8654 | PPL=17.6 | Top1=35.7% Top5=63.6% TF-SeqEM=1.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.4%
         AR-LCS=0.395 AR-SetF1=0.524
         len(pred)=6.4 len(ref)=7.8 |lenErr|=3.0 earlyEOS=16.4% empty=0.0%
         rep=5.2% dup=0.6% badTrans=8.6%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 8/50
----------------------------------------------------------------------
Epoch 8/50 [TF, n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [13:32<00:00,  4.75it/s, loss=7.7665, main=7.6842]

  Train: Loss=7.0044 (main=6.8923, len=0.099, tcls=0.004)
  Val:   Loss=2.8700 | PPL=17.6 | Top1=35.9% Top5=63.2% TF-SeqEM=1.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
         AR-LCS=0.395 AR-SetF1=0.513
         len(pred)=6.4 len(ref)=7.8 |lenErr|=3.1 earlyEOS=21.1% empty=0.0%
         rep=6.4% dup=0.4% badTrans=13.1%
  TF=1.000, AR=0%, LR=0.000048
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 9/50
----------------------------------------------------------------------
Epoch 9/50 [TF, n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [47:29<00:00,  1.35it/s, loss=5.9295, main=5.8387]

  Train: Loss=6.9174 (main=6.8068, len=0.096, tcls=0.003)
  Val:   Loss=2.8517 | PPL=17.3 | Top1=36.2% Top5=63.7% TF-SeqEM=0.8% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.1%
         AR-LCS=0.383 AR-SetF1=0.514
         len(pred)=6.5 len(ref)=7.8 |lenErr|=3.2 earlyEOS=20.3% empty=0.0%
         rep=8.0% dup=1.1% badTrans=12.9%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 10/50
----------------------------------------------------------------------
Epoch 10/50 [TF, n=61715]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [50:14<00:00,  1.28it/s, loss=6.4317, main=6.3643]

  Train: Loss=6.8590 (main=6.7511, len=0.091, tcls=0.003)
  Val:   Loss=2.8434 | PPL=17.2 | Top1=36.7% Top5=63.5% TF-SeqEM=1.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=15.2%
         AR-LCS=0.395 AR-SetF1=0.519
         len(pred)=6.7 len(ref)=7.8 |lenErr|=2.8 earlyEOS=15.6% empty=0.0%
         rep=6.7% dup=0.8% badTrans=10.3%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 11/50
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61715]:   0%|                                                                                                                             | 1/3857 [00:00<1:02:48,  1.02it/s, loss=6.7050, main=6.6151]
  [Diag] BERT top-layer gradients (after backward): OK ✓
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:21:56<00:00,  1.27s/it, loss=8.1260, main=7.1239]

  Train: Loss=9.9922 (main=7.2805, len=0.122, tcls=0.003)
  Val:   Loss=2.8319 | PPL=17.0 | Top1=34.4% Top5=64.4% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.373 AR-SetF1=0.517
         len(pred)=9.8 len(ref)=7.8 |lenErr|=4.3 earlyEOS=7.0% empty=0.0%
         rep=29.7% dup=0.7% badTrans=20.2%
  TF=0.417, AR=50%, LR=0.000046
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 12/50
----------------------------------------------------------------------
Epoch 12/50 [AR-SS(tf=0.41,ar=51%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [49:44<00:00,  1.29it/s, loss=8.0974, main=7.4706]

  Train: Loss=9.5566 (main=7.2423, len=0.123, tcls=0.004)
  Val:   Loss=2.8427 | PPL=17.2 | Top1=34.1% Top5=64.6% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.6%
         AR-LCS=0.349 AR-SetF1=0.492
         len(pred)=12.0 len(ref)=7.8 |lenErr|=5.9 earlyEOS=3.9% empty=0.0%
         rep=37.1% dup=0.1% badTrans=19.6%
  TF=0.408, AR=51%, LR=0.000045
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 13/50
----------------------------------------------------------------------
Epoch 13/50 [AR-SS(tf=0.40,ar=52%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [43:52<00:00,  1.46it/s, loss=7.2075, main=6.8128]

  Train: Loss=9.3859 (main=7.2181, len=0.123, tcls=0.004)
  Val:   Loss=2.8292 | PPL=16.9 | Top1=34.8% Top5=65.0% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
         AR-LCS=0.382 AR-SetF1=0.524
         len(pred)=11.0 len(ref)=7.8 |lenErr|=4.8 earlyEOS=3.1% empty=0.0%
         rep=31.8% dup=0.5% badTrans=16.4%
  TF=0.398, AR=52%, LR=0.000044
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 14/50
----------------------------------------------------------------------
Epoch 14/50 [AR-SS(tf=0.39,ar=54%), n=61715]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [43:41<00:00,  1.47it/s, loss=13.7060, main=8.2329]

  Train: Loss=9.2553 (main=7.2116, len=0.120, tcls=0.004)
  Val:   Loss=2.8114 | PPL=16.6 | Top1=35.3% Top5=64.8% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
         AR-LCS=0.404 AR-SetF1=0.538
         len(pred)=9.3 len(ref)=7.8 |lenErr|=3.3 earlyEOS=5.5% empty=0.0%
         rep=23.7% dup=0.5% badTrans=16.9%
  TF=0.387, AR=54%, LR=0.000043
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 15/50
----------------------------------------------------------------------
Epoch 15/50 [AR-SS(tf=0.38,ar=55%), n=61715]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [48:03<00:00,  1.34it/s, loss=17.6257, main=6.6781]

  Train: Loss=9.1778 (main=7.1889, len=0.121, tcls=0.003)
  Val:   Loss=2.8016 | PPL=16.5 | Top1=36.0% Top5=65.8% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
         AR-LCS=0.411 AR-SetF1=0.554
         len(pred)=7.4 len(ref)=7.8 |lenErr|=2.6 earlyEOS=10.2% empty=0.0%
         rep=11.5% dup=0.7% badTrans=13.8%
  TF=0.376, AR=55%, LR=0.000042
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 16/50
----------------------------------------------------------------------
Epoch 16/50 [AR-SS(tf=0.36,ar=56%), n=61715]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [51:15<00:00,  1.25it/s, loss=15.9430, main=8.5126]

  Train: Loss=9.1913 (main=7.1914, len=0.120, tcls=0.003)
  Val:   Loss=2.8431 | PPL=17.2 | Top1=34.2% Top5=63.6% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.9%
         AR-LCS=0.392 AR-SetF1=0.531
         len(pred)=8.3 len(ref)=7.8 |lenErr|=3.4 earlyEOS=7.8% empty=0.0%
         rep=18.0% dup=0.4% badTrans=14.4%
  TF=0.364, AR=56%, LR=0.000040
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 17/50
----------------------------------------------------------------------
Epoch 17/50 [AR-SS(tf=0.35,ar=57%), n=61715]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [47:15<00:00,  1.36it/s, loss=15.9824, main=7.4821]

  Train: Loss=9.0507 (main=7.1432, len=0.117, tcls=0.003)
  Val:   Loss=2.8162 | PPL=16.7 | Top1=36.0% Top5=64.8% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.1%
         AR-LCS=0.383 AR-SetF1=0.523
         len(pred)=8.5 len(ref)=7.8 |lenErr|=3.6 earlyEOS=9.4% empty=0.0%
         rep=18.0% dup=0.3% badTrans=14.8%
  TF=0.351, AR=57%, LR=0.000039
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 18/50
----------------------------------------------------------------------
Epoch 18/50 [AR-SS(tf=0.34,ar=59%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [47:56<00:00,  1.34it/s, loss=7.9104, main=7.5704]

  Train: Loss=9.0379 (main=7.1706, len=0.120, tcls=0.003)
  Val:   Loss=2.8302 | PPL=16.9 | Top1=35.4% Top5=64.4% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.8%
         AR-LCS=0.393 AR-SetF1=0.529
         len(pred)=8.2 len(ref)=7.8 |lenErr|=3.3 earlyEOS=10.2% empty=0.0%
         rep=20.0% dup=0.5% badTrans=16.5%
  TF=0.338, AR=59%, LR=0.000038
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 19/50
----------------------------------------------------------------------
Epoch 19/50 [AR-SS(tf=0.32,ar=60%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [47:40<00:00,  1.35it/s, loss=8.1852, main=7.8668]

  Train: Loss=9.0312 (main=7.1406, len=0.120, tcls=0.003)
  Val:   Loss=2.8263 | PPL=16.9 | Top1=35.5% Top5=64.6% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.5%
         AR-LCS=0.397 AR-SetF1=0.535
         len(pred)=10.1 len(ref)=7.8 |lenErr|=4.4 earlyEOS=6.2% empty=0.0%
         rep=27.9% dup=0.4% badTrans=19.3%
  TF=0.324, AR=60%, LR=0.000036
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 20/50
----------------------------------------------------------------------
Epoch 20/50 [AR-SS(tf=0.31,ar=61%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [49:08<00:00,  1.31it/s, loss=6.7408, main=6.6621]

  Train: Loss=9.0191 (main=7.1577, len=0.119, tcls=0.002)
  Val:   Loss=2.8122 | PPL=16.6 | Top1=36.4% Top5=65.2% TF-SeqEM=0.7% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.5%
         AR-LCS=0.398 AR-SetF1=0.537
         len(pred)=7.5 len(ref)=7.8 |lenErr|=3.0 earlyEOS=13.3% empty=0.0%
         rep=14.3% dup=0.7% badTrans=14.5%
  TF=0.309, AR=61%, LR=0.000035
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 21/50
----------------------------------------------------------------------
Epoch 21/50 [AR-SS(tf=0.29,ar=62%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [50:14<00:00,  1.28it/s, loss=7.1613, main=6.9426]

  Train: Loss=8.9736 (main=7.1585, len=0.119, tcls=0.002)
  Val:   Loss=2.8311 | PPL=17.0 | Top1=35.6% Top5=64.5% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.9%
         AR-LCS=0.385 AR-SetF1=0.529
         len(pred)=8.1 len(ref)=7.8 |lenErr|=3.0 earlyEOS=9.4% empty=0.0%
         rep=16.7% dup=0.9% badTrans=13.2%
  TF=0.294, AR=62%, LR=0.000033
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 22/50
----------------------------------------------------------------------
Epoch 22/50 [AR-SS(tf=0.28,ar=64%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [51:41<00:00,  1.24it/s, loss=7.9403, main=7.7986]

  Train: Loss=8.9670 (main=7.1614, len=0.118, tcls=0.002)
  Val:   Loss=2.8192 | PPL=16.8 | Top1=35.5% Top5=65.5% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
         AR-LCS=0.408 AR-SetF1=0.558
         len(pred)=7.6 len(ref)=7.8 |lenErr|=2.7 earlyEOS=10.2% empty=0.0%
         rep=12.9% dup=0.5% badTrans=13.5%
  TF=0.279, AR=64%, LR=0.000032
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 23/50
----------------------------------------------------------------------
Epoch 23/50 [AR-SS(tf=0.26,ar=65%), n=61715]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [52:39<00:00,  1.22it/s, loss=14.3814, main=7.7648]

  Train: Loss=8.9775 (main=7.1627, len=0.119, tcls=0.002)
  Val:   Loss=2.8243 | PPL=16.8 | Top1=36.1% Top5=64.8% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.9%
         AR-LCS=0.402 AR-SetF1=0.551
         len(pred)=7.8 len(ref)=7.8 |lenErr|=3.0 earlyEOS=10.9% empty=0.0%
         rep=13.8% dup=0.6% badTrans=19.9%
  TF=0.264, AR=65%, LR=0.000030
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 24/50
----------------------------------------------------------------------
Epoch 24/50 [AR-SS(tf=0.25,ar=66%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [55:43<00:00,  1.15it/s, loss=7.3450, main=7.2467]

  Train: Loss=8.8876 (main=7.1436, len=0.121, tcls=0.002)
  Val:   Loss=2.8477 | PPL=17.2 | Top1=34.5% Top5=64.1% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
         AR-LCS=0.395 AR-SetF1=0.549
         len(pred)=10.0 len(ref)=7.8 |lenErr|=3.9 earlyEOS=3.1% empty=0.0%
         rep=29.3% dup=0.5% badTrans=13.9%
  TF=0.248, AR=66%, LR=0.000029
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 25/50
----------------------------------------------------------------------
Epoch 25/50 [AR-SS(tf=0.23,ar=68%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [57:23<00:00,  1.12it/s, loss=7.2660, main=6.9909]

  Train: Loss=8.8971 (main=7.1545, len=0.120, tcls=0.002)
  Val:   Loss=2.8379 | PPL=17.1 | Top1=35.0% Top5=64.7% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
         AR-LCS=0.387 AR-SetF1=0.532
         len(pred)=10.4 len(ref)=7.8 |lenErr|=4.5 earlyEOS=6.2% empty=0.0%
         rep=32.8% dup=0.7% badTrans=16.0%
  TF=0.232, AR=68%, LR=0.000027
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 26/50
----------------------------------------------------------------------
Epoch 26/50 [AR-SS(tf=0.22,ar=69%), n=61715]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [55:59<00:00,  1.15it/s, loss=11.3206, main=7.1947]

  Train: Loss=8.8587 (main=7.1489, len=0.119, tcls=0.002)
  Val:   Loss=2.8252 | PPL=16.9 | Top1=36.0% Top5=64.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
         AR-LCS=0.409 AR-SetF1=0.539
         len(pred)=7.4 len(ref)=7.8 |lenErr|=2.8 earlyEOS=13.3% empty=0.0%
         rep=14.5% dup=1.0% badTrans=16.9%
  TF=0.217, AR=69%, LR=0.000026
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 27/50
----------------------------------------------------------------------
Epoch 27/50 [AR-SS(tf=0.20,ar=70%), n=61715]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [57:16<00:00,  1.12it/s, loss=13.4099, main=7.1807]

  Train: Loss=8.8326 (main=7.1279, len=0.119, tcls=0.002)
  Val:   Loss=2.8285 | PPL=16.9 | Top1=35.9% Top5=64.9% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
         AR-LCS=0.405 AR-SetF1=0.553
         len(pred)=7.9 len(ref)=7.8 |lenErr|=3.0 earlyEOS=14.8% empty=0.0%
         rep=17.2% dup=0.9% badTrans=15.3%
  TF=0.202, AR=70%, LR=0.000024
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 28/50
----------------------------------------------------------------------
Epoch 28/50 [AR-SS(tf=0.19,ar=71%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [58:03<00:00,  1.11it/s, loss=6.6194, main=6.5238]

  Train: Loss=8.8976 (main=7.1534, len=0.120, tcls=0.002)
  Val:   Loss=2.8355 | PPL=17.0 | Top1=36.1% Top5=64.4% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
         AR-LCS=0.414 AR-SetF1=0.544
         len(pred)=7.1 len(ref)=7.8 |lenErr|=2.7 earlyEOS=14.8% empty=0.0%
         rep=11.9% dup=1.2% badTrans=15.5%
  TF=0.187, AR=71%, LR=0.000022
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 29/50
----------------------------------------------------------------------
Epoch 29/50 [AR-SS(tf=0.17,ar=72%), n=61715]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [59:34<00:00,  1.08it/s, loss=6.9813, main=6.8882]

  Train: Loss=8.8842 (main=7.1633, len=0.120, tcls=0.002)
  Val:   Loss=2.8327 | PPL=17.0 | Top1=35.4% Top5=64.8% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.405 AR-SetF1=0.545
         len(pred)=7.7 len(ref)=7.8 |lenErr|=2.8 earlyEOS=8.6% empty=0.0%
         rep=16.6% dup=0.9% badTrans=17.7%
  TF=0.173, AR=72%, LR=0.000021
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 30/50
----------------------------------------------------------------------
Epoch 30/50 [AR-SS(tf=0.16,ar=74%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:00:29<00:00,  1.06it/s, loss=6.4368, main=6.3355]

  Train: Loss=8.8407 (main=7.1563, len=0.120, tcls=0.002)
  Val:   Loss=2.8533 | PPL=17.3 | Top1=35.1% Top5=63.9% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.1%
         AR-LCS=0.410 AR-SetF1=0.541
         len(pred)=8.0 len(ref)=7.8 |lenErr|=2.9 earlyEOS=9.4% empty=0.0%
         rep=17.0% dup=1.1% badTrans=18.1%
  TF=0.159, AR=74%, LR=0.000019
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 31/50
----------------------------------------------------------------------
Epoch 31/50 [AR-SS(tf=0.15,ar=75%), n=61715]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:01:42<00:00,  1.04it/s, loss=14.4688, main=8.2845]

  Train: Loss=8.8170 (main=7.1650, len=0.121, tcls=0.002)
  Val:   Loss=2.8490 | PPL=17.3 | Top1=34.7% Top5=64.5% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.4%
         AR-LCS=0.407 AR-SetF1=0.543
         len(pred)=8.6 len(ref)=7.8 |lenErr|=2.8 earlyEOS=7.0% empty=0.0%
         rep=21.3% dup=0.9% badTrans=17.1%
  TF=0.145, AR=75%, LR=0.000018
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 32/50
----------------------------------------------------------------------
Epoch 32/50 [AR-SS(tf=0.13,ar=76%), n=61715]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:00:35<00:00,  1.06it/s, loss=11.8654, main=6.0667]

  Train: Loss=8.8531 (main=7.1445, len=0.122, tcls=0.002)
  Val:   Loss=2.8307 | PPL=17.0 | Top1=35.0% Top5=64.8% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.1%
         AR-LCS=0.392 AR-SetF1=0.534
         len(pred)=9.2 len(ref)=7.8 |lenErr|=3.3 earlyEOS=6.2% empty=0.0%
         rep=24.2% dup=0.9% badTrans=16.2%
  TF=0.133, AR=76%, LR=0.000016
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 33/50
----------------------------------------------------------------------
Epoch 33/50 [AR-SS(tf=0.12,ar=78%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:01:52<00:00,  1.04it/s, loss=7.3948, main=7.1954]

  Train: Loss=8.7495 (main=7.1476, len=0.122, tcls=0.002)
  Val:   Loss=2.8396 | PPL=17.1 | Top1=35.2% Top5=65.0% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
         AR-LCS=0.397 AR-SetF1=0.539
         len(pred)=8.0 len(ref)=7.8 |lenErr|=3.0 earlyEOS=7.8% empty=0.0%
         rep=19.7% dup=1.0% badTrans=19.2%
  TF=0.121, AR=78%, LR=0.000015
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 34/50
----------------------------------------------------------------------
Epoch 34/50 [AR-SS(tf=0.11,ar=79%), n=61715]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:02:16<00:00,  1.03it/s, loss=14.2025, main=7.5376]

  Train: Loss=8.7265 (main=7.1323, len=0.122, tcls=0.001)
  Val:   Loss=2.8229 | PPL=16.8 | Top1=35.9% Top5=65.0% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
         AR-LCS=0.410 AR-SetF1=0.548
         len(pred)=7.6 len(ref)=7.8 |lenErr|=2.7 earlyEOS=10.2% empty=0.0%
         rep=14.6% dup=1.4% badTrans=16.0%
  TF=0.110, AR=79%, LR=0.000013
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 35/50
----------------------------------------------------------------------
Epoch 35/50 [AR-SS(tf=0.10,ar=80%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:02:52<00:00,  1.02it/s, loss=7.8033, main=7.6205]

  Train: Loss=8.7954 (main=7.1527, len=0.121, tcls=0.001)
  Val:   Loss=2.8665 | PPL=17.6 | Top1=34.8% Top5=64.2% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
         AR-LCS=0.403 AR-SetF1=0.540
         len(pred)=9.0 len(ref)=7.8 |lenErr|=3.3 earlyEOS=7.0% empty=0.0%
         rep=25.9% dup=1.1% badTrans=21.3%
  TF=0.100, AR=80%, LR=0.000012
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 36/50
----------------------------------------------------------------------
Epoch 36/50 [AR-SS(tf=0.09,ar=81%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:03:26<00:00,  1.01it/s, loss=7.6329, main=7.4099]

  Train: Loss=8.6738 (main=7.1380, len=0.122, tcls=0.001)
  Val:   Loss=2.8458 | PPL=17.2 | Top1=35.0% Top5=64.6% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=18.1%
         AR-LCS=0.417 AR-SetF1=0.555
         len(pred)=8.3 len(ref)=7.8 |lenErr|=2.7 earlyEOS=6.2% empty=0.0%
         rep=21.0% dup=1.1% badTrans=19.0%
  TF=0.090, AR=81%, LR=0.000011
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 37/50
----------------------------------------------------------------------
Epoch 37/50 [AR-SS(tf=0.08,ar=82%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:04:55<00:00,  1.01s/it, loss=7.0765, main=6.9973]

  Train: Loss=8.7286 (main=7.1628, len=0.123, tcls=0.001)
  Val:   Loss=2.8920 | PPL=18.0 | Top1=34.0% Top5=62.9% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.8%
         AR-LCS=0.391 AR-SetF1=0.525
         len(pred)=8.8 len(ref)=7.8 |lenErr|=3.1 earlyEOS=7.0% empty=0.0%
         rep=23.2% dup=1.0% badTrans=23.1%
  TF=0.081, AR=82%, LR=0.000009
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 38/50
----------------------------------------------------------------------
Epoch 38/50 [AR-SS(tf=0.07,ar=84%), n=61715]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:05:45<00:00,  1.02s/it, loss=12.7722, main=6.9660]

  Train: Loss=8.7528 (main=7.1759, len=0.122, tcls=0.001)
  Val:   Loss=2.8816 | PPL=17.8 | Top1=34.2% Top5=63.7% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
         AR-LCS=0.396 AR-SetF1=0.536
         len(pred)=8.6 len(ref)=7.8 |lenErr|=3.1 earlyEOS=7.0% empty=0.0%
         rep=23.6% dup=0.9% badTrans=23.2%
  TF=0.073, AR=84%, LR=0.000008
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 39/50
----------------------------------------------------------------------
Epoch 39/50 [AR-SS(tf=0.07,ar=85%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:06:11<00:00,  1.03s/it, loss=6.1258, main=6.0194]

  Train: Loss=8.7119 (main=7.1681, len=0.123, tcls=0.001)
  Val:   Loss=2.8802 | PPL=17.8 | Top1=34.2% Top5=63.6% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
         AR-LCS=0.407 AR-SetF1=0.542
         len(pred)=8.3 len(ref)=7.8 |lenErr|=2.8 earlyEOS=6.2% empty=0.0%
         rep=21.4% dup=1.2% badTrans=23.6%
  TF=0.066, AR=85%, LR=0.000007
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 40/50
----------------------------------------------------------------------
Epoch 40/50 [AR-SS(tf=0.06,ar=86%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:07:16<00:00,  1.05s/it, loss=6.9748, main=6.7993]

  Train: Loss=8.7252 (main=7.1670, len=0.124, tcls=0.001)
  Val:   Loss=2.8701 | PPL=17.6 | Top1=34.3% Top5=64.0% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.408 AR-SetF1=0.546
         len(pred)=7.6 len(ref)=7.8 |lenErr|=2.4 earlyEOS=7.8% empty=0.0%
         rep=16.9% dup=1.4% badTrans=18.9%
  TF=0.059, AR=86%, LR=0.000006
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 41/50
----------------------------------------------------------------------
Epoch 41/50 [AR-SS(tf=0.05,ar=88%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:07:11<00:00,  1.05s/it, loss=8.2521, main=8.0596]

  Train: Loss=8.7152 (main=7.1706, len=0.124, tcls=0.001)
  Val:   Loss=2.8755 | PPL=17.7 | Top1=34.0% Top5=63.9% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
         AR-LCS=0.411 AR-SetF1=0.546
         len(pred)=8.0 len(ref)=7.8 |lenErr|=2.7 earlyEOS=7.8% empty=0.0%
         rep=18.2% dup=1.1% badTrans=21.0%
  TF=0.053, AR=88%, LR=0.000005
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 42/50
----------------------------------------------------------------------
Epoch 42/50 [AR-SS(tf=0.05,ar=89%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:08:27<00:00,  1.06s/it, loss=7.3791, main=7.2757]

  Train: Loss=8.6694 (main=7.1494, len=0.125, tcls=0.001)
  Val:   Loss=2.8836 | PPL=17.9 | Top1=33.9% Top5=63.6% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.402 AR-SetF1=0.546
         len(pred)=8.3 len(ref)=7.8 |lenErr|=2.9 earlyEOS=7.0% empty=0.0%
         rep=20.5% dup=1.3% badTrans=19.9%
  TF=0.047, AR=89%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 43/50
----------------------------------------------------------------------
Epoch 43/50 [AR-SS(tf=0.04,ar=90%), n=61715]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:08:50<00:00,  1.07s/it, loss=14.3545, main=7.6055]

  Train: Loss=8.6709 (main=7.1827, len=0.123, tcls=0.001)
  Val:   Loss=2.8919 | PPL=18.0 | Top1=33.6% Top5=63.6% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
         AR-LCS=0.410 AR-SetF1=0.548
         len(pred)=8.0 len(ref)=7.8 |lenErr|=2.7 earlyEOS=7.8% empty=0.0%
         rep=20.1% dup=1.1% badTrans=20.8%
  TF=0.042, AR=90%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 44/50
----------------------------------------------------------------------
Epoch 44/50 [AR-SS(tf=0.04,ar=91%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:07:59<00:00,  1.06s/it, loss=7.1933, main=7.1085]

  Train: Loss=8.6813 (main=7.1949, len=0.126, tcls=0.001)
  Val:   Loss=2.9136 | PPL=18.4 | Top1=33.1% Top5=62.8% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
         AR-LCS=0.405 AR-SetF1=0.543
         len(pred)=8.0 len(ref)=7.8 |lenErr|=2.9 earlyEOS=7.8% empty=0.0%
         rep=19.1% dup=1.0% badTrans=22.8%
  TF=0.037, AR=91%, LR=0.000003
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 45/50
----------------------------------------------------------------------
Epoch 45/50 [AR-SS(tf=0.03,ar=92%), n=61715]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:07:18<00:00,  1.05s/it, loss=14.6207, main=6.7276]

  Train: Loss=8.7558 (main=7.1863, len=0.125, tcls=0.001)
  Val:   Loss=2.9183 | PPL=18.5 | Top1=32.6% Top5=62.8% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.407 AR-SetF1=0.543
         len(pred)=7.8 len(ref)=7.8 |lenErr|=2.7 earlyEOS=7.8% empty=0.0%
         rep=19.1% dup=1.0% badTrans=20.6%
  TF=0.033, AR=92%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 46/50
----------------------------------------------------------------------
Epoch 46/50 [AR-SS(tf=0.03,ar=94%), n=61715]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:09:45<00:00,  1.09s/it, loss=12.9210, main=6.1019]

  Train: Loss=8.6331 (main=7.1743, len=0.127, tcls=0.001)
  Val:   Loss=2.9173 | PPL=18.5 | Top1=32.8% Top5=62.8% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.409 AR-SetF1=0.543
         len(pred)=7.9 len(ref)=7.8 |lenErr|=2.7 earlyEOS=7.8% empty=0.0%
         rep=18.6% dup=1.0% badTrans=21.9%
  TF=0.030, AR=94%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 47/50
----------------------------------------------------------------------
Epoch 47/50 [AR-SS(tf=0.03,ar=95%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:12:15<00:00,  1.12s/it, loss=6.7179, main=6.5436]

  Train: Loss=8.6488 (main=7.2051, len=0.129, tcls=0.001)
  Val:   Loss=2.9297 | PPL=18.7 | Top1=32.5% Top5=62.7% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.0%
         AR-LCS=0.412 AR-SetF1=0.549
         len(pred)=8.0 len(ref)=7.8 |lenErr|=2.7 earlyEOS=7.0% empty=0.0%
         rep=20.6% dup=0.9% badTrans=24.6%
  TF=0.026, AR=95%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 48/50
----------------------------------------------------------------------
Epoch 48/50 [AR-SS(tf=0.02,ar=96%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:12:35<00:00,  1.13s/it, loss=5.9916, main=5.9177]

  Train: Loss=8.6986 (main=7.2003, len=0.129, tcls=0.001)
  Val:   Loss=2.9424 | PPL=19.0 | Top1=31.9% Top5=62.3% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.0%
         AR-LCS=0.412 AR-SetF1=0.550
         len(pred)=8.6 len(ref)=7.8 |lenErr|=3.0 earlyEOS=6.2% empty=0.0%
         rep=24.7% dup=1.0% badTrans=27.1%
  TF=0.023, AR=96%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 49/50
----------------------------------------------------------------------
Epoch 49/50 [AR-SS(tf=0.02,ar=98%), n=61715]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:13:51<00:00,  1.15s/it, loss=7.0085, main=6.7456]

  Train: Loss=8.7073 (main=7.2263, len=0.131, tcls=0.001)
  Val:   Loss=2.9483 | PPL=19.1 | Top1=31.5% Top5=62.0% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.406 AR-SetF1=0.547
         len(pred)=8.0 len(ref)=7.8 |lenErr|=2.7 earlyEOS=7.0% empty=0.0%
         rep=21.3% dup=1.0% badTrans=25.2%
  TF=0.021, AR=98%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 50/50
----------------------------------------------------------------------
Epoch 50/50 [AR-SS(tf=0.02,ar=99%), n=61715]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3857/3857 [1:04:10<00:00,  1.00it/s, loss=13.1718, main=6.8927]

  Train: Loss=8.7422 (main=7.2223, len=0.131, tcls=0.001)
  Val:   Loss=2.9552 | PPL=19.2 | Top1=31.5% Top5=61.7% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.1%
         AR-LCS=0.405 AR-SetF1=0.542
         len(pred)=7.9 len(ref)=7.8 |lenErr|=2.7 earlyEOS=6.2% empty=0.0%
         rep=20.1% dup=1.1% badTrans=25.0%
  TF=0.018, AR=99%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

================================================================================
Training complete! Loading latest checkpoint for test evaluation...

Test Results:
  Loss=3.0015 PPL=20.1
  Top1=30.0% Top5=60.1%
  TF-SeqEM=0.1% avglen(ref)=9.5
  AR-SeqEM=1.6% AR-TokenAcc=19.9%
  AR-LCS=0.424 AR-SetF1=0.548
  len(pred)=8.9 len(ref)=7.0 |lenErr|=3.2
  earlyEOS=7.8% empty=0.0%
  rep=34.6% dup=0.0% badTrans=41.0%

History saved: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/training_history_v4_6.json
Checkpoint selection manifest saved: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/checkpoint_selection_manifest_v4_6.json

V4.6 Quality-Gate training summary:
  trainer: V4.6
  mode: from_scratch
  mr_registry: {'status': 'disabled', 'path': None, 'ratio': 0.0, 'task_groups': 0, 'matched_train_samples': 0}
  mrv_training_dataset: {'status': 'enabled', 'version_name': 'mr_all_220', 'manifest_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mrv_training_ablation_manifest.json', 'report_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/mrv_training_ablation_report.json', 'data_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/labeled_workflows_l3_v4_quality_gate.json', 'splits_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/dataset_splits_v4_quality_gate.json', 'task_vocab_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/task_type_vocabulary_v4_quality_gate.json', 'injected_variants': 220, 'available_verified_mr_variants': 220, 'train_injection_rate_vs_base_train': 0.00357753, 'equivalence_family_counts': {'filter_filter': 30, 'select_filter': 8, 'select_clip': 3, 'boundary_review_candidate': 175, 'high_precision_review_candidate': 3, 'other': 1}, 'risk_level_counts': {'low': 31, 'medium': 10, 'reviewed': 178, 'unknown': 1}}
  length_bucket_training: {'status': 'enabled', 'path': '/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json', 'loss_weight': 0.1, 'target': 'task_type_bucket_expected_length', 'splits': {'train': {'samples': 61715, 'bucket_counts': {'medium': 38447, 'long': 22810, 'short': 458}}, 'val': {'samples': 7694, 'bucket_counts': {'long': 2846, 'medium': 4791, 'short': 57}}, 'test': {'samples': 7695, 'bucket_counts': {'medium': 4793, 'short': 57, 'long': 2845}}}, 'expected_length_by_bucket': {'short': 3, 'medium': 5, 'long': 8, 'very_long': 13}}
  training_contract: {'system_objective': 'increase usable/executable multi-solution GIS operator chains', 'known_limitations': ['token_ce_is_single_reference_supervision', 'ranking_is_post_training_not_a_training_objective', 'semantic_constraints_are_evaluated_outside_the_loss', 'inference_beam_constraints_are_not_fully_mirrored_in_ar_sampling'], 'required_post_training_validation': ['p0_evidence_aware_ranking_calibration', 'workflow_usability_evaluation', 'qgis_mapping_or_execution_diagnostics']}
  metric_contract: {'primary': ['set_f1', 'usable', 'executable', 'qgis_mapping'], 'supporting': ['lcs'], 'diagnostic_only': ['token_acc', 'sequence_em', 'loss', 'perplexity', 'top1', 'top5'], 'multi_solution_policy': 'TokenAcc and exact sequence match are diagnostic only for GIS workflow quality.'}
  checkpoint_policy: {'latest_snapshot': 'best_model.pth', 'latest_snapshot_note': 'historical compatibility name; overwritten each epoch', 'additional_selection_snapshots': ['best_gen_set_f1_model.pth', 'best_gen_lcs_model.pth'], 'selection_snapshot_note': 'post-training comparison aids; does not change training objective'}
  data_path: outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/labeled_workflows_l3_v4_quality_gate.json
  splits_path: outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/dataset_splits_v4_quality_gate.json
  task_vocab_path: outputs_v2/v4_qg_mr_ablation_from_multisolution/mr_all_220/task_type_vocabulary_v4_quality_gate.json
  warmstart_path: None
  checkpoint_dir: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate
  workflows_total: 77104
  train: 61715
  val: 7694
  test: 7695
  num_task_types: 47
  vocab_size: 98
  num_epochs: 50
  tf_phase_epochs: 10
  device: cuda
  dry_run: False
  history_epochs: 50