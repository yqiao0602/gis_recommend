(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_v4_6_quality_gate.py
Traceback (most recent call last):
  File "/home/qy/system_redesign/scripts/train_v4_6_quality_gate.py", line 634, in <module>
    main()
  File "/home/qy/system_redesign/scripts/train_v4_6_quality_gate.py", line 605, in main
    result = train_quality_gate_v4_6(
  File "/home/qy/system_redesign/scripts/train_v4_6_quality_gate.py", line 420, in train_quality_gate_v4_6
    train_dataset = TaskConditionedL3DatasetV4(
TypeError: TaskConditionedL3DatasetV4.__init__() got an unexpected keyword argument 'mr_registry'
(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_v4_6_quality_gate.py
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
Epoch 1/50 [TF, n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:35:10<00:00,  1.49s/it, loss=7.7519, main=7.5965]

  Train: Loss=9.7805 (main=8.9336, len=0.442, tcls=1.854)
  Val:   Loss=3.4260 | PPL=30.8 | Top1=15.5% Top5=45.4% TF-SeqEM=0.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.5%
         AR-LCS=0.206 AR-SetF1=0.279
         len(pred)=6.2 len(ref)=7.8 |lenErr|=4.9 earlyEOS=39.1% empty=0.0%
         rep=29.8% dup=0.0% badTrans=54.2%
  TF=1.000, AR=0%, LR=0.000050
  [Diag] BERT gradient check moved to _train_step_autoregressive (after backward)
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth
  [SNAPSHOT] Saved best Gen SetF1: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_gen_set_f1_model.pth
  [SNAPSHOT] Saved best Gen LCS: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_gen_lcs_model.pth

Epoch 2/50
----------------------------------------------------------------------
Epoch 2/50 [TF, n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [2:01:32<00:00,  1.90s/it, loss=6.3955, main=6.2641]

  Train: Loss=8.3214 (main=8.1715, len=0.157, tcls=0.038)
  Val:   Loss=3.3092 | PPL=27.4 | Top1=17.5% Top5=47.8% TF-SeqEM=0.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.5%
         AR-LCS=0.211 AR-SetF1=0.309
         len(pred)=27.1 len(ref)=7.8 |lenErr|=20.2 earlyEOS=3.9% empty=0.0%
         rep=74.0% dup=0.3% badTrans=55.5%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 3/50
----------------------------------------------------------------------
Epoch 3/50 [TF, n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [2:01:43<00:00,  1.90s/it, loss=7.6023, main=7.4769]

  Train: Loss=7.9229 (main=7.7900, len=0.135, tcls=0.018)
  Val:   Loss=3.1281 | PPL=22.8 | Top1=25.2% Top5=53.8% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.7%
         AR-LCS=0.337 AR-SetF1=0.445
         len(pred)=8.9 len(ref)=7.8 |lenErr|=5.1 earlyEOS=19.5% empty=0.0%
         rep=37.4% dup=0.0% badTrans=32.3%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 4/50
----------------------------------------------------------------------
Epoch 4/50 [TF, n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:27:29<00:00,  1.37s/it, loss=7.7122, main=7.5475]

  Train: Loss=7.6333 (main=7.5065, len=0.125, tcls=0.011)
  Val:   Loss=3.0150 | PPL=20.4 | Top1=29.5% Top5=57.6% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.1%
         AR-LCS=0.329 AR-SetF1=0.448
         len(pred)=7.6 len(ref)=7.8 |lenErr|=4.4 earlyEOS=23.4% empty=0.0%
         rep=23.6% dup=0.0% badTrans=27.8%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 5/50
----------------------------------------------------------------------
Epoch 5/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [13:43<00:00,  4.67it/s, loss=6.0300, main=5.9351]

  Train: Loss=7.3950 (main=7.2743, len=0.115, tcls=0.008)
  Val:   Loss=2.9200 | PPL=18.5 | Top1=32.5% Top5=60.5% TF-SeqEM=0.9% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.3%
         AR-LCS=0.363 AR-SetF1=0.494
         len(pred)=6.1 len(ref)=7.8 |lenErr|=3.4 earlyEOS=28.1% empty=0.0%
         rep=9.3% dup=0.2% badTrans=17.4%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 6/50
----------------------------------------------------------------------
Epoch 6/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [14:22<00:00,  4.45it/s, loss=6.9276, main=6.8371]

  Train: Loss=7.2174 (main=7.1001, len=0.109, tcls=0.006)
  Val:   Loss=2.8978 | PPL=18.1 | Top1=34.0% Top5=61.5% TF-SeqEM=0.8% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.3%
         AR-LCS=0.362 AR-SetF1=0.499
         len(pred)=6.2 len(ref)=7.8 |lenErr|=3.2 earlyEOS=26.6% empty=0.0%
         rep=9.5% dup=0.9% badTrans=15.4%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 7/50
----------------------------------------------------------------------
Epoch 7/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [13:33<00:00,  4.72it/s, loss=7.8468, main=7.7426]

  Train: Loss=7.0979 (main=6.9844, len=0.101, tcls=0.005)
  Val:   Loss=2.8569 | PPL=17.4 | Top1=34.9% Top5=62.8% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.8%
         AR-LCS=0.380 AR-SetF1=0.524
         len(pred)=6.4 len(ref)=7.8 |lenErr|=3.2 earlyEOS=20.3% empty=0.0%
         rep=7.2% dup=0.3% badTrans=11.4%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 8/50
----------------------------------------------------------------------
Epoch 8/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [13:53<00:00,  4.61it/s, loss=7.2588, main=7.1500]

  Train: Loss=6.9996 (main=6.8888, len=0.097, tcls=0.004)
  Val:   Loss=2.8381 | PPL=17.1 | Top1=35.7% Top5=63.5% TF-SeqEM=1.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=15.3%
         AR-LCS=0.398 AR-SetF1=0.526
         len(pred)=6.3 len(ref)=7.8 |lenErr|=3.1 earlyEOS=22.7% empty=0.0%
         rep=6.1% dup=0.3% badTrans=11.1%
  TF=1.000, AR=0%, LR=0.000048
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 9/50
----------------------------------------------------------------------
Epoch 9/50 [TF, n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [41:15<00:00,  1.55it/s, loss=5.1061, main=4.9705]

  Train: Loss=6.9297 (main=6.8207, len=0.093, tcls=0.003)
  Val:   Loss=2.8608 | PPL=17.5 | Top1=35.9% Top5=62.9% TF-SeqEM=1.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=15.2%
         AR-LCS=0.389 AR-SetF1=0.519
         len(pred)=7.1 len(ref)=7.8 |lenErr|=3.2 earlyEOS=15.6% empty=0.0%
         rep=14.6% dup=1.2% badTrans=17.4%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 10/50
----------------------------------------------------------------------
Epoch 10/50 [TF, n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [50:06<00:00,  1.28it/s, loss=7.2101, main=7.0847]

  Train: Loss=6.8465 (main=6.7393, len=0.090, tcls=0.003)
  Val:   Loss=2.8170 | PPL=16.7 | Top1=37.1% Top5=64.5% TF-SeqEM=0.9% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
         AR-LCS=0.398 AR-SetF1=0.527
         len(pred)=7.9 len(ref)=7.8 |lenErr|=3.4 earlyEOS=16.4% empty=0.0%
         rep=13.2% dup=1.0% badTrans=15.8%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 11/50
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61495]:   0%|                                                                                                                               | 1/3843 [00:00<44:29,  1.44it/s, loss=6.5290, main=6.4061]
  [Diag] BERT top-layer gradients (after backward): OK ✓
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=61495]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:20:26<00:00,  1.26s/it, loss=11.6221, main=6.8328]

  Train: Loss=10.0069 (main=7.2888, len=0.121, tcls=0.003)
  Val:   Loss=2.8149 | PPL=16.7 | Top1=35.1% Top5=64.6% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
         AR-LCS=0.392 AR-SetF1=0.539
         len(pred)=9.1 len(ref)=7.8 |lenErr|=4.4 earlyEOS=11.7% empty=0.0%
         rep=20.8% dup=0.1% badTrans=10.9%
  TF=0.417, AR=50%, LR=0.000046
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 12/50
----------------------------------------------------------------------
Epoch 12/50 [AR-SS(tf=0.41,ar=51%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [54:56<00:00,  1.17it/s, loss=6.9399, main=6.8288]

  Train: Loss=9.4382 (main=7.2236, len=0.120, tcls=0.004)
  Val:   Loss=2.8280 | PPL=16.9 | Top1=34.5% Top5=64.2% TF-SeqEM=0.7% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.9%
         AR-LCS=0.387 AR-SetF1=0.524
         len(pred)=8.7 len(ref)=7.8 |lenErr|=3.5 earlyEOS=10.2% empty=0.0%
         rep=21.0% dup=0.3% badTrans=15.4%
  TF=0.408, AR=51%, LR=0.000045
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 13/50
----------------------------------------------------------------------
Epoch 13/50 [AR-SS(tf=0.40,ar=52%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [43:38<00:00,  1.47it/s, loss=6.9568, main=6.8787]

  Train: Loss=9.3367 (main=7.2407, len=0.122, tcls=0.004)
  Val:   Loss=2.8164 | PPL=16.7 | Top1=35.0% Top5=64.8% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.7%
         AR-LCS=0.370 AR-SetF1=0.517
         len(pred)=11.5 len(ref)=7.8 |lenErr|=6.1 earlyEOS=7.8% empty=0.0%
         rep=34.8% dup=0.4% badTrans=20.5%
  TF=0.398, AR=52%, LR=0.000044
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 14/50
----------------------------------------------------------------------
Epoch 14/50 [AR-SS(tf=0.39,ar=54%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [42:38<00:00,  1.50it/s, loss=6.6469, main=6.5694]

  Train: Loss=9.1868 (main=7.1907, len=0.119, tcls=0.003)
  Val:   Loss=2.8242 | PPL=16.8 | Top1=35.5% Top5=64.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.2%
         AR-LCS=0.375 AR-SetF1=0.514
         len(pred)=9.6 len(ref)=7.8 |lenErr|=4.4 earlyEOS=10.2% empty=0.0%
         rep=29.4% dup=0.3% badTrans=21.0%
  TF=0.387, AR=54%, LR=0.000043
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 15/50
----------------------------------------------------------------------
Epoch 15/50 [AR-SS(tf=0.38,ar=55%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [45:42<00:00,  1.40it/s, loss=7.7729, main=7.6208]

  Train: Loss=9.1046 (main=7.1648, len=0.117, tcls=0.003)
  Val:   Loss=2.8231 | PPL=16.8 | Top1=35.6% Top5=64.1% TF-SeqEM=0.7% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=18.2%
         AR-LCS=0.407 AR-SetF1=0.540
         len(pred)=8.6 len(ref)=7.8 |lenErr|=3.2 earlyEOS=7.8% empty=0.0%
         rep=18.7% dup=0.8% badTrans=14.4%
  TF=0.376, AR=55%, LR=0.000042
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 16/50
----------------------------------------------------------------------
Epoch 16/50 [AR-SS(tf=0.36,ar=56%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [50:02<00:00,  1.28it/s, loss=6.0903, main=5.9986]

  Train: Loss=9.0856 (main=7.1843, len=0.120, tcls=0.003)
  Val:   Loss=2.8420 | PPL=17.1 | Top1=34.8% Top5=63.5% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
         AR-LCS=0.399 AR-SetF1=0.532
         len(pred)=7.2 len(ref)=7.8 |lenErr|=3.0 earlyEOS=11.7% empty=0.0%
         rep=11.9% dup=1.3% badTrans=11.6%
  TF=0.364, AR=56%, LR=0.000040
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 17/50
----------------------------------------------------------------------
Epoch 17/50 [AR-SS(tf=0.35,ar=57%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [48:42<00:00,  1.32it/s, loss=13.5759, main=8.1580]

  Train: Loss=9.1825 (main=7.2025, len=0.117, tcls=0.003)
  Val:   Loss=2.8406 | PPL=17.1 | Top1=35.3% Top5=63.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.2%
         AR-LCS=0.394 AR-SetF1=0.537
         len(pred)=8.0 len(ref)=7.8 |lenErr|=3.4 earlyEOS=10.9% empty=0.0%
         rep=15.2% dup=0.4% badTrans=13.3%
  TF=0.351, AR=57%, LR=0.000039
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 18/50
----------------------------------------------------------------------
Epoch 18/50 [AR-SS(tf=0.34,ar=59%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [46:42<00:00,  1.37it/s, loss=7.4407, main=7.1905]

  Train: Loss=8.9956 (main=7.1649, len=0.119, tcls=0.003)
  Val:   Loss=2.8201 | PPL=16.8 | Top1=36.1% Top5=64.7% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
         AR-LCS=0.390 AR-SetF1=0.525
         len(pred)=7.8 len(ref)=7.8 |lenErr|=3.3 earlyEOS=13.3% empty=0.0%
         rep=15.2% dup=1.0% badTrans=14.7%
  TF=0.338, AR=59%, LR=0.000038
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 19/50
----------------------------------------------------------------------
Epoch 19/50 [AR-SS(tf=0.32,ar=60%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [47:24<00:00,  1.35it/s, loss=16.3001, main=8.6023]

  Train: Loss=9.0044 (main=7.1687, len=0.118, tcls=0.003)
  Val:   Loss=2.8421 | PPL=17.2 | Top1=36.0% Top5=63.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=18.2%
         AR-LCS=0.402 AR-SetF1=0.534
         len(pred)=8.4 len(ref)=7.8 |lenErr|=3.5 earlyEOS=11.7% empty=0.0%
         rep=16.7% dup=0.7% badTrans=19.3%
  TF=0.324, AR=60%, LR=0.000036
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 20/50
----------------------------------------------------------------------
Epoch 20/50 [AR-SS(tf=0.31,ar=61%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [48:19<00:00,  1.33it/s, loss=13.1485, main=7.1419]

  Train: Loss=9.0134 (main=7.1623, len=0.120, tcls=0.002)
  Val:   Loss=2.8364 | PPL=17.1 | Top1=35.5% Top5=64.3% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.2%
         AR-LCS=0.384 AR-SetF1=0.516
         len(pred)=8.9 len(ref)=7.8 |lenErr|=3.4 earlyEOS=9.4% empty=0.0%
         rep=22.6% dup=0.6% badTrans=20.4%
  TF=0.309, AR=61%, LR=0.000035
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 21/50
----------------------------------------------------------------------
Epoch 21/50 [AR-SS(tf=0.29,ar=62%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [48:43<00:00,  1.31it/s, loss=6.8550, main=6.6515]

  Train: Loss=9.0104 (main=7.1672, len=0.118, tcls=0.002)
  Val:   Loss=2.8046 | PPL=16.5 | Top1=36.1% Top5=65.4% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
         AR-LCS=0.398 AR-SetF1=0.536
         len(pred)=7.5 len(ref)=7.8 |lenErr|=3.0 earlyEOS=12.5% empty=0.0%
         rep=15.0% dup=0.6% badTrans=14.0%
  TF=0.294, AR=62%, LR=0.000033
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 22/50
----------------------------------------------------------------------
Epoch 22/50 [AR-SS(tf=0.28,ar=64%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [49:34<00:00,  1.29it/s, loss=13.1528, main=7.1020]

  Train: Loss=8.9888 (main=7.1532, len=0.120, tcls=0.002)
  Val:   Loss=2.8126 | PPL=16.7 | Top1=35.7% Top5=65.5% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.409 AR-SetF1=0.540
         len(pred)=7.1 len(ref)=7.8 |lenErr|=3.0 earlyEOS=15.6% empty=0.0%
         rep=10.4% dup=0.6% badTrans=11.2%
  TF=0.279, AR=64%, LR=0.000032
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 23/50
----------------------------------------------------------------------
Epoch 23/50 [AR-SS(tf=0.26,ar=65%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [52:37<00:00,  1.22it/s, loss=6.6430, main=6.5259]

  Train: Loss=8.9089 (main=7.1544, len=0.118, tcls=0.002)
  Val:   Loss=2.8333 | PPL=17.0 | Top1=35.5% Top5=64.2% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=18.0%
         AR-LCS=0.409 AR-SetF1=0.540
         len(pred)=7.9 len(ref)=7.8 |lenErr|=2.9 earlyEOS=10.2% empty=0.0%
         rep=18.5% dup=0.3% badTrans=16.7%
  TF=0.264, AR=65%, LR=0.000030
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 24/50
----------------------------------------------------------------------
Epoch 24/50 [AR-SS(tf=0.25,ar=66%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [53:09<00:00,  1.20it/s, loss=6.7695, main=6.6692]

  Train: Loss=8.8492 (main=7.1517, len=0.119, tcls=0.002)
  Val:   Loss=2.8282 | PPL=16.9 | Top1=35.8% Top5=64.5% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
         AR-LCS=0.406 AR-SetF1=0.546
         len(pred)=7.3 len(ref)=7.8 |lenErr|=2.8 earlyEOS=14.1% empty=0.0%
         rep=15.0% dup=0.6% badTrans=13.4%
  TF=0.248, AR=66%, LR=0.000029
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 25/50
----------------------------------------------------------------------
Epoch 25/50 [AR-SS(tf=0.23,ar=68%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [55:41<00:00,  1.15it/s, loss=15.2291, main=7.8596]

  Train: Loss=8.8984 (main=7.1565, len=0.120, tcls=0.002)
  Val:   Loss=2.8160 | PPL=16.7 | Top1=36.2% Top5=65.4% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.7%
         AR-LCS=0.396 AR-SetF1=0.537
         len(pred)=8.6 len(ref)=7.8 |lenErr|=3.2 earlyEOS=8.6% empty=0.0%
         rep=21.1% dup=0.6% badTrans=18.2%
  TF=0.232, AR=68%, LR=0.000027
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 26/50
----------------------------------------------------------------------
Epoch 26/50 [AR-SS(tf=0.22,ar=69%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [56:08<00:00,  1.14it/s, loss=7.3560, main=7.2287]

  Train: Loss=8.8645 (main=7.1422, len=0.119, tcls=0.002)
  Val:   Loss=2.8525 | PPL=17.3 | Top1=34.9% Top5=63.4% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.1%
         AR-LCS=0.390 AR-SetF1=0.524
         len(pred)=8.6 len(ref)=7.8 |lenErr|=3.5 earlyEOS=7.0% empty=0.0%
         rep=22.3% dup=0.5% badTrans=22.6%
  TF=0.217, AR=69%, LR=0.000026
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 27/50
----------------------------------------------------------------------
Epoch 27/50 [AR-SS(tf=0.20,ar=70%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [55:44<00:00,  1.15it/s, loss=7.0410, main=6.9430]

  Train: Loss=8.8602 (main=7.1277, len=0.117, tcls=0.002)
  Val:   Loss=2.8450 | PPL=17.2 | Top1=35.5% Top5=63.7% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.2%
         AR-LCS=0.407 AR-SetF1=0.542
         len(pred)=8.0 len(ref)=7.8 |lenErr|=2.9 earlyEOS=10.2% empty=0.0%
         rep=16.4% dup=0.4% badTrans=18.3%
  TF=0.202, AR=70%, LR=0.000024
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 28/50
----------------------------------------------------------------------
Epoch 28/50 [AR-SS(tf=0.19,ar=71%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [57:06<00:00,  1.12it/s, loss=5.9975, main=5.8529]

  Train: Loss=8.7845 (main=7.1324, len=0.120, tcls=0.002)
  Val:   Loss=2.8431 | PPL=17.2 | Top1=35.3% Top5=63.8% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.0%
         AR-LCS=0.390 AR-SetF1=0.528
         len(pred)=8.1 len(ref)=7.8 |lenErr|=3.0 earlyEOS=14.8% empty=0.0%
         rep=18.3% dup=0.8% badTrans=20.2%
  TF=0.187, AR=71%, LR=0.000022
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 29/50
----------------------------------------------------------------------
Epoch 29/50 [AR-SS(tf=0.17,ar=72%), n=61495]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [58:55<00:00,  1.09it/s, loss=11.3506, main=6.9256]

  Train: Loss=8.8919 (main=7.1577, len=0.120, tcls=0.002)
  Val:   Loss=2.8328 | PPL=17.0 | Top1=35.8% Top5=64.5% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.409 AR-SetF1=0.546
         len(pred)=8.0 len(ref)=7.8 |lenErr|=3.0 earlyEOS=10.9% empty=0.0%
         rep=17.6% dup=0.6% badTrans=19.9%
  TF=0.173, AR=72%, LR=0.000021
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 30/50
----------------------------------------------------------------------
Epoch 30/50 [AR-SS(tf=0.16,ar=74%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [59:34<00:00,  1.08it/s, loss=7.4229, main=7.1578]

  Train: Loss=8.7568 (main=7.1345, len=0.118, tcls=0.002)
  Val:   Loss=2.8564 | PPL=17.4 | Top1=35.4% Top5=64.0% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.4%
         AR-LCS=0.398 AR-SetF1=0.542
         len(pred)=8.3 len(ref)=7.8 |lenErr|=2.9 earlyEOS=10.2% empty=0.0%
         rep=19.5% dup=0.6% badTrans=20.2%
  TF=0.159, AR=74%, LR=0.000019
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 31/50
----------------------------------------------------------------------
Epoch 31/50 [AR-SS(tf=0.15,ar=75%), n=61495]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:01:23<00:00,  1.04it/s, loss=13.5490, main=7.5897]

  Train: Loss=8.7823 (main=7.1316, len=0.122, tcls=0.002)
  Val:   Loss=2.8632 | PPL=17.5 | Top1=34.0% Top5=63.9% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
         AR-LCS=0.380 AR-SetF1=0.517
         len(pred)=8.6 len(ref)=7.8 |lenErr|=3.5 earlyEOS=5.5% empty=0.0%
         rep=23.1% dup=0.4% badTrans=21.9%
  TF=0.145, AR=75%, LR=0.000018
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 32/50
----------------------------------------------------------------------
Epoch 32/50 [AR-SS(tf=0.13,ar=76%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [59:35<00:00,  1.07it/s, loss=7.3255, main=7.1141]

  Train: Loss=8.7415 (main=7.1364, len=0.121, tcls=0.001)
  Val:   Loss=2.8714 | PPL=17.7 | Top1=34.8% Top5=63.2% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.1%
         AR-LCS=0.385 AR-SetF1=0.528
         len(pred)=9.5 len(ref)=7.8 |lenErr|=3.9 earlyEOS=8.6% empty=0.0%
         rep=28.0% dup=0.6% badTrans=24.9%
  TF=0.133, AR=76%, LR=0.000016
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 33/50
----------------------------------------------------------------------
Epoch 33/50 [AR-SS(tf=0.12,ar=78%), n=61495]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [59:12<00:00,  1.08it/s, loss=8.2826, main=8.1004]

  Train: Loss=8.6999 (main=7.1460, len=0.120, tcls=0.001)
  Val:   Loss=2.8578 | PPL=17.4 | Top1=35.2% Top5=63.6% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.2%
         AR-LCS=0.396 AR-SetF1=0.541
         len(pred)=8.4 len(ref)=7.8 |lenErr|=3.4 earlyEOS=10.9% empty=0.0%
         rep=19.5% dup=0.6% badTrans=18.8%
  TF=0.121, AR=78%, LR=0.000015
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 34/50
----------------------------------------------------------------------
Epoch 34/50 [AR-SS(tf=0.11,ar=79%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:00:22<00:00,  1.06it/s, loss=7.4197, main=7.2160]

  Train: Loss=8.7057 (main=7.1446, len=0.121, tcls=0.001)
  Val:   Loss=2.8542 | PPL=17.4 | Top1=34.9% Top5=64.1% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
         AR-LCS=0.403 AR-SetF1=0.546
         len(pred)=8.4 len(ref)=7.8 |lenErr|=2.8 earlyEOS=9.4% empty=0.0%
         rep=20.4% dup=0.7% badTrans=21.2%
  TF=0.110, AR=79%, LR=0.000013
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 35/50
----------------------------------------------------------------------
Epoch 35/50 [AR-SS(tf=0.10,ar=80%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:00:41<00:00,  1.06it/s, loss=7.2050, main=6.9863]

  Train: Loss=8.6885 (main=7.1388, len=0.121, tcls=0.001)
  Val:   Loss=2.8567 | PPL=17.4 | Top1=35.5% Top5=64.0% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
         AR-LCS=0.398 AR-SetF1=0.541
         len(pred)=7.9 len(ref)=7.8 |lenErr|=3.2 earlyEOS=13.3% empty=0.0%
         rep=17.5% dup=0.5% badTrans=22.2%
  TF=0.100, AR=80%, LR=0.000012
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 36/50
----------------------------------------------------------------------
Epoch 36/50 [AR-SS(tf=0.09,ar=81%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:01:58<00:00,  1.03it/s, loss=8.6049, main=8.3918]

  Train: Loss=8.7033 (main=7.1550, len=0.121, tcls=0.001)
  Val:   Loss=2.8579 | PPL=17.4 | Top1=34.9% Top5=64.1% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.8%
         AR-LCS=0.398 AR-SetF1=0.538
         len(pred)=8.3 len(ref)=7.8 |lenErr|=3.2 earlyEOS=11.7% empty=0.0%
         rep=21.9% dup=0.8% badTrans=22.8%
  TF=0.090, AR=81%, LR=0.000011
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 37/50
----------------------------------------------------------------------
Epoch 37/50 [AR-SS(tf=0.08,ar=82%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:02:15<00:00,  1.03it/s, loss=6.1966, main=6.0282]

  Train: Loss=8.6549 (main=7.1527, len=0.122, tcls=0.001)
  Val:   Loss=2.8771 | PPL=17.8 | Top1=34.4% Top5=64.0% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=18.2%
         AR-LCS=0.411 AR-SetF1=0.550
         len(pred)=8.5 len(ref)=7.8 |lenErr|=3.1 earlyEOS=7.0% empty=0.0%
         rep=23.5% dup=0.5% badTrans=21.9%
  TF=0.081, AR=82%, LR=0.000009
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 38/50
----------------------------------------------------------------------
Epoch 38/50 [AR-SS(tf=0.07,ar=84%), n=61495]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:02:05<00:00,  1.03it/s, loss=17.6003, main=7.1472]

  Train: Loss=8.7093 (main=7.1433, len=0.120, tcls=0.001)
  Val:   Loss=2.8742 | PPL=17.7 | Top1=34.5% Top5=63.6% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
         AR-LCS=0.401 AR-SetF1=0.539
         len(pred)=7.8 len(ref)=7.8 |lenErr|=3.1 earlyEOS=13.3% empty=0.0%
         rep=17.7% dup=0.8% badTrans=23.8%
  TF=0.073, AR=84%, LR=0.000008
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 39/50
----------------------------------------------------------------------
Epoch 39/50 [AR-SS(tf=0.07,ar=85%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:03:36<00:00,  1.01it/s, loss=7.7183, main=7.4605]

  Train: Loss=8.6884 (main=7.1400, len=0.124, tcls=0.001)
  Val:   Loss=2.8795 | PPL=17.8 | Top1=34.5% Top5=63.6% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
         AR-LCS=0.391 AR-SetF1=0.522
         len(pred)=7.5 len(ref)=7.8 |lenErr|=3.0 earlyEOS=13.3% empty=0.0%
         rep=16.7% dup=1.0% badTrans=22.7%
  TF=0.066, AR=85%, LR=0.000007
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 40/50
----------------------------------------------------------------------
Epoch 40/50 [AR-SS(tf=0.06,ar=86%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:04:17<00:00,  1.00s/it, loss=7.0201, main=6.8449]

  Train: Loss=8.7087 (main=7.1522, len=0.123, tcls=0.001)
  Val:   Loss=2.8718 | PPL=17.7 | Top1=34.4% Top5=63.8% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
         AR-LCS=0.392 AR-SetF1=0.531
         len(pred)=7.7 len(ref)=7.8 |lenErr|=3.1 earlyEOS=14.1% empty=0.0%
         rep=15.7% dup=0.8% badTrans=19.8%
  TF=0.059, AR=86%, LR=0.000006
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 41/50
----------------------------------------------------------------------
Epoch 41/50 [AR-SS(tf=0.05,ar=88%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:05:12<00:00,  1.02s/it, loss=6.5697, main=6.4923]

  Train: Loss=8.5843 (main=7.1510, len=0.124, tcls=0.001)
  Val:   Loss=2.8923 | PPL=18.0 | Top1=34.0% Top5=63.1% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.1%
         AR-LCS=0.394 AR-SetF1=0.525
         len(pred)=8.2 len(ref)=7.8 |lenErr|=2.9 earlyEOS=9.4% empty=0.0%
         rep=20.9% dup=0.9% badTrans=24.2%
  TF=0.053, AR=88%, LR=0.000005
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 42/50
----------------------------------------------------------------------
Epoch 42/50 [AR-SS(tf=0.05,ar=89%), n=61495]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:05:47<00:00,  1.03s/it, loss=13.5314, main=7.8647]

  Train: Loss=8.6338 (main=7.1830, len=0.124, tcls=0.001)
  Val:   Loss=2.8920 | PPL=18.0 | Top1=33.9% Top5=63.3% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.401 AR-SetF1=0.531
         len(pred)=8.1 len(ref)=7.8 |lenErr|=2.9 earlyEOS=8.6% empty=0.0%
         rep=21.1% dup=0.7% badTrans=23.8%
  TF=0.047, AR=89%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 43/50
----------------------------------------------------------------------
Epoch 43/50 [AR-SS(tf=0.04,ar=90%), n=61495]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:06:43<00:00,  1.04s/it, loss=10.8751, main=6.8940]

  Train: Loss=8.6066 (main=7.1658, len=0.126, tcls=0.001)
  Val:   Loss=2.8998 | PPL=18.2 | Top1=33.7% Top5=63.1% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.1%
         AR-LCS=0.399 AR-SetF1=0.528
         len(pred)=8.2 len(ref)=7.8 |lenErr|=2.9 earlyEOS=9.4% empty=0.0%
         rep=21.4% dup=0.7% badTrans=24.9%
  TF=0.042, AR=90%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 44/50
----------------------------------------------------------------------
Epoch 44/50 [AR-SS(tf=0.04,ar=91%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:07:27<00:00,  1.05s/it, loss=7.3867, main=7.0968]

  Train: Loss=8.6653 (main=7.1827, len=0.127, tcls=0.001)
  Val:   Loss=2.9084 | PPL=18.3 | Top1=33.2% Top5=62.8% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
         AR-LCS=0.400 AR-SetF1=0.528
         len(pred)=9.0 len(ref)=7.8 |lenErr|=3.3 earlyEOS=8.6% empty=0.0%
         rep=28.3% dup=0.4% badTrans=25.5%
  TF=0.037, AR=91%, LR=0.000003
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 45/50
----------------------------------------------------------------------
Epoch 45/50 [AR-SS(tf=0.03,ar=92%), n=61495]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:06:29<00:00,  1.04s/it, loss=12.0400, main=7.4154]

  Train: Loss=8.7042 (main=7.1916, len=0.125, tcls=0.001)
  Val:   Loss=2.9113 | PPL=18.4 | Top1=33.1% Top5=63.0% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
         AR-LCS=0.408 AR-SetF1=0.540
         len(pred)=8.1 len(ref)=7.8 |lenErr|=2.9 earlyEOS=11.7% empty=0.0%
         rep=22.3% dup=0.7% badTrans=24.7%
  TF=0.033, AR=92%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 46/50
----------------------------------------------------------------------
Epoch 46/50 [AR-SS(tf=0.03,ar=94%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:05:18<00:00,  1.02s/it, loss=7.3360, main=7.2032]

  Train: Loss=8.6322 (main=7.1809, len=0.126, tcls=0.001)
  Val:   Loss=2.9195 | PPL=18.5 | Top1=32.9% Top5=62.7% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.0%
         AR-LCS=0.408 AR-SetF1=0.536
         len(pred)=8.3 len(ref)=7.8 |lenErr|=2.9 earlyEOS=10.2% empty=0.0%
         rep=22.7% dup=0.4% badTrans=25.8%
  TF=0.030, AR=94%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 47/50
----------------------------------------------------------------------
Epoch 47/50 [AR-SS(tf=0.03,ar=95%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:08:07<00:00,  1.06s/it, loss=8.2491, main=8.1070]

  Train: Loss=8.6368 (main=7.1714, len=0.127, tcls=0.001)
  Val:   Loss=2.9175 | PPL=18.5 | Top1=32.8% Top5=62.8% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.9%
         AR-LCS=0.407 AR-SetF1=0.535
         len(pred)=7.8 len(ref)=7.8 |lenErr|=2.8 earlyEOS=12.5% empty=0.0%
         rep=19.6% dup=0.6% badTrans=24.6%
  TF=0.026, AR=95%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 48/50
----------------------------------------------------------------------
Epoch 48/50 [AR-SS(tf=0.02,ar=96%), n=61495]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:09:37<00:00,  1.09s/it, loss=14.0464, main=7.4047]

  Train: Loss=8.6980 (main=7.2012, len=0.128, tcls=0.001)
  Val:   Loss=2.9334 | PPL=18.8 | Top1=32.3% Top5=62.4% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.1%
         AR-LCS=0.400 AR-SetF1=0.527
         len(pred)=8.3 len(ref)=7.8 |lenErr|=3.0 earlyEOS=10.2% empty=0.0%
         rep=23.6% dup=0.5% badTrans=27.8%
  TF=0.023, AR=96%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 49/50
----------------------------------------------------------------------
Epoch 49/50 [AR-SS(tf=0.02,ar=98%), n=61495]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:11:02<00:00,  1.11s/it, loss=13.5808, main=7.9158]

  Train: Loss=8.7481 (main=7.2025, len=0.130, tcls=0.001)
  Val:   Loss=2.9466 | PPL=19.0 | Top1=31.9% Top5=62.1% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.4%
         AR-LCS=0.398 AR-SetF1=0.531
         len(pred)=8.6 len(ref)=7.8 |lenErr|=3.0 earlyEOS=7.0% empty=0.0%
         rep=25.8% dup=0.6% badTrans=28.2%
  TF=0.021, AR=98%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 50/50
----------------------------------------------------------------------
Epoch 50/50 [AR-SS(tf=0.02,ar=99%), n=61495]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3843/3843 [1:11:57<00:00,  1.12s/it, loss=7.5426, main=7.3545]

  Train: Loss=8.6322 (main=7.1980, len=0.129, tcls=0.001)
  Val:   Loss=2.9595 | PPL=19.3 | Top1=31.5% Top5=61.5% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.399 AR-SetF1=0.531
         len(pred)=8.5 len(ref)=7.8 |lenErr|=2.9 earlyEOS=6.2% empty=0.0%
         rep=25.9% dup=0.7% badTrans=29.4%
  TF=0.018, AR=99%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

================================================================================
Training complete! Loading latest checkpoint for test evaluation...

Test Results:
  Loss=3.0088 PPL=20.3
  Top1=30.0% Top5=59.8%
  TF-SeqEM=0.0% avglen(ref)=9.5
  AR-SeqEM=1.6% AR-TokenAcc=21.9%
  AR-LCS=0.433 AR-SetF1=0.565
  len(pred)=9.4 len(ref)=7.0 |lenErr|=4.0
  earlyEOS=4.7% empty=0.0%
  rep=36.4% dup=0.0% badTrans=30.9%

History saved: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/training_history_v4_6.json
Checkpoint selection manifest saved: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/checkpoint_selection_manifest_v4_6.json

V4.6 Quality-Gate training summary:
  trainer: V4.6
  mode: from_scratch
  mr_registry: {'status': 'disabled', 'path': None, 'ratio': 0.0, 'task_groups': 0, 'matched_train_samples': 0}
  mrv_training_dataset: {'status': 'disabled', 'version_name': None, 'injected_variants': 0}
  length_bucket_training: {'status': 'enabled', 'path': '/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json', 'loss_weight': 0.1, 'target': 'task_type_bucket_expected_length', 'splits': {'train': {'samples': 61495, 'bucket_counts': {'medium': 38264, 'long': 22783, 'short': 448}}, 'val': {'samples': 7694, 'bucket_counts': {'long': 2846, 'medium': 4791, 'short': 57}}, 'test': {'samples': 7695, 'bucket_counts': {'medium': 4793, 'short': 57, 'long': 2845}}}, 'expected_length_by_bucket': {'short': 3, 'medium': 5, 'long': 8, 'very_long': 13}}
  training_contract: {'system_objective': 'increase usable/executable multi-solution GIS operator chains', 'known_limitations': ['token_ce_is_single_reference_supervision', 'ranking_is_post_training_not_a_training_objective', 'semantic_constraints_are_evaluated_outside_the_loss', 'inference_beam_constraints_are_not_fully_mirrored_in_ar_sampling'], 'required_post_training_validation': ['p0_evidence_aware_ranking_calibration', 'workflow_usability_evaluation', 'qgis_mapping_or_execution_diagnostics']}
  metric_contract: {'primary': ['set_f1', 'usable', 'executable', 'qgis_mapping'], 'supporting': ['lcs'], 'diagnostic_only': ['token_acc', 'sequence_em', 'loss', 'perplexity', 'top1', 'top5'], 'multi_solution_policy': 'TokenAcc and exact sequence match are diagnostic only for GIS workflow quality.'}
  checkpoint_policy: {'latest_snapshot': 'best_model.pth', 'latest_snapshot_note': 'historical compatibility name; overwritten each epoch', 'additional_selection_snapshots': ['best_gen_set_f1_model.pth', 'best_gen_lcs_model.pth'], 'selection_snapshot_note': 'post-training comparison aids; does not change training objective'}
  data_path: /home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json
  splits_path: /home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json
  task_vocab_path: /home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/task_type_vocabulary_v4_quality_gate.json
  warmstart_path: None
  checkpoint_dir: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate
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