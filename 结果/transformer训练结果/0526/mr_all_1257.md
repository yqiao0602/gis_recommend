(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_v4_6_quality_gate.py --mrv-ablation-dir outputs_v2/   v4_qg_mr_ablation_from_multisolution_unified --mrv-ablation-version mr_all_1257
usage: train_v4_6_quality_gate.py [-h] [--data DATA] [--splits SPLITS] [--task-vocab TASK_VOCAB] [--l3-embeddings L3_EMBEDDINGS] [--checkpoint-dir CHECKPOINT_DIR] [--warmstart WARMSTART] [--num-epochs NUM_EPOCHS]
                                  [--num-workers NUM_WORKERS] [--generation-eval-batches GENERATION_EVAL_BATCHES] [--bert-model BERT_MODEL] [--allow-bert-download] [--freeze-bert] [--dry-run] [--mr-registry MR_REGISTRY]
                                  [--mr-ratio MR_RATIO] [--length-stats LENGTH_STATS] [--length-bucket-loss-weight LENGTH_BUCKET_LOSS_WEIGHT] [--mrv-ablation-dir MRV_ABLATION_DIR] [--mrv-ablation-version MRV_ABLATION_VERSION]
train_v4_6_quality_gate.py: error: unrecognized arguments: v4_qg_mr_ablation_from_multisolution_unified
(transformer) qy@mdzhang:~/system_redesign$ python scripts/train_v4_6_quality_gate.py --mrv-ablation-dir outputs_v2/v4_qg_mr_ablation_from_multisolution_unified --mrv-ablation-version mr_all_1257
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
Epoch 1/50 [TF, n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [47:44<00:00,  1.37it/s, loss=8.8526, main=8.6595]

  Train: Loss=9.6660 (main=8.8656, len=0.423, tcls=1.733)
  Val:   Loss=3.5732 | PPL=35.6 | Top1=10.5% Top5=39.3% TF-SeqEM=0.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.2%
         AR-LCS=0.111 AR-SetF1=0.149
         len(pred)=52.4 len(ref)=7.8 |lenErr|=45.5 earlyEOS=6.2% empty=0.0%
         rep=88.2% dup=0.0% badTrans=67.9%
  TF=1.000, AR=0%, LR=0.000050
  [Diag] BERT gradient check moved to _train_step_autoregressive (after backward)
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth
  [SNAPSHOT] Saved best Gen SetF1: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_gen_set_f1_model.pth
  [SNAPSHOT] Saved best Gen LCS: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_gen_lcs_model.pth

Epoch 2/50
----------------------------------------------------------------------
Epoch 2/50 [TF, n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [52:07<00:00,  1.25it/s, loss=8.7434, main=8.6135]

  Train: Loss=8.2442 (main=8.0979, len=0.153, tcls=0.033)
  Val:   Loss=3.2765 | PPL=26.5 | Top1=20.2% Top5=48.9% TF-SeqEM=0.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.5%
         AR-LCS=0.260 AR-SetF1=0.359
         len(pred)=16.9 len(ref)=7.8 |lenErr|=12.2 earlyEOS=18.8% empty=0.0%
         rep=67.5% dup=0.0% badTrans=57.0%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 3/50
----------------------------------------------------------------------
Epoch 3/50 [TF, n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [59:32<00:00,  1.10it/s, loss=8.5069, main=8.3898]

  Train: Loss=7.8976 (main=7.7661, len=0.133, tcls=0.016)
  Val:   Loss=3.1251 | PPL=22.8 | Top1=25.5% Top5=55.1% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.5%
         AR-LCS=0.282 AR-SetF1=0.397
         len(pred)=18.8 len(ref)=7.8 |lenErr|=13.6 earlyEOS=15.6% empty=0.0%
         rep=67.0% dup=0.0% badTrans=52.8%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 4/50
----------------------------------------------------------------------
Epoch 4/50 [TF, n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [37:44<00:00,  1.73it/s, loss=6.9175, main=6.7929]

  Train: Loss=7.5825 (main=7.4568, len=0.123, tcls=0.011)
  Val:   Loss=3.0018 | PPL=20.1 | Top1=30.7% Top5=58.7% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.2%
         AR-LCS=0.350 AR-SetF1=0.484
         len(pred)=6.6 len(ref)=7.8 |lenErr|=3.1 earlyEOS=22.7% empty=0.0%
         rep=11.2% dup=0.0% badTrans=21.9%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 5/50
----------------------------------------------------------------------
Epoch 5/50 [TF, n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [19:44<00:00,  3.31it/s, loss=7.7277, main=7.5589]

  Train: Loss=7.3538 (main=7.2322, len=0.117, tcls=0.008)
  Val:   Loss=2.9172 | PPL=18.5 | Top1=33.2% Top5=61.4% TF-SeqEM=0.8% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.6%
         AR-LCS=0.368 AR-SetF1=0.509
         len(pred)=6.1 len(ref)=7.8 |lenErr|=2.9 earlyEOS=22.7% empty=0.0%
         rep=5.1% dup=0.2% badTrans=12.4%
  TF=1.000, AR=0%, LR=0.000050
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 6/50
----------------------------------------------------------------------
Epoch 6/50 [TF, n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [19:22<00:00,  3.38it/s, loss=7.5572, main=7.4516]

  Train: Loss=7.2097 (main=7.0921, len=0.110, tcls=0.006)
  Val:   Loss=2.9005 | PPL=18.2 | Top1=33.7% Top5=61.6% TF-SeqEM=0.9% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.4%
         AR-LCS=0.367 AR-SetF1=0.509
         len(pred)=7.4 len(ref)=7.8 |lenErr|=3.4 earlyEOS=17.2% empty=0.0%
         rep=15.8% dup=0.2% badTrans=18.0%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 7/50
----------------------------------------------------------------------
Epoch 7/50 [TF, n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [19:52<00:00,  3.29it/s, loss=5.3028, main=5.2318]

  Train: Loss=7.0812 (main=6.9674, len=0.103, tcls=0.004)
  Val:   Loss=2.8952 | PPL=18.1 | Top1=34.4% Top5=61.7% TF-SeqEM=1.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.8%
         AR-LCS=0.379 AR-SetF1=0.516
         len(pred)=6.7 len(ref)=7.8 |lenErr|=3.0 earlyEOS=19.5% empty=0.0%
         rep=7.5% dup=0.5% badTrans=12.2%
  TF=1.000, AR=0%, LR=0.000049
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 8/50
----------------------------------------------------------------------
Epoch 8/50 [TF, n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [19:46<00:00,  3.31it/s, loss=5.5792, main=5.4884]

  Train: Loss=6.9915 (main=6.8800, len=0.098, tcls=0.004)
  Val:   Loss=2.8520 | PPL=17.3 | Top1=35.0% Top5=63.1% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.0%
         AR-LCS=0.386 AR-SetF1=0.518
         len(pred)=7.2 len(ref)=7.8 |lenErr|=2.5 earlyEOS=7.8% empty=0.0%
         rep=10.9% dup=1.0% badTrans=15.4%
  TF=1.000, AR=0%, LR=0.000048
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 9/50
----------------------------------------------------------------------
Epoch 9/50 [TF, n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [19:52<00:00,  3.29it/s, loss=5.7141, main=5.6301]

  Train: Loss=6.9266 (main=6.8161, len=0.096, tcls=0.003)
  Val:   Loss=2.8382 | PPL=17.1 | Top1=36.7% Top5=63.9% TF-SeqEM=1.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
         AR-LCS=0.402 AR-SetF1=0.531
         len(pred)=7.0 len(ref)=7.8 |lenErr|=2.8 earlyEOS=12.5% empty=0.0%
         rep=8.4% dup=0.5% badTrans=14.9%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 10/50
----------------------------------------------------------------------
Epoch 10/50 [TF, n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [19:39<00:00,  3.33it/s, loss=7.8702, main=7.7974]

  Train: Loss=6.8511 (main=6.7420, len=0.094, tcls=0.002)
  Val:   Loss=2.8001 | PPL=16.4 | Top1=37.2% Top5=64.9% TF-SeqEM=1.0% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.9%
         AR-LCS=0.400 AR-SetF1=0.527
         len(pred)=6.4 len(ref)=7.8 |lenErr|=2.8 earlyEOS=21.9% empty=0.0%
         rep=5.5% dup=0.6% badTrans=12.8%
  TF=1.000, AR=0%, LR=0.000047
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 11/50
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=62752]:   0%|                                                                                                                               | 1/3922 [00:00<25:33,  2.56it/s, loss=6.0519, main=5.9527]
  [Diag] BERT top-layer gradients (after backward): OK ✓
Epoch 11/50 [AR-SS(tf=0.42,ar=50%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [47:32<00:00,  1.37it/s, loss=16.6684, main=8.4029]

  Train: Loss=9.9360 (main=7.2541, len=0.123, tcls=0.003)
  Val:   Loss=2.8160 | PPL=16.7 | Top1=33.5% Top5=65.4% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
         AR-LCS=0.381 AR-SetF1=0.519
         len(pred)=9.4 len(ref)=7.8 |lenErr|=3.8 earlyEOS=7.8% empty=0.0%
         rep=26.3% dup=0.3% badTrans=15.7%
  TF=0.417, AR=50%, LR=0.000046
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 12/50
----------------------------------------------------------------------
Epoch 12/50 [AR-SS(tf=0.41,ar=51%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [48:10<00:00,  1.36it/s, loss=7.8973, main=7.3661]

  Train: Loss=9.5381 (main=7.2584, len=0.123, tcls=0.004)
  Val:   Loss=2.8330 | PPL=17.0 | Top1=35.4% Top5=64.4% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.5%
         AR-LCS=0.387 AR-SetF1=0.522
         len(pred)=8.8 len(ref)=7.8 |lenErr|=3.1 earlyEOS=6.2% empty=0.0%
         rep=19.7% dup=0.2% badTrans=19.5%
  TF=0.408, AR=51%, LR=0.000045
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 13/50
----------------------------------------------------------------------
Epoch 13/50 [AR-SS(tf=0.40,ar=52%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [45:22<00:00,  1.44it/s, loss=12.1609, main=7.2166]

  Train: Loss=9.3246 (main=7.2361, len=0.122, tcls=0.004)
  Val:   Loss=2.8454 | PPL=17.2 | Top1=33.8% Top5=63.8% TF-SeqEM=0.1% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
         AR-LCS=0.378 AR-SetF1=0.520
         len(pred)=10.9 len(ref)=7.8 |lenErr|=4.5 earlyEOS=2.3% empty=0.0%
         rep=33.1% dup=0.3% badTrans=23.9%
  TF=0.398, AR=52%, LR=0.000044
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 14/50
----------------------------------------------------------------------
Epoch 14/50 [AR-SS(tf=0.39,ar=54%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [46:05<00:00,  1.42it/s, loss=16.2642, main=8.0304]

  Train: Loss=9.2408 (main=7.2247, len=0.122, tcls=0.004)
  Val:   Loss=2.8053 | PPL=16.5 | Top1=35.9% Top5=65.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.5%
         AR-LCS=0.389 AR-SetF1=0.532
         len(pred)=9.0 len(ref)=7.8 |lenErr|=4.3 earlyEOS=10.9% empty=0.0%
         rep=26.8% dup=0.2% badTrans=18.8%
  TF=0.387, AR=54%, LR=0.000043
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 15/50
----------------------------------------------------------------------
Epoch 15/50 [AR-SS(tf=0.38,ar=55%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [45:36<00:00,  1.43it/s, loss=11.5198, main=6.3816]

  Train: Loss=9.1748 (main=7.1919, len=0.121, tcls=0.004)
  Val:   Loss=2.8241 | PPL=16.8 | Top1=35.4% Top5=64.2% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.4%
         AR-LCS=0.393 AR-SetF1=0.523
         len(pred)=7.9 len(ref)=7.8 |lenErr|=3.0 earlyEOS=7.8% empty=0.0%
         rep=16.0% dup=0.6% badTrans=16.2%
  TF=0.376, AR=55%, LR=0.000042
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 16/50
----------------------------------------------------------------------
Epoch 16/50 [AR-SS(tf=0.36,ar=56%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [47:46<00:00,  1.37it/s, loss=15.3372, main=7.3760]

  Train: Loss=9.2471 (main=7.2234, len=0.121, tcls=0.003)
  Val:   Loss=2.8529 | PPL=17.3 | Top1=34.8% Top5=64.0% TF-SeqEM=0.6% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.0%
         AR-LCS=0.391 AR-SetF1=0.528
         len(pred)=7.8 len(ref)=7.8 |lenErr|=2.9 earlyEOS=10.9% empty=0.0%
         rep=16.1% dup=0.8% badTrans=16.1%
  TF=0.364, AR=56%, LR=0.000040
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 17/50
----------------------------------------------------------------------
Epoch 17/50 [AR-SS(tf=0.35,ar=57%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [48:34<00:00,  1.35it/s, loss=6.8620, main=6.7839]

  Train: Loss=9.1712 (main=7.2166, len=0.122, tcls=0.003)
  Val:   Loss=2.8319 | PPL=17.0 | Top1=35.5% Top5=64.0% TF-SeqEM=0.8% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.0%
         AR-LCS=0.411 AR-SetF1=0.544
         len(pred)=7.9 len(ref)=7.8 |lenErr|=3.1 earlyEOS=10.2% empty=0.0%
         rep=17.2% dup=1.0% badTrans=15.0%
  TF=0.351, AR=57%, LR=0.000039
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 18/50
----------------------------------------------------------------------
Epoch 18/50 [AR-SS(tf=0.34,ar=59%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [49:53<00:00,  1.31it/s, loss=14.9607, main=6.4588]

  Train: Loss=9.0394 (main=7.1799, len=0.121, tcls=0.003)
  Val:   Loss=2.8448 | PPL=17.2 | Top1=34.7% Top5=63.8% TF-SeqEM=0.8% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.378 AR-SetF1=0.514
         len(pred)=9.4 len(ref)=7.8 |lenErr|=4.2 earlyEOS=6.2% empty=0.0%
         rep=26.0% dup=0.4% badTrans=23.5%
  TF=0.338, AR=59%, LR=0.000038
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 19/50
----------------------------------------------------------------------
Epoch 19/50 [AR-SS(tf=0.32,ar=60%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [49:37<00:00,  1.32it/s, loss=7.0434, main=6.9525]

  Train: Loss=8.9958 (main=7.1621, len=0.120, tcls=0.003)
  Val:   Loss=2.8225 | PPL=16.8 | Top1=35.5% Top5=64.6% TF-SeqEM=0.7% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.9%
         AR-LCS=0.396 AR-SetF1=0.529
         len(pred)=8.2 len(ref)=7.8 |lenErr|=3.8 earlyEOS=10.2% empty=0.0%
         rep=22.1% dup=0.4% badTrans=14.3%
  TF=0.324, AR=60%, LR=0.000036
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 20/50
----------------------------------------------------------------------
Epoch 20/50 [AR-SS(tf=0.31,ar=61%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [53:34<00:00,  1.22it/s, loss=11.9989, main=7.2858]

  Train: Loss=9.0184 (main=7.1602, len=0.121, tcls=0.003)
  Val:   Loss=2.8332 | PPL=17.0 | Top1=35.2% Top5=63.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.6%
         AR-LCS=0.399 AR-SetF1=0.539
         len(pred)=8.7 len(ref)=7.8 |lenErr|=4.3 earlyEOS=10.9% empty=0.0%
         rep=23.2% dup=0.6% badTrans=22.7%
  TF=0.309, AR=61%, LR=0.000035
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 21/50
----------------------------------------------------------------------
Epoch 21/50 [AR-SS(tf=0.29,ar=62%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [54:37<00:00,  1.20it/s, loss=7.2511, main=7.0417]

  Train: Loss=8.9876 (main=7.1489, len=0.122, tcls=0.002)
  Val:   Loss=2.8291 | PPL=16.9 | Top1=35.5% Top5=64.4% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.1%
         AR-LCS=0.397 AR-SetF1=0.534
         len(pred)=7.7 len(ref)=7.8 |lenErr|=3.3 earlyEOS=12.5% empty=0.0%
         rep=15.9% dup=0.5% badTrans=16.1%
  TF=0.294, AR=62%, LR=0.000033
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 22/50
----------------------------------------------------------------------
Epoch 22/50 [AR-SS(tf=0.28,ar=64%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [53:56<00:00,  1.21it/s, loss=6.1449, main=6.0343]

  Train: Loss=8.9499 (main=7.1630, len=0.120, tcls=0.002)
  Val:   Loss=2.8257 | PPL=16.9 | Top1=34.6% Top5=64.2% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.382 AR-SetF1=0.525
         len(pred)=11.7 len(ref)=7.8 |lenErr|=5.6 earlyEOS=6.2% empty=0.0%
         rep=40.9% dup=0.3% badTrans=19.6%
  TF=0.279, AR=64%, LR=0.000032
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 23/50
----------------------------------------------------------------------
Epoch 23/50 [AR-SS(tf=0.26,ar=65%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [55:12<00:00,  1.18it/s, loss=13.4613, main=7.9461]

  Train: Loss=8.9421 (main=7.1671, len=0.120, tcls=0.002)
  Val:   Loss=2.8434 | PPL=17.2 | Top1=35.3% Top5=64.1% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.8%
         AR-LCS=0.393 AR-SetF1=0.529
         len(pred)=10.5 len(ref)=7.8 |lenErr|=4.1 earlyEOS=3.9% empty=0.0%
         rep=29.4% dup=0.4% badTrans=22.6%
  TF=0.264, AR=65%, LR=0.000030
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 24/50
----------------------------------------------------------------------
Epoch 24/50 [AR-SS(tf=0.25,ar=66%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [56:22<00:00,  1.16it/s, loss=6.7431, main=6.6379]

  Train: Loss=8.9476 (main=7.1838, len=0.121, tcls=0.002)
  Val:   Loss=2.8526 | PPL=17.3 | Top1=35.0% Top5=63.2% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.3%
         AR-LCS=0.384 AR-SetF1=0.522
         len(pred)=10.6 len(ref)=7.8 |lenErr|=5.3 earlyEOS=8.6% empty=0.0%
         rep=35.9% dup=0.5% badTrans=33.0%
  TF=0.248, AR=66%, LR=0.000029
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 25/50
----------------------------------------------------------------------
Epoch 25/50 [AR-SS(tf=0.23,ar=68%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [58:07<00:00,  1.12it/s, loss=15.1533, main=7.3457]

  Train: Loss=8.9280 (main=7.1893, len=0.122, tcls=0.002)
  Val:   Loss=2.8258 | PPL=16.9 | Top1=35.4% Top5=64.6% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.1%
         AR-LCS=0.400 AR-SetF1=0.547
         len(pred)=10.9 len(ref)=7.8 |lenErr|=5.0 earlyEOS=5.5% empty=0.0%
         rep=33.0% dup=0.2% badTrans=23.8%
  TF=0.232, AR=68%, LR=0.000027
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 26/50
----------------------------------------------------------------------
Epoch 26/50 [AR-SS(tf=0.22,ar=69%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [58:56<00:00,  1.11it/s, loss=13.6191, main=7.3193]

  Train: Loss=8.8643 (main=7.1759, len=0.121, tcls=0.002)
  Val:   Loss=2.8205 | PPL=16.8 | Top1=36.3% Top5=64.7% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
         AR-LCS=0.411 AR-SetF1=0.546
         len(pred)=7.8 len(ref)=7.8 |lenErr|=3.3 earlyEOS=10.9% empty=0.0%
         rep=17.1% dup=0.7% badTrans=23.1%
  TF=0.217, AR=69%, LR=0.000026
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 27/50
----------------------------------------------------------------------
Epoch 27/50 [AR-SS(tf=0.20,ar=70%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [59:08<00:00,  1.11it/s, loss=8.0013, main=7.8842]

  Train: Loss=8.8702 (main=7.1771, len=0.121, tcls=0.002)
  Val:   Loss=2.8246 | PPL=16.9 | Top1=35.8% Top5=64.8% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
         AR-LCS=0.399 AR-SetF1=0.542
         len(pred)=9.2 len(ref)=7.8 |lenErr|=3.9 earlyEOS=7.0% empty=0.0%
         rep=25.9% dup=0.9% badTrans=25.2%
  TF=0.202, AR=70%, LR=0.000024
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 28/50
----------------------------------------------------------------------
Epoch 28/50 [AR-SS(tf=0.19,ar=71%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [57:24<00:00,  1.14it/s, loss=12.5729, main=7.2053]

  Train: Loss=8.8476 (main=7.1463, len=0.121, tcls=0.002)
  Val:   Loss=2.8038 | PPL=16.5 | Top1=36.6% Top5=64.9% TF-SeqEM=0.8% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
         AR-LCS=0.409 AR-SetF1=0.547
         len(pred)=6.8 len(ref)=7.8 |lenErr|=3.0 earlyEOS=14.8% empty=0.0%
         rep=6.6% dup=0.7% badTrans=12.6%
  TF=0.187, AR=71%, LR=0.000022
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 29/50
----------------------------------------------------------------------
Epoch 29/50 [AR-SS(tf=0.17,ar=72%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [58:22<00:00,  1.12it/s, loss=6.0059, main=5.9160]

  Train: Loss=8.8609 (main=7.1924, len=0.121, tcls=0.002)
  Val:   Loss=2.8464 | PPL=17.2 | Top1=35.2% Top5=63.6% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.2%
         AR-LCS=0.400 AR-SetF1=0.533
         len(pred)=8.3 len(ref)=7.8 |lenErr|=3.7 earlyEOS=9.4% empty=0.0%
         rep=20.9% dup=0.6% badTrans=26.2%
  TF=0.173, AR=72%, LR=0.000021
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 30/50
----------------------------------------------------------------------
Epoch 30/50 [AR-SS(tf=0.16,ar=74%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [58:38<00:00,  1.11it/s, loss=15.0432, main=8.3933]

  Train: Loss=8.8161 (main=7.1762, len=0.121, tcls=0.002)
  Val:   Loss=2.8259 | PPL=16.9 | Top1=36.0% Top5=64.4% TF-SeqEM=0.7% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
         AR-LCS=0.407 AR-SetF1=0.543
         len(pred)=8.8 len(ref)=7.8 |lenErr|=3.6 earlyEOS=4.7% empty=0.0%
         rep=24.0% dup=0.8% badTrans=25.8%
  TF=0.159, AR=74%, LR=0.000019
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 31/50
----------------------------------------------------------------------
Epoch 31/50 [AR-SS(tf=0.15,ar=75%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [59:22<00:00,  1.10it/s, loss=6.2713, main=6.1876]

  Train: Loss=8.8270 (main=7.1902, len=0.123, tcls=0.002)
  Val:   Loss=2.8105 | PPL=16.6 | Top1=36.1% Top5=64.7% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.0%
         AR-LCS=0.392 AR-SetF1=0.525
         len(pred)=7.5 len(ref)=7.8 |lenErr|=3.3 earlyEOS=14.8% empty=0.0%
         rep=16.8% dup=1.0% badTrans=21.2%
  TF=0.145, AR=75%, LR=0.000018
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 32/50
----------------------------------------------------------------------
Epoch 32/50 [AR-SS(tf=0.13,ar=76%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [59:39<00:00,  1.10it/s, loss=7.3098, main=7.1948]

  Train: Loss=8.8051 (main=7.1767, len=0.121, tcls=0.001)
  Val:   Loss=2.8635 | PPL=17.5 | Top1=35.2% Top5=63.5% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.6%
         AR-LCS=0.399 AR-SetF1=0.540
         len(pred)=9.8 len(ref)=7.8 |lenErr|=3.8 earlyEOS=4.7% empty=0.0%
         rep=29.1% dup=0.9% badTrans=25.7%
  TF=0.133, AR=76%, LR=0.000016
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 33/50
----------------------------------------------------------------------
Epoch 33/50 [AR-SS(tf=0.12,ar=78%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:00:19<00:00,  1.08it/s, loss=7.7644, main=7.6479]

  Train: Loss=8.8200 (main=7.1750, len=0.122, tcls=0.001)
  Val:   Loss=2.8495 | PPL=17.3 | Top1=35.7% Top5=63.9% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.410 AR-SetF1=0.550
         len(pred)=8.9 len(ref)=7.8 |lenErr|=3.7 earlyEOS=6.2% empty=0.0%
         rep=25.9% dup=0.9% badTrans=29.5%
  TF=0.121, AR=78%, LR=0.000015
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 34/50
----------------------------------------------------------------------
Epoch 34/50 [AR-SS(tf=0.11,ar=79%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:01:32<00:00,  1.06it/s, loss=7.0308, main=6.8910]

  Train: Loss=8.7765 (main=7.1874, len=0.123, tcls=0.001)
  Val:   Loss=2.8412 | PPL=17.1 | Top1=35.5% Top5=64.6% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.3%
         AR-LCS=0.416 AR-SetF1=0.551
         len(pred)=8.2 len(ref)=7.8 |lenErr|=3.5 earlyEOS=7.8% empty=0.0%
         rep=21.4% dup=0.9% badTrans=25.8%
  TF=0.110, AR=79%, LR=0.000013
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 35/50
----------------------------------------------------------------------
Epoch 35/50 [AR-SS(tf=0.10,ar=80%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:02:15<00:00,  1.05it/s, loss=7.1401, main=6.9487]

  Train: Loss=8.7475 (main=7.1841, len=0.124, tcls=0.001)
  Val:   Loss=2.8364 | PPL=17.1 | Top1=36.1% Top5=64.3% TF-SeqEM=0.7% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.401 AR-SetF1=0.540
         len(pred)=8.3 len(ref)=7.8 |lenErr|=3.5 earlyEOS=9.4% empty=0.0%
         rep=21.0% dup=1.0% badTrans=23.4%
  TF=0.100, AR=80%, LR=0.000012
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 36/50
----------------------------------------------------------------------
Epoch 36/50 [AR-SS(tf=0.09,ar=81%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:03:04<00:00,  1.04it/s, loss=7.4720, main=7.3062]

  Train: Loss=8.7999 (main=7.1878, len=0.125, tcls=0.001)
  Val:   Loss=2.8744 | PPL=17.7 | Top1=34.1% Top5=63.7% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
         AR-LCS=0.397 AR-SetF1=0.536
         len(pred)=11.4 len(ref)=7.8 |lenErr|=5.4 earlyEOS=4.7% empty=0.0%
         rep=39.3% dup=1.0% badTrans=29.1%
  TF=0.090, AR=81%, LR=0.000011
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 37/50
----------------------------------------------------------------------
Epoch 37/50 [AR-SS(tf=0.08,ar=82%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:03:36<00:00,  1.03it/s, loss=7.8297, main=7.7001]

  Train: Loss=8.7400 (main=7.1888, len=0.123, tcls=0.001)
  Val:   Loss=2.8363 | PPL=17.1 | Top1=35.7% Top5=64.8% TF-SeqEM=0.5% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.1%
         AR-LCS=0.408 AR-SetF1=0.549
         len(pred)=8.2 len(ref)=7.8 |lenErr|=3.4 earlyEOS=12.5% empty=0.0%
         rep=20.3% dup=1.0% badTrans=25.8%
  TF=0.081, AR=82%, LR=0.000009
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 38/50
----------------------------------------------------------------------
Epoch 38/50 [AR-SS(tf=0.07,ar=84%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:04:31<00:00,  1.01it/s, loss=7.1821, main=6.9014]

  Train: Loss=8.6733 (main=7.1745, len=0.126, tcls=0.001)
  Val:   Loss=2.8676 | PPL=17.6 | Top1=34.6% Top5=63.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
         AR-LCS=0.401 AR-SetF1=0.536
         len(pred)=9.1 len(ref)=7.8 |lenErr|=3.7 earlyEOS=6.2% empty=0.0%
         rep=28.0% dup=0.6% badTrans=30.3%
  TF=0.073, AR=84%, LR=0.000008
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 39/50
----------------------------------------------------------------------
Epoch 39/50 [AR-SS(tf=0.07,ar=85%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:05:50<00:00,  1.01s/it, loss=7.5109, main=7.4182]

  Train: Loss=8.7514 (main=7.2067, len=0.126, tcls=0.001)
  Val:   Loss=2.8739 | PPL=17.7 | Top1=34.4% Top5=63.5% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.7%
         AR-LCS=0.390 AR-SetF1=0.525
         len(pred)=9.4 len(ref)=7.8 |lenErr|=3.9 earlyEOS=4.7% empty=0.0%
         rep=28.1% dup=0.6% badTrans=29.4%
  TF=0.066, AR=85%, LR=0.000007
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 40/50
----------------------------------------------------------------------
Epoch 40/50 [AR-SS(tf=0.06,ar=86%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:06:07<00:00,  1.01s/it, loss=8.3445, main=8.0367]

  Train: Loss=8.7282 (main=7.2192, len=0.127, tcls=0.001)
  Val:   Loss=2.8893 | PPL=18.0 | Top1=34.1% Top5=63.2% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=15.8%
         AR-LCS=0.397 AR-SetF1=0.535
         len(pred)=9.1 len(ref)=7.8 |lenErr|=3.7 earlyEOS=6.2% empty=0.0%
         rep=27.4% dup=0.6% badTrans=32.9%
  TF=0.059, AR=86%, LR=0.000006
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 41/50
----------------------------------------------------------------------
Epoch 41/50 [AR-SS(tf=0.05,ar=88%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:05:15<00:00,  1.00it/s, loss=7.6840, main=7.5652]

  Train: Loss=8.6692 (main=7.1942, len=0.127, tcls=0.001)
  Val:   Loss=2.8845 | PPL=17.9 | Top1=34.4% Top5=63.7% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.0%
         AR-LCS=0.402 AR-SetF1=0.538
         len(pred)=8.9 len(ref)=7.8 |lenErr|=3.6 earlyEOS=8.6% empty=0.0%
         rep=25.7% dup=1.1% badTrans=31.4%
  TF=0.053, AR=88%, LR=0.000005
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 42/50
----------------------------------------------------------------------
Epoch 42/50 [AR-SS(tf=0.05,ar=89%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:04:57<00:00,  1.01it/s, loss=6.0795, main=5.9886]

  Train: Loss=8.6606 (main=7.2058, len=0.126, tcls=0.001)
  Val:   Loss=2.8793 | PPL=17.8 | Top1=34.4% Top5=63.7% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.7%
         AR-LCS=0.408 AR-SetF1=0.541
         len(pred)=8.5 len(ref)=7.8 |lenErr|=3.5 earlyEOS=10.2% empty=0.0%
         rep=24.6% dup=0.6% badTrans=31.2%
  TF=0.047, AR=89%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 43/50
----------------------------------------------------------------------
Epoch 43/50 [AR-SS(tf=0.04,ar=90%), n=62752]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:07:19<00:00,  1.03s/it, loss=13.2478, main=8.8075]

  Train: Loss=8.6921 (main=7.2126, len=0.128, tcls=0.001)
  Val:   Loss=2.8775 | PPL=17.8 | Top1=34.1% Top5=63.9% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.3%
         AR-LCS=0.419 AR-SetF1=0.557
         len(pred)=8.2 len(ref)=7.8 |lenErr|=3.1 earlyEOS=7.8% empty=0.0%
         rep=22.3% dup=0.5% badTrans=29.0%
  TF=0.042, AR=90%, LR=0.000004
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 44/50
----------------------------------------------------------------------
Epoch 44/50 [AR-SS(tf=0.04,ar=91%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:08:50<00:00,  1.05s/it, loss=7.6137, main=7.5138]

  Train: Loss=8.7340 (main=7.2163, len=0.128, tcls=0.001)
  Val:   Loss=2.8963 | PPL=18.1 | Top1=33.5% Top5=63.2% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.9%
         AR-LCS=0.403 AR-SetF1=0.536
         len(pred)=9.8 len(ref)=7.8 |lenErr|=3.8 earlyEOS=3.9% empty=0.0%
         rep=31.7% dup=0.5% badTrans=31.9%
  TF=0.037, AR=91%, LR=0.000003
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 45/50
----------------------------------------------------------------------
Epoch 45/50 [AR-SS(tf=0.03,ar=92%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:09:46<00:00,  1.07s/it, loss=7.3089, main=7.1259]

  Train: Loss=8.7042 (main=7.2152, len=0.129, tcls=0.001)
  Val:   Loss=2.9060 | PPL=18.3 | Top1=33.3% Top5=62.8% TF-SeqEM=0.4% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.2%
         AR-LCS=0.401 AR-SetF1=0.535
         len(pred)=8.8 len(ref)=7.8 |lenErr|=3.7 earlyEOS=7.0% empty=0.0%
         rep=25.9% dup=0.8% badTrans=35.6%
  TF=0.033, AR=92%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 46/50
----------------------------------------------------------------------
Epoch 46/50 [AR-SS(tf=0.03,ar=94%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:10:46<00:00,  1.08s/it, loss=9.3045, main=9.2110]

  Train: Loss=8.6839 (main=7.2279, len=0.130, tcls=0.001)
  Val:   Loss=2.9091 | PPL=18.3 | Top1=33.0% Top5=62.9% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.5%
         AR-LCS=0.408 AR-SetF1=0.541
         len(pred)=8.9 len(ref)=7.8 |lenErr|=3.6 earlyEOS=6.2% empty=0.0%
         rep=27.5% dup=0.6% badTrans=32.4%
  TF=0.030, AR=94%, LR=0.000002
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 47/50
----------------------------------------------------------------------
Epoch 47/50 [AR-SS(tf=0.03,ar=95%), n=62752]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [1:01:29<00:00,  1.06it/s, loss=6.9772, main=6.8654]

  Train: Loss=8.7564 (main=7.2491, len=0.129, tcls=0.001)
  Val:   Loss=2.9234 | PPL=18.6 | Top1=32.6% Top5=62.5% TF-SeqEM=0.3% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.0%
         AR-LCS=0.395 AR-SetF1=0.524
         len(pred)=8.8 len(ref)=7.8 |lenErr|=3.4 earlyEOS=7.8% empty=0.0%
         rep=27.1% dup=0.6% badTrans=37.4%
  TF=0.026, AR=95%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 48/50
----------------------------------------------------------------------
Epoch 48/50 [AR-SS(tf=0.02,ar=96%), n=62752]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [52:58<00:00,  1.23it/s, loss=14.5308, main=7.1169]

  Train: Loss=8.7754 (main=7.2468, len=0.130, tcls=0.001)
  Val:   Loss=2.9259 | PPL=18.7 | Top1=32.4% Top5=62.5% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.6%
         AR-LCS=0.404 AR-SetF1=0.533
         len(pred)=9.3 len(ref)=7.8 |lenErr|=3.4 earlyEOS=6.2% empty=0.0%
         rep=30.4% dup=0.7% badTrans=32.2%
  TF=0.023, AR=96%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 49/50
----------------------------------------------------------------------
Epoch 49/50 [AR-SS(tf=0.02,ar=98%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [52:40<00:00,  1.24it/s, loss=7.2411, main=7.0247]

  Train: Loss=8.6856 (main=7.2568, len=0.133, tcls=0.001)
  Val:   Loss=2.9303 | PPL=18.7 | Top1=32.3% Top5=62.5% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=16.4%
         AR-LCS=0.406 AR-SetF1=0.537
         len(pred)=8.6 len(ref)=7.8 |lenErr|=3.5 earlyEOS=7.0% empty=0.0%
         rep=25.3% dup=0.7% badTrans=31.5%
  TF=0.021, AR=98%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

Epoch 50/50
----------------------------------------------------------------------
Epoch 50/50 [AR-SS(tf=0.02,ar=99%), n=62752]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 3922/3922 [54:11<00:00,  1.21it/s, loss=7.8781, main=7.6888]

  Train: Loss=8.7473 (main=7.2647, len=0.132, tcls=0.001)
  Val:   Loss=2.9472 | PPL=19.1 | Top1=31.8% Top5=62.0% TF-SeqEM=0.2% avglen(ref)=9.6
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=17.4%
         AR-LCS=0.401 AR-SetF1=0.533
         len(pred)=9.3 len(ref)=7.8 |lenErr|=3.5 earlyEOS=7.0% empty=0.0%
         rep=31.0% dup=0.7% badTrans=33.8%
  TF=0.018, AR=99%, LR=0.000001
  [SNAPSHOT] Saved latest epoch: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/best_model.pth

================================================================================
Training complete! Loading latest checkpoint for test evaluation...

Test Results:
  Loss=2.9971 PPL=20.0
  Top1=30.1% Top5=60.6%
  TF-SeqEM=0.0% avglen(ref)=9.5
  AR-SeqEM=0.0% AR-TokenAcc=19.7%
  AR-LCS=0.421 AR-SetF1=0.557
  len(pred)=10.5 len(ref)=7.0 |lenErr|=5.0
  earlyEOS=7.8% empty=0.0%
  rep=43.7% dup=0.2% badTrans=44.6%

History saved: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/training_history_v4_6.json
Checkpoint selection manifest saved: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate/checkpoint_selection_manifest_v4_6.json

V4.6 Quality-Gate training summary:
  trainer: V4.6
  mode: from_scratch
  mr_registry: {'status': 'disabled', 'path': None, 'ratio': 0.0, 'task_groups': 0, 'matched_train_samples': 0}
  mrv_training_dataset: {'status': 'enabled', 'version_name': 'mr_all_1257', 'manifest_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mrv_training_ablation_manifest.json', 'report_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/mrv_training_ablation_report.json', 'data_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/labeled_workflows_l3_v4_quality_gate.json', 'splits_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/dataset_splits_v4_quality_gate.json', 'task_vocab_path': 'outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/task_type_vocabulary_v4_quality_gate.json', 'injected_variants': 1257, 'available_verified_mr_variants': 1257, 'train_injection_rate_vs_base_train': 0.02044069, 'equivalence_family_counts': {'filter_filter': 661, 'select_filter': 8, 'select_clip': 3, 'other': 1, 'structural_equivalence_conservative': 178, 'structural_equivalence_relaxed': 406}, 'risk_level_counts': {'low': 31, 'medium': 10, 'sampled_low': 631, 'unknown': 1, 'reviewed': 584}}
  length_bucket_training: {'status': 'enabled', 'path': '/home/qy/system_redesign/outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json', 'loss_weight': 0.1, 'target': 'task_type_bucket_expected_length', 'splits': {'train': {'samples': 62752, 'bucket_counts': {'medium': 39257, 'long': 22997, 'short': 498}}, 'val': {'samples': 7694, 'bucket_counts': {'long': 2846, 'medium': 4791, 'short': 57}}, 'test': {'samples': 7695, 'bucket_counts': {'medium': 4793, 'short': 57, 'long': 2845}}}, 'expected_length_by_bucket': {'short': 3, 'medium': 5, 'long': 8, 'very_long': 13}}
  training_contract: {'system_objective': 'increase usable/executable multi-solution GIS operator chains', 'known_limitations': ['token_ce_is_single_reference_supervision', 'ranking_is_post_training_not_a_training_objective', 'semantic_constraints_are_evaluated_outside_the_loss', 'inference_beam_constraints_are_not_fully_mirrored_in_ar_sampling'], 'required_post_training_validation': ['p0_evidence_aware_ranking_calibration', 'workflow_usability_evaluation', 'qgis_mapping_or_execution_diagnostics']}
  metric_contract: {'primary': ['set_f1', 'usable', 'executable', 'qgis_mapping'], 'supporting': ['lcs'], 'diagnostic_only': ['token_acc', 'sequence_em', 'loss', 'perplexity', 'top1', 'top5'], 'multi_solution_policy': 'TokenAcc and exact sequence match are diagnostic only for GIS workflow quality.'}
  checkpoint_policy: {'latest_snapshot': 'best_model.pth', 'latest_snapshot_note': 'historical compatibility name; overwritten each epoch', 'additional_selection_snapshots': ['best_gen_set_f1_model.pth', 'best_gen_lcs_model.pth'], 'selection_snapshot_note': 'post-training comparison aids; does not change training objective'}
  data_path: outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/labeled_workflows_l3_v4_quality_gate.json
  splits_path: outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/dataset_splits_v4_quality_gate.json
  task_vocab_path: outputs_v2/v4_qg_mr_ablation_from_multisolution_unified/mr_all_1257/task_type_vocabulary_v4_quality_gate.json
  warmstart_path: None
  checkpoint_dir: /home/qy/system_redesign/outputs_v2/transformer_checkpoints_v4_6_quality_gate
  workflows_total: 78141
  train: 62752
  val: 7694
  test: 7695
  num_task_types: 47
  vocab_size: 98
  num_epochs: 50
  tf_phase_epochs: 10
  device: cuda
  dry_run: False
  history_epochs: 50