# -*- coding: utf-8 -*-
# ==============================================================================
# US State Department Press Briefings Crawler (2021–2025)
#
# Description (English)
# ------------------------------------------------------------------------------
# This script scrapes press briefings from the U.S. State Department websites:
#   - Current version: https://www.state.gov/department-press-briefings/
#   - Archived version: https://2021-2025.state.gov/department-press-briefings/
#
# The script works by:
#   1) Collecting article metadata (publish time, type, title, URL) from index pages
#   2) Visiting each article page to extract the full content (including <p>, <h3>,
#      and nested <ul>/<li> lists with indentation and numbering).
#
# Workflow:
#   1) Load progress from CSV (to support resume by source_url)
#   2) Collect article info from index pages (TOTAL_PAGES)
#   3) De-duplicate and filter out processed URLs
#   4) Crawl new article pages and append results to:
#        - CSV  (UTF-8 with BOM) [progress/resume file]
#        - JSON (UTF-8, one JSON object per line)
#
# Resume / checkpoint logic:
#   - The script uses the CSV file as the progress record.
#   - If a source_url already exists in the CSV, it will be skipped on rerun.
#
# Output schema (per record):
# ------------------------------------------------------------------------------
#   source, type, title, date, url, content
#
# Dependencies
# ------------------------------------------------------------------------------
#   pip install requests beautifulsoup4 pandas tqdm openpyxl urllib3 playwright
#
# ------------------------------------------------------------------------------
# 中文说明
# ------------------------------------------------------------------------------
# 本脚本用于爬取美国国务院网站的新闻简报，包括：
#   - 当前版本：https://www.state.gov/department-press-briefings/
#   - 归档版本：https://2021-2025.state.gov/department-press-briefings/
#
# 脚本的功能：
#   1) 从索引页收集文章元数据（发布时间、类型、标题、链接）
#   2) 访问每篇文章的页面并提取完整内容（包括 <p>、<h3> 标签，
#      以及带有缩进和编号的嵌套 <ul>/<li> 列表）
#
# 流程：
#   1）从 CSV 读取进度（按 source_url 断点续爬）
#   2）从多个索引页（TOTAL_PAGES）收集文章信息
#   3）去重并过滤已爬取链接
#   4）爬取新文章详情并追加写入：
#        - CSV（UTF-8 带 BOM）【作为进度文件】
#        - JSONL（UTF-8，每行一个 JSON 记录）
#
# 断点续爬逻辑：
#   - 脚本使用 CSV 文件记录进度。
#   - 如果 CSV 中已存在某个 source_url，则下次运行时跳过该链接。
#
# 输出格式（每条记录）：
# ------------------------------------------------------------------------------
#   source, type, title, date, url, content
#
# 依赖安装：
#   pip install requests beautifulsoup4 pandas tqdm openpyxl urllib3 playwright
# ==============================================================================


import asyncio
import csv
import json
import os
import re
from typing import List, Dict

import pandas as pd
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
from tqdm import tqdm


# ---------------- 参数 ----------------
SITES = [
    {"base": "https://www.state.gov", "index": "https://www.state.gov/department-press-briefings/", "pages": 7},
    {"base": "https://2021-2025.state.gov", "index": "https://2021-2025.state.gov/department-press-briefings/", "pages": 105},
]

OUT_CSV = "state_department_press_briefings.csv"
OUT_JSON = "state_department_press_briefings.json"


# ---------------- 工具函数 ----------------
def ensure_dir_for(path: str):
    d = os.path.dirname(os.path.abspath(path))
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)


def sanitize_text(txt: str) -> str:
    if not txt:
        return ""
    txt = txt.replace("\xa0", " ").replace("\r", " ")
    txt = re.sub(r"[ \t\f\v]+", " ", txt)
    return txt.strip()


def load_done_urls() -> set:
    if not os.path.exists(OUT_CSV):
        return set()
    try:
        df = pd.read_csv(OUT_CSV)
        return set(df["url"].dropna().tolist())
    except Exception:
        return set()


def open_writer():
    file_exists = os.path.exists(OUT_CSV)
    fh = open(OUT_CSV, "a", encoding="utf-8-sig", newline="")
    writer = csv.DictWriter(
        fh,
        fieldnames=["source", "type", "title", "date", "url", "content"],
        quoting=csv.QUOTE_ALL,
        delimiter=",",
        lineterminator="\n",
        escapechar="\\",
    )
    if not file_exists:
        writer.writeheader()
    return fh, writer


# ---------------- 解析函数 ----------------
def parse_index_items(html: str, base_url: str) -> List[Dict]:
    """新版与旧版索引页结构相同"""
    soup = BeautifulSoup(html, "lxml")
    items = []
    for li in soup.select("li.collection-result"):
        a = li.select_one("a.collection-result__link[href]")
        if not a:
            continue
        href = a.get("href", "").strip()
        if href.startswith("/"):
            href = base_url + href
        title = sanitize_text(a.get_text(" ", strip=True))
        typ = sanitize_text(
            (li.select_one("p.collection-result__date") or {}).get_text(" ", strip=True)
        )
        date_el = li.select_one("div.collection-result-meta span:last-child")
        date_text = sanitize_text(date_el.get_text(" ", strip=True) if date_el else "")
        if href and title:
            items.append(
                {"type": typ, "title": title, "url": href, "date": date_text}
            )
    return items


def parse_detail_content(html: str) -> str:
    """提取新闻简报正文"""
    soup = BeautifulSoup(html, "lxml")
    entry = (
        soup.select_one("div.classic-block-wrapper")
        or soup.select_one("div.entry-content")
        or soup.select_one("article")
    )
    if not entry:
        return ""

    # 删除不相关元素
    for bad in entry.select("script, style, noscript, figure, iframe, svg, form, input, button"):
        bad.decompose()

    paragraphs = []
    for tag in entry.find_all(["h2", "h3", "p", "li", "blockquote"]):
        text = sanitize_text(tag.get_text(" ", strip=True))
        if text:
            paragraphs.append(text)

    if not paragraphs:
        text = entry.get_text("\n", strip=True)
        return sanitize_text(text)

    return "\n\n".join(paragraphs)


# ---------------- 网络与写入 ----------------
async def fetch_html(page, url: str, wait_selector: str = None, extra_wait_sec: float = 0.0) -> str:
    await page.goto(url, timeout=120_000, wait_until="domcontentloaded")
    if extra_wait_sec:
        await asyncio.sleep(extra_wait_sec)
    if wait_selector:
        await page.wait_for_selector(wait_selector, timeout=30_000)
    return await page.content()


def write_dual(data: Dict, writer, fh):
    csv_data = data.copy()
    if isinstance(csv_data["content"], str):
        csv_data["content"] = csv_data["content"].replace("\n", "\\n").replace("\r", "")
    writer.writerow(csv_data)
    fh.flush()
    with open(OUT_JSON, "a", encoding="utf-8") as jf:
        jf.write(json.dumps(data, ensure_ascii=False) + "\n")


# ---------------- 主函数 ----------------
async def crawl_all():
    ensure_dir_for(OUT_CSV)
    done = load_done_urls()
    print(f"✅ 已完成 {len(done)} 条，开始爬取新版 + 旧版新闻简报会 ...")

    fh, writer = open_writer()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124 Safari/537.36"
        )

        for site in SITES:
            base, index_base, total_pages = site["base"], site["index"], site["pages"]
            print(f"\n🌐 开始爬取: {base} 共 {total_pages} 页")

            page = await context.new_page()
            for i in tqdm(range(1, total_pages + 1), desc=f"{base} 索引页"):
                index_url = index_base if i == 1 else f"{index_base}page/{i}/"
                try:
                    index_html = await fetch_html(page, index_url, "li.collection-result", 2.0)
                except Exception as e:
                    print(f"⚠️ 第{i}页加载失败: {e}")
                    continue

                items = parse_index_items(index_html, base)
                if not items:
                    print(f"⚠️ 第{i}页为空或结构变化：{index_url}")
                    continue

                for it in items:
                    if it["url"] in done:
                        continue

                    dpage = await context.new_page()
                    try:
                        detail_html = await fetch_html(dpage, it["url"], "div.classic-block-wrapper, div.entry-content, article", 1.5)
                        content = parse_detail_content(detail_html)
                    except Exception as e:
                        print(f"⚠️ 详情页失败 {it['url']}: {e}")
                        content = ""
                    finally:
                        await dpage.close()

                    row = {
                        "source": base,
                        "type": it["type"],
                        "title": it["title"],
                        "date": it["date"],
                        "url": it["url"],
                        "content": content,
                    }
                    write_dual(row, writer, fh)
                    done.add(it["url"])
                    await asyncio.sleep(1.0)

            await page.close()

        await browser.close()
    fh.close()
    print("🏁 全部完成！CSV + JSON 已保存。")


if __name__ == "__main__":
    asyncio.run(crawl_all())
