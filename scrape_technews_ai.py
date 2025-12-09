#!/usr/bin/env python3
"""
Scrape articles from https://technews.tw/category/ai/

Saves each article as one JSON object per line to the output file (JSONL).

Usage:
  python scrape_technews_ai.py --output ai_articles.jsonl --max-pages 5
"""
from __future__ import annotations

import argparse
import json
import time
from typing import List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; TechNewsAI-Scraper/1.0; +https://example.com)"
}


def fetch(url: str, session: requests.Session, timeout: int = 10) -> Optional[str]:
    try:
        resp = session.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None


def parse_articles(soup: BeautifulSoup, base: str) -> List[dict]:
    results: List[dict] = []

    # Try semantic <article> tags first
    article_nodes = soup.find_all("article")

    if not article_nodes:
        # fallback selectors: common patterns on WordPress sites
        selectors = [
            ".entry-title a",
            ".post .title a",
            "h2 a",
            "h3 a",
            ".post a[href*='/'], .article a[href*='/']",
        ]
        links = []
        for sel in selectors:
            links = soup.select(sel)
            if links:
                for a in links:
                    href = a.get("href")
                    if not href:
                        continue
                    title = a.get_text(strip=True)
                    url = urljoin(base, href)
                    results.append({"title": title, "url": url})
                return results
        return results

    for node in article_nodes:
        a = node.find("a", href=True)
        if not a:
            continue
        href = a["href"]
        title = a.get_text(strip=True)
        link = urljoin(base, href)

        # date: try <time datetime=> or meta with class names
        date = None
        time_tag = node.find("time")
        if time_tag and time_tag.has_attr("datetime"):
            date = time_tag["datetime"]
        elif time_tag:
            date = time_tag.get_text(strip=True)
        else:
            date_node = node.select_one(".entry-date, .post-date, .date")
            if date_node:
                date = date_node.get_text(strip=True)

        # summary: try common summary/excerpt selectors
        summary = None
        summary_node = node.select_one(".entry-summary, .summary, .excerpt, p")
        if summary_node:
            summary = summary_node.get_text(strip=True)

        results.append({"title": title, "url": link, "date": date, "summary": summary})

    return results


def fetch_article_details(url: str, session: requests.Session, timeout: int = 10) -> dict:
    """Fetch an article page and extract author, tags and full content (plain text)."""
    data = {"author": None, "tags": None, "content": None}
    html = fetch(url, session, timeout=timeout)
    if html is None:
        return data
    soup = BeautifulSoup(html, "html.parser")

    # Author: try several common selectors
    author = None
    # meta name=author
    meta_author = soup.find("meta", attrs={"name": "author"})
    if meta_author and meta_author.get("content"):
        author = meta_author.get("content").strip()
    if not author:
        sel = soup.select_one(".author, .byline, .entry-author, .post-author, a[rel='author']")
        if sel:
            author = sel.get_text(strip=True)

    # Tags: common patterns
    tags = []
    tag_selectors = [".tags a", ".post-tags a", ".entry-tags a", "a[rel='tag']"]
    for ts in tag_selectors:
        nodes = soup.select(ts)
        for n in nodes:
            t = n.get_text(strip=True)
            if t:
                tags.append(t)
    if not tags:
        tags = None

    # Content: try common content containers
    content_node = None
    content_selectors = [".entry-content", ".post-content", "article .content", ".content", "#content"]
    for cs in content_selectors:
        content_node = soup.select_one(cs)
        if content_node:
            break

    if not content_node:
        # fallback to article body
        content_node = soup.find("article")

    content_text = None
    if content_node:
        # remove script/style
        for s in content_node(["script", "style", "aside", "figure"]):
            s.decompose()
        content_text = content_node.get_text(separator="\n", strip=True)
    else:
        # last resort: whole page text
        content_text = soup.get_text(separator="\n", strip=True)

    data["author"] = author
    data["tags"] = tags
    data["content"] = content_text
    return data


def find_next_page(soup: BeautifulSoup, base: str) -> Optional[str]:
    # rel=next
    a = soup.find("a", rel="next")
    if a and a.get("href"):
        return urljoin(base, a["href"])

    # Links with next labels (English/Taiwanese)
    candidates = soup.find_all("a")
    next_texts = ["下一頁", "下一页", "Next", "Older Posts", "Older"]
    for c in candidates:
        if not c.string:
            continue
        txt = c.get_text(strip=True)
        if txt in next_texts or txt.lower() in [t.lower() for t in next_texts]:
            href = c.get("href")
            if href:
                return urljoin(base, href)

    # Try common pager classes
    nxt = soup.select_one(".nav-previous a, .pagination a.next, a.next-page")
    if nxt and nxt.get("href"):
        return urljoin(base, nxt["href"])

    return None


def scrape(start_url: str, output: str, max_pages: int = 0, delay: float = 1.0) -> None:
    session = requests.Session()
    url = start_url
    page = 0

    with open(output, "w", encoding="utf-8") as fh:
        while url:
            if max_pages and page >= max_pages:
                break
            print(f"Fetching page: {url}")
            html = fetch(url, session)
            if html is None:
                break
            soup = BeautifulSoup(html, "html.parser")

            articles = parse_articles(soup, url)
            # For each article found on listing, fetch details from its page
            for a in articles:
                details = fetch_article_details(a["url"], session)
                # merge details into article dict
                a.update(details)
                fh.write(json.dumps(a, ensure_ascii=False) + "\n")

            page += 1
            next_page = find_next_page(soup, url)
            if not next_page:
                print("No next page found, finished.")
                break
            url = next_page
            time.sleep(delay)

    print(f"Saved articles to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape TechNews AI category pages")
    parser.add_argument("--start", default="https://technews.tw/category/ai/", help="Start URL")
    parser.add_argument("--output", default="ai_articles.jsonl", help="Output JSONL file")
    parser.add_argument("--max-pages", type=int, default=0, help="Maximum pages to fetch (0 = all)")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between page requests (seconds)")
    args = parser.parse_args()

    scrape(args.start, args.output, max_pages=args.max_pages, delay=args.delay)


if __name__ == "__main__":
    main()
