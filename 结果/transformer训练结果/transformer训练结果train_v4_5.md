(transformer) qy@mdzhang:~/system_redesign/src$ python -m gis_recommend.training.train_v4_5
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
V4.5 Training: Balanced Task Sampling + Stronger Task Signal
  Changes: WeightedRandomSampler + task_cls_loss_weight 0.1->0.3
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
  Unique task types in train: 120
  Top-5 task types (count): [('Land use/land cover', 29687), ('Vegetation', 16922), ('Land surface/agriculture indicators', 13093), ('Terrestrial hydrosphere indicators', 6191), ('Surface thermal properties', 3124)]
  Bot-5 task types (count): [('Geometric operations', 1), ('Deforestation', 1), ('Time/date manipulation', 1), ('Sustainability', 1), ('Vegetation Index Analysis', 1)]

[6] Creating model...
  [V4] Loaded L3 embeddings: 350 tokens from /home/qy/system_redesign/outputs/l3_embeddings.pt
  Params: 22.8M trainable, 117.5M total

[7] Loading warm-start checkpoint...
  Loading warm-start from /home/qy/system_redesign/outputs/transformer_checkpoints_v4_3/best_model.pth ...
  Model loaded (epoch 28, val_loss=2.1974

[8] Creating V4.5 trainer...
  [V4.2] Using frequency-weighted CE loss (alpha=0.5)
  [V4.2] 转移矩阵: 99 states loaded
  [V4.5] task_cls_loss_weight overridden to 0.3
  Task classifier weights loaded from V4.2

[9] V4.5 Schedule Preview:
  Warm-start: YES
  Balanced sampling: YES (WeightedRandomSampler by task type)
  task_cls_loss_weight: 0.3
  Length loss weight: 0.5
  Early END penalty: 2.0 (threshold=0.7)
  Epoch   1: tf_ratio=0.417, ar_ratio=50%
  Epoch   3: tf_ratio=0.391, ar_ratio=53%
  Epoch   6: tf_ratio=0.342, ar_ratio=58%
  Epoch  11: tf_ratio=0.243, ar_ratio=67%
  Epoch  16: tf_ratio=0.145, ar_ratio=75%
  Epoch  21: tf_ratio=0.076, ar_ratio=83%
  Epoch  30: tf_ratio=0.019, ar_ratio=98%

[10] Starting training...
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
Epoch 1/30 [AR-SS(tf=0.42,ar=50%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:15:56<00:00,  1.59s/it, loss=4.0886, main=3.9826]

  Train: Loss=4.8366 (main=4.6508, len=0.098, tcls=0.067)
  Val:   Loss=2.3110 | PPL=10.1 | Top1=46.3% Top5=81.0% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=14.3%
  TF=0.417, AR=50%, LR=0.000050
  [Diag] BERT top-layer gradients: MISSING (check Fix D)
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_5/best_model.pth (val_loss=2.3110)

Epoch 2/30
----------------------------------------------------------------------
Epoch 2/30 [AR-SS(tf=0.40,ar=52%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:18:47<00:00,  1.65s/it, loss=3.9223, main=3.8378]

  Train: Loss=4.4326 (main=4.3433, len=0.079, tcls=0.013)
  Val:   Loss=2.3244 | PPL=10.2 | Top1=45.6% Top5=80.9% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=14.3%
  TF=0.404, AR=52%, LR=0.000050
  No improvement for 1 epoch(s)

Epoch 3/30
----------------------------------------------------------------------
Epoch 3/30 [AR-SS(tf=0.39,ar=53%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:29:22<00:00,  1.88s/it, loss=4.8436, main=4.7831]

  Train: Loss=4.3168 (main=4.2407, len=0.071, tcls=0.008)
  Val:   Loss=2.3202 | PPL=10.2 | Top1=45.3% Top5=80.8% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.9%
  TF=0.391, AR=53%, LR=0.000050
  No improvement for 2 epoch(s)

Epoch 4/30
----------------------------------------------------------------------
Epoch 4/30 [AR-SS(tf=0.38,ar=55%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:29:49<00:00,  1.88s/it, loss=3.7453, main=3.6803]

  Train: Loss=4.2756 (main=4.2068, len=0.067, tcls=0.007)
  Val:   Loss=2.3109 | PPL=10.1 | Top1=45.6% Top5=81.0% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.8%
  TF=0.376, AR=55%, LR=0.000049
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_5/best_model.pth (val_loss=2.3109)

Epoch 5/30
----------------------------------------------------------------------
Epoch 5/30 [AR-SS(tf=0.36,ar=57%), n=91520]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [1:24:43<00:00,  1.78s/it, loss=3.9026, main=3.8953]

  Train: Loss=4.2422 (main=4.1784, len=0.065, tcls=0.007)
  Val:   Loss=2.3081 | PPL=10.1 | Top1=45.5% Top5=80.9% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.3%
  TF=0.360, AR=57%, LR=0.000049
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_5/best_model.pth (val_loss=2.3081)

Epoch 6/30
----------------------------------------------------------------------
Epoch 6/30 [AR-SS(tf=0.34,ar=58%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [33:29<00:00,  1.42it/s, loss=4.4919, main=4.4667]

  Train: Loss=4.2154 (main=4.1547, len=0.062, tcls=0.006)
  Val:   Loss=2.3508 | PPL=10.5 | Top1=44.2% Top5=80.3% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.9%
  TF=0.342, AR=58%, LR=0.000048
  No improvement for 1 epoch(s)

Epoch 7/30
----------------------------------------------------------------------
Epoch 7/30 [AR-SS(tf=0.32,ar=60%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [34:50<00:00,  1.37it/s, loss=4.2912, main=4.1836]

  Train: Loss=4.1968 (main=4.1397, len=0.059, tcls=0.006)
  Val:   Loss=2.3069 | PPL=10.0 | Top1=45.5% Top5=81.0% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.3%
  TF=0.324, AR=60%, LR=0.000046
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_5/best_model.pth (val_loss=2.3069)

Epoch 8/30
----------------------------------------------------------------------
Epoch 8/30 [AR-SS(tf=0.30,ar=62%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [36:18<00:00,  1.31it/s, loss=5.1281, main=5.0384]

  Train: Loss=4.1935 (main=4.1394, len=0.058, tcls=0.005)
  Val:   Loss=2.3362 | PPL=10.3 | Top1=44.7% Top5=80.6% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.0%
  TF=0.304, AR=62%, LR=0.000045
  No improvement for 1 epoch(s)

Epoch 9/30
----------------------------------------------------------------------
Epoch 9/30 [AR-SS(tf=0.28,ar=63%), n=91520]: 100%|█████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [36:12<00:00,  1.32it/s, loss=3.5824, main=3.5336]

  Train: Loss=4.1931 (main=4.1410, len=0.057, tcls=0.005)
  Val:   Loss=2.3460 | PPL=10.4 | Top1=44.3% Top5=80.4% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=13.2%
  TF=0.284, AR=63%, LR=0.000043
  No improvement for 2 epoch(s)

Epoch 10/30
----------------------------------------------------------------------
Epoch 10/30 [AR-SS(tf=0.26,ar=65%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [37:34<00:00,  1.27it/s, loss=5.1918, main=5.0914]

  Train: Loss=4.1938 (main=4.1433, len=0.056, tcls=0.006)
  Val:   Loss=2.3447 | PPL=10.4 | Top1=44.6% Top5=80.3% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=12.2%
  TF=0.264, AR=65%, LR=0.000041
  No improvement for 3 epoch(s)

Epoch 11/30
----------------------------------------------------------------------
Epoch 11/30 [AR-SS(tf=0.24,ar=67%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [40:15<00:00,  1.18it/s, loss=4.1348, main=4.1133]

  Train: Loss=4.2197 (main=4.1714, len=0.056, tcls=0.006)
  Val:   Loss=2.3920 | PPL=10.9 | Top1=43.5% Top5=79.9% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.3%
  TF=0.243, AR=67%, LR=0.000039
  No improvement for 4 epoch(s)

Epoch 12/30
----------------------------------------------------------------------
Epoch 12/30 [AR-SS(tf=0.22,ar=68%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [39:29<00:00,  1.21it/s, loss=4.7599, main=4.7366]

  Train: Loss=4.2089 (main=4.1629, len=0.054, tcls=0.006)
  Val:   Loss=2.3767 | PPL=10.8 | Top1=43.7% Top5=79.9% TF-SeqEM=2.1%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.9%
  TF=0.222, AR=68%, LR=0.000036
  No improvement for 5 epoch(s)

Epoch 13/30
----------------------------------------------------------------------
Epoch 13/30 [AR-SS(tf=0.20,ar=70%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [39:38<00:00,  1.20it/s, loss=4.2875, main=4.1879]

  Train: Loss=4.2112 (main=4.1667, len=0.054, tcls=0.006)
  Val:   Loss=2.3881 | PPL=10.9 | Top1=43.3% Top5=79.7% TF-SeqEM=2.1%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.7%
  TF=0.202, AR=70%, LR=0.000034
  No improvement for 6 epoch(s)

Epoch 14/30
----------------------------------------------------------------------
Epoch 14/30 [AR-SS(tf=0.18,ar=72%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [41:05<00:00,  1.16it/s, loss=4.4892, main=4.4436]

  Train: Loss=4.2182 (main=4.1760, len=0.053, tcls=0.007)
  Val:   Loss=2.4048 | PPL=11.1 | Top1=43.0% Top5=79.4% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.3%
  TF=0.182, AR=72%, LR=0.000031
  No improvement for 7 epoch(s)

Epoch 15/30
----------------------------------------------------------------------
Epoch 15/30 [AR-SS(tf=0.16,ar=73%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [41:04<00:00,  1.16it/s, loss=4.6108, main=4.5883]

  Train: Loss=4.2219 (main=4.1805, len=0.052, tcls=0.007)
  Val:   Loss=2.4146 | PPL=11.2 | Top1=42.7% Top5=79.2% TF-SeqEM=2.0%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=11.4%
  TF=0.163, AR=73%, LR=0.000028
  No improvement for 8 epoch(s)

Epoch 16/30
----------------------------------------------------------------------
Epoch 16/30 [AR-SS(tf=0.15,ar=75%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [42:00<00:00,  1.13it/s, loss=3.2131, main=3.1540]

  Train: Loss=4.2103 (main=4.1709, len=0.053, tcls=0.006)
  Val:   Loss=2.4349 | PPL=11.4 | Top1=42.3% Top5=79.0% TF-SeqEM=1.9%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=12.5%
  TF=0.145, AR=75%, LR=0.000026
  No improvement for 9 epoch(s)

Epoch 17/30
----------------------------------------------------------------------
Epoch 17/30 [AR-SS(tf=0.13,ar=77%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [42:32<00:00,  1.12it/s, loss=3.6509, main=3.5862]

  Train: Loss=4.2117 (main=4.1738, len=0.052, tcls=0.006)
  Val:   Loss=2.4713 | PPL=11.8 | Top1=40.9% Top5=78.1% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=13.6%
  TF=0.129, AR=77%, LR=0.000023
  No improvement for 10 epoch(s)

Epoch 18/30
----------------------------------------------------------------------
Epoch 18/30 [AR-SS(tf=0.11,ar=78%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [43:39<00:00,  1.09it/s, loss=4.4808, main=4.4690]

  Train: Loss=4.2274 (main=4.1911, len=0.052, tcls=0.007)
  Val:   Loss=2.4771 | PPL=11.9 | Top1=40.8% Top5=78.0% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=13.3%
  TF=0.114, AR=78%, LR=0.000020
  No improvement for 11 epoch(s)

Epoch 19/30
----------------------------------------------------------------------
Epoch 19/30 [AR-SS(tf=0.10,ar=80%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [44:05<00:00,  1.08it/s, loss=4.3964, main=4.3585]

  Train: Loss=4.2115 (main=4.1764, len=0.051, tcls=0.006)
  Val:   Loss=2.4738 | PPL=11.9 | Top1=41.0% Top5=78.0% TF-SeqEM=1.7%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=13.0%
  TF=0.100, AR=80%, LR=0.000017
  No improvement for 12 epoch(s)

Early stopping at epoch 19

================================================================================
Training complete! Loading best model for test evaluation...

Test Results:
  Loss=2.3019 PPL=10.0
  Top1=45.5% Top5=81.1%
  TF-SeqEM=2.5%
  AR-SeqEM=0.8% AR-TokenAcc=12.1%

History saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_5/training_history_v4_2.json

V4.5 training complete!