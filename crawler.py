#!/usr/bin/env python3
"""
crawler.py

Simple polite crawler that:
- accepts 5-10 seed URLs (or uses defaults)
- respects robots.txt
- enforces delay >= 2s between requests
- crawls up to max_pages (default 1000)
- stores documents as JSONL with fields: url, title, main_text, fetch_time

Usage:
  python crawler.py --seeds seeds.txt --output corpus.jsonl --max-pages 1000
"""
from __future__ import annotations

import argparse
import json
import time
import re
from datetime import datetime
from typing import List, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from urllib import robotparser


HEADERS = {"User-Agent": "PoliteCrawler/1.0 (+https://example.com)"}


def load_seeds(path: str) -> List[str]:
    with open(path, "r", encoding="utf-8") as fh:
        seeds = [line.strip() for line in fh if line.strip() and not line.startswith("#")]
    return seeds


def same_domain(a: str, b: str) -> bool:
    return urlparse(a).netloc == urlparse(b).netloc


def text_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    # remove scripts and styles
    for s in soup(["script", "style", "aside", "footer", "nav", "form"]):
        s.decompose()
    # try common content selectors
    selectors = [".entry-content", ".post-content", "article .content", ".content", "#content"]
    for sel in selectors:
        node = soup.select_one(sel)
        if node:
            return node.get_text(separator="\n", strip=True)
    # fallback to whole page
    return soup.get_text(separator="\n", strip=True)


def get_links(html: str, base: str, base_domain: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("mailto:") or href.startswith("javascript:") or href.startswith("#"):
            continue
        # 只處理 http/https 開頭或 / 開頭的連結
        if not (href.startswith("http") or href.startswith("/")):
            continue
        try:
            full = urljoin(base, href)
        except Exception:
            continue
        # only keep links from the same domain
        if urlparse(full).netloc != base_domain:
            continue
        # 只保留新聞文章頁（INSIDE: /article/），排除 /tag/、/author/、/feature/ 等分類頁
        if "/article/" in full:
            links.append(full)
    return links


def title_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    if soup.title:
        return soup.title.get_text(strip=True)
    h1 = soup.find("h1")
    if h1:
        return h1.get_text(strip=True)
    return ""


def is_html(response: requests.Response) -> bool:
    ctype = response.headers.get("Content-Type", "")
    return "html" in ctype


def crawl(seeds: List[str], output: str, max_pages: int = 1000, delay: float = 0.1) -> None:
    session = requests.Session()
    visited: Set[str] = set()
    queue: List[str] = list(seeds)
    parsed_robots = {}
    fetched = 0

    with open(output, "w", encoding="utf-8") as fh:
        while queue and fetched < max_pages:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)

            parsed = urlparse(url)
            base = f"{parsed.scheme}://{parsed.netloc}"
            rp = parsed_robots.get(base)
            if rp is None:
                rp = robotparser.RobotFileParser()
                rp.set_url(urljoin(base, "/robots.txt"))
                try:
                    rp.read()
                except Exception:
                    # if robots.txt unreachable, assume allowed
                    pass
                parsed_robots[base] = rp

            if not rp.can_fetch(HEADERS["User-Agent"], url):
                continue  # silently skip robots.txt blocked URLs

            try:
                resp = session.get(url, headers=HEADERS, timeout=15)
            except Exception:
                continue  # silently skip fetch errors

            if resp.status_code != 200 or not is_html(resp):
                continue

            html = resp.text
            title = title_from_html(html)
            main_text = text_from_html(html)
            fetch_time = datetime.utcnow().isoformat() + "Z"

            doc = {"url": url, "title": title, "main_text": main_text, "fetch_time": fetch_time}
            fh.write(json.dumps(doc, ensure_ascii=False) + "\n")
            fetched += 1
            print(f"[{fetched}] {url}")

            # enqueue links from same domain only
            domain = urlparse(url).netloc
            links = get_links(html, url, domain)
            for link in links:
                # normalize: drop fragments
                link = re.sub(r"#.*$", "", link)
                if link and link not in visited:
                    queue.append(link)

            time.sleep(delay)

    print(f"Crawl complete, fetched {fetched} pages -> {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", default="seeds.txt", help="File with seed URLs (one per line)")
    parser.add_argument("--output", default="corpus.jsonl", help="Output JSONL file")
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between requests (seconds, default 2.0)")
    args = parser.parse_args()

    try:
        seeds = load_seeds(args.seeds)
    except Exception:
        # fallback seeds: technews ai + NTU + arXiv cs.AI
        seeds = [
            "https://technews.tw/category/ai/",
            "https://www.ntu.edu.tw/",
            "https://ocw.ntu.edu.tw/",
            "https://arxiv.org/list/cs.AI/recent",
            "https://medium.com/tag/artificial-intelligence",
        ]

    crawl(seeds, args.output, max_pages=args.max_pages, delay=args.delay)


if __name__ == "__main__":
    main()
