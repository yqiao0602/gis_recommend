# system_redesign/train_hgt_embeddings.py
"""
Train Relational Graph Embedding model（基于RelGraphConv）以学习L3嵌入。

说明：原脚本命名为“HGT”，但实际使用RelGraphConv而非Heterogeneous Graph Transformer。
这里将其视作“Graph Embedding”模型，强调其作用是提供L3的图谱先验。

特性：
1. 边类型特定的消息传递 (Edge-type-specific message passing)
2. Basis分解减少参数 (Basis decomposition for parameter efficiency)
3. 支持自环 (Self-loops for better expressiveness)
4. 正则化防止过拟合 (Regularization)

Training tasks:
1. Node classification: Predict L2 category from L3
2. Link prediction: Predict if GEE/QGIS operator implements L3
3. Contrastive learning: Align operators mapping to same L3
"""
# system_redesign/train_graph_embeddings.py
"""
Train Relational Graph Embedding model（基于RelGraphConv）以学习L3嵌入。

说明：原脚本命名为“HGT”，但实际使用RelGraphConv而非Heterogeneous Graph Transformer。
这里将其视作“Graph Embedding”模型，强调其作用是提供L3的图谱先验。

Training tasks:
1. Node classification: Predict L2 category from L3
2. Link prediction: Predict if GEE/QGIS operator implements L3
3. Contrastive learning: Align operators mapping to same L3
"""
import json
import torch
import torch.nn as nn
import torch.nn.functional as F
import dgl
from tqdm import trange

from gis_recommend.config.config import (
    HETERO_GRAPH_PATH,
    ID_MAPPINGS_PATH,
    L3_EMBEDDINGS_PATH,
    HGT_MODEL_PATH,
    HGT_INPUT_DIM,
    HGT_HIDDEN_DIM,
    HGT_OUTPUT_DIM,
    HGT_NUM_HEADS,       # NOTE: 仍保留参数，但RelGraphConv不使用head
    HGT_NUM_LAYERS,
    HGT_DROPOUT,
    DEVICE,
    LEARNING_RATE,
    NUM_EPOCHS,
    PATIENCE,
    WEIGHT_NODE_CLS,
    WEIGHT_LINK_PRED,
    WEIGHT_CONTRASTIVE,
    NUM_NEG_SAMPLES,
    EVAL_SPLIT,
    VERBOSE,
    SAVE_CHECKPOINT_EVERY
)


class GraphEmbeddingModel(nn.Module):
    """RelGraphConv-based heterogeneous图嵌入模型"""
    def __init__(self, g, in_dim, hidden_dim, out_dim, num_heads, num_layers, dropout=0.2):
        super().__init__()
        self.g = g
        self.in_dim = in_dim
        self.hidden_dim = hidden_dim
        self.out_dim = out_dim
        self.num_heads = num_heads
        self.num_layers = num_layers

        # Node type embeddings (initial features)
        self.node_embeds = nn.ModuleDict()
        for ntype in g.ntypes:
            num_nodes = g.num_nodes(ntype)
            self.node_embeds[ntype] = nn.Embedding(num_nodes, in_dim)

        from dgl.nn.pytorch import RelGraphConv

        self.layers = nn.ModuleList()
        for layer_idx in range(num_layers):
            self.layers.append(
                RelGraphConv(
                    in_dim if layer_idx == 0 else hidden_dim,
                    hidden_dim,
                    num_rels=len(g.canonical_etypes),
                    regularizer='basis',
                    num_bases=len(g.ntypes),
                    self_loop=True,
                    dropout=dropout
                )
            )

        # Output projection for L3 nodes
        self.l3_output_proj = nn.Linear(hidden_dim, out_dim)

        # Task-specific heads
        self.l2_classifier = nn.Linear(out_dim, g.num_nodes('l2'))

        # 边类型映射
        self.etype_to_id = {etype: i for i, etype in enumerate(g.canonical_etypes)}

    def forward(self, blocks=None):
        """
        Forward pass using RelGraphConv for heterogeneous graphs.
        Returns: Dict of node embeddings {ntype: embeddings}
        """
        g = blocks if blocks is not None else self.g
        device = next(self.parameters()).device

        # ======= 关键修复 1：确保 g 在同一 device =======
        if g.device != device:
            g = g.to(device)

        # RelGraphConv 用同构图 + 边类型张量
        homo_g = dgl.to_homogeneous(g, store_type=True)

        # ======= 关键修复 2：确保 homo_g / etypes 在同一 device =======
        if homo_g.device != device:
            homo_g = homo_g.to(device)

        etypes = homo_g.edata[dgl.ETYPE]
        if etypes.device != device:
            etypes = etypes.to(device)

        # 初始化节点特征（每个ntype一个Embedding）
        h_list = []
        node_counts = {}
        for ntype in g.ntypes:
            num_nodes = g.num_nodes(ntype)
            node_counts[ntype] = num_nodes
            node_ids = torch.arange(num_nodes, device=device)
            h_list.append(self.node_embeds[ntype](node_ids))

        # 拼接所有节点的嵌入（与 to_homogeneous 的 ntype 顺序一致）
        h = torch.cat(h_list, dim=0)

        for layer in self.layers:
            h = layer(homo_g, h, etypes)
            h = F.relu(h)

        # 拆分回异构格式
        h_dict = {}
        offset = 0
        for ntype in g.ntypes:
            count = node_counts[ntype]
            h_dict[ntype] = h[offset:offset + count]
            offset += count

        return h_dict

    @torch.no_grad()
    def get_l3_embeddings(self):
        """Get final L3 embeddings for downstream tasks"""
        self.eval()
        h_dict = self.forward()
        l3_emb = self.l3_output_proj(h_dict['l3'])
        return F.normalize(l3_emb, p=2, dim=1)


class GraphEmbeddingTrainer:
    """Trainer for RelGraphConv graph embeddings（非Transformer）"""

    def __init__(self, model, graph, id_mappings, device='cpu'):
        # ======= 关键修复 3：device 统一入口 + fallback =======
        if isinstance(device, str):
            if device.startswith('cuda') and (not torch.cuda.is_available()):
                print("[WARN] DEVICE is cuda but cuda is not available. Fallback to cpu.")
                device = 'cpu'
        self.device = torch.device(device)

        # ======= 关键修复 4：graph 上 device，并同步给 model.g =======
        self.graph = graph.to(self.device)
        self.model = model.to(self.device)
        self.model.g = self.graph  # 让 forward 默认用 GPU 图

        self.id_mappings = id_mappings

        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=LEARNING_RATE)

        self._prepare_data()

        self.best_val_loss = float('inf')
        self.patience_counter = 0

    def _prepare_data(self):
        """Prepare training/validation splits and labels"""
        # 1) Node classification labels (L3 -> L2)
        l3_to_l2_map = {}
        with open(ID_MAPPINGS_PATH, 'r', encoding='utf-8') as f:
            mappings = json.load(f)
            for l3_code, l3_meta in mappings['metadata']['l3'].items():
                l2_code = l3_meta['l2_code']
                l3_id = self.id_mappings[2][l3_code]  # l3_id_map
                l2_id = self.id_mappings[3][l2_code]  # l2_id_map
                l3_to_l2_map[l3_id] = l2_id

        num_l3 = self.graph.num_nodes('l3')
        self.l3_labels = torch.zeros(num_l3, dtype=torch.long, device=self.device)
        for l3_id, l2_id in l3_to_l2_map.items():
            self.l3_labels[l3_id] = l2_id

        # Train/val split
        perm = torch.randperm(num_l3, device=self.device)
        val_size = int(num_l3 * EVAL_SPLIT)

        self.train_l3_mask = torch.zeros(num_l3, dtype=torch.bool, device=self.device)
        self.val_l3_mask = torch.zeros(num_l3, dtype=torch.bool, device=self.device)

        self.val_l3_mask[perm[:val_size]] = True
        self.train_l3_mask[perm[val_size:]] = True

        # 2) Link prediction edges: use existing edges as positive samples
        gee_l3_edges = self.graph.edges(etype=('gee_op', 'implements', 'l3'))
        qgis_l3_edges = self.graph.edges(etype=('qgis_op', 'implements', 'l3'))

        # ======= 关键修复 5：不要 cpu()，全留在 device =======
        self.pos_edges_gee = (gee_l3_edges[0].to(self.device), gee_l3_edges[1].to(self.device))
        self.pos_edges_qgis = (qgis_l3_edges[0].to(self.device), qgis_l3_edges[1].to(self.device))

        if VERBOSE:
            print(f"\nTraining data prepared:")
            print(f"  L3 nodes for classification: {num_l3}")
            print(f"    Train: {self.train_l3_mask.sum().item()}")
            print(f"    Val: {self.val_l3_mask.sum().item()}")
            print(f"  Positive edges (GEE): {len(self.pos_edges_gee[0])}")
            print(f"  Positive edges (QGIS): {len(self.pos_edges_qgis[0])}")

    def _node_classification_loss(self, h_dict):
        l3_emb = self.model.l3_output_proj(h_dict['l3'])
        logits = self.model.l2_classifier(l3_emb)

        loss = F.cross_entropy(logits[self.train_l3_mask], self.l3_labels[self.train_l3_mask])

        with torch.no_grad():
            val_acc = (logits[self.val_l3_mask].argmax(dim=1) == self.l3_labels[self.val_l3_mask]).float().mean()

        return loss, val_acc.item()

    def _link_prediction_loss(self, h_dict):
        l3_emb = self.model.l3_output_proj(h_dict['l3'])

        total_loss = 0.0
        num_batches = 0

        # GEE -> L3
        if len(self.pos_edges_gee[0]) > 0:
            pos_src = self.pos_edges_gee[0][:1000]
            pos_dst = self.pos_edges_gee[1][:1000]

            gee_emb = self.model.l3_output_proj(h_dict['gee_op'])
            pos_score = (gee_emb[pos_src] * l3_emb[pos_dst]).sum(dim=1)

            neg_dst = torch.randint(
                0, self.graph.num_nodes('l3'),
                (len(pos_src) * NUM_NEG_SAMPLES,),
                device=self.device
            )
            neg_src = pos_src.repeat_interleave(NUM_NEG_SAMPLES)
            neg_score = (gee_emb[neg_src] * l3_emb[neg_dst]).sum(dim=1)

            pos_loss = F.binary_cross_entropy_with_logits(pos_score, torch.ones_like(pos_score))
            neg_loss = F.binary_cross_entropy_with_logits(neg_score, torch.zeros_like(neg_score))
            total_loss += (pos_loss + neg_loss) / 2
            num_batches += 1

        # QGIS -> L3
        if len(self.pos_edges_qgis[0]) > 0:
            pos_src = self.pos_edges_qgis[0][:1000]
            pos_dst = self.pos_edges_qgis[1][:1000]

            qgis_emb = self.model.l3_output_proj(h_dict['qgis_op'])
            pos_score = (qgis_emb[pos_src] * l3_emb[pos_dst]).sum(dim=1)

            neg_dst = torch.randint(
                0, self.graph.num_nodes('l3'),
                (len(pos_src) * NUM_NEG_SAMPLES,),
                device=self.device
            )
            neg_src = pos_src.repeat_interleave(NUM_NEG_SAMPLES)
            neg_score = (qgis_emb[neg_src] * l3_emb[neg_dst]).sum(dim=1)

            pos_loss = F.binary_cross_entropy_with_logits(pos_score, torch.ones_like(pos_score))
            neg_loss = F.binary_cross_entropy_with_logits(neg_score, torch.zeros_like(neg_score))
            total_loss += (pos_loss + neg_loss) / 2
            num_batches += 1

        return total_loss / max(num_batches, 1)

    def _contrastive_loss(self, h_dict):
        l3_emb = F.normalize(self.model.l3_output_proj(h_dict['l3']), p=2, dim=1)

        num_samples = min(500, self.graph.num_nodes('l3'))
        anchors = torch.randperm(self.graph.num_nodes('l3'), device=self.device)[:num_samples]
        positives = torch.randperm(self.graph.num_nodes('l3'), device=self.device)[:num_samples]
        negatives = torch.randperm(self.graph.num_nodes('l3'), device=self.device)[:num_samples]

        anchor_emb = l3_emb[anchors]
        pos_emb = l3_emb[positives]
        neg_emb = l3_emb[negatives]

        return F.triplet_margin_loss(anchor_emb, pos_emb, neg_emb, margin=0.5)

    def train_epoch(self):
        self.model.train()
        self.optimizer.zero_grad()

        h_dict = self.model()

        cls_loss, val_acc = self._node_classification_loss(h_dict)
        link_loss = self._link_prediction_loss(h_dict)
        contrast_loss = self._contrastive_loss(h_dict)

        total_loss = (
            WEIGHT_NODE_CLS * cls_loss +
            WEIGHT_LINK_PRED * link_loss +
            WEIGHT_CONTRASTIVE * contrast_loss
        )

        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
        self.optimizer.step()

        return {
            'total_loss': total_loss.item(),
            'cls_loss': cls_loss.item(),
            'link_loss': link_loss.item(),
            'contrast_loss': contrast_loss.item(),
            'val_acc': val_acc
        }

    @torch.no_grad()
    def validate(self):
        self.model.eval()
        h_dict = self.model()
        cls_loss, val_acc = self._node_classification_loss(h_dict)
        link_loss = self._link_prediction_loss(h_dict)
        val_loss = WEIGHT_NODE_CLS * cls_loss + WEIGHT_LINK_PRED * link_loss
        return val_loss.item(), val_acc

    def train(self):
        print("\n" + "=" * 60)
        print("Training Graph Embedding Model")
        print("=" * 60)

        for epoch in trange(NUM_EPOCHS, desc="Training"):
            metrics = self.train_epoch()
            val_loss, val_acc = self.validate()

            if VERBOSE and (epoch + 1) % 5 == 0:
                print(f"\nEpoch {epoch + 1}/{NUM_EPOCHS}")
                print(f"  Train Loss: {metrics['total_loss']:.4f}")
                print(f"    - Classification: {metrics['cls_loss']:.4f}")
                print(f"    - Link Prediction: {metrics['link_loss']:.4f}")
                print(f"    - Contrastive: {metrics['contrast_loss']:.4f}")
                print(f"  Val Loss: {val_loss:.4f}")
                print(f"  Val Accuracy: {val_acc:.4f}")

            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss
                self.patience_counter = 0
                self.save_checkpoint('best')
            else:
                self.patience_counter += 1
                if self.patience_counter >= PATIENCE:
                    print(f"\nEarly stopping at epoch {epoch + 1}")
                    break

            if (epoch + 1) % SAVE_CHECKPOINT_EVERY == 0:
                self.save_checkpoint(f'epoch_{epoch + 1}')

        print("\n" + "=" * 60)
        print("Training completed!")
        print(f"Best validation loss: {self.best_val_loss:.4f}")
        print("=" * 60)

    def save_checkpoint(self, name='best'):
        checkpoint_path = HGT_MODEL_PATH.parent / f"graph_embedding_model_{name}.pth"
        torch.save({
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'best_val_loss': self.best_val_loss
        }, checkpoint_path)

        if name == 'best' and VERBOSE:
            print(f"  Checkpoint saved: {checkpoint_path}")

    @torch.no_grad()
    def export_l3_embeddings(self):
        self.model.eval()
        l3_emb = self.model.get_l3_embeddings().cpu()

        # ======= 关键修复 6：按 node_id 顺序导出 l3_codes，保证对齐 embeddings =======
        l3_code_to_id = self.id_mappings[2]          # {code -> id}
        num_l3 = len(l3_code_to_id)
        l3_codes_by_id = [None] * num_l3
        for code, idx in l3_code_to_id.items():
            l3_codes_by_id[idx] = code

        torch.save({
            'embeddings': l3_emb,
            'l3_codes': l3_codes_by_id,
            'embedding_dim': l3_emb.size(1)
        }, L3_EMBEDDINGS_PATH)

        if VERBOSE:
            print(f"\nL3 embeddings exported to: {L3_EMBEDDINGS_PATH}")
            print(f"  Shape: {l3_emb.shape}")


def main():
    if VERBOSE:
        print("Loading heterogeneous graph...")

    graphs, _ = dgl.load_graphs(str(HETERO_GRAPH_PATH))
    graph = graphs[0]

    # device fallback
    use_device = DEVICE
    if isinstance(use_device, str) and use_device.startswith('cuda') and (not torch.cuda.is_available()):
        print("[WARN] DEVICE is cuda but cuda is not available. Fallback to cpu.")
        use_device = 'cpu'

    # Load ID mappings
    with open(ID_MAPPINGS_PATH, 'r', encoding='utf-8') as f:
        id_mappings_data = json.load(f)

    id_mappings = (
        id_mappings_data['gee_op'],
        id_mappings_data['qgis_op'],
        id_mappings_data['l3'],
        id_mappings_data['l2'],
        id_mappings_data['l1']
    )

    model = GraphEmbeddingModel(
        g=graph,
        in_dim=HGT_INPUT_DIM,
        hidden_dim=HGT_HIDDEN_DIM,
        out_dim=HGT_OUTPUT_DIM,
        num_heads=HGT_NUM_HEADS,
        num_layers=HGT_NUM_LAYERS,
        dropout=HGT_DROPOUT
    )

    if VERBOSE:
        print(f"\nModel created (RelGraphConv Graph Embedding):")
        print(f"  Input dim: {HGT_INPUT_DIM}")
        print(f"  Hidden dim: {HGT_HIDDEN_DIM}")
        print(f"  Output dim: {HGT_OUTPUT_DIM}")
        print(f"  Layers: {HGT_NUM_LAYERS}")
        print(f"  Total parameters: {sum(p.numel() for p in model.parameters()):,}")
        print(f"\n  RelGraphConv特性:")
        print(f"    ✓ 边类型特定的消息传递")
        print(f"    ✓ Basis分解减少参数")
        print(f"    ✓ 自环提高表达能力")
        print(f"    ✓ 正则化防止过拟合")

    trainer = GraphEmbeddingTrainer(model, graph, id_mappings, device=use_device)
    trainer.train()
    trainer.export_l3_embeddings()

    return model, trainer


if __name__ == "__main__":
    main()
