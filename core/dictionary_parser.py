# -*- coding: utf-8 -*-
"""Structured dictionary output parser and data models."""

import re
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class DefinitionItem:
    pos: str = ""              # e.g., "adj.", "n.", "v."
    meaning: str = ""          # e.g., "a scientific procedure undertaken to make a discovery"
    meaning_trans: str = ""    # e.g., "实验，试验；尝试"


@dataclass
class ExampleItem:
    source: str = ""    # e.g., "Fame in the modern world is fleeting and ephemeral."
    target: str = ""    # e.g., "现代社会的声名短暂而转瞬即逝。"


@dataclass
class DictionaryEntry:
    word: str = ""
    pronunciation: str = ""
    definitions: List[DefinitionItem] = field(default_factory=list)
    examples: List[ExampleItem] = field(default_factory=list)
    phrases: List[str] = field(default_factory=list)
    synonyms: List[str] = field(default_factory=list)
    antonyms: List[str] = field(default_factory=list)
    is_structured: bool = True
    raw_text: str = ""


def parse_dictionary_output(text: str) -> DictionaryEntry:
    """
    Parses LLM output into a structured DictionaryEntry.

    Supports the Tagged Section Protocol:
    [WORD] ...
    [PRON] ...
    [DEFS] ...
    [EXAMPLES] ...
    [PHRASES] ...
    [SYNONYMS] ...
    [ANTONYMS] ...

    If the text lacks tags (fallback mode), intelligently extracts headings,
    pronunciations, and bullet points, or provides safe raw fallback.
    """
    if not text:
        return DictionaryEntry(raw_text="")

    raw = text.strip()
    entry = DictionaryEntry(raw_text=raw)

    # 检查是否存在结构化标签
    has_tags = bool(re.search(r'\[(WORD|PRON|DEFS|EXAMPLES|PHRASES|SYNONYMS|ANTONYMS)\]', raw, re.I))

    if has_tags:
        _parse_tagged_protocol(raw, entry)
    else:
        _parse_fallback_freeform(raw, entry)

    return entry


def _is_incomplete_tag_fragment(line: str) -> bool:
    """Detects whether a line is an unclosed/incomplete protocol tag fragment being streamed."""
    clean = re.sub(r'^[-*•\d\.]+\s*', '', line).strip()
    if not clean:
        return True
    if clean in ('[', ']', '•', '-', '*'):
        return True
    # 检查是否以 [ 开头但未闭合 ]
    if clean.startswith('[') and ']' not in clean:
        tag_prefix = clean[1:].strip().upper()
        known_tags = ("WORD", "PRON", "DEFS", "EXAMPLES", "PHRASES", "SYNONYMS", "ANTONYMS")
        if any(kt.startswith(tag_prefix) for kt in known_tags) or (len(tag_prefix) <= 10 and tag_prefix.isalpha()):
            return True
    # 过滤完整协议标签误入内容行
    if re.match(r'^\[(?:WORD|PRON|DEFS|EXAMPLES|PHRASES|SYNONYMS|ANTONYMS)\]', clean, re.I):
        return True
    return False


def _parse_tagged_protocol(raw: str, entry: DictionaryEntry):
    """Parses text structured with [TAG] markers."""
    entry.is_structured = True

    # 提取 [WORD]
    m_word = re.search(r'\[WORD\][ \t]*([^\n\r]+)', raw, re.I)
    if m_word:
        entry.word = m_word.group(1).strip()

    # 提取 [PRON]
    m_pron = re.search(r'\[PRON\][ \t]*([^\n\r]+)', raw, re.I)
    if m_pron:
        pron_str = m_pron.group(1).strip()
        parts = pron_str.split()
        if len(parts) == 2 and parts[0] == parts[1]:
            pron_str = parts[0]
        entry.pronunciation = pron_str

    # 切分各个主区域
    sections = re.split(r'(?=\[(?:WORD|PRON|DEFS|EXAMPLES|PHRASES|SYNONYMS|ANTONYMS)\])', raw, flags=re.I)

    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue

        # [DEFS]
        if re.match(r'^\[DEFS\]', sec, re.I):
            content = re.sub(r'^\[DEFS\][ \t]*\n?', '', sec, flags=re.I).strip()
            for line in content.splitlines():
                line = line.strip()
                if not line or _is_incomplete_tag_fragment(line):
                    continue
                # 去除前导符号如 -, *, •, 1., 2.
                clean_line = re.sub(r'^[-*•\d\.]+\s*', '', line).strip()
                if not clean_line or clean_line in ('[', ']'):
                    continue
                # 尝试匹配词性如 "adj. 短暂的", "[adj.] 短暂的", "n. 词语", "名詞. 行為", "動詞. 摂ること"
                m_pos = re.match(r'^(?:\[?([a-zA-Z\u4e00-\u9fa5\./]+)\]?\.?)\s+(.+)$', clean_line)
                if m_pos and len(m_pos.group(1)) <= 6:
                    pos = m_pos.group(1).strip()
                    if not pos.endswith('.'):
                        pos += '.'
                    raw_meaning = m_pos.group(2).strip()
                else:
                    pos = ""
                    raw_meaning = clean_line

                meaning = raw_meaning
                meaning_trans = ""

                # 1. 优先使用标准分隔符 ("|", "——", "—", "\t", "//", "::")
                for sep in ['|', '——', '—', '\t', '//', '::']:
                    if sep in raw_meaning:
                        parts = raw_meaning.split(sep, 1)
                        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                            meaning = parts[0].strip()
                            meaning_trans = parts[1].strip()
                            break

                # 2. 若无分隔符，智能检测西文/日文原释义与汉字对照分界
                if not meaning_trans:
                    m_cjk = re.search(r'^([A-Za-z0-9\s,\.\?\!\'\"\-:;\(\)/]+?)\s+([\u4e00-\u9fa5\u3040-\u30ff].*)$', raw_meaning)
                    if m_cjk and len(m_cjk.group(1).strip()) > 3:
                        meaning = m_cjk.group(1).strip()
                        meaning_trans = m_cjk.group(2).strip()
                    else:
                        m_ja_zh = re.search(r'^(.+?[\u3040-\u309f\u30a0-\u30ff][^。\n]*[。？！\s]+)([\u4e00-\u9fa5].+)$', raw_meaning)
                        if m_ja_zh:
                            tgt = m_ja_zh.group(2).strip()
                            if not any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff' for ch in tgt):
                                meaning = m_ja_zh.group(1).strip()
                                meaning_trans = tgt

                entry.definitions.append(DefinitionItem(pos=pos, meaning=meaning, meaning_trans=meaning_trans))

        # [EXAMPLES]
        elif re.match(r'^\[EXAMPLES\]', sec, re.I):
            content = re.sub(r'^\[EXAMPLES\][ \t]*\n?', '', sec, flags=re.I).strip()
            for line in content.splitlines():
                line = line.strip()
                if not line or _is_incomplete_tag_fragment(line):
                    continue
                clean_line = re.sub(r'^[-*•\d\.]+\s*', '', line).strip()
                if not clean_line or clean_line in ('[', ']', '|'):
                    continue

                # 若行首以 | 开头，说明是换行备选译文或格式残片
                if clean_line.startswith('|'):
                    pipe_sub = clean_line.lstrip('| ').strip()
                    if pipe_sub and entry.examples and not entry.examples[-1].target:
                        entry.examples[-1].target = pipe_sub
                    continue

                # 1. 优先使用标准分隔符 ("|", "——", "—", "\t", "//", "::")
                split_matched = False
                for sep in ['|', '——', '—', '\t', '//', '::']:
                    if sep in clean_line:
                        parts = clean_line.split(sep, 1)
                        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                            entry.examples.append(ExampleItem(source=parts[0].strip(), target=parts[1].strip()))
                            split_matched = True
                            break
                if split_matched:
                    continue

                # 2. 智能检测日语原句与中文译文分界（日语原句含假名，紧随中文译文，无假名）
                m_ja_zh = re.search(r'^(.+?[\u3040-\u309f\u30a0-\u30ff][^。\n]*[。？！\s]+)([\u4e00-\u9fa5].+)$', clean_line)
                if m_ja_zh:
                    src_part = m_ja_zh.group(1).strip()
                    tgt_part = m_ja_zh.group(2).strip()
                    if not any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff' for ch in tgt_part):
                        entry.examples.append(ExampleItem(source=src_part, target=tgt_part))
                        continue

                # 3. 智能检测西文原句与汉字/假名译文的分界线（处理模型偶发漏标 | 的情况）
                m_cjk = re.search(r'^([A-Za-z0-9\s,\.\?\!\'\"\-:;\(\)/]+?)\s+([\u4e00-\u9fa5\u3040-\u30ff].*)$', clean_line)
                if m_cjk and len(m_cjk.group(1).strip()) > 3:
                    entry.examples.append(ExampleItem(source=m_cjk.group(1).strip(), target=m_cjk.group(2).strip()))
                else:
                    entry.examples.append(ExampleItem(source=clean_line, target=""))

        # [PHRASES]
        elif re.match(r'^\[PHRASES\]', sec, re.I):
            content = re.sub(r'^\[PHRASES\][ \t]*\n?', '', sec, flags=re.I).strip()
            items = re.split(r'[,;，；\n]+', content)
            entry.phrases = [it.strip().lstrip('-*• ') for it in items if it.strip()]

        # [SYNONYMS]
        elif re.match(r'^\[SYNONYMS\]', sec, re.I):
            content = re.sub(r'^\[SYNONYMS\][ \t]*\n?', '', sec, flags=re.I).strip()
            items = re.split(r'[,;，；\n]+', content)
            entry.synonyms = [it.strip().lstrip('-*• ') for it in items if it.strip()]

        # [ANTONYMS]
        elif re.match(r'^\[ANTONYMS\]', sec, re.I):
            content = re.sub(r'^\[ANTONYMS\][ \t]*\n?', '', sec, flags=re.I).strip()
            items = re.split(r'[,;，；\n]+', content)
            entry.antonyms = [it.strip().lstrip('-*• ') for it in items if it.strip()]


def _parse_fallback_freeform(raw: str, entry: DictionaryEntry):
    """Fallback parser for unstructured or markdown-formatted outputs."""
    lines = raw.splitlines()
    if not lines:
        return

    entry.is_structured = False

    # 尝试从自由文本首行提取词头与音标
    first_line = lines[0].strip().lstrip('#* -')
    m_pron = re.search(r'(/[^\n/]+/|\[[^\n\]]+\])', first_line)
    if m_pron:
        entry.pronunciation = m_pron.group(1)
        entry.word = first_line.replace(entry.pronunciation, '').strip().strip(':：')
    else:
        entry.word = first_line
