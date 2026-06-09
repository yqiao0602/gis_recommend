(transformer) qy@mdzhang:~/system_redesign/src$ python -m gis_recommend.training.train_v4_2
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
V4.2 Task-Conditioned L3 Transformer Training
  All bug fixes: FiLM init, BERT grad, label smooth AR, aux forward, attn mask, optimizer
================================================================================
  CUDA: Available (NVIDIA A10)
  GPU Memory: 23.7 GB

[1] Loading data...
  Workflows: 114401

[2] Loading task type vocabulary...
  Task types: 132
  BERT tokenizer loaded

[3] Splitting dataset...
  Created new splits: train=91520, val=11440, test=11441
  Train: 91520, Val: 11440, Test: 11441

[4] Computing token frequency weights...
  Lowest weights (most frequent): [(350, '0.000'), (345, '0.098'), (115, '0.118'), (133, '0.127'), (352, '0.131')]
  Highest weights (least frequent): ['3.554', '3.526', '3.298', '2.872', '2.800']

[5] Creating datasets...

[6] Creating V4 model (with FiLM init fix)...
  [V4] Loaded L3 embeddings: 350 tokens from /home/qy/system_redesign/outputs/l3_embeddings.pt
  [Verify] FiLM gamma diagonal mean: 1.0000 (should be ~1.0)
  [Verify] FiLM gamma off-diagonal mean: 0.000000 (should be ~0.0)
  Total params: 117.5M
  Trainable: 22.8M (BERT: 14.8M, Other: 8.0M)

[7] Forward pass verification...
  logits: (32, 100, 354)
  length_pred: (32, 1)
  contrastive_repr: (32, 128)

[8] Starting V4.2 training...
  [V4.2] Using frequency-weighted CE loss (alpha=0.5)
  [V4.2] 转移矩阵: 99 states loaded
================================================================================
V4.2 Training: All Bug Fixes + Low-VRAM Optimization
================================================================================
  Device: cuda, AMP: True
  Batch: 32 x 1 accum = 32 effective
  LR: BERT=1.0e-05, Other=1.0e-04
  TF Phase: epoch 0-9, then AR-SS
  AR ratio: 10% -> 70% (gradual)
  AR max steps: 40
  AR sampling: temp=0.8, top_p=0.9
  Decode rep penalty: 2.0, window=3
  Curriculum: phase1 <=8 (ep 0-5), phase2 <=15 (ep 6-15)
  Warmup: 3 epochs, Patience: 18
  Fixes applied: FiLM init, BERT grad, label smooth AR, aux from forward, attn mask, optimizer
================================================================================

Epoch 1/60
----------------------------------------------------------------------
Epoch 1/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:47<00:00,  7.36it/s, loss=6.5375, main=6.4808]

  Train: Loss=7.1059 (main=6.9261, len=0.148, tcls=1.123)
  Val:   Loss=4.1559 | PPL=63.8 | Top1=11.4% Top5=39.3% TF-SeqEM=0.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=4.8%
  TF=1.000, AR=0%, LR=0.000100
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=4.1559)

Epoch 2/60
----------------------------------------------------------------------
Epoch 2/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:42<00:00,  7.62it/s, loss=6.5068, main=6.4616]

  Train: Loss=6.3223 (main=6.2626, len=0.073, tcls=0.163)
  Val:   Loss=3.9595 | PPL=52.4 | Top1=15.3% Top5=43.5% TF-SeqEM=0.1%
  TF=1.000, AR=0%, LR=0.000100
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=3.9595)

Epoch 3/60
----------------------------------------------------------------------
Epoch 3/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:42<00:00,  7.61it/s, loss=6.1314, main=6.0811]

  Train: Loss=5.9870 (main=5.9349, len=0.071, tcls=0.096)
  Val:   Loss=3.9257 | PPL=50.7 | Top1=18.5% Top5=46.7% TF-SeqEM=0.5%
  TF=1.000, AR=0%, LR=0.000100
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=3.9257)

Epoch 4/60
----------------------------------------------------------------------
Epoch 4/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:42<00:00,  7.59it/s, loss=5.8429, main=5.7995]

  Train: Loss=5.7762 (main=5.7279, len=0.070, tcls=0.062)
  Val:   Loss=3.8710 | PPL=48.0 | Top1=19.9% Top5=48.4% TF-SeqEM=0.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=6.3%
  TF=1.000, AR=0%, LR=0.000100
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=3.8710)

Epoch 5/60
----------------------------------------------------------------------
Epoch 5/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:43<00:00,  7.58it/s, loss=5.2359, main=5.1849]

  Train: Loss=5.6456 (main=5.5994, len=0.070, tcls=0.044)
  Val:   Loss=3.8745 | PPL=48.2 | Top1=20.9% Top5=49.4% TF-SeqEM=0.8%
  TF=1.000, AR=0%, LR=0.000100
  No improvement for 1 epoch(s)

Epoch 6/60
----------------------------------------------------------------------
Epoch 6/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:41<00:00,  7.65it/s, loss=5.8847, main=5.8370]

  Train: Loss=5.5471 (main=5.5023, len=0.069, tcls=0.033)
  Val:   Loss=4.0310 | PPL=56.3 | Top1=21.5% Top5=48.3% TF-SeqEM=1.1%
  TF=1.000, AR=0%, LR=0.000099
  No improvement for 2 epoch(s)

Epoch 7/60
----------------------------------------------------------------------
  [Curriculum] Phase 0 -> 1, resetting patience
Epoch 7/60 [TF, n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [04:47<00:00,  7.20it/s, loss=5.6841, main=5.6385]

  Train: Loss=5.6135 (main=5.5622, len=0.140, tcls=0.026)
  Val:   Loss=2.9224 | PPL=18.6 | Top1=30.5% Top5=67.9% TF-SeqEM=1.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.5%
  TF=1.000, AR=0%, LR=0.000099
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.9224)

Epoch 8/60
----------------------------------------------------------------------
Epoch 8/60 [TF, n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [04:46<00:00,  7.22it/s, loss=5.4503, main=5.4095]

  Train: Loss=5.4942 (main=5.4444, len=0.134, tcls=0.019)
  Val:   Loss=2.9191 | PPL=18.5 | Top1=31.8% Top5=67.8% TF-SeqEM=1.2%
  TF=1.000, AR=0%, LR=0.000098
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.9191)

Epoch 9/60
----------------------------------------------------------------------
Epoch 9/60 [TF, n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [04:43<00:00,  7.30it/s, loss=5.3693, main=5.3218]

  Train: Loss=5.4130 (main=5.3638, len=0.131, tcls=0.016)
  Val:   Loss=3.0101 | PPL=20.3 | Top1=32.1% Top5=67.0% TF-SeqEM=1.3%
  TF=1.000, AR=0%, LR=0.000097
  No improvement for 1 epoch(s)

Epoch 10/60
----------------------------------------------------------------------
Epoch 10/60 [TF, n=66173]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [04:40<00:00,  7.36it/s, loss=4.9852, main=4.9255]

  Train: Loss=5.3450 (main=5.2962, len=0.129, tcls=0.013)
  Val:   Loss=2.9531 | PPL=19.2 | Top1=33.0% Top5=68.6% TF-SeqEM=1.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=9.5%
  TF=1.000, AR=0%, LR=0.000096
  No improvement for 2 epoch(s)

Epoch 11/60
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling, resetting patience
Epoch 11/60 [AR-SS(tf=0.85,ar=10%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:08<00:00,  5.61it/s, loss=5.6730, main=5.6226]

  Train: Loss=5.3416 (main=5.2773, len=0.127, tcls=0.012)
  Val:   Loss=3.0303 | PPL=20.7 | Top1=32.9% Top5=67.5% TF-SeqEM=1.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=7.2%
  TF=0.850, AR=10%, LR=0.000095
  [Diag] BERT top-layer gradients: MISSING (check Fix D)
  No improvement for 1 epoch(s)

Epoch 12/60
----------------------------------------------------------------------
Epoch 12/60 [AR-SS(tf=0.84,ar=11%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:29<00:00,  5.31it/s, loss=5.2147, main=5.1670]

  Train: Loss=5.2992 (main=5.2392, len=0.126, tcls=0.011)
  Val:   Loss=3.1281 | PPL=22.8 | Top1=33.3% Top5=66.1% TF-SeqEM=1.7%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=9.7%
  TF=0.837, AR=11%, LR=0.000094
  No improvement for 2 epoch(s)

Epoch 13/60
----------------------------------------------------------------------
Epoch 13/60 [AR-SS(tf=0.82,ar=12%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:28<00:00,  5.32it/s, loss=5.5006, main=5.4526]

  Train: Loss=5.2554 (main=5.1989, len=0.125, tcls=0.011)
  Val:   Loss=3.1332 | PPL=22.9 | Top1=33.4% Top5=65.1% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.3%
  TF=0.823, AR=12%, LR=0.000093
  No improvement for 3 epoch(s)

Epoch 14/60
----------------------------------------------------------------------
Epoch 14/60 [AR-SS(tf=0.81,ar=14%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:40<00:00,  5.16it/s, loss=4.9356, main=4.8889]

  Train: Loss=5.2264 (main=5.1707, len=0.123, tcls=0.009)
  Val:   Loss=3.1128 | PPL=22.5 | Top1=33.8% Top5=65.8% TF-SeqEM=1.9%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.7%
  TF=0.809, AR=14%, LR=0.000091
  No improvement for 4 epoch(s)

Epoch 15/60
----------------------------------------------------------------------
Epoch 15/60 [AR-SS(tf=0.79,ar=15%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:40<00:00,  5.16it/s, loss=4.6554, main=4.5963]

  Train: Loss=5.1913 (main=5.1369, len=0.122, tcls=0.010)
  Val:   Loss=3.1649 | PPL=23.7 | Top1=33.7% Top5=65.1% TF-SeqEM=1.9%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=9.9%
  TF=0.793, AR=15%, LR=0.000090
  No improvement for 5 epoch(s)

Epoch 16/60
----------------------------------------------------------------------
Epoch 16/60 [AR-SS(tf=0.78,ar=16%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:47<00:00,  5.07it/s, loss=5.1994, main=5.1521]

  Train: Loss=5.1580 (main=5.1041, len=0.122, tcls=0.009)
  Val:   Loss=3.1693 | PPL=23.8 | Top1=34.1% Top5=65.2% TF-SeqEM=2.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.3%
  TF=0.777, AR=16%, LR=0.000088
  No improvement for 6 epoch(s)

Epoch 17/60
----------------------------------------------------------------------
  [Curriculum] Phase 1 -> 2, resetting patience
Epoch 17/60 [AR-SS(tf=0.76,ar=17%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [15:13<00:00,  3.13it/s, loss=5.3957, main=5.3333]

  Train: Loss=5.4679 (main=5.4053, len=0.229, tcls=0.013)
  Val:   Loss=2.4003 | PPL=11.0 | Top1=41.4% Top5=78.6% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=9.7%
  TF=0.760, AR=17%, LR=0.000086
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.4003)

Epoch 18/60
----------------------------------------------------------------------
Epoch 18/60 [AR-SS(tf=0.74,ar=18%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [16:04<00:00,  2.96it/s, loss=5.7167, main=5.6527]

  Train: Loss=5.3862 (main=5.3252, len=0.217, tcls=0.010)
  Val:   Loss=2.3519 | PPL=10.5 | Top1=42.5% Top5=79.4% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.5%
  TF=0.742, AR=18%, LR=0.000084
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.3519)

Epoch 19/60
----------------------------------------------------------------------
Epoch 19/60 [AR-SS(tf=0.72,ar=20%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [16:04<00:00,  2.96it/s, loss=5.2757, main=5.2096]

  Train: Loss=5.3309 (main=5.2712, len=0.213, tcls=0.009)
  Val:   Loss=2.3179 | PPL=10.2 | Top1=43.5% Top5=80.3% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.7%
  TF=0.723, AR=20%, LR=0.000082
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.3179)

Epoch 20/60
----------------------------------------------------------------------
Epoch 20/60 [AR-SS(tf=0.70,ar=21%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [16:40<00:00,  2.86it/s, loss=5.5429, main=5.4751]

  Train: Loss=5.3023 (main=5.2432, len=0.210, tcls=0.008)
  Val:   Loss=2.3082 | PPL=10.1 | Top1=43.9% Top5=80.4% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.2%
  TF=0.703, AR=21%, LR=0.000080
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.3082)

Epoch 21/60
----------------------------------------------------------------------
Epoch 21/60 [AR-SS(tf=0.68,ar=22%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [16:54<00:00,  2.82it/s, loss=5.2078, main=5.1485]

  Train: Loss=5.2761 (main=5.2179, len=0.206, tcls=0.008)
  Val:   Loss=2.2852 | PPL=9.8 | Top1=44.6% Top5=80.9% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.5%
  TF=0.683, AR=22%, LR=0.000078
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2852)

Epoch 22/60
----------------------------------------------------------------------
Epoch 22/60 [AR-SS(tf=0.66,ar=23%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [17:15<00:00,  2.76it/s, loss=6.0377, main=5.9689]

  Train: Loss=5.2579 (main=5.2001, len=0.203, tcls=0.007)
  Val:   Loss=2.2805 | PPL=9.8 | Top1=44.9% Top5=81.1% TF-SeqEM=2.0%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.3%
  TF=0.662, AR=23%, LR=0.000075
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2805)

Epoch 23/60
----------------------------------------------------------------------
Epoch 23/60 [AR-SS(tf=0.64,ar=24%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [17:53<00:00,  2.66it/s, loss=6.4804, main=6.3872]

  Train: Loss=5.2420 (main=5.1845, len=0.200, tcls=0.008)
  Val:   Loss=2.2495 | PPL=9.5 | Top1=45.8% Top5=81.6% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.2%
  TF=0.641, AR=24%, LR=0.000073
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2495)

Epoch 24/60
----------------------------------------------------------------------
Epoch 24/60 [AR-SS(tf=0.62,ar=26%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [19:14<00:00,  2.48it/s, loss=4.9029, main=4.8565]

  Train: Loss=5.2658 (main=5.2087, len=0.200, tcls=0.007)
  Val:   Loss=2.2509 | PPL=9.5 | Top1=46.0% Top5=81.9% TF-SeqEM=2.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.5%
  TF=0.619, AR=26%, LR=0.000070
  No improvement for 1 epoch(s)

Epoch 25/60
----------------------------------------------------------------------
Epoch 25/60 [AR-SS(tf=0.60,ar=27%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [19:28<00:00,  2.45it/s, loss=4.6180, main=4.5679]

  Train: Loss=5.2562 (main=5.1998, len=0.197, tcls=0.007)
  Val:   Loss=2.2213 | PPL=9.2 | Top1=46.5% Top5=82.1% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.3%
  TF=0.597, AR=27%, LR=0.000068
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2213)

Epoch 26/60
----------------------------------------------------------------------
Epoch 26/60 [AR-SS(tf=0.57,ar=28%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [19:49<00:00,  2.40it/s, loss=4.6040, main=4.5512]

  Train: Loss=5.2518 (main=5.1955, len=0.196, tcls=0.007)
  Val:   Loss=2.2090 | PPL=9.1 | Top1=47.1% Top5=82.7% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.9%
  TF=0.575, AR=28%, LR=0.000065
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2090)

Epoch 27/60
----------------------------------------------------------------------
Epoch 27/60 [AR-SS(tf=0.55,ar=29%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [20:15<00:00,  2.35it/s, loss=5.0648, main=5.0131]

  Train: Loss=5.2506 (main=5.1945, len=0.194, tcls=0.007)
  Val:   Loss=2.1976 | PPL=9.0 | Top1=47.1% Top5=82.5% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.8%
  TF=0.552, AR=29%, LR=0.000063
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1976)

Epoch 28/60
----------------------------------------------------------------------
Epoch 28/60 [AR-SS(tf=0.53,ar=30%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [21:08<00:00,  2.25it/s, loss=4.9953, main=4.9368]

  Train: Loss=5.2698 (main=5.2140, len=0.193, tcls=0.007)
  Val:   Loss=2.2109 | PPL=9.1 | Top1=47.1% Top5=82.8% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.2%
  TF=0.530, AR=30%, LR=0.000060
  No improvement for 1 epoch(s)

Epoch 29/60
----------------------------------------------------------------------
Epoch 29/60 [AR-SS(tf=0.51,ar=32%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [22:06<00:00,  2.16it/s, loss=4.9975, main=4.9503]

  Train: Loss=5.2874 (main=5.2324, len=0.192, tcls=0.007)
  Val:   Loss=2.1957 | PPL=9.0 | Top1=47.3% Top5=82.6% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.3%
  TF=0.507, AR=32%, LR=0.000057
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1957)

Epoch 30/60
----------------------------------------------------------------------
Epoch 30/60 [AR-SS(tf=0.49,ar=33%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [21:37<00:00,  2.20it/s, loss=4.8151, main=4.7510]

  Train: Loss=5.2744 (main=5.2194, len=0.191, tcls=0.007)
  Val:   Loss=2.1783 | PPL=8.8 | Top1=47.7% Top5=82.9% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.7%
  TF=0.485, AR=33%, LR=0.000055
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1783)

Epoch 31/60
----------------------------------------------------------------------
Epoch 31/60 [AR-SS(tf=0.46,ar=34%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [22:26<00:00,  2.12it/s, loss=5.7847, main=5.7093]

  Train: Loss=5.2988 (main=5.2439, len=0.189, tcls=0.007)
  Val:   Loss=2.1876 | PPL=8.9 | Top1=47.3% Top5=82.6% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.2%
  TF=0.463, AR=34%, LR=0.000052
  No improvement for 1 epoch(s)

Epoch 32/60
----------------------------------------------------------------------
Epoch 32/60 [AR-SS(tf=0.44,ar=35%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [23:25<00:00,  2.04it/s, loss=6.1704, main=6.1184]

  Train: Loss=5.3224 (main=5.2677, len=0.189, tcls=0.008)
  Val:   Loss=2.2056 | PPL=9.1 | Top1=47.3% Top5=82.7% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.5%
  TF=0.442, AR=35%, LR=0.000049
  No improvement for 2 epoch(s)

Epoch 33/60
----------------------------------------------------------------------
Epoch 33/60 [AR-SS(tf=0.42,ar=36%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [24:01<00:00,  1.98it/s, loss=4.9846, main=4.9288]

  Train: Loss=5.3473 (main=5.2929, len=0.188, tcls=0.008)
  Val:   Loss=2.1904 | PPL=8.9 | Top1=47.5% Top5=82.7% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=9.8%
  TF=0.421, AR=36%, LR=0.000046
  No improvement for 3 epoch(s)

Epoch 34/60
----------------------------------------------------------------------
Epoch 34/60 [AR-SS(tf=0.40,ar=38%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [24:40<00:00,  1.93it/s, loss=4.7254, main=4.6632]

  Train: Loss=5.3609 (main=5.3072, len=0.187, tcls=0.007)
  Val:   Loss=2.1882 | PPL=8.9 | Top1=47.9% Top5=83.2% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.3%
  TF=0.401, AR=38%, LR=0.000044
  No improvement for 4 epoch(s)

Epoch 35/60
----------------------------------------------------------------------
Epoch 35/60 [AR-SS(tf=0.38,ar=39%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [24:15<00:00,  1.96it/s, loss=4.7158, main=4.6578]

  Train: Loss=5.3442 (main=5.2903, len=0.186, tcls=0.007)
  Val:   Loss=2.1773 | PPL=8.8 | Top1=48.0% Top5=82.9% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=13.2%
  TF=0.381, AR=39%, LR=0.000041
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1773)

Epoch 36/60
----------------------------------------------------------------------
Epoch 36/60 [AR-SS(tf=0.36,ar=40%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [25:57<00:00,  1.84it/s, loss=4.9805, main=4.9224]

  Train: Loss=5.3907 (main=5.3372, len=0.186, tcls=0.007)
  Val:   Loss=2.1638 | PPL=8.7 | Top1=48.3% Top5=83.2% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.8%
  TF=0.362, AR=40%, LR=0.000038
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1638)

Epoch 37/60
----------------------------------------------------------------------
Epoch 37/60 [AR-SS(tf=0.34,ar=41%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [26:15<00:00,  1.82it/s, loss=4.5062, main=4.4421]

  Train: Loss=5.4183 (main=5.3651, len=0.185, tcls=0.007)
  Val:   Loss=2.1824 | PPL=8.9 | Top1=47.7% Top5=82.9% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.0%
  TF=0.344, AR=41%, LR=0.000036
  No improvement for 1 epoch(s)

Epoch 38/60
----------------------------------------------------------------------
Epoch 38/60 [AR-SS(tf=0.33,ar=42%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [27:05<00:00,  1.76it/s, loss=4.6780, main=4.6273]

  Train: Loss=5.4438 (main=5.3910, len=0.185, tcls=0.007)
  Val:   Loss=2.1759 | PPL=8.8 | Top1=48.1% Top5=83.2% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.3%
  TF=0.326, AR=42%, LR=0.000033
  No improvement for 2 epoch(s)

Epoch 39/60
----------------------------------------------------------------------
Epoch 39/60 [AR-SS(tf=0.31,ar=44%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [27:01<00:00,  1.76it/s, loss=6.4847, main=6.4662]

  Train: Loss=5.4442 (main=5.3919, len=0.184, tcls=0.007)
  Val:   Loss=2.1610 | PPL=8.7 | Top1=48.5% Top5=83.2% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.7%
  TF=0.310, AR=44%, LR=0.000031
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1610)

Epoch 40/60
----------------------------------------------------------------------
Epoch 40/60 [AR-SS(tf=0.29,ar=45%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [27:42<00:00,  1.72it/s, loss=6.3288, main=6.2876]

  Train: Loss=5.4689 (main=5.4167, len=0.184, tcls=0.007)
  Val:   Loss=2.1594 | PPL=8.7 | Top1=48.4% Top5=83.4% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.5%
  TF=0.294, AR=45%, LR=0.000028
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1594)

Epoch 41/60
----------------------------------------------------------------------
Epoch 41/60 [AR-SS(tf=0.28,ar=46%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [29:09<00:00,  1.64it/s, loss=6.6431, main=6.6023]

  Train: Loss=5.5248 (main=5.4728, len=0.183, tcls=0.008)
  Val:   Loss=2.1764 | PPL=8.8 | Top1=48.3% Top5=83.1% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.7%
  TF=0.279, AR=46%, LR=0.000026
  No improvement for 1 epoch(s)

Epoch 42/60
----------------------------------------------------------------------
Epoch 42/60 [AR-SS(tf=0.27,ar=47%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [28:34<00:00,  1.67it/s, loss=4.0672, main=4.0098]

  Train: Loss=5.5049 (main=5.4532, len=0.184, tcls=0.008)
  Val:   Loss=2.1703 | PPL=8.8 | Top1=48.1% Top5=83.1% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=9.9%
  TF=0.265, AR=47%, LR=0.000023
  No improvement for 2 epoch(s)

Epoch 43/60
----------------------------------------------------------------------
Epoch 43/60 [AR-SS(tf=0.25,ar=48%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [29:55<00:00,  1.59it/s, loss=6.2148, main=6.1748]

  Train: Loss=5.5590 (main=5.5075, len=0.183, tcls=0.007)
  Val:   Loss=2.1602 | PPL=8.7 | Top1=48.4% Top5=83.3% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.0%
  TF=0.252, AR=48%, LR=0.000021
  No improvement for 3 epoch(s)

Epoch 44/60
----------------------------------------------------------------------
Epoch 44/60 [AR-SS(tf=0.24,ar=50%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [30:46<00:00,  1.55it/s, loss=4.8382, main=4.7827]

  Train: Loss=5.5764 (main=5.5252, len=0.183, tcls=0.008)
  Val:   Loss=2.1723 | PPL=8.8 | Top1=48.2% Top5=83.2% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.7%
  TF=0.240, AR=50%, LR=0.000019
  No improvement for 4 epoch(s)

Epoch 45/60
----------------------------------------------------------------------
Epoch 45/60 [AR-SS(tf=0.23,ar=51%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [30:13<00:00,  1.58it/s, loss=5.9799, main=5.9375]

  Train: Loss=5.5712 (main=5.5202, len=0.183, tcls=0.008)
  Val:   Loss=2.1725 | PPL=8.8 | Top1=48.1% Top5=83.1% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.8%
  TF=0.229, AR=51%, LR=0.000017
  No improvement for 5 epoch(s)

Epoch 46/60
----------------------------------------------------------------------
Epoch 46/60 [AR-SS(tf=0.22,ar=52%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [30:40<00:00,  1.55it/s, loss=6.1970, main=6.1749]

  Train: Loss=5.5856 (main=5.5348, len=0.183, tcls=0.008)
  Val:   Loss=2.1786 | PPL=8.8 | Top1=48.1% Top5=83.1% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.0%
  TF=0.218, AR=52%, LR=0.000015
  No improvement for 6 epoch(s)

Epoch 47/60
----------------------------------------------------------------------
Epoch 47/60 [AR-SS(tf=0.21,ar=53%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [31:49<00:00,  1.50it/s, loss=5.9469, main=5.9107]

  Train: Loss=5.6260 (main=5.5755, len=0.182, tcls=0.008)
  Val:   Loss=2.1761 | PPL=8.8 | Top1=48.1% Top5=83.1% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.8%
  TF=0.208, AR=53%, LR=0.000013
  No improvement for 7 epoch(s)

Epoch 48/60
----------------------------------------------------------------------
Epoch 48/60 [AR-SS(tf=0.20,ar=54%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [31:54<00:00,  1.49it/s, loss=4.6972, main=4.6343]

  Train: Loss=5.6276 (main=5.5769, len=0.183, tcls=0.008)
  Val:   Loss=2.1682 | PPL=8.7 | Top1=48.3% Top5=83.3% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.4%
  TF=0.199, AR=54%, LR=0.000011
  No improvement for 8 epoch(s)

Epoch 49/60
----------------------------------------------------------------------
Epoch 49/60 [AR-SS(tf=0.19,ar=56%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [32:53<00:00,  1.45it/s, loss=5.0414, main=4.9919]

  Train: Loss=5.6599 (main=5.6097, len=0.183, tcls=0.008)
  Val:   Loss=2.1757 | PPL=8.8 | Top1=48.2% Top5=83.2% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.7%
  TF=0.191, AR=56%, LR=0.000010
  No improvement for 9 epoch(s)

Epoch 50/60
----------------------------------------------------------------------
Epoch 50/60 [AR-SS(tf=0.18,ar=57%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [33:28<00:00,  1.42it/s, loss=6.3259, main=6.2978]

  Train: Loss=5.6728 (main=5.6228, len=0.182, tcls=0.008)
  Val:   Loss=2.1808 | PPL=8.9 | Top1=48.0% Top5=83.0% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.9%
  TF=0.183, AR=57%, LR=0.000008
  No improvement for 10 epoch(s)

Epoch 51/60
----------------------------------------------------------------------
Epoch 51/60 [AR-SS(tf=0.18,ar=58%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [34:32<00:00,  1.38it/s, loss=5.9679, main=5.9436]

  Train: Loss=5.7155 (main=5.6658, len=0.182, tcls=0.009)
  Val:   Loss=2.1801 | PPL=8.8 | Top1=48.0% Top5=83.1% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.6%
  TF=0.176, AR=58%, LR=0.000007
  No improvement for 11 epoch(s)

Epoch 52/60
----------------------------------------------------------------------
Epoch 52/60 [AR-SS(tf=0.17,ar=59%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [34:52<00:00,  1.37it/s, loss=6.7310, main=6.6628]

  Train: Loss=5.7276 (main=5.6782, len=0.182, tcls=0.008)
  Val:   Loss=2.1815 | PPL=8.9 | Top1=48.0% Top5=83.0% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.3%
  TF=0.169, AR=59%, LR=0.000006
  No improvement for 12 epoch(s)

Epoch 53/60
----------------------------------------------------------------------
Epoch 53/60 [AR-SS(tf=0.16,ar=60%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [34:41<00:00,  1.37it/s, loss=4.8249, main=4.7658]

  Train: Loss=5.7263 (main=5.6768, len=0.182, tcls=0.009)
  Val:   Loss=2.1833 | PPL=8.9 | Top1=48.0% Top5=83.0% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.5%
  TF=0.163, AR=60%, LR=0.000005
  No improvement for 13 epoch(s)

Epoch 54/60
----------------------------------------------------------------------
Epoch 54/60 [AR-SS(tf=0.16,ar=62%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [36:04<00:00,  1.32it/s, loss=6.4064, main=6.3490]

  Train: Loss=5.7659 (main=5.7170, len=0.181, tcls=0.009)
  Val:   Loss=2.1902 | PPL=8.9 | Top1=48.0% Top5=82.9% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.0%
  TF=0.157, AR=62%, LR=0.000004
  No improvement for 14 epoch(s)

Epoch 55/60
----------------------------------------------------------------------
Epoch 55/60 [AR-SS(tf=0.15,ar=63%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [35:59<00:00,  1.32it/s, loss=5.2729, main=5.2119]

  Train: Loss=5.7671 (main=5.7182, len=0.183, tcls=0.009)
  Val:   Loss=2.1950 | PPL=9.0 | Top1=47.8% Top5=82.9% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.2%
  TF=0.152, AR=63%, LR=0.000003
  No improvement for 15 epoch(s)

Epoch 56/60
----------------------------------------------------------------------
Epoch 56/60 [AR-SS(tf=0.15,ar=64%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [36:47<00:00,  1.30it/s, loss=6.4274, main=6.3658]

  Train: Loss=5.7931 (main=5.7446, len=0.183, tcls=0.009)
  Val:   Loss=2.1893 | PPL=8.9 | Top1=47.9% Top5=83.0% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=11.8%
  TF=0.147, AR=64%, LR=0.000002
  No improvement for 16 epoch(s)

Epoch 57/60
----------------------------------------------------------------------
Epoch 57/60 [AR-SS(tf=0.14,ar=65%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [37:10<00:00,  1.28it/s, loss=4.9554, main=4.8873]

  Train: Loss=5.8253 (main=5.7768, len=0.182, tcls=0.010)
  Val:   Loss=2.2103 | PPL=9.1 | Top1=47.6% Top5=82.8% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.4%
  TF=0.143, AR=65%, LR=0.000002
  No improvement for 17 epoch(s)

Epoch 58/60
----------------------------------------------------------------------
Epoch 58/60 [AR-SS(tf=0.14,ar=66%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [37:42<00:00,  1.26it/s, loss=6.5628, main=6.5224]

  Train: Loss=5.8614 (main=5.8133, len=0.182, tcls=0.010)
  Val:   Loss=2.2025 | PPL=9.0 | Top1=47.7% Top5=82.7% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.5%
  TF=0.139, AR=66%, LR=0.000001
  No improvement for 18 epoch(s)

Early stopping at epoch 58

================================================================================
Training complete! Loading best model for test evaluation...

Test Results:
  Loss=2.1520 PPL=8.6
  Top1=48.5% Top5=83.4%
  TF-SeqEM=2.6%
  AR-SeqEM=0.0% AR-TokenAcc=13.3%

History saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/training_history_v4_2.json

Done!(transformer) qy@mdzhang:~/system_redesign/src$ python -m gis_recommend.training.train_v4_2
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
V4.2 Task-Conditioned L3 Transformer Training
  All bug fixes: FiLM init, BERT grad, label smooth AR, aux forward, attn mask, optimizer
================================================================================
  CUDA: Available (NVIDIA A10)
  GPU Memory: 23.7 GB

[1] Loading data...
  Workflows: 114401

[2] Loading task type vocabulary...
  Task types: 132
  BERT tokenizer loaded

[3] Splitting dataset...
  Created new splits: train=91520, val=11440, test=11441
  Train: 91520, Val: 11440, Test: 11441

[4] Computing token frequency weights...
  Lowest weights (most frequent): [(350, '0.000'), (345, '0.098'), (115, '0.118'), (133, '0.127'), (352, '0.131')]
  Highest weights (least frequent): ['3.554', '3.526', '3.298', '2.872', '2.800']

[5] Creating datasets...

[6] Creating V4 model (with FiLM init fix)...
  [V4] Loaded L3 embeddings: 350 tokens from /home/qy/system_redesign/outputs/l3_embeddings.pt
  [Verify] FiLM gamma diagonal mean: 1.0000 (should be ~1.0)
  [Verify] FiLM gamma off-diagonal mean: 0.000000 (should be ~0.0)
  Total params: 117.5M
  Trainable: 22.8M (BERT: 14.8M, Other: 8.0M)

[7] Forward pass verification...
  logits: (32, 100, 354)
  length_pred: (32, 1)
  contrastive_repr: (32, 128)

[8] Starting V4.2 training...
  [V4.2] Using frequency-weighted CE loss (alpha=0.5)
  [V4.2] 转移矩阵: 99 states loaded
================================================================================
V4.2 Training: All Bug Fixes + Low-VRAM Optimization
================================================================================
  Device: cuda, AMP: True
  Batch: 32 x 1 accum = 32 effective
  LR: BERT=1.0e-05, Other=1.0e-04
  TF Phase: epoch 0-9, then AR-SS
  AR ratio: 10% -> 70% (gradual)
  AR max steps: 40
  AR sampling: temp=0.8, top_p=0.9
  Decode rep penalty: 2.0, window=3
  Curriculum: phase1 <=8 (ep 0-5), phase2 <=15 (ep 6-15)
  Warmup: 3 epochs, Patience: 18
  Fixes applied: FiLM init, BERT grad, label smooth AR, aux from forward, attn mask, optimizer
================================================================================

Epoch 1/60
----------------------------------------------------------------------
Epoch 1/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:47<00:00,  7.36it/s, loss=6.5375, main=6.4808]

  Train: Loss=7.1059 (main=6.9261, len=0.148, tcls=1.123)
  Val:   Loss=4.1559 | PPL=63.8 | Top1=11.4% Top5=39.3% TF-SeqEM=0.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=4.8%
  TF=1.000, AR=0%, LR=0.000100
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=4.1559)

Epoch 2/60
----------------------------------------------------------------------
Epoch 2/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:42<00:00,  7.62it/s, loss=6.5068, main=6.4616]

  Train: Loss=6.3223 (main=6.2626, len=0.073, tcls=0.163)
  Val:   Loss=3.9595 | PPL=52.4 | Top1=15.3% Top5=43.5% TF-SeqEM=0.1%
  TF=1.000, AR=0%, LR=0.000100
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=3.9595)

Epoch 3/60
----------------------------------------------------------------------
Epoch 3/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:42<00:00,  7.61it/s, loss=6.1314, main=6.0811]

  Train: Loss=5.9870 (main=5.9349, len=0.071, tcls=0.096)
  Val:   Loss=3.9257 | PPL=50.7 | Top1=18.5% Top5=46.7% TF-SeqEM=0.5%
  TF=1.000, AR=0%, LR=0.000100
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=3.9257)

Epoch 4/60
----------------------------------------------------------------------
Epoch 4/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:42<00:00,  7.59it/s, loss=5.8429, main=5.7995]

  Train: Loss=5.7762 (main=5.7279, len=0.070, tcls=0.062)
  Val:   Loss=3.8710 | PPL=48.0 | Top1=19.9% Top5=48.4% TF-SeqEM=0.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=6.3%
  TF=1.000, AR=0%, LR=0.000100
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=3.8710)

Epoch 5/60
----------------------------------------------------------------------
Epoch 5/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:43<00:00,  7.58it/s, loss=5.2359, main=5.1849]

  Train: Loss=5.6456 (main=5.5994, len=0.070, tcls=0.044)
  Val:   Loss=3.8745 | PPL=48.2 | Top1=20.9% Top5=49.4% TF-SeqEM=0.8%
  TF=1.000, AR=0%, LR=0.000100
  No improvement for 1 epoch(s)

Epoch 6/60
----------------------------------------------------------------------
Epoch 6/60 [TF, n=39535]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 1235/1235 [02:41<00:00,  7.65it/s, loss=5.8847, main=5.8370]

  Train: Loss=5.5471 (main=5.5023, len=0.069, tcls=0.033)
  Val:   Loss=4.0310 | PPL=56.3 | Top1=21.5% Top5=48.3% TF-SeqEM=1.1%
  TF=1.000, AR=0%, LR=0.000099
  No improvement for 2 epoch(s)

Epoch 7/60
----------------------------------------------------------------------
  [Curriculum] Phase 0 -> 1, resetting patience
Epoch 7/60 [TF, n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [04:47<00:00,  7.20it/s, loss=5.6841, main=5.6385]

  Train: Loss=5.6135 (main=5.5622, len=0.140, tcls=0.026)
  Val:   Loss=2.9224 | PPL=18.6 | Top1=30.5% Top5=67.9% TF-SeqEM=1.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.5%
  TF=1.000, AR=0%, LR=0.000099
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.9224)

Epoch 8/60
----------------------------------------------------------------------
Epoch 8/60 [TF, n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [04:46<00:00,  7.22it/s, loss=5.4503, main=5.4095]

  Train: Loss=5.4942 (main=5.4444, len=0.134, tcls=0.019)
  Val:   Loss=2.9191 | PPL=18.5 | Top1=31.8% Top5=67.8% TF-SeqEM=1.2%
  TF=1.000, AR=0%, LR=0.000098
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.9191)

Epoch 9/60
----------------------------------------------------------------------
Epoch 9/60 [TF, n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [04:43<00:00,  7.30it/s, loss=5.3693, main=5.3218]

  Train: Loss=5.4130 (main=5.3638, len=0.131, tcls=0.016)
  Val:   Loss=3.0101 | PPL=20.3 | Top1=32.1% Top5=67.0% TF-SeqEM=1.3%
  TF=1.000, AR=0%, LR=0.000097
  No improvement for 1 epoch(s)

Epoch 10/60
----------------------------------------------------------------------
Epoch 10/60 [TF, n=66173]: 100%|███████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [04:40<00:00,  7.36it/s, loss=4.9852, main=4.9255]

  Train: Loss=5.3450 (main=5.2962, len=0.129, tcls=0.013)
  Val:   Loss=2.9531 | PPL=19.2 | Top1=33.0% Top5=68.6% TF-SeqEM=1.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=9.5%
  TF=1.000, AR=0%, LR=0.000096
  No improvement for 2 epoch(s)

Epoch 11/60
----------------------------------------------------------------------
  [AR-SS] Starting autoregressive scheduled sampling, resetting patience
Epoch 11/60 [AR-SS(tf=0.85,ar=10%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:08<00:00,  5.61it/s, loss=5.6730, main=5.6226]

  Train: Loss=5.3416 (main=5.2773, len=0.127, tcls=0.012)
  Val:   Loss=3.0303 | PPL=20.7 | Top1=32.9% Top5=67.5% TF-SeqEM=1.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=7.2%
  TF=0.850, AR=10%, LR=0.000095
  [Diag] BERT top-layer gradients: MISSING (check Fix D)
  No improvement for 1 epoch(s)

Epoch 12/60
----------------------------------------------------------------------
Epoch 12/60 [AR-SS(tf=0.84,ar=11%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:29<00:00,  5.31it/s, loss=5.2147, main=5.1670]

  Train: Loss=5.2992 (main=5.2392, len=0.126, tcls=0.011)
  Val:   Loss=3.1281 | PPL=22.8 | Top1=33.3% Top5=66.1% TF-SeqEM=1.7%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=9.7%
  TF=0.837, AR=11%, LR=0.000094
  No improvement for 2 epoch(s)

Epoch 13/60
----------------------------------------------------------------------
Epoch 13/60 [AR-SS(tf=0.82,ar=12%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:28<00:00,  5.32it/s, loss=5.5006, main=5.4526]

  Train: Loss=5.2554 (main=5.1989, len=0.125, tcls=0.011)
  Val:   Loss=3.1332 | PPL=22.9 | Top1=33.4% Top5=65.1% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.3%
  TF=0.823, AR=12%, LR=0.000093
  No improvement for 3 epoch(s)

Epoch 14/60
----------------------------------------------------------------------
Epoch 14/60 [AR-SS(tf=0.81,ar=14%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:40<00:00,  5.16it/s, loss=4.9356, main=4.8889]

  Train: Loss=5.2264 (main=5.1707, len=0.123, tcls=0.009)
  Val:   Loss=3.1128 | PPL=22.5 | Top1=33.8% Top5=65.8% TF-SeqEM=1.9%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=8.7%
  TF=0.809, AR=14%, LR=0.000091
  No improvement for 4 epoch(s)

Epoch 15/60
----------------------------------------------------------------------
Epoch 15/60 [AR-SS(tf=0.79,ar=15%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:40<00:00,  5.16it/s, loss=4.6554, main=4.5963]

  Train: Loss=5.1913 (main=5.1369, len=0.122, tcls=0.010)
  Val:   Loss=3.1649 | PPL=23.7 | Top1=33.7% Top5=65.1% TF-SeqEM=1.9%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=9.9%
  TF=0.793, AR=15%, LR=0.000090
  No improvement for 5 epoch(s)

Epoch 16/60
----------------------------------------------------------------------
Epoch 16/60 [AR-SS(tf=0.78,ar=16%), n=66173]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2067/2067 [06:47<00:00,  5.07it/s, loss=5.1994, main=5.1521]

  Train: Loss=5.1580 (main=5.1041, len=0.122, tcls=0.009)
  Val:   Loss=3.1693 | PPL=23.8 | Top1=34.1% Top5=65.2% TF-SeqEM=2.0%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.3%
  TF=0.777, AR=16%, LR=0.000088
  No improvement for 6 epoch(s)

Epoch 17/60
----------------------------------------------------------------------
  [Curriculum] Phase 1 -> 2, resetting patience
Epoch 17/60 [AR-SS(tf=0.76,ar=17%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [15:13<00:00,  3.13it/s, loss=5.3957, main=5.3333]

  Train: Loss=5.4679 (main=5.4053, len=0.229, tcls=0.013)
  Val:   Loss=2.4003 | PPL=11.0 | Top1=41.4% Top5=78.6% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=9.7%
  TF=0.760, AR=17%, LR=0.000086
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.4003)

Epoch 18/60
----------------------------------------------------------------------
Epoch 18/60 [AR-SS(tf=0.74,ar=18%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [16:04<00:00,  2.96it/s, loss=5.7167, main=5.6527]

  Train: Loss=5.3862 (main=5.3252, len=0.217, tcls=0.010)
  Val:   Loss=2.3519 | PPL=10.5 | Top1=42.5% Top5=79.4% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.5%
  TF=0.742, AR=18%, LR=0.000084
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.3519)

Epoch 19/60
----------------------------------------------------------------------
Epoch 19/60 [AR-SS(tf=0.72,ar=20%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [16:04<00:00,  2.96it/s, loss=5.2757, main=5.2096]

  Train: Loss=5.3309 (main=5.2712, len=0.213, tcls=0.009)
  Val:   Loss=2.3179 | PPL=10.2 | Top1=43.5% Top5=80.3% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.7%
  TF=0.723, AR=20%, LR=0.000082
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.3179)

Epoch 20/60
----------------------------------------------------------------------
Epoch 20/60 [AR-SS(tf=0.70,ar=21%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [16:40<00:00,  2.86it/s, loss=5.5429, main=5.4751]

  Train: Loss=5.3023 (main=5.2432, len=0.210, tcls=0.008)
  Val:   Loss=2.3082 | PPL=10.1 | Top1=43.9% Top5=80.4% TF-SeqEM=1.8%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.2%
  TF=0.703, AR=21%, LR=0.000080
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.3082)

Epoch 21/60
----------------------------------------------------------------------
Epoch 21/60 [AR-SS(tf=0.68,ar=22%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [16:54<00:00,  2.82it/s, loss=5.2078, main=5.1485]

  Train: Loss=5.2761 (main=5.2179, len=0.206, tcls=0.008)
  Val:   Loss=2.2852 | PPL=9.8 | Top1=44.6% Top5=80.9% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.5%
  TF=0.683, AR=22%, LR=0.000078
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2852)

Epoch 22/60
----------------------------------------------------------------------
Epoch 22/60 [AR-SS(tf=0.66,ar=23%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [17:15<00:00,  2.76it/s, loss=6.0377, main=5.9689]

  Train: Loss=5.2579 (main=5.2001, len=0.203, tcls=0.007)
  Val:   Loss=2.2805 | PPL=9.8 | Top1=44.9% Top5=81.1% TF-SeqEM=2.0%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.3%
  TF=0.662, AR=23%, LR=0.000075
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2805)

Epoch 23/60
----------------------------------------------------------------------
Epoch 23/60 [AR-SS(tf=0.64,ar=24%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [17:53<00:00,  2.66it/s, loss=6.4804, main=6.3872]

  Train: Loss=5.2420 (main=5.1845, len=0.200, tcls=0.008)
  Val:   Loss=2.2495 | PPL=9.5 | Top1=45.8% Top5=81.6% TF-SeqEM=2.2%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.2%
  TF=0.641, AR=24%, LR=0.000073
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2495)

Epoch 24/60
----------------------------------------------------------------------
Epoch 24/60 [AR-SS(tf=0.62,ar=26%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [19:14<00:00,  2.48it/s, loss=4.9029, main=4.8565]

  Train: Loss=5.2658 (main=5.2087, len=0.200, tcls=0.007)
  Val:   Loss=2.2509 | PPL=9.5 | Top1=46.0% Top5=81.9% TF-SeqEM=2.1%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.5%
  TF=0.619, AR=26%, LR=0.000070
  No improvement for 1 epoch(s)

Epoch 25/60
----------------------------------------------------------------------
Epoch 25/60 [AR-SS(tf=0.60,ar=27%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [19:28<00:00,  2.45it/s, loss=4.6180, main=4.5679]

  Train: Loss=5.2562 (main=5.1998, len=0.197, tcls=0.007)
  Val:   Loss=2.2213 | PPL=9.2 | Top1=46.5% Top5=82.1% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.3%
  TF=0.597, AR=27%, LR=0.000068
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2213)

Epoch 26/60
----------------------------------------------------------------------
Epoch 26/60 [AR-SS(tf=0.57,ar=28%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [19:49<00:00,  2.40it/s, loss=4.6040, main=4.5512]

  Train: Loss=5.2518 (main=5.1955, len=0.196, tcls=0.007)
  Val:   Loss=2.2090 | PPL=9.1 | Top1=47.1% Top5=82.7% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.9%
  TF=0.575, AR=28%, LR=0.000065
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.2090)

Epoch 27/60
----------------------------------------------------------------------
Epoch 27/60 [AR-SS(tf=0.55,ar=29%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [20:15<00:00,  2.35it/s, loss=5.0648, main=5.0131]

  Train: Loss=5.2506 (main=5.1945, len=0.194, tcls=0.007)
  Val:   Loss=2.1976 | PPL=9.0 | Top1=47.1% Top5=82.5% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.8%
  TF=0.552, AR=29%, LR=0.000063
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1976)

Epoch 28/60
----------------------------------------------------------------------
Epoch 28/60 [AR-SS(tf=0.53,ar=30%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [21:08<00:00,  2.25it/s, loss=4.9953, main=4.9368]

  Train: Loss=5.2698 (main=5.2140, len=0.193, tcls=0.007)
  Val:   Loss=2.2109 | PPL=9.1 | Top1=47.1% Top5=82.8% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.2%
  TF=0.530, AR=30%, LR=0.000060
  No improvement for 1 epoch(s)

Epoch 29/60
----------------------------------------------------------------------
Epoch 29/60 [AR-SS(tf=0.51,ar=32%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [22:06<00:00,  2.16it/s, loss=4.9975, main=4.9503]

  Train: Loss=5.2874 (main=5.2324, len=0.192, tcls=0.007)
  Val:   Loss=2.1957 | PPL=9.0 | Top1=47.3% Top5=82.6% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.3%
  TF=0.507, AR=32%, LR=0.000057
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1957)

Epoch 30/60
----------------------------------------------------------------------
Epoch 30/60 [AR-SS(tf=0.49,ar=33%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [21:37<00:00,  2.20it/s, loss=4.8151, main=4.7510]

  Train: Loss=5.2744 (main=5.2194, len=0.191, tcls=0.007)
  Val:   Loss=2.1783 | PPL=8.8 | Top1=47.7% Top5=82.9% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.7%
  TF=0.485, AR=33%, LR=0.000055
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1783)

Epoch 31/60
----------------------------------------------------------------------
Epoch 31/60 [AR-SS(tf=0.46,ar=34%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [22:26<00:00,  2.12it/s, loss=5.7847, main=5.7093]

  Train: Loss=5.2988 (main=5.2439, len=0.189, tcls=0.007)
  Val:   Loss=2.1876 | PPL=8.9 | Top1=47.3% Top5=82.6% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.2%
  TF=0.463, AR=34%, LR=0.000052
  No improvement for 1 epoch(s)

Epoch 32/60
----------------------------------------------------------------------
Epoch 32/60 [AR-SS(tf=0.44,ar=35%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [23:25<00:00,  2.04it/s, loss=6.1704, main=6.1184]

  Train: Loss=5.3224 (main=5.2677, len=0.189, tcls=0.008)
  Val:   Loss=2.2056 | PPL=9.1 | Top1=47.3% Top5=82.7% TF-SeqEM=2.3%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.5%
  TF=0.442, AR=35%, LR=0.000049
  No improvement for 2 epoch(s)

Epoch 33/60
----------------------------------------------------------------------
Epoch 33/60 [AR-SS(tf=0.42,ar=36%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [24:01<00:00,  1.98it/s, loss=4.9846, main=4.9288]

  Train: Loss=5.3473 (main=5.2929, len=0.188, tcls=0.008)
  Val:   Loss=2.1904 | PPL=8.9 | Top1=47.5% Top5=82.7% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=9.8%
  TF=0.421, AR=36%, LR=0.000046
  No improvement for 3 epoch(s)

Epoch 34/60
----------------------------------------------------------------------
Epoch 34/60 [AR-SS(tf=0.40,ar=38%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [24:40<00:00,  1.93it/s, loss=4.7254, main=4.6632]

  Train: Loss=5.3609 (main=5.3072, len=0.187, tcls=0.007)
  Val:   Loss=2.1882 | PPL=8.9 | Top1=47.9% Top5=83.2% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.3%
  TF=0.401, AR=38%, LR=0.000044
  No improvement for 4 epoch(s)

Epoch 35/60
----------------------------------------------------------------------
Epoch 35/60 [AR-SS(tf=0.38,ar=39%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [24:15<00:00,  1.96it/s, loss=4.7158, main=4.6578]

  Train: Loss=5.3442 (main=5.2903, len=0.186, tcls=0.007)
  Val:   Loss=2.1773 | PPL=8.8 | Top1=48.0% Top5=82.9% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=13.2%
  TF=0.381, AR=39%, LR=0.000041
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1773)

Epoch 36/60
----------------------------------------------------------------------
Epoch 36/60 [AR-SS(tf=0.36,ar=40%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [25:57<00:00,  1.84it/s, loss=4.9805, main=4.9224]

  Train: Loss=5.3907 (main=5.3372, len=0.186, tcls=0.007)
  Val:   Loss=2.1638 | PPL=8.7 | Top1=48.3% Top5=83.2% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.8%
  TF=0.362, AR=40%, LR=0.000038
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1638)

Epoch 37/60
----------------------------------------------------------------------
Epoch 37/60 [AR-SS(tf=0.34,ar=41%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [26:15<00:00,  1.82it/s, loss=4.5062, main=4.4421]

  Train: Loss=5.4183 (main=5.3651, len=0.185, tcls=0.007)
  Val:   Loss=2.1824 | PPL=8.9 | Top1=47.7% Top5=82.9% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.0%
  TF=0.344, AR=41%, LR=0.000036
  No improvement for 1 epoch(s)

Epoch 38/60
----------------------------------------------------------------------
Epoch 38/60 [AR-SS(tf=0.33,ar=42%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [27:05<00:00,  1.76it/s, loss=4.6780, main=4.6273]

  Train: Loss=5.4438 (main=5.3910, len=0.185, tcls=0.007)
  Val:   Loss=2.1759 | PPL=8.8 | Top1=48.1% Top5=83.2% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.3%
  TF=0.326, AR=42%, LR=0.000033
  No improvement for 2 epoch(s)

Epoch 39/60
----------------------------------------------------------------------
Epoch 39/60 [AR-SS(tf=0.31,ar=44%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [27:01<00:00,  1.76it/s, loss=6.4847, main=6.4662]

  Train: Loss=5.4442 (main=5.3919, len=0.184, tcls=0.007)
  Val:   Loss=2.1610 | PPL=8.7 | Top1=48.5% Top5=83.2% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.7%
  TF=0.310, AR=44%, LR=0.000031
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1610)

Epoch 40/60
----------------------------------------------------------------------
Epoch 40/60 [AR-SS(tf=0.29,ar=45%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [27:42<00:00,  1.72it/s, loss=6.3288, main=6.2876]

  Train: Loss=5.4689 (main=5.4167, len=0.184, tcls=0.007)
  Val:   Loss=2.1594 | PPL=8.7 | Top1=48.4% Top5=83.4% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.5%
  TF=0.294, AR=45%, LR=0.000028
  [BEST] Saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/best_model.pth (val_loss=2.1594)

Epoch 41/60
----------------------------------------------------------------------
Epoch 41/60 [AR-SS(tf=0.28,ar=46%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [29:09<00:00,  1.64it/s, loss=6.6431, main=6.6023]

  Train: Loss=5.5248 (main=5.4728, len=0.183, tcls=0.008)
  Val:   Loss=2.1764 | PPL=8.8 | Top1=48.3% Top5=83.1% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.7%
  TF=0.279, AR=46%, LR=0.000026
  No improvement for 1 epoch(s)

Epoch 42/60
----------------------------------------------------------------------
Epoch 42/60 [AR-SS(tf=0.27,ar=47%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [28:34<00:00,  1.67it/s, loss=4.0672, main=4.0098]

  Train: Loss=5.5049 (main=5.4532, len=0.184, tcls=0.008)
  Val:   Loss=2.1703 | PPL=8.8 | Top1=48.1% Top5=83.1% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=9.9%
  TF=0.265, AR=47%, LR=0.000023
  No improvement for 2 epoch(s)

Epoch 43/60
----------------------------------------------------------------------
Epoch 43/60 [AR-SS(tf=0.25,ar=48%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [29:55<00:00,  1.59it/s, loss=6.2148, main=6.1748]

  Train: Loss=5.5590 (main=5.5075, len=0.183, tcls=0.007)
  Val:   Loss=2.1602 | PPL=8.7 | Top1=48.4% Top5=83.3% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.0%
  TF=0.252, AR=48%, LR=0.000021
  No improvement for 3 epoch(s)

Epoch 44/60
----------------------------------------------------------------------
Epoch 44/60 [AR-SS(tf=0.24,ar=50%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [30:46<00:00,  1.55it/s, loss=4.8382, main=4.7827]

  Train: Loss=5.5764 (main=5.5252, len=0.183, tcls=0.008)
  Val:   Loss=2.1723 | PPL=8.8 | Top1=48.2% Top5=83.2% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.7%
  TF=0.240, AR=50%, LR=0.000019
  No improvement for 4 epoch(s)

Epoch 45/60
----------------------------------------------------------------------
Epoch 45/60 [AR-SS(tf=0.23,ar=51%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [30:13<00:00,  1.58it/s, loss=5.9799, main=5.9375]

  Train: Loss=5.5712 (main=5.5202, len=0.183, tcls=0.008)
  Val:   Loss=2.1725 | PPL=8.8 | Top1=48.1% Top5=83.1% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.8%
  TF=0.229, AR=51%, LR=0.000017
  No improvement for 5 epoch(s)

Epoch 46/60
----------------------------------------------------------------------
Epoch 46/60 [AR-SS(tf=0.22,ar=52%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [30:40<00:00,  1.55it/s, loss=6.1970, main=6.1749]

  Train: Loss=5.5856 (main=5.5348, len=0.183, tcls=0.008)
  Val:   Loss=2.1786 | PPL=8.8 | Top1=48.1% Top5=83.1% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.0%
  TF=0.218, AR=52%, LR=0.000015
  No improvement for 6 epoch(s)

Epoch 47/60
----------------------------------------------------------------------
Epoch 47/60 [AR-SS(tf=0.21,ar=53%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [31:49<00:00,  1.50it/s, loss=5.9469, main=5.9107]

  Train: Loss=5.6260 (main=5.5755, len=0.182, tcls=0.008)
  Val:   Loss=2.1761 | PPL=8.8 | Top1=48.1% Top5=83.1% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.8%
  TF=0.208, AR=53%, LR=0.000013
  No improvement for 7 epoch(s)

Epoch 48/60
----------------------------------------------------------------------
Epoch 48/60 [AR-SS(tf=0.20,ar=54%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [31:54<00:00,  1.49it/s, loss=4.6972, main=4.6343]

  Train: Loss=5.6276 (main=5.5769, len=0.183, tcls=0.008)
  Val:   Loss=2.1682 | PPL=8.7 | Top1=48.3% Top5=83.3% TF-SeqEM=2.6%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=10.4%
  TF=0.199, AR=54%, LR=0.000011
  No improvement for 8 epoch(s)

Epoch 49/60
----------------------------------------------------------------------
Epoch 49/60 [AR-SS(tf=0.19,ar=56%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [32:53<00:00,  1.45it/s, loss=5.0414, main=4.9919]

  Train: Loss=5.6599 (main=5.6097, len=0.183, tcls=0.008)
  Val:   Loss=2.1757 | PPL=8.8 | Top1=48.2% Top5=83.2% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=12.7%
  TF=0.191, AR=56%, LR=0.000010
  No improvement for 9 epoch(s)

Epoch 50/60
----------------------------------------------------------------------
Epoch 50/60 [AR-SS(tf=0.18,ar=57%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [33:28<00:00,  1.42it/s, loss=6.3259, main=6.2978]

  Train: Loss=5.6728 (main=5.6228, len=0.182, tcls=0.008)
  Val:   Loss=2.1808 | PPL=8.9 | Top1=48.0% Top5=83.0% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.9%
  TF=0.183, AR=57%, LR=0.000008
  No improvement for 10 epoch(s)

Epoch 51/60
----------------------------------------------------------------------
Epoch 51/60 [AR-SS(tf=0.18,ar=58%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [34:32<00:00,  1.38it/s, loss=5.9679, main=5.9436]

  Train: Loss=5.7155 (main=5.6658, len=0.182, tcls=0.009)
  Val:   Loss=2.1801 | PPL=8.8 | Top1=48.0% Top5=83.1% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=13.6%
  TF=0.176, AR=58%, LR=0.000007
  No improvement for 11 epoch(s)

Epoch 52/60
----------------------------------------------------------------------
Epoch 52/60 [AR-SS(tf=0.17,ar=59%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [34:52<00:00,  1.37it/s, loss=6.7310, main=6.6628]

  Train: Loss=5.7276 (main=5.6782, len=0.182, tcls=0.008)
  Val:   Loss=2.1815 | PPL=8.9 | Top1=48.0% Top5=83.0% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.3%
  TF=0.169, AR=59%, LR=0.000006
  No improvement for 12 epoch(s)

Epoch 53/60
----------------------------------------------------------------------
Epoch 53/60 [AR-SS(tf=0.16,ar=60%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [34:41<00:00,  1.37it/s, loss=4.8249, main=4.7658]

  Train: Loss=5.7263 (main=5.6768, len=0.182, tcls=0.009)
  Val:   Loss=2.1833 | PPL=8.9 | Top1=48.0% Top5=83.0% TF-SeqEM=2.5%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.5%
  TF=0.163, AR=60%, LR=0.000005
  No improvement for 13 epoch(s)

Epoch 54/60
----------------------------------------------------------------------
Epoch 54/60 [AR-SS(tf=0.16,ar=62%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [36:04<00:00,  1.32it/s, loss=6.4064, main=6.3490]

  Train: Loss=5.7659 (main=5.7170, len=0.181, tcls=0.009)
  Val:   Loss=2.1902 | PPL=8.9 | Top1=48.0% Top5=82.9% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.0%
  TF=0.157, AR=62%, LR=0.000004
  No improvement for 14 epoch(s)

Epoch 55/60
----------------------------------------------------------------------
Epoch 55/60 [AR-SS(tf=0.15,ar=63%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [35:59<00:00,  1.32it/s, loss=5.2729, main=5.2119]

  Train: Loss=5.7671 (main=5.7182, len=0.183, tcls=0.009)
  Val:   Loss=2.1950 | PPL=9.0 | Top1=47.8% Top5=82.9% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=12.2%
  TF=0.152, AR=63%, LR=0.000003
  No improvement for 15 epoch(s)

Epoch 56/60
----------------------------------------------------------------------
Epoch 56/60 [AR-SS(tf=0.15,ar=64%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [36:47<00:00,  1.30it/s, loss=6.4274, main=6.3658]

  Train: Loss=5.7931 (main=5.7446, len=0.183, tcls=0.009)
  Val:   Loss=2.1893 | PPL=8.9 | Top1=47.9% Top5=83.0% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=3.1% AR-TokenAcc=11.8%
  TF=0.147, AR=64%, LR=0.000002
  No improvement for 16 epoch(s)

Epoch 57/60
----------------------------------------------------------------------
Epoch 57/60 [AR-SS(tf=0.14,ar=65%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [37:10<00:00,  1.28it/s, loss=4.9554, main=4.8873]

  Train: Loss=5.8253 (main=5.7768, len=0.182, tcls=0.010)
  Val:   Loss=2.2103 | PPL=9.1 | Top1=47.6% Top5=82.8% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=1.6% AR-TokenAcc=11.4%
  TF=0.143, AR=65%, LR=0.000002
  No improvement for 17 epoch(s)

Epoch 58/60
----------------------------------------------------------------------
Epoch 58/60 [AR-SS(tf=0.14,ar=66%), n=91520]: 100%|████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████| 2860/2860 [37:42<00:00,  1.26it/s, loss=6.5628, main=6.5224]

  Train: Loss=5.8614 (main=5.8133, len=0.182, tcls=0.010)
  Val:   Loss=2.2025 | PPL=9.0 | Top1=47.7% Top5=82.7% TF-SeqEM=2.4%
  Gen:   AR-SeqEM=0.0% AR-TokenAcc=11.5%
  TF=0.139, AR=66%, LR=0.000001
  No improvement for 18 epoch(s)

Early stopping at epoch 58

================================================================================
Training complete! Loading best model for test evaluation...

Test Results:
  Loss=2.1520 PPL=8.6
  Top1=48.5% Top5=83.4%
  TF-SeqEM=2.6%
  AR-SeqEM=0.0% AR-TokenAcc=13.3%

History saved: /home/qy/system_redesign/outputs/transformer_checkpoints_v4_2/training_history_v4_2.json

Done!





 V4.2 完整训练轨迹分析

  关键里程碑

  ┌───────┬────────────┬──────────┬──────────┬───────────┬───────┬──────────┬─────────────┐
  │ Epoch │    阶段    │ TF ratio │ AR ratio │ Val Loss  │ Top1  │ AR-SeqEM │ AR-TokenAcc │
  ├───────┼────────────┼──────────┼──────────┼───────────┼───────┼──────────┼─────────────┤
  │ 1-10  │ TF-only    │ 1.0      │ 0%       │ 2.91→3.01 │ 32%   │ -        │ -           │
  ├───────┼────────────┼──────────┼──────────┼───────────┼───────┼──────────┼─────────────┤
  │ 11    │ AR-SS开始  │ 0.85     │ 10%      │ 3.03      │ 32.9% │ 0%       │ 7.2%        │
  ├───────┼────────────┼──────────┼──────────┼───────────┼───────┼──────────┼─────────────┤
  │ 23    │ 全量数据   │ 0.64     │ 24%      │ 2.25      │ 45.8% │ 1.6%     │ 11.2%       │
  ├───────┼────────────┼──────────┼──────────┼───────────┼───────┼──────────┼─────────────┤
  │ 40    │ best       │ 0.29     │ 45%      │ 2.1594    │ 48.4% │ 0%       │ 11.5%       │
  ├───────┼────────────┼──────────┼──────────┼───────────┼───────┼──────────┼─────────────┤
  │ 55+   │ early stop │ 0.16     │ 62%      │ 2.18+     │ 48%   │ 0%       │ 11%         │
  └───────┴────────────┴──────────┴──────────┴───────────┴───────┴──────────┴─────────────┘

  关键观察

  1. AR ratio 超过 45% 后模型开始退化 — 最佳点恰好在 45% AR，之后 val loss 回升
  2. AR-SeqEM 极不稳定（在 0% 和 1.6% 之间跳动）— 说明完整序列预测能力很弱，评估批次太小导致方差大
  3. Top1 平台期在 48% — epoch 40 之后 Top1 几乎不再提升，说明 TF 指标已饱和
  4. Train loss 持续上升（AR-SS 阶段从 5.24 涨到 5.77）— 这是正常的 exposure bias 现象，但说明 AR 训练对模型是挑战
  5. BERT top-layer gradients: MISSING — 从 epoch 11 开始就存在，贯穿整个训练，但模型仍然收敛，说明这个问题影响有限但确实存在

  最大的问题

  AR ratio 到 45% 就见顶了，模型无法在更高 AR 比例下继续提升。这说明：
  - Exposure bias 问题严重——TF 训练和 AR 推理之间的 gap 没有被有效弥合
  - V4.3/V4.4 试图用 warm-start 跳过 TF phase 直接从 50% AR 开始，反而更激进，导致退化

---
  综合结论：问题的本质

  所有版本面临同一个根本问题：模型的 val loss 在 AR ratio ~45% 附近达到极限，无法通过调整训练策略（curriculum、length loss、balanced sampling）突破这个瓶颈。

  这个瓶颈更可能来自：
  1. 模型容量不足（d_model=256，6层，22.8M 可训练参数）
  2. 任务本身的歧义性（同一个任务描述可以有多种合理的 L3 序列）
  3. 数据质量（114K 样本但序列多样性有限，AR-SeqEM 始终 ≤3%）