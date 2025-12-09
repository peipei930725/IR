#!/usr/bin/env python3
"""
Flask web UI for searching the built index.

Run: `python app.py --index index_dir --host 127.0.0.1 --port 5000`
"""
from __future__ import annotations

import argparse
import json
import os
from flask import Flask, request, render_template_string

from search import rank


PAGE = """
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>Search</title></head>
  <body>
    <h1>Search</h1>
    <form method="get">
      <input name="q" value="{{q|default('')}}" style="width:60%" />
      <input type="submit" value="Search" />
    </form>
    <p>Found: {{results|length}} results</p>
    <ul>
    {% for r in results %}
      <li>
        <a href="{{r.doc.url}}" target="_blank">{{r.doc.title}}</a>
        <br/><small>{{r.doc.url}}</small>
        <p>Score: {{"%.4f"|format(r.score)}}</p>
        <p>Snippet: {{r.snippet}}</p>
      </li>
    {% endfor %}
    </ul>
    <hr/>
    <p><a href="/about">About</a></p>
  </body>
 </html>
"""

ABOUT = """
<!doctype html>
<html>
  <head><meta charset="utf-8"><title>About</title></head>
  <body>
    <h1>About</h1>
    <p>Index directory: {{index_dir}}</p>
    <p>Docs indexed: {{docs_count}}</p>
    <p><a href="/">Back</a></p>
  </body>
 </html>
"""


app = Flask(__name__)
INDEX_DIR = "index_dir"


@app.route("/")
def search_page():
    q = request.args.get("q", "")
    results = []
    if q:
        ranked = rank(q, INDEX_DIR, topk=20)
        for r in ranked:
            doc = r["doc"]
            text = doc.get("main_text", "")
            snippet = ""
            if text:
                idx = text.find(q)
                if idx != -1:
                    start = max(0, idx-50)
                    end = min(len(text), idx+50)
                    snippet = text[start:end]
                else:
                    snippet = text[:100]
            results.append({"score": r["score"], "doc": doc, "snippet": snippet})
    return render_template_string(PAGE, q=q, results=results)


@app.route("/about")
def about():
    docs = json.load(open(os.path.join(INDEX_DIR, "docs.json"), encoding="utf-8"))
    return render_template_string(ABOUT, index_dir=INDEX_DIR, docs_count=len(docs))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="index_dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    global INDEX_DIR
    INDEX_DIR = args.index
    app.run(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
