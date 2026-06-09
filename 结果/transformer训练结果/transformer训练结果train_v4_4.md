(transformer) qy@mdzhang:~/system_redesign/src$ python -m gis_recommend.training.train_v4_4
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
V4.4 Training: Length-Aware Warm-start from V4.2
  Fixes: no curriculum, length loss 0.5, early END penalty, dynamic min_length
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

[8] Creating V4.4 trainer...
  [V4.2] Using frequency-weighted CE loss (alpha=0.5)
  [V4.2] 转移矩阵: 99 states loaded
  Task classifier weights loaded from V4.2

[9] V4.4 Schedule Preview:
  Warm-start: YES
  Length loss weight: 0.5
  Early END penalty: 2.0 (threshold=0.7)
  Dynamic min_length ratio: 0.5
  Epoch   1: tf_ratio=0.417, ar_ratio=50%
  Epoch   3: tf_ratio=0.391, ar_ratio=53%
  Epoch   6: tf_ratio=0.342, ar_ratio=58%
  Epoch  11: tf_ratio=0.243, ar_ratio=67%
  Epoch  16: tf_ratio=0.145, ar_ratio=75%
  Epoch  21: tf_ratio=0.076, ar_ratio=83%
  Epoch  25: tf_ratio=0.042, ar_ratio=90%

[10] Starting V4.4 training...
================================================================================
V4.2 Training: All Bug Fixes + Low-VRAM Optimization
================================================================================
  Device: cuda, AMP: True
  Batch: 32 x 1 accum = 32 effective
  LR: BERT=2.0e-06, Other=5.0e-05
  TF Phase: epoch 0--1, then AR-SS
  AR ratio: 50% -> 100% (gradual)
  AR max steps: 40
  AR sampling: temp=0.8, top_p=0.9
  Decode rep penalty: 2.0, window=3
  Curriculum: phase1 <=999 (ep 0--1), phase2 <=999 (ep 0--1)
  Warmup: 2 epochs, Patience: 12
  Fixes applied: FiLM init, BERT grad, label smooth AR, aux from forward, attn mask, optimizer
================================================================================

Epoch 1/30
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling, resetting patience
Epoch 1/30 [AR-SS(tf=0.42,ar=50%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:01:23<00:00,  1.29s/it, loss=5.2268, main=5.0346]

  Train: Loss=5.5171 (main=5.4336, len=0.182, tcls=0.009)
  Val:   Loss=2.1997 | PPL=9.0 | Top1=47.5% Top5=82.8% TF-SeqEM=2.7%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.2%
  TF=0.417, AR=50%, LR=0.000050
  [Diag] BERT top-layer gradients: MISSING (check Fix D)
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_4/best_model.pth (val_loss=2.1997)

Epoch 2/30
----------------------------------------------------------------------
Epoch 2/30 [AR-SS(tf=0.40,ar=52%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [57:25<00:00,  1.20s/it, loss=6.0394, main=5.9985]

  Train: Loss=5.5082 (main=5.4256, len=0.177, tcls=0.007)
  Val:   Loss=2.1963 | PPL=9.0 | Top1=47.8% Top5=83.0% TF-SeqEM=2.8%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.8%
  TF=0.404, AR=52%, LR=0.000050
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_4/best_model.pth (val_loss=2.1963)

Epoch 3/30
----------------------------------------------------------------------
Epoch 3/30 [AR-SS(tf=0.39,ar=53%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [42:54<00:00,  1.11it/s, loss=4.6228, main=4.5007]

  Train: Loss=5.5176 (main=5.4367, len=0.175, tcls=0.007)
  Val:   Loss=2.1823 | PPL=8.9 | Top1=47.8% Top5=83.0% TF-SeqEM=2.8%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.7%
  TF=0.391, AR=53%, LR=0.000050
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_4/best_model.pth (val_loss=2.1823)

Epoch 4/30
----------------------------------------------------------------------
█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [43:59<00:00,  1.08it/s, loss=5.9530, main=5.9089]

  Train: Loss=5.5622 (main=5.4837, len=0.173, tcls=0.008)
  Val:   Loss=2.2057 | PPL=9.1 | Top1=47.3% Top5=82.6% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=14.1%
  TF=0.376, AR=55%, LR=0.000049
  No improvement for 1 epoch(s)

Epoch 5/30
----------------------------------------------------------------------
Epoch 5/30 [AR-SS(tf=0.36,ar=57%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:02:58<00:00,  1.32s/it, loss=4.9368, main=4.7960]

  Train: Loss=5.6114 (main=5.5362, len=0.172, tcls=0.009)
  Val:   Loss=2.1948 | PPL=9.0 | Top1=47.6% Top5=82.8% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=13.7%
  TF=0.360, AR=57%, LR=0.000049
  No improvement for 2 epoch(s)

Epoch 6/30
----------------------------------------------------------------------
Epoch 6/30 [AR-SS(tf=0.34,ar=58%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [37:27<00:00,  1.27it/s, loss=5.9709, main=5.9149]

  Train: Loss=5.6260 (main=5.5518, len=0.170, tcls=0.009)
  Val:   Loss=2.1999 | PPL=9.0 | Top1=47.3% Top5=82.6% TF-SeqEM=2.7%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=13.3%
  TF=0.342, AR=58%, LR=0.000048
  No improvement for 3 epoch(s)

Epoch 7/30
----------------------------------------------------------------------
Epoch 7/30 [AR-SS(tf=0.32,ar=60%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:07:43<00:00,  1.42s/it, loss=4.7474, main=4.6648]

  Train: Loss=5.6547 (main=5.5818, len=0.170, tcls=0.009)
  Val:   Loss=2.1985 | PPL=9.0 | Top1=47.5% Top5=82.9% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=13.2%
  TF=0.324, AR=60%, LR=0.000046
  No improvement for 4 epoch(s)

Epoch 8/30
----------------------------------------------------------------------
Epoch 8/30 [AR-SS(tf=0.30,ar=62%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:08:56<00:00,  1.45s/it, loss=4.8050, main=4.6938]

  Train: Loss=5.6828 (main=5.6109, len=0.168, tcls=0.009)
  Val:   Loss=2.1869 | PPL=8.9 | Top1=47.7% Top5=82.9% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=14.2%
  TF=0.304, AR=62%, LR=0.000045
  No improvement for 5 epoch(s)

Epoch 9/30
----------------------------------------------------------------------
Epoch 9/30 [AR-SS(tf=0.28,ar=63%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:40:51<00:00,  2.12s/it, loss=6.6545, main=6.6113]

  Train: Loss=5.7161 (main=5.6462, len=0.168, tcls=0.010)
  Val:   Loss=2.1952 | PPL=9.0 | Top1=47.7% Top5=82.7% TF-SeqEM=2.7%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=12.3%
  TF=0.284, AR=63%, LR=0.000043
  No improvement for 6 epoch(s)

Epoch 10/30
----------------------------------------------------------------------
Epoch 10/30 [AR-SS(tf=0.26,ar=65%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:53:52<00:00,  2.39s/it, loss=6.1200, main=6.0898]

  Train: Loss=5.7449 (main=5.6760, len=0.167, tcls=0.010)
  Val:   Loss=2.2234 | PPL=9.2 | Top1=47.0% Top5=82.5% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=13.2%
  TF=0.264, AR=65%, LR=0.000041
  No improvement for 7 epoch(s)

Epoch 11/30
----------------------------------------------------------------------
Epoch 11/30 [AR-SS(tf=0.24,ar=67%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:57:43<00:00,  2.47s/it, loss=6.2918, main=6.2551]

  Train: Loss=5.7842 (main=5.7175, len=0.167, tcls=0.011)
  Val:   Loss=2.2133 | PPL=9.1 | Top1=47.3% Top5=82.5% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=12.5%
  TF=0.243, AR=67%, LR=0.000039
  No improvement for 8 epoch(s)

Epoch 12/30
----------------------------------------------------------------------
Epoch 12/30 [AR-SS(tf=0.22,ar=68%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:32:40<00:00,  1.94s/it, loss=6.1093, main=6.0485]

  Train: Loss=5.8297 (main=5.7648, len=0.166, tcls=0.011)
  Val:   Loss=2.2116 | PPL=9.1 | Top1=47.3% Top5=82.7% TF-SeqEM=2.7%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=13.2%
  TF=0.222, AR=68%, LR=0.000036
  No improvement for 9 epoch(s)

Epoch 13/30
----------------------------------------------------------------------
Epoch 13/30 [AR-SS(tf=0.20,ar=70%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:38:06<00:00,  2.06s/it, loss=5.2171, main=5.0641]

  Train: Loss=5.8682 (main=5.8050, len=0.167, tcls=0.012)
  Val:   Loss=2.2890 | PPL=9.9 | Top1=45.3% Top5=81.4% TF-SeqEM=2.1%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=12.7%
  TF=0.202, AR=70%, LR=0.000034
  No improvement for 10 epoch(s)

Epoch 14/30
----------------------------------------------------------------------
Epoch 14/30 [AR-SS(tf=0.18,ar=72%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:39:51<00:00,  2.09s/it, loss=6.7461, main=6.7124]

  Train: Loss=5.8979 (main=5.8364, len=0.167, tcls=0.013)
  Val:   Loss=2.2573 | PPL=9.6 | Top1=46.1% Top5=82.0% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=14.8%
  TF=0.182, AR=72%, LR=0.000031
  No improvement for 11 epoch(s)

Epoch 15/30
----------------------------------------------------------------------
Epoch 15/30 [AR-SS(tf=0.16,ar=73%), n=91520]: 100%|██████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:41:25<00:00,  2.13s/it, loss=6.2979, main=6.2674]

  Train: Loss=5.9184 (main=5.8586, len=0.166, tcls=0.013)
  Val:   Loss=2.2552 | PPL=9.5 | Top1=46.1% Top5=81.9% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=13.0%
  TF=0.163, AR=73%, LR=0.000028
  No improvement for 12 epoch(s)

Early stopping at epoch 15

================================================================================
Training complete! Loading best model for test evaluation...

Test Results:
  Loss=2.1737 PPL=8.8
  Top1=47.8% Top5=83.0%
  TF-SeqEM=2.7%
  AR-SeqEM=0.8% AR-TokenAcc=13.2%

History saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_4/training_history_v4_4.json

V4.4 training complete!