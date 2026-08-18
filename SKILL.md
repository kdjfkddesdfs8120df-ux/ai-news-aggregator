---
name: "ai-news-aggregator"
description: "Aggregates AI-related news from configurable RSS feeds and generates a Chinese document containing only title, link, date and summary. Invoke when user asks for AI news, RSS aggregation, or AI news briefs."
---

# AI 新闻聚合器

## 用途

本 Skill 用于从可配置的 RSS 源抓取 AI 相关新闻，并生成一份格式化的中文文档。输出内容仅保留：

- 标题
- 链接
- 发布日期
- 摘要

其他字段或装饰性内容会被去除。

## 触发条件

当用户提出以下需求时调用本 Skill：

- "搜索 AI 新闻"
- "聚合 RSS 新闻"
- "生成 AI 新闻简报/中文文档"
- "获取最新 AI 资讯"

## 配置 RSS 源

RSS 源在脚本同目录的 `rss_sources.json` 中配置，结构如下：

```json
{
  "sources": [
    {"name": "机器之心", "url": "https://www.jiqizhixin.com/rss"},
    {"name": "MIT Technology Review", "url": "https://www.technologyreview.com/feed/"}
  ]
}
```

用户可通过增删 `sources` 数组来自定义新闻来源。

## 输出格式

生成的中文文档中，每条新闻固定为以下四行：

```text
标题：{新闻标题}
链接：{新闻链接}
发布日期：{YYYY-MM-DD}
摘要：{摘要内容}
```

不同新闻之间用空行分隔，不保留作者、分类、图片等额外信息。

## 执行流程

1. 读取 `rss_sources.json` 获取 RSS 源列表。
2. 逐个拉取 RSS Feed。
3. 解析条目，提取标题、链接、发布日期和摘要。
4. 按发布日期倒序排列。
5. 生成中文文档并保存到工作目录。

## 实现脚本

以下 Python 脚本采用模块化设计，核心逻辑分为配置加载、Feed 拉取、内容解析、文档格式化四个模块。脚本文件通常命名为 `ai_news_aggregator.py`，与 `rss_sources.json` 放在同一目录。

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 新闻聚合器
功能：读取配置的 RSS 源，抓取 AI 相关新闻，生成格式化中文文档。
"""

import json
import os
from datetime import datetime
from urllib.parse import urljoin

import feedparser
import requests


# 模块 1：配置加载
# 负责读取 rss_sources.json 中的 RSS 源配置
def load_sources(config_path="rss_sources.json"):
    """加载 RSS 源配置文件"""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"配置文件不存在：{config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    sources = config.get("sources", [])
    if not sources:
        raise ValueError("配置文件中未找到有效的 RSS 源")

    return sources


# 模块 2：Feed 拉取
# 负责从指定 URL 拉取 RSS 原始数据
def fetch_feed(url, timeout=15):
    """拉取单个 RSS Feed"""
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"[警告] 拉取失败 {url}：{e}")
        return None


# 模块 3：内容解析
# 负责从 Feed 中提取标题、链接、发布日期、摘要
def parse_entries(feed_content):
    """解析 RSS Feed，返回统一格式的新闻条目列表"""
    if feed_content is None:
        return []

    parsed = feedparser.parse(feed_content)
    entries = []

    for entry in parsed.entries:
        # 标题
        title = entry.get("title", "").strip()

        # 链接：优先使用 link，否则从 links 中补全
        link = entry.get("link", "").strip()
        if not link and "links" in entry:
            for l in entry.links:
                if l.get("rel") == "alternate":
                    link = l.get("href", "")
                    break

        # 发布日期：尝试多个常见字段
        published = ""
        for field in ["published_parsed", "updated_parsed", "created_parsed"]:
            if field in entry:
                struct_time = entry[field]
                if struct_time:
                    published = datetime(*struct_time[:6]).strftime("%Y-%m-%d")
                    break

        # 摘要：优先 summary，其次 description，再次 content
        summary = entry.get("summary", "").strip()
        if not summary:
            summary = entry.get("description", "").strip()
        if not summary and "content" in entry:
            summary = entry.content[0].value.strip()

        # 去除 HTML 标签，保留纯文本
        summary = clean_html(summary)

        if title and link:
            entries.append({
                "title": title,
                "link": link,
                "published": published,
                "summary": summary
            })

    return entries


# 辅助函数：去除简单 HTML 标签
def clean_html(raw_html):
    """去除 HTML 标签，返回纯文本摘要"""
    import re
    text = re.sub(r"<[^>]+>", "", raw_html)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# 模块 4：文档格式化
# 负责将新闻条目列表转换为最终中文文档内容
def format_document(entries):
    """生成格式化中文文档"""
    lines = []
    lines.append("# AI 新闻简报")
    lines.append(f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 按发布日期倒序排列
    entries.sort(key=lambda x: x["published"] or "1970-01-01", reverse=True)

    for idx, entry in enumerate(entries, start=1):
        lines.append(f"## {idx}. {entry['title']}")
        lines.append(f"标题：{entry['title']}")
        lines.append(f"链接：{entry['link']}")
        lines.append(f"发布日期：{entry['published'] or '未知'}")
        lines.append(f"摘要：{entry['summary']}")
        lines.append("")

    return "\n".join(lines)


# 主入口
def main():
    """主函数：串联配置加载、拉取、解析、格式化、保存"""
    sources = load_sources()
    all_entries = []

    for source in sources:
        print(f"[信息] 正在拉取：{source['name']} ({source['url']})")
        feed_content = fetch_feed(source["url"])
        entries = parse_entries(feed_content)
        print(f"[信息] 解析到 {len(entries)} 条新闻")
        all_entries.extend(entries)

    document = format_document(all_entries)

    output_path = "ai_news_brief.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(document)

    print(f"[完成] 已生成文档：{output_path}，共 {len(all_entries)} 条新闻")


if __name__ == "__main__":
    main()
```

## 使用方式

1. 将 `ai_news_aggregator.py` 和 `rss_sources.json` 放到同一目录。
2. 安装依赖：

   ```bash
   pip install feedparser requests
   ```

3. 运行脚本：

   ```bash
   python ai_news_aggregator.py
   ```

4. 查看生成的 `ai_news_brief.md`。

## 依赖

- Python 3.8+
- `feedparser`
- `requests`

## 注意事项

- 若 RSS 源返回非标准格式，可能需要针对具体源调整解析逻辑。
- 建议在脚本中增加重试、去重、缓存等机制以提升稳定性。
- 摘要过长的条目可在 `format_document` 中增加截断逻辑。
