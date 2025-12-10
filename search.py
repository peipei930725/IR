#!/usr/bin/env python3
"""
search.py

Load index artifacts and perform TF-IDF + cosine similarity search.
With added support for:
1. Phrase Search (e.g., "data science")
2. Boolean Search (AND, OR, NOT)
"""
from __future__ import annotations

import argparse
import json
import os
import re
from typing import List, Set, Dict, Any

import numpy as np
from sklearn.preprocessing import normalize

# 假設 indexer.py 有這個函式，若沒有請確保在此檔案定義或 import
# from indexer import simple_tokenize 
# 為了方便執行，這裡補上 simple_tokenize 的簡單版本，若你有 jieba 需一併加入
import jieba
def simple_tokenize(text: str) -> List[str]:
    if re.search(r"[\u4e00-\u9fff]", text):
        return [t for t in jieba.cut_for_search(text) if t.strip()]
    return re.findall(r"\b\w+\b", text.lower())

def load_index(index_dir: str):
    print("Loading index...")
    vocab = json.load(open(os.path.join(index_dir, "vocab.json"), encoding="utf-8"))
    docs = json.load(open(os.path.join(index_dir, "docs.json"), encoding="utf-8"))
    
    # 載入倒排索引 (Inverted Index) 用於布林查詢
    inverted = json.load(open(os.path.join(index_dir, "inverted.json"), encoding="utf-8"))
    
    tfidf = np.load(os.path.join(index_dir, "tfidf.npz"))["data"]
    return vocab, docs, tfidf, inverted

def query_to_vector(query: str, vocab: dict, tfidf_matrix: np.ndarray) -> np.ndarray:
    # 移除布林運算子與引號，只保留關鍵字來計算向量分數
    clean_query = query.replace('"', '').replace(' AND ', ' ').replace(' OR ', ' ').replace(' NOT ', ' ')
    tokens = simple_tokenize(clean_query)
    
    vec = np.zeros((tfidf_matrix.shape[1],), dtype=float)
    for t in tokens:
        idx = vocab.get(t)
        if idx is not None and idx < vec.shape[0]:
            vec[idx] += 1.0
    if vec.sum() > 0:
        vec = vec / np.linalg.norm(vec)
    return vec

def boolean_filter(query: str, inverted: Dict[str, List], total_docs: int) -> Set[int] | None:
    """
    解析布林查詢 (AND, OR, NOT) 並回傳符合條件的 Document IDs 集合。
    如果沒有布林運算子，回傳 None (代表不進行過濾)。
    """
    # 簡單的布林解析：假設查詢以空格分隔，運算子為大寫
    # 注意：這裡實作簡化版，不支援複雜括號 (A OR B) AND C
    
    tokens = query.split()
    if 'AND' not in tokens and 'OR' not in tokens and 'NOT' not in tokens:
        return None

    # 初始化結果集合：預設為 None
    result_ids = None
    current_op = 'OR' # 預設起始邏輯，或視為第一個詞的加入
    
    # 輔助函式：從倒排索引取得某個詞的 doc_ids
    def get_ids(term):
        # 移除可能黏在詞上的引號
        term = term.replace('"', '').lower()
        postings = inverted.get(term, [])
        # postings 結構是 [[doc_id, freq], ...]，我們只需要 doc_id
        return set(p[0] for p in postings)

    i = 0
    while i < len(tokens):
        token = tokens[i]
        
        if token in ('AND', 'OR', 'NOT'):
            current_op = token
            i += 1
            continue
        
        # 取得目前詞彙的 ID 集合
        term_ids = get_ids(token)
        
        if result_ids is None:
            # 第一個詞，直接賦值 (如果是 NOT 則是用全集減去)
            if current_op == 'NOT':
                all_ids = set(range(total_docs))
                result_ids = all_ids - term_ids
            else:
                result_ids = term_ids
        else:
            # 根據運算子進行集合運算
            if current_op == 'AND':
                result_ids = result_ids & term_ids   # 交集
            elif current_op == 'OR':
                result_ids = result_ids | term_ids   # 聯集
            elif current_op == 'NOT':
                result_ids = result_ids - term_ids   # 差集
        
        i += 1
        
    return result_ids

def rank(query: str, index_dir: str, topk: int = 10):
    vocab, docs, tfidf, inverted = load_index(index_dir)
    
    # 1. 布林查詢過濾 (Boolean Search)
    allowed_ids = boolean_filter(query, inverted, len(docs))
    
    # 2. 向量計算 (Vector Space Model)
    qv = query_to_vector(query, vocab, tfidf)
    tfidf_norm = normalize(tfidf)
    sims = tfidf_norm @ qv
    
    # 如果有布林過濾，將不符合條件的文件分數設為 0 (或負無窮)
    if allowed_ids is not None:
        mask = np.zeros(sims.shape, dtype=bool)
        # 只保留在 allowed_ids 裡面的 index
        for doc_id in allowed_ids:
            if doc_id < len(sims):
                mask[doc_id] = True
        # 將不在名單內的相似度設為 -1 (排除)
        sims[~mask] = -1.0

    # 排序 (由大到小)
    ranked_indices = sims.argsort()[::-1]
    
    results = []
    
    # 3. 片語搜尋過濾 (Phrase Search)
    # 檢查是否有被雙引號包起來的字串
    phrases = re.findall(r'"([^"]*)"', query)
    
    count = 0
    for idx in ranked_indices:
        score = float(sims[idx])
        if score <= 0: break # 分數為 0 或 -1 代表不相關或被布林排除
        
        doc = docs[idx]
        
        # 片語檢查邏輯
        if phrases:
            # 必須讀取內文來檢查順序。
            # 注意：這裡假設 docs.json 裡有存 'main_text' 或 'content'
            # 如果你的 indexer 沒存內文，這裡會失效。
            text_content = doc.get('main_text') or doc.get('content') or doc.get('snippet') or ""
            text_content = text_content.lower()
            
            # 檢查所有片語是否都出現在內文中
            is_match = True
            for p in phrases:
                if p.lower() not in text_content:
                    is_match = False
                    break
            
            if not is_match:
                continue # 跳過這篇，找下一篇
        
        results.append({"score": score, "doc": doc})
        count += 1
        if count >= topk:
            break
            
    return results

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="index_dir")
    parser.add_argument("--query", required=True)
    parser.add_argument("--topk", type=int, default=10)
    args = parser.parse_args()

    res = rank(args.query, args.index, args.topk)
    
    print(f"Query: {args.query}")
    print(f"Found {len(res)} results.")
    print("-" * 40)
    for r in res:
        print(f"[{r['score']:.4f}] {r['doc']['title']}")
        print(f"Link: {r['doc']['url']}")
        print("")

if __name__ == "__main__":
    main()