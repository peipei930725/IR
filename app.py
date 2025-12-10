#!/usr/bin/env python3
"""
Flask web UI for searching the built index.
Updated with Bonus features:
1. Query Execution Time Display 
2. Keyword Highlighting in Snippets
3. Enhanced UI with CSS

Run: `python app.py --index index_dir --host 127.0.0.1 --port 5000`
"""
from __future__ import annotations

import argparse
import json
import os
import time  # <--- 新增：用於計算時間
from flask import Flask, request, render_template_string
from markupsafe import Markup

from search import rank

# 更新後的 HTML 模板，包含 CSS 美化與時間顯示
PAGE = """
<!doctype html>
<html lang="zh-TW">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Course Search Engine</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }
      h1 { color: #2c3e50; text-align: center; }
      .search-box { text-align: center; margin-bottom: 30px; background: #f8f9fa; padding: 20px; border-radius: 8px; }
      input[name="q"] { width: 70%; padding: 10px; font-size: 16px; border: 1px solid #ddd; border-radius: 4px; }
      input[type="submit"] { padding: 10px 20px; font-size: 16px; background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
      input[type="submit"]:hover { background-color: #0056b3; }
      .meta-info { color: #666; font-size: 0.9em; margin-bottom: 20px; border-bottom: 1px solid #eee; padding-bottom: 10px; }
      ul { list-style: none; padding: 0; }
      li { margin-bottom: 25px; }
      .result-title { font-size: 1.2em; color: #1a0dab; text-decoration: none; font-weight: bold; }
      .result-title:hover { text-decoration: underline; }
      .result-url { color: #006621; font-size: 0.85em; display: block; margin-bottom: 4px; }
      .result-snippet { color: #545454; font-size: 0.95em; }
      .score { font-size: 0.8em; color: #aaa; }
      em { font-weight: bold; font-style: normal; background-color: #fff3cd; } /* 關鍵字高亮樣式 */
      .footer { text-align: center; margin-top: 50px; font-size: 0.9em; }
    </style>
  </head>
  <body>
    <h1>🔍 Term Project Search</h1>
    
    <div class="search-box">
      <form method="get">
        <input name="q" value="{{q|default('')}}" placeholder="Enter keywords..." />
        <input type="submit" value="Search" />
      </form>
    </div>

    {% if q %}
      <div class="meta-info">
        Found {{results|length}} results in <strong>{{ "%.4f"|format(elapsed) }}</strong> seconds.
      </div>
    {% endif %}

    <ul>
    {% for r in results %}
      <li>
        <a href="{{r.doc.url}}" class="result-title" target="_blank">{{r.doc.title}}</a>
        <span class="result-url">{{r.doc.url}}</span>
        <div class="result-snippet">
           ...{{r.snippet|safe}}...
        </div>
        <div class="score">Rel Score: {{"%.4f"|format(r.score)}}</div>
      </li>
    {% endfor %}
    </ul>
    
    <div class="footer">
      <hr/>
      <p><a href="/about">System Stats (About)</a></p>
    </div>
  </body>
</html>
"""

ABOUT = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8">
    <title>About</title>
    <style>body{font-family: sans-serif; max-width: 600px; margin: 40px auto; padding: 20px;}</style>
  </head>
  <body>
    <h1>System Statistics</h1>
    <p><strong>Index Directory:</strong> {{index_dir}}</p>
    <p><strong>Total Documents Indexed:</strong> {{docs_count}}</p>
    <p><a href="/">&larr; Back to Search</a></p>
  </body>
</html>
"""


app = Flask(__name__)
INDEX_DIR = "index_dir"


@app.route("/")
def search_page():
    q = request.args.get("q", "")
    results = []
    elapsed = 0.0

    if q:
        # Bonus: 開始計時
        start_time = time.time()
        
        ranked = rank(q, INDEX_DIR, topk=20)
        
        # Bonus: 結束計時
        end_time = time.time()
        elapsed = end_time - start_time

        for r in ranked:
            doc = r["doc"]
            
            # --- 修改重點開始 ---
            # 1. 嘗試從 doc 中直接讀取 indexer.py 存好的 'snippet'
            #    如果沒有 snippet，則嘗試讀取 'main_text' (以防萬一)
            raw_snippet = doc.get("snippet") or doc.get("main_text") or ""
            
            # 2. 如果讀出來的是完整的 main_text (太長)，我們需要截斷它
            #    如果你在 indexer.py 已經截斷過了，這裡就不會執行
            if len(raw_snippet) > 150:
                # 簡單截取前 150 字
                raw_snippet = raw_snippet[:150] + "..."

            # 3. 處理關鍵字高亮 (Highlighting)
            #    這是加分項：將關鍵字用 <em> 標籤包起來
            if q and raw_snippet:
                # 注意：這裡使用簡單的字串取代。
                # 如果要做到不分大小寫取代 (Case-insensitive)，需要用 re 模組，
                # 但作業等級用 replace 即可。
                snippet = raw_snippet.replace(q, f"<em>{q}</em>")
            else:
                snippet = raw_snippet
            # --- 修改重點結束 ---

            results.append({"score": r["score"], "doc": doc, "snippet": snippet})

    return render_template_string(PAGE, q=q, results=results, elapsed=elapsed)


@app.route("/about")
def about():
    # 確保 index_dir 存在，避免報錯
    docs_path = os.path.join(INDEX_DIR, "docs.json")
    if os.path.exists(docs_path):
        docs = json.load(open(docs_path, encoding="utf-8"))
        count = len(docs)
    else:
        count = 0
    return render_template_string(ABOUT, index_dir=INDEX_DIR, docs_count=count)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="index_dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    global INDEX_DIR
    INDEX_DIR = args.index
    
    print(f"Starting Search Engine on http://{args.host}:{args.port}")
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()