#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fingerprint adapter directories for the A1 SHA gate (read-only)."""
import hashlib
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")


def fingerprint(d):
    entries = []
    for root, _, files in os.walk(d):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, d).replace(os.sep, "/")
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for c in iter(lambda: f.read(1 << 20), b""):
                    h.update(c)
            entries.append((rel, h.hexdigest()))
    entries.sort()
    dh = hashlib.sha256()
    for rel, fh in entries:
        dh.update(rel.encode())
        dh.update(fh.encode())
    return dh.hexdigest(), entries


if __name__ == "__main__":
    for d in sys.argv[1:]:
        dh, entries = fingerprint(d)
        print(f"== {d}")
        print(f"   dir_sha256: {dh}  (n_files={len(entries)})")
        for rel, fh in entries:
            print(f"   {fh[:12]}  {rel}")
