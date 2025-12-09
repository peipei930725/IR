#!/usr/bin/env python3
"""
indexer.py

Builds an inverted index and TF-IDF vectors from a JSONL corpus.

Outputs a small index directory with:
- docs.json   (list of metadata: id,title,url,fetch_time)
- vocab.json  (term -> index)
- tfidf.npz   (TF-IDF matrix saved via numpy)
- counts.npz  (raw term counts)
- inverted.json (term -> [(doc_id, term_freq), ...])

Usage:
  python indexer.py --input corpus.jsonl --outdir index_dir
"""
from __future__ import annotations

import argparse
import json
import os
import re
import math
from typing import List, Tuple

import jieba
import numpy as np
from sklearn.feature_extraction.text import CountVectorizer, TfidfTransformer


def simple_tokenize(text: str) -> List[str]:
    # If contains CJK characters, use jieba
    if re.search(r"[\u4e00-\u9fff]", text):
        tokens = [t for t in jieba.cut_for_search(text) if t.strip()]
    else:
        tokens = re.findall(r"\b\w+\b", text.lower())
    return tokens


def read_corpus(path: str) -> List[dict]:
    docs = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            try:
                obj = json.loads(line)
            except Exception:
                continue
            docs.append(obj)
    return docs


def build_index(docs: List[dict], outdir: str) -> None:
    texts = [d.get("main_text") or d.get("content") or "" for d in docs]
    titles = [d.get("title", "") for d in docs]
    os.makedirs(outdir, exist_ok=True)

    vect = CountVectorizer(tokenizer=simple_tokenize)
    counts = vect.fit_transform(texts)
    vocab = vect.vocabulary_

    tfidf_transformer = TfidfTransformer()
    tfidf = tfidf_transformer.fit_transform(counts)

    # Build inverted index: term -> list of (doc_id, term_freq)
    inverted = {}
    for term, idx in vocab.items():
        col = counts[:, idx].toarray().ravel()
        postings = []
        nz = np.nonzero(col)[0]
        for doc_id in nz:
            postings.append([int(doc_id), int(col[doc_id])])
        inverted[term] = postings

    # save artifacts
    docs_meta = []
    for i, d in enumerate(docs):
        docs_meta.append({"id": i, "title": d.get("title"), "url": d.get("url"), "fetch_time": d.get("fetch_time")})

    # numpy save
    np.savez_compressed(os.path.join(outdir, "counts.npz"), data=counts.toarray())
    np.savez_compressed(os.path.join(outdir, "tfidf.npz"), data=tfidf.toarray())

    with open(os.path.join(outdir, "vocab.json"), "w", encoding="utf-8") as fh:
        json.dump(vocab, fh, ensure_ascii=False)
    with open(os.path.join(outdir, "docs.json"), "w", encoding="utf-8") as fh:
        json.dump(docs_meta, fh, ensure_ascii=False)
    with open(os.path.join(outdir, "inverted.json"), "w", encoding="utf-8") as fh:
        json.dump(inverted, fh, ensure_ascii=False)

    print(f"Index built: {len(docs)} docs, {len(vocab)} terms -> {outdir}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="corpus.jsonl")
    parser.add_argument("--outdir", default="index_dir")
    args = parser.parse_args()

    docs = read_corpus(args.input)
    build_index(docs, args.outdir)


if __name__ == "__main__":
    main()
