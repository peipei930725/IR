#!/usr/bin/env python3
"""
search.py

Load index artifacts and perform TF-IDF + cosine similarity search.

Usage:
  python search.py --index index_dir --query "your query"
"""
from __future__ import annotations

import argparse
import json
import os
import math
from typing import List, Tuple

import numpy as np
from sklearn.preprocessing import normalize

from indexer import simple_tokenize


def load_index(index_dir: str):
    vocab = json.load(open(os.path.join(index_dir, "vocab.json"), encoding="utf-8"))
    docs = json.load(open(os.path.join(index_dir, "docs.json"), encoding="utf-8"))
    tfidf = np.load(os.path.join(index_dir, "tfidf.npz"))["data"]
    return vocab, docs, tfidf


def query_to_vector(query: str, vocab: dict, tfidf_matrix: np.ndarray) -> np.ndarray:
    tokens = simple_tokenize(query)
    vec = np.zeros((tfidf_matrix.shape[1],), dtype=float)
    # simple query TF (binary)
    for t in tokens:
        idx = vocab.get(t)
        if idx is not None and idx < vec.shape[0]:
            vec[idx] += 1.0
    # normalize
    if vec.sum() > 0:
        vec = vec / np.linalg.norm(vec)
    return vec


def rank(query: str, index_dir: str, topk: int = 10):
    vocab, docs, tfidf = load_index(index_dir)
    qv = query_to_vector(query, vocab, tfidf)
    # normalize tfidf rows
    tfidf_norm = normalize(tfidf)
    sims = tfidf_norm @ qv
    ranked = sims.argsort()[::-1]
    results = []
    for idx in ranked[:topk]:
        score = float(sims[idx])
        results.append({"score": score, "doc": docs[idx]})
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="index_dir")
    parser.add_argument("--query", required=True)
    parser.add_argument("--topk", type=int, default=10)
    args = parser.parse_args()

    res = rank(args.query, args.index, args.topk)
    for r in res:
        print(f"{r['score']:.4f}\t{r['doc']['title']}\t{r['doc']['url']}")


if __name__ == "__main__":
    main()
