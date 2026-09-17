#!/usr/bin/env python3
"""Thin wrapper (owner tree layout); all logic lives in train.py."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from train import main

def main_with(argv):
    import argparse
    sys.argv = [sys.argv[0]] + argv
    return main()

if __name__ == "__main__":
    argv = sys.argv[1:]
    if "--config" not in " ".join(argv):
        argv = ["--config", str(Path(__file__).parent / "configs" / "A1_gee_dapt_qgis_sft.yaml")] + argv
    raise SystemExit(main_with(argv))
