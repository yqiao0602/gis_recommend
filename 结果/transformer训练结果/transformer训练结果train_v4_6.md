(transformer) qy@mdzhang:~/system_redesign/src$ python -m gis_recommend.training.train_v4_6
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
================================================================================
V4.6 Training: Gradient Fix + AR-based Model Selection
  Fixes: no detach, no no_grad for aux, best model by AR-TokenAcc
  Inherits: V4.5 balanced sampling + strong task signal
================================================================================
  CUDA: NVIDIA A10
  GPU Memory: 23.7 GB

[1] Loading data...
  Workflows: 114401

[2] Loading task type vocabulary...
  Task types: 132

[3] Splitting dataset...
  Loaded existing splits from /home/qy/system_redesign/outputs/dataset_splits_v4.json
  Train: 91520, Val: 11440, Test: 11441

[4] Computing token frequency weights...

[5] Creating datasets...

[6] Creating model...
  [V4] Loaded L3 embeddings: 350 tokens from /home/qy/system_redesign/outputs/l3_embeddings.pt
  Params: 22.8M trainable, 117.5M total

[7] Loading warm-start checkpoint...
  Loading warm-start from /home/qy/system_redesign/outputs/transformer_checkpoints_v4_3/best_model.pth ...
  Model loaded (epoch 28, val_loss=2.1974

[8] Creating V4.6 trainer...
  [V4.2] Using frequency-weighted CE loss (alpha=0.5)
  [V4.2] 转移矩阵: 99 states loaded
  [V4.5] task_cls_loss_weight overridden to 0.3
  Task classifier weights loaded from warm-start

[9] Starting V4.6 training...

================================================================================
V4.6 Training: Gradient Fix + AR-based Model Selection
================================================================================
  Device: cuda, AMP: True
  Batch: 16 x 2 accum = 32 effective
  LR: BERT=2.0e-06, Other=5.0e-05
  AR max steps: 20
  Gen eval batches: 8
  Best model selection: AR-TokenAcc (not TF val_loss)
================================================================================


Epoch 1/30
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling, resetting patience
Epoch 1/30 [AR-SS(tf=0.42,ar=50%), n=91520]:   0%|                                                                                                                              | 1/5720 [00:01<2:27:36,  1.55s/it, loss=5.4919, main=4.9374]
  [Diag] BERT top-layer gradients (after backward): OK ✓
Epoch 1/30 [AR-SS(tf=0.42,ar=50%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [31:37<00:00,  3.02it/s, loss=3.8447, main=3.7746]

  Train: Loss=inf (main=inf, len=0.125, tcls=0.058)
  Val:   Loss=2.2887 | PPL=9.9 | Top1=45.8% Top5=81.0% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.4%
  TF=0.417, AR=50%, LR=0.000050
  [Diag] BERT gradient check moved to _train_step_autoregressive (after backward)
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_6/best_model.pth (ar_token_acc=12.4%)

Epoch 2/30
----------------------------------------------------------------------
Epoch 2/30 [AR-SS(tf=0.40,ar=52%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [32:02<00:00,  2.97it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.104, tcls=0.008)
  Val:   Loss=2.2551 | PPL=9.5 | Top1=45.8% Top5=81.7% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.3%
  TF=0.404, AR=52%, LR=0.000050
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_6/best_model.pth (ar_token_acc=14.3%)

Epoch 3/30
----------------------------------------------------------------------
Epoch 3/30 [AR-SS(tf=0.39,ar=53%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [32:51<00:00,  2.90it/s, loss=3.8063, main=3.7119]

  Train: Loss=inf (main=inf, len=0.097, tcls=0.005)
  Val:   Loss=2.2744 | PPL=9.7 | Top1=45.7% Top5=81.3% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=13.8%
  TF=0.391, AR=53%, LR=0.000050
  No improvement for 1 epoch(s)

Epoch 4/30
----------------------------------------------------------------------
Epoch 4/30 [AR-SS(tf=0.38,ar=55%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [33:26<00:00,  2.85it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.091, tcls=0.003)
  Val:   Loss=2.2831 | PPL=9.8 | Top1=45.6% Top5=81.3% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.9%
  TF=0.376, AR=55%, LR=0.000049
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_6/best_model.pth (ar_token_acc=14.9%)

Epoch 5/30
----------------------------------------------------------------------
Epoch 5/30 [AR-SS(tf=0.36,ar=57%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [34:51<00:00,  2.74it/s, loss=3.6540, main=3.6098]

  Train: Loss=inf (main=inf, len=0.090, tcls=0.003)
  Val:   Loss=2.3219 | PPL=10.2 | Top1=45.4% Top5=80.8% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=13.2%
  TF=0.360, AR=57%, LR=0.000049
  No improvement for 1 epoch(s)

Epoch 6/30
----------------------------------------------------------------------
Epoch 6/30 [AR-SS(tf=0.34,ar=58%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [34:52<00:00,  2.73it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.088, tcls=0.002)
  Val:   Loss=2.2990 | PPL=10.0 | Top1=45.2% Top5=81.0% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.1%
  TF=0.342, AR=58%, LR=0.000048
  No improvement for 2 epoch(s)

Epoch 7/30
----------------------------------------------------------------------
Epoch 7/30 [AR-SS(tf=0.32,ar=60%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [35:55<00:00,  2.65it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.085, tcls=0.002)
  Val:   Loss=2.3064 | PPL=10.0 | Top1=45.4% Top5=81.0% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=13.7%
  TF=0.324, AR=60%, LR=0.000046
  No improvement for 3 epoch(s)

Epoch 8/30
----------------------------------------------------------------------
Epoch 8/30 [AR-SS(tf=0.30,ar=62%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [37:00<00:00,  2.58it/s, loss=4.1328, main=4.0516]

  Train: Loss=inf (main=inf, len=0.084, tcls=0.002)
  Val:   Loss=2.3267 | PPL=10.2 | Top1=43.9% Top5=80.6% TF-SeqEM=1.9%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=13.5%
  TF=0.304, AR=62%, LR=0.000045
  No improvement for 4 epoch(s)

Epoch 9/30
----------------------------------------------------------------------
Epoch 9/30 [AR-SS(tf=0.28,ar=63%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [37:29<00:00,  2.54it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.084, tcls=0.002)
  Val:   Loss=2.3274 | PPL=10.3 | Top1=44.1% Top5=80.9% TF-SeqEM=1.9%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=12.3%
  TF=0.284, AR=63%, LR=0.000043
  No improvement for 5 epoch(s)

Epoch 10/30
----------------------------------------------------------------------
Epoch 10/30 [AR-SS(tf=0.26,ar=65%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [38:04<00:00,  2.50it/s, loss=4.0490, main=3.9445]

  Train: Loss=inf (main=inf, len=0.084, tcls=0.001)
  Val:   Loss=2.3246 | PPL=10.2 | Top1=44.0% Top5=80.7% TF-SeqEM=2.0%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=12.1%
  TF=0.264, AR=65%, LR=0.000041
  No improvement for 6 epoch(s)

Epoch 11/30
----------------------------------------------------------------------
Epoch 11/30 [AR-SS(tf=0.24,ar=67%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [39:00<00:00,  2.44it/s, loss=3.9123, main=3.8521]

  Train: Loss=inf (main=inf, len=0.084, tcls=0.001)
  Val:   Loss=2.3433 | PPL=10.4 | Top1=43.6% Top5=80.6% TF-SeqEM=2.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.9%
  TF=0.243, AR=67%, LR=0.000039
  No improvement for 7 epoch(s)

Epoch 12/30
----------------------------------------------------------------------
Epoch 12/30 [AR-SS(tf=0.22,ar=68%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [39:20<00:00,  2.42it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.083, tcls=0.001)
  Val:   Loss=2.3326 | PPL=10.3 | Top1=44.0% Top5=80.7% TF-SeqEM=2.0%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=13.9%
  TF=0.222, AR=68%, LR=0.000036
  No improvement for 8 epoch(s)

Epoch 13/30
----------------------------------------------------------------------
Epoch 13/30 [AR-SS(tf=0.20,ar=70%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [40:22<00:00,  2.36it/s, loss=3.9585, main=3.8821]

  Train: Loss=inf (main=inf, len=0.082, tcls=0.001)
  Val:   Loss=2.3763 | PPL=10.8 | Top1=42.9% Top5=80.0% TF-SeqEM=1.7%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=14.6%
  TF=0.202, AR=70%, LR=0.000034
  No improvement for 9 epoch(s)

Epoch 14/30
----------------------------------------------------------------------
Epoch 14/30 [AR-SS(tf=0.18,ar=72%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [41:05<00:00,  2.32it/s, loss=4.1489, main=4.0751]

  Train: Loss=inf (main=inf, len=0.083, tcls=0.001)
  Val:   Loss=2.3495 | PPL=10.5 | Top1=43.2% Top5=80.3% TF-SeqEM=2.0%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=15.0%
  TF=0.182, AR=72%, LR=0.000031
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_6/best_model.pth (ar_token_acc=15.0%)

Epoch 15/30
----------------------------------------------------------------------
Epoch 15/30 [AR-SS(tf=0.16,ar=73%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [42:12<00:00,  2.26it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.083, tcls=0.001)
  Val:   Loss=2.3545 | PPL=10.5 | Top1=43.4% Top5=80.3% TF-SeqEM=2.1%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=13.9%
  TF=0.163, AR=73%, LR=0.000028
  No improvement for 1 epoch(s)

Epoch 16/30
----------------------------------------------------------------------
Epoch 16/30 [AR-SS(tf=0.15,ar=75%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [42:06<00:00,  2.26it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.082, tcls=0.001)
  Val:   Loss=2.3705 | PPL=10.7 | Top1=43.0% Top5=80.1% TF-SeqEM=2.0%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=13.4%
  TF=0.145, AR=75%, LR=0.000026
  No improvement for 2 epoch(s)

Epoch 17/30
----------------------------------------------------------------------
Epoch 17/30 [AR-SS(tf=0.13,ar=77%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [43:39<00:00,  2.18it/s, loss=3.7028, main=3.6478]

  Train: Loss=inf (main=inf, len=0.084, tcls=0.001)
  Val:   Loss=2.4139 | PPL=11.2 | Top1=41.6% Top5=79.3% TF-SeqEM=1.6%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=12.1%
  TF=0.129, AR=77%, LR=0.000023
  No improvement for 3 epoch(s)

Epoch 18/30
----------------------------------------------------------------------
Epoch 18/30 [AR-SS(tf=0.11,ar=78%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [43:43<00:00,  2.18it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.084, tcls=0.001)
  Val:   Loss=2.4157 | PPL=11.2 | Top1=41.7% Top5=79.3% TF-SeqEM=1.7%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=13.8%
  TF=0.114, AR=78%, LR=0.000020
  No improvement for 4 epoch(s)

Epoch 19/30
----------------------------------------------------------------------
Epoch 19/30 [AR-SS(tf=0.10,ar=80%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [44:45<00:00,  2.13it/s, loss=3.6073, main=3.5540]

  Train: Loss=inf (main=inf, len=0.084, tcls=0.001)
  Val:   Loss=2.4422 | PPL=11.5 | Top1=41.1% Top5=78.8% TF-SeqEM=1.7%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=14.1%
  TF=0.100, AR=80%, LR=0.000017
  No improvement for 5 epoch(s)

Epoch 20/30
----------------------------------------------------------------------
Epoch 20/30 [AR-SS(tf=0.09,ar=82%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [45:38<00:00,  2.09it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.083, tcls=0.001)
  Val:   Loss=2.4532 | PPL=11.6 | Top1=40.5% Top5=78.6% TF-SeqEM=1.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.9%
  TF=0.087, AR=82%, LR=0.000015
  No improvement for 6 epoch(s)

Epoch 21/30
----------------------------------------------------------------------
Epoch 21/30 [AR-SS(tf=0.08,ar=83%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [46:17<00:00,  2.06it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.085, tcls=0.001)
  Val:   Loss=2.4831 | PPL=12.0 | Top1=39.9% Top5=77.9% TF-SeqEM=1.6%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=14.7%
  TF=0.076, AR=83%, LR=0.000012
  No improvement for 7 epoch(s)

Epoch 22/30
----------------------------------------------------------------------
Epoch 22/30 [AR-SS(tf=0.07,ar=85%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [47:09<00:00,  2.02it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.087, tcls=0.001)
  Val:   Loss=2.4657 | PPL=11.8 | Top1=40.3% Top5=78.4% TF-SeqEM=1.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.1%
  TF=0.066, AR=85%, LR=0.000010
  No improvement for 8 epoch(s)

Epoch 23/30
----------------------------------------------------------------------
Epoch 23/30 [AR-SS(tf=0.06,ar=87%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [47:48<00:00,  1.99it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.085, tcls=0.001)
  Val:   Loss=2.4698 | PPL=11.8 | Top1=40.1% Top5=78.2% TF-SeqEM=1.6%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=14.4%
  TF=0.057, AR=87%, LR=0.000008
  No improvement for 9 epoch(s)

Epoch 24/30
----------------------------------------------------------------------
Epoch 24/30 [AR-SS(tf=0.05,ar=88%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [48:20<00:00,  1.97it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.087, tcls=0.001)
  Val:   Loss=2.5028 | PPL=12.2 | Top1=39.4% Top5=77.7% TF-SeqEM=1.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.1%
  TF=0.049, AR=88%, LR=0.000006
  No improvement for 10 epoch(s)

Epoch 25/30
----------------------------------------------------------------------
Epoch 25/30 [AR-SS(tf=0.04,ar=90%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [49:14<00:00,  1.94it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.087, tcls=0.001)
  Val:   Loss=2.5192 | PPL=12.4 | Top1=38.7% Top5=77.3% TF-SeqEM=1.5%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=14.7%
  TF=0.042, AR=90%, LR=0.000005
  No improvement for 11 epoch(s)

Epoch 26/30
----------------------------------------------------------------------
Epoch 26/30 [AR-SS(tf=0.04,ar=92%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 5720/5720 [50:09<00:00,  1.90it/s, loss=inf, main=inf]

  Train: Loss=inf (main=inf, len=0.089, tcls=0.001)
  Val:   Loss=2.5496 | PPL=12.8 | Top1=37.7% Top5=76.6% TF-SeqEM=1.3%
  Gen:   AR-SeqEM=0.8% AR-TokenAcc=14.9%
  TF=0.036, AR=92%, LR=0.000003
  No improvement for 12 epoch(s)

Early stopping at epoch 26

================================================================================
Training complete! Loading best model for test evaluation...

Test Results:
  Loss=2.3410 PPL=10.4
  Top1=43.5% Top5=80.3%
  TF-SeqEM=2.2%
  AR-SeqEM=0.0% AR-TokenAcc=15.8%

History saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_6/training_history_v4_6.json [transformer训练结果train_v4_6.md.md](transformer训练结果train_v4_6.md.md) 