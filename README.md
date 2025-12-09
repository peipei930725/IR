# TechNews AI Category Scraper

這個小工具用來爬取 TechNews 的 AI 分類頁面（https://technews.tw/category/ai/），並將每篇文章輸出成 JSONL（每行一個 JSON 物件）。

使用方式（Windows PowerShell）：

1. 建議先建立虛擬環境並安裝套件：

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

2. 執行爬蟲（範例：抓 1 頁）：

```powershell
python crawler.py --seeds seeds.txt --output corpus.jsonl --max-pages 1000 --delay 0.1
```

3. 執行查詢網頁
```powershell
python app.py
```


輸出檔案：`corpus.jsonl`（UTF-8），每行為一個 JSON 物件。新增擷取欄位包含：

```json
{
	"title": "文章標題",
	"url": "https://technews.tw/xxxxx/",
	"date": "2025-01-02T12:00:00+08:00",
	"summary": "文章摘要...",
	"author": "作者名稱",
	"tags": ["AI", "研究"],
	"content": "文章全文純文字..."
}
```

說明：`content` 欄位會儘量抓取文章本體的純文字（移除 script/figure/aside），`author` 與 `tags` 使用多種常見 selector 抓取，若網站不同結構可能為 null。

注意事項：
- 程式使用多種備援選擇器來解析頁面，若 TechNews 網站架構變動，解析結果可能需要微調。
- 請尊重網站 robots.txt 與使用頻率，必要時可加大 `--delay`。
