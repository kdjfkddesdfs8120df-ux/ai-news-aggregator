#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 新闻聚合器
功能：读取配置的 RSS 源，抓取 AI 相关新闻，生成格式化中文文档。
"""

import html
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

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
    """拉取单个 RSS Feed，禁用代理并模拟浏览器 User-Agent"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    proxies = {
        "http": None,
        "https": None
    }

    try:
        response = requests.get(url, headers=headers, proxies=proxies, timeout=timeout)
        response.raise_for_status()
        return response.content
    except requests.RequestException as e:
        print(f"[警告] 拉取失败 {url}：{e}")
        return None


# 辅助函数：去除简单 HTML 标签并解码实体
def clean_html(raw_html):
    """去除 HTML 标签，解码 HTML 实体，返回纯文本摘要"""
    text = re.sub(r"<[^>]+>", "", raw_html)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# 辅助函数：从 XML 元素中提取文本
def get_text(parent, tag, namespaces=None):
    """获取指定子元素的文本内容"""
    elem = parent.find(tag, namespaces) if namespaces else parent.find(tag)
    return elem.text.strip() if elem is not None and elem.text else ""


# 辅助函数：解析常见日期格式为 YYYY-MM-DD
def parse_date(date_str):
    """解析 RSS/Atom 日期字符串"""
    if not date_str:
        return ""

    # 尝试 RSS 标准日期格式，如 Mon, 06 Sep 2021 07:00:00 GMT
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    # 尝试 ISO 8601 格式，如 2021-09-06T07:00:00Z
    try:
        normalized = date_str.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return ""


# 模块 3：内容解析
# 负责从 Feed 中提取标题、链接、发布日期、摘要
def parse_entries(feed_content):
    """解析 RSS/Atom Feed，返回统一格式的新闻条目列表"""
    if feed_content is None:
        return []

    try:
        root = ET.fromstring(feed_content)
    except ET.ParseError as e:
        print(f"[警告] XML 解析失败：{e}")
        return []

    entries = []
    root_tag = root.tag.split("}")[-1]  # 去除命名空间前缀

    if root_tag == "rss":
        # RSS 2.0 格式解析
        channel = root.find("channel")
        if channel is None:
            return entries

        for item in channel.findall("item"):
            title = get_text(item, "title")
            link = get_text(item, "link")
            pub_date = get_text(item, "pubDate")
            description = get_text(item, "description")

            if title and link:
                entries.append({
                    "title": title,
                    "link": link,
                    "published": parse_date(pub_date),
                    "summary": clean_html(description)
                })

    elif root_tag == "feed":
        # Atom 格式解析
        namespaces = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", namespaces):
            title = get_text(entry, "atom:title", namespaces)
            updated = get_text(entry, "atom:updated", namespaces)
            summary = get_text(entry, "atom:summary", namespaces)

            # 链接在 Atom 中通常是 link 元素的 href 属性
            link = ""
            link_elem = entry.find("atom:link", namespaces)
            if link_elem is not None:
                link = link_elem.get("href", "").strip()

            # 若 summary 为空，尝试 content 元素
            if not summary:
                content_elem = entry.find("atom:content", namespaces)
                if content_elem is not None and content_elem.text:
                    summary = content_elem.text.strip()

            if title and link:
                entries.append({
                    "title": title,
                    "link": link,
                    "published": parse_date(updated),
                    "summary": clean_html(summary)
                })

    return entries


# 模块 4：文档格式化
# 负责将新闻条目列表转换为最终中文文档内容
def format_document(entries, max_entries=200, max_summary_length=500):
    """生成格式化中文文档，限制总条数和摘要长度"""
    lines = []
    lines.append("# AI 新闻简报")
    lines.append(f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    # 按发布日期倒序排列
    entries.sort(key=lambda x: x["published"] or "1970-01-01", reverse=True)

    # 限制最终输出条数，避免文档过大
    entries = entries[:max_entries]

    for idx, entry in enumerate(entries, start=1):
        # 摘要过长时截断，保持文档简洁
        summary = entry["summary"]
        if len(summary) > max_summary_length:
            summary = summary[:max_summary_length] + "..."

        lines.append(f"## {idx}. {entry['title']}")
        lines.append(f"标题：{entry['title']}")
        lines.append(f"链接：{entry['link']}")
        lines.append(f"发布日期：{entry['published'] or '未知'}")
        lines.append(f"摘要：{summary}")
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
    output_count = min(len(all_entries), 200)

    output_path = "ai_news_brief.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(document)

    print(f"[完成] 已生成文档：{output_path}，共 {output_count} 条新闻（原始抓取 {len(all_entries)} 条）")


if __name__ == "__main__":
    main()
