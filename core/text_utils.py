# -*- coding: utf-8 -*-
"""Text processing utilities, including prefix stripping, extraction of polished body text, and Markdown-to-HTML rendering."""

import re
import markdown
import markdown.extensions.tables
import markdown.extensions.fenced_code
import markdown.extensions.nl2br
import markdown.extensions.sane_lists

from typing import Optional

def render_markdown_to_html(text: str, is_dark: Optional[bool] = None) -> str:
    """Converts Markdown text to theme-styled HTML with full support for tables, code blocks, and lists."""
    if not text or not text.strip():
        return ""

    if is_dark is None:
        try:
            from core.theme_manager import ThemeManager
            is_dark = ThemeManager.get_instance().is_dark()
        except Exception:
            is_dark = True

    html_body = markdown.markdown(
        text,
        extensions=[
            'tables',
            'fenced_code',
            'nl2br',
            'sane_lists'
        ]
    )

    if is_dark:
        style_css = """
    body {
        color: #E4E4E7;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        font-size: 14px;
        line-height: 1.6;
        margin: 0;
        padding: 0;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 10px 0;
        border: 1px solid #3F3F46;
    }
    th {
        background-color: #27272A;
        color: #F4F4F5;
        font-weight: bold;
        padding: 8px 12px;
        border: 1px solid #3F3F46;
        text-align: left;
    }
    td {
        padding: 8px 12px;
        border: 1px solid #3F3F46;
        color: #E4E4E7;
        vertical-align: top;
    }
    tr:nth-child(even) {
        background-color: #1E1E22;
    }
    code {
        background-color: #27272A;
        color: #38BDF8;
        padding: 2px 5px;
        border-radius: 4px;
        font-family: "Cascadia Code", Consolas, "Courier New", monospace;
        font-size: 13px;
    }
    pre {
        background-color: #18181B;
        border: 1px solid #27272A;
        padding: 10px;
        border-radius: 6px;
    }
    pre code {
        background-color: transparent;
        padding: 0;
        color: #E4E4E7;
    }
    blockquote {
        border-left: 3px solid #6366F1;
        margin: 8px 0;
        padding-left: 12px;
        color: #A1A1AA;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #F4F4F5;
        margin-top: 12px;
        margin-bottom: 6px;
        font-weight: bold;
    }
    h1 { font-size: 18px; border-bottom: 1px solid #3F3F46; padding-bottom: 4px; }
    h2 { font-size: 16px; border-bottom: 1px solid #27272A; padding-bottom: 3px; }
    h3 { font-size: 15px; }
    strong, b {
        color: #FAFAFA;
        font-weight: bold;
    }
    em, i {
        color: #E4E4E7;
        font-style: italic;
    }
    hr {
        border: none;
        border-top: 1px solid #3F3F46;
        margin: 12px 0;
    }
    ul, ol {
        margin: 6px 0;
        padding-left: 20px;
    }
    li {
        margin-bottom: 4px;
    }
    a {
        color: #60A5FA;
        text-decoration: none;
    }
"""
    else:
        style_css = """
    body {
        color: #0F172A;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif;
        font-size: 14px;
        line-height: 1.6;
        margin: 0;
        padding: 0;
    }
    table {
        border-collapse: collapse;
        width: 100%;
        margin: 10px 0;
        border: 1px solid #CBD5E1;
    }
    th {
        background-color: #F1F5F9;
        color: #0F172A;
        font-weight: bold;
        padding: 8px 12px;
        border: 1px solid #CBD5E1;
        text-align: left;
    }
    td {
        padding: 8px 12px;
        border: 1px solid #CBD5E1;
        color: #334155;
        vertical-align: top;
    }
    tr:nth-child(even) {
        background-color: #F8FAFC;
    }
    code {
        background-color: #F1F5F9;
        color: #0284C7;
        padding: 2px 5px;
        border-radius: 4px;
        font-family: "Cascadia Code", Consolas, "Courier New", monospace;
        font-size: 13px;
    }
    pre {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        padding: 10px;
        border-radius: 6px;
    }
    pre code {
        background-color: transparent;
        padding: 0;
        color: #0F172A;
    }
    blockquote {
        border-left: 3px solid #4F46E5;
        margin: 8px 0;
        padding-left: 12px;
        color: #64748B;
    }
    h1, h2, h3, h4, h5, h6 {
        color: #0F172A;
        margin-top: 12px;
        margin-bottom: 6px;
        font-weight: bold;
    }
    h1 { font-size: 18px; border-bottom: 1px solid #E2E8F0; padding-bottom: 4px; }
    h2 { font-size: 16px; border-bottom: 1px solid #F1F5F9; padding-bottom: 3px; }
    h3 { font-size: 15px; }
    strong, b {
        color: #0F172A;
        font-weight: bold;
    }
    em, i {
        color: #334155;
        font-style: italic;
    }
    hr {
        border: none;
        border-top: 1px solid #E2E8F0;
        margin: 12px 0;
    }
    ul, ol {
        margin: 6px 0;
        padding-left: 20px;
    }
    li {
        margin-bottom: 4px;
    }
    a {
        color: #2563EB;
        text-decoration: none;
    }
"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
{style_css}
</style>
</head>
<body>
{html_body}
</body>
</html>
"""

def strip_unwanted_prefixes(text: str) -> str:
    """清理输出开头可能混入的模型自言自语、系统指令复述或提示词残留。
    
    例如：“重要提醒：请保持使用同种语言【English】进行润色输出...” 或 “润色后：” 等。
    """
    if not text:
        return ""

    unwanted_patterns = [
        # 重要提醒 / 重要提示 / Important Note 等指令复述
        r'^\s*(?:【?\s*重要(?:提醒|提示)\s*】?|Important\s+Note|Important|Note)[\s:：][^\n]*(?:\n+|$)',
        r'^\s*请保持使用同种语言[^\n]*(?:\n+|$)',
        r'^\s*严格(?:保持|使用)同语言[^\n]*(?:\n+|$)',
        # 常见无意义的标题前缀
        r'^\s*###?\s*(?:润色结果|润色正文|润色后|Polished Version|Polished Text|Result)[\s:：]*',
        r'^\s*【(?:润色结果|润色正文|润色后)】[\s:：]*',
        r'^\s*\*\*(?:润色结果|润色正文|润色后)\*\*[\s:：]*',
    ]

    cleaned = text
    changed = True
    # 循环清理，防止存在多行连续前缀
    while changed:
        changed = False
        for pattern in unwanted_patterns:
            new_cleaned = re.sub(pattern, '', cleaned, count=1, flags=re.IGNORECASE)
            if new_cleaned != cleaned:
                cleaned = new_cleaned.lstrip()
                changed = True
                break

    return cleaned.strip()

def extract_polished_body(text: str) -> str:
    """提取润色输出中的纯净正文部分，剥离前缀指令复述与后续的优化要点/修改说明。"""
    if not text:
        return ""

    # 1. 先过滤开头的指令复述与前缀
    body = strip_unwanted_prefixes(text)

    # 2. 识别常见的分割线与说明标题
    split_patterns = [
        r'\n\s*---\s*\n',                     # 标准分割线 ---
        r'\n\s*【\s*(?:优化|修改)要点\s*】',    # 【优化要点】 / 【修改要点】
        r'\n\s*【\s*(?:优化|修改)说明\s*】',    # 【优化说明】 / 【修改说明】
        r'\n\s*###?\s*(?:优化|修改)要点',       # ### 优化要点
        r'\n\s*###?\s*(?:优化|修改)说明',       # ### 修改说明
        r'\n\s*\*\*\s*(?:优化|修改)要点\s*\*\*',# **优化要点**
        r'\n\s*\*\*\s*(?:优化|修改)说明\s*\*\*',# **修改说明**
        r'\n\s*(?:Key\s+)?Revisions?:',        # 英文说明标题
        r'\n\s*Improvements?:',                # 英文说明标题
        r'\n\s*\[\s*(?:Key\s+)?Improvements?\s*\]', # [Key Improvements]
        r'\n\s*###?\s*(?:Key\s+)?Improvements?',    # ### Key Improvements
        r'\n\s*Optimization\s+Notes?:',        # 英文说明标题
        r'\n\s*【\s*(?:改善|推敲)ポイント\s*】',   # 日文说明标题
    ]

    for pattern in split_patterns:
        match = re.search(pattern, body, flags=re.IGNORECASE)
        if match:
            body = body[:match.start()]
            break

    # 3. 再次清理正文残留的前缀
    body = strip_unwanted_prefixes(body)
    return body.strip() if body.strip() else text.strip()


def has_markdown_features(text: str) -> bool:
    """Checks whether the text contains Markdown structures that truly require HTML rendering.

    Returns False for regular sentences, paragraphs, and plain translations, allowing them to
    remain as smooth streamed plain text without jarring re-rendering.
    """
    if not text or not text.strip():
        return False

    # 1. 标题: # 标题, ## 标题
    if re.search(r'(?m)^#{1,6}\s+\S+', text):
        return True

    # 2. 代码块: ``` 或 ~~~
    if '```' in text or '~~~' in text:
        return True

    # 3. 表格: 包含表格结构行与分隔线 | --- |
    if re.search(r'\|[^\n]+\|\n\s*\|[\s\-:]+\|', text):
        return True

    # 4. 引用块: > 引用内容
    if re.search(r'(?m)^>\s+\S+', text):
        return True

    # 5. 无序列表: 行首以 -, *, + 开头并紧跟空格和文字
    if re.search(r'(?m)^[\*\-\+]\s+\S+', text):
        return True

    # 6. 有序列表: 行首以数字点开头并紧跟空格和文字 (如 "1. 第一项")
    if re.search(r'(?m)^\d+\.\s+\S+', text):
        return True

    # 7. 分割线: 连续三个以上 -, *, _
    if re.search(r'(?m)^(?:\-{3,}|\*{3,}|_{3,})\s*$', text):
        return True

    # 8. 行内代码: `code`
    if re.search(r'`[^`\n]+`', text):
        return True

    # 9. 粗体/斜体强调: **bold**, __bold__
    if re.search(r'\*\*[^\*\n]+\*\*|__[^\_\n]+__', text):
        return True

    # 10. Markdown 链接: [text](url)
    if re.search(r'\[[^\]\n]+\]\([^\)\n\s]+\)', text):
        return True

    return False

