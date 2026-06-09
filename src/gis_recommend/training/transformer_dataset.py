# system_redesign/transformer_dataset.py
"""
Dataset and DataLoader for Transformer training
"""
import json
import torch
import numpy as np
from torch.utils.data import Dataset, DataLoader
from typing import List, Dict, Tuple

from gis_recommend.config.transformer_config import (
    LABELED_WORKFLOWS_PATH,
    SPECIAL_TOKENS,
    MAX_SEQ_LENGTH,
    MIN_SEQ_LENGTH,
    INCLUDE_UNK_TOKENS,
    TRAIN_SPLIT,
    VAL_SPLIT,
    BATCH_SIZE,
    DEVICE,
    VERBOSE
)


class L3SequenceDataset(Dataset):
    """Dataset for L3 sequence modeling"""

    def __init__(self, sequences: List[Dict], max_length: int = MAX_SEQ_LENGTH):
        """
        Args:
            sequences: List of workflow dictionaries with 'l3_sequence'
            max_length: Maximum sequence length (for truncation)
        """
        self.sequences = sequences
        self.max_length = max_length

        # Token ID mapping
        self.pad_token_id = SPECIAL_TOKENS['<PAD>']
        self.unk_token_id = SPECIAL_TOKENS['<UNK>']
        self.start_token_id = SPECIAL_TOKENS['<START>']
        self.end_token_id = SPECIAL_TOKENS['<END>']

        # Filter and preprocess sequences
        self.processed_sequences = self._process_sequences()

    def _process_sequences(self) -> List[List[int]]:
        """Process and filter sequences

        Note: START and END tokens are now included in the labeled data,
        so we don't need to add them here.
        """
        processed = []

        for wf in self.sequences:
            seq = wf['l3_sequence']

            # Filter by length (sequences already include START/END)
            if len(seq) < MIN_SEQ_LENGTH:
                continue

            # Optionally filter out <UNK> tokens (but keep START/END)
            if not INCLUDE_UNK_TOKENS:
                # Keep START and END, only remove UNK from middle
                start_token = seq[0] if seq[0] == self.start_token_id else None
                end_token = seq[-1] if seq[-1] == self.end_token_id else None
                middle_seq = [token for token in seq[1:-1] if token != self.unk_token_id]

                # Reconstruct sequence
                seq = []
                if start_token is not None:
                    seq.append(start_token)
                seq.extend(middle_seq)
                if end_token is not None:
                    seq.append(end_token)

                if len(seq) < MIN_SEQ_LENGTH:
                    continue

            # Truncate if too long (keeping START, truncate middle, keep END)
            if len(seq) > self.max_length:
                # Keep START token, truncate middle, keep END token
                start = seq[0] if seq[0] == self.start_token_id else None
                end = seq[-1] if seq[-1] == self.end_token_id else None

                if start is not None and end is not None:
                    # Truncate middle part
                    middle_length = self.max_length - 2
                    seq = [start] + seq[1:-1][:middle_length] + [end]
                else:
                    seq = seq[:self.max_length]

            processed.append(seq)

        return processed

    def __len__(self) -> int:
        return len(self.processed_sequences)

    def __getitem__(self, idx: int) -> Dict[str, torch.Tensor]:
        """
        Get a single training example

        Returns:
            {
                'input_ids': [START, token1, token2, ..., tokenN],
                'target_ids': [token1, token2, ..., tokenN, END],
                'attention_mask': [1, 1, 1, ..., 1, 0, 0]  # 1 for real tokens, 0 for padding
            }
        """
        seq = self.processed_sequences[idx]

        # For causal language modeling:
        # Input: [START, token1, token2, ..., tokenN]
        # Target: [token1, token2, ..., tokenN, END]
        input_ids = seq[:-1]
        target_ids = seq[1:]

        seq_length = len(input_ids)

        # Pad to max_length
        if seq_length < self.max_length:
            padding_length = self.max_length - seq_length
            input_ids = input_ids + [self.pad_token_id] * padding_length
            target_ids = target_ids + [self.pad_token_id] * padding_length

        # Create attention mask (1 for real tokens, 0 for padding)
        attention_mask = [1] * seq_length + [0] * (self.max_length - seq_length)

        return {
            'input_ids': torch.tensor(input_ids, dtype=torch.long),
            'target_ids': torch.tensor(target_ids, dtype=torch.long),
            'attention_mask': torch.tensor(attention_mask, dtype=torch.bool)
        }


def load_and_split_data(labeled_workflows_path: str = LABELED_WORKFLOWS_PATH,
                        train_split: float = TRAIN_SPLIT,
                        val_split: float = VAL_SPLIT) -> Tuple[List, List, List]:
    """
    Load and split workflow data into train/val/test sets

    Args:
        labeled_workflows_path: Path to labeled workflows JSON
        train_split: Fraction for training
        val_split: Fraction for validation

    Returns:
        (train_workflows, val_workflows, test_workflows)
    """
    # Load data
    with open(labeled_workflows_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    workflows = data['labeled_workflows']

    # Shuffle
    np.random.seed(42)
    indices = np.random.permutation(len(workflows))
    workflows = [workflows[i] for i in indices]

    # Split
    n_train = int(len(workflows) * train_split)
    n_val = int(len(workflows) * val_split)

    train_workflows = workflows[:n_train]
    val_workflows = workflows[n_train:n_train + n_val]
    test_workflows = workflows[n_train + n_val:]

    if VERBOSE:
        print(f"\nData split:")
        print(f"  Train: {len(train_workflows)} workflows")
        print(f"  Val: {len(val_workflows)} workflows")
        print(f"  Test: {len(test_workflows)} workflows")

    return train_workflows, val_workflows, test_workflows


def create_dataloaders(train_workflows: List,
                       val_workflows: List,
                       test_workflows: List,
                       batch_size: int = BATCH_SIZE) -> Tuple[DataLoader, DataLoader, DataLoader]:
    """
    Create DataLoaders for train/val/test sets

    Args:
        train_workflows, val_workflows, test_workflows: Workflow lists
        batch_size: Batch size

    Returns:
        (train_loader, val_loader, test_loader)
    """
    train_dataset = L3SequenceDataset(train_workflows)
    val_dataset = L3SequenceDataset(val_workflows)
    test_dataset = L3SequenceDataset(test_workflows)

    if VERBOSE:
        print(f"\nDataset sizes:")
        print(f"  Train: {len(train_dataset)} sequences")
        print(f"  Val: {len(val_dataset)} sequences")
        print(f"  Test: {len(test_dataset)} sequences")

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
        num_workers=0,  # Windows compatibility
        pin_memory=False
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=False
    )

    test_loader = DataLoader(
        test_dataset,
        batch_size=batch_size,
        shuffle=False,
        num_workers=0,
        pin_memory=False
    )

    return train_loader, val_loader, test_loader


# Test
if __name__ == "__main__":
    print("=" * 60)
    print("Testing L3 Sequence Dataset")
    print("=" * 60)

    # Load and split
    train_wf, val_wf, test_wf = load_and_split_data()

    # Create datasets
    train_dataset = L3SequenceDataset(train_wf)
    val_dataset = L3SequenceDataset(val_wf)

    # Test a single example
    print(f"\nSample from train dataset:")
    sample = train_dataset[0]
    print(f"  Input IDs shape: {sample['input_ids'].shape}")
    print(f"  Target IDs shape: {sample['target_ids'].shape}")
    print(f"  Attention mask shape: {sample['attention_mask'].shape}")
    print(f"  First 10 input tokens: {sample['input_ids'][:10].tolist()}")
    print(f"  First 10 target tokens: {sample['target_ids'][:10].tolist()}")
    print(f"  Num real tokens: {sample['attention_mask'].sum().item()}")

    # Create dataloaders
    train_loader, val_loader, test_loader = create_dataloaders(train_wf, val_wf, test_wf)

    print(f"\nDataLoader test:")
    batch = next(iter(train_loader))
    print(f"  Batch input_ids shape: {batch['input_ids'].shape}")
    print(f"  Batch target_ids shape: {batch['target_ids'].shape}")
    print(f"  Batch attention_mask shape: {batch['attention_mask'].shape}")

    print("\n" + "=" * 60)
    print("Dataset test completed!")
    print("=" * 60)
