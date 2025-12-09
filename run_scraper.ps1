#!/usr/bin/env pwsh
# PowerShell helper to run the scraper (Windows PowerShell compatible)

if (Test-Path -Path .venv) {
    Write-Host "Activating .venv..."
    . ".\.venv\Scripts\Activate.ps1"
}

python scrape_technews_ai.py --output ai_articles.jsonl --max-pages 1 --delay 1.0
