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
        # 防御性回退：若存在部分标签但缺少 [DEFS] 与 [EXAMPLES]，补充自由格式解析
        if not entry.definitions and not entry.examples:
            _parse_fallback_freeform(raw, entry, preserve_extracted=True)
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


VALID_POS_TAGS = {
    # English abbreviations
    "v", "n", "adj", "adv", "vt", "vi", "prep", "conj", "pron", "int", "art",
    "num", "aux", "abbr", "pl", "sing", "idiom", "phr", "interj", "part", "det",
    # Chinese POS
    "名", "动", "形", "副", "介", "连", "代", "叹", "数", "量", "助",
    "名词", "动词", "形容词", "副词", "介词", "连词", "代词", "感叹词",
    "及物", "不及物", "及物动词", "不及物动词", "成语", "熟语", "短语",
    # Japanese POS
    "動", "名詞", "動詞", "形容詞", "形容動詞", "副詞", "助詞", "感動詞", "連体詞", "接続詞", "句"
}


def _is_valid_pos_tag(tag: str) -> bool:
    """Checks if candidate string is a recognized part-of-speech abbreviation or word."""
    cleaned = tag.strip('[]()（）:：. /').lower()
    if not cleaned:
        return False
    if cleaned in VALID_POS_TAGS:
        return True
    without_dots = cleaned.replace('.', '')
    if without_dots in VALID_POS_TAGS:
        return True
    parts = without_dots.split('/')
    if len(parts) > 1 and all(p in VALID_POS_TAGS for p in parts if p):
        return True
    return False


def _extract_pos_and_meaning(clean_line: str) -> Optional[tuple[str, str, str]]:
    """
    Extracts (pos, meaning, meaning_trans) from a single definition line.
    Returns None if the line does not match any recognized POS pattern.
    """
    if not clean_line or clean_line in ('[', ']'):
        return None

    pos = ""
    raw_meaning = ""

    # 1. 显式方括号/圆括号词性：如 [v.], [n.], [adj.], [vt.], [vi.], (v.), (动), [名], [動詞]
    m_bracket = re.match(r'^[\[（\(]([a-zA-Z\u4e00-\u9fa5\./]{1,10})[\]）\)]\.?\s*(.+)$', clean_line)
    if m_bracket:
        raw_pos = m_bracket.group(1).strip()
        if _is_valid_pos_tag(raw_pos):
            cleaned_pos = raw_pos.strip('[]()（）:：. ')
            if cleaned_pos:
                if cleaned_pos.isascii():
                    cleaned_pos = cleaned_pos.lower()
                pos = cleaned_pos + '.'
                raw_meaning = m_bracket.group(2).strip()

    # 2. 常见英文缩写词性加点：如 v. n. adj. adv. vt. vi. prep. conj. pron. int. art. num. aux. abbr. pl. idiom.
    if not pos:
        m_dot = re.match(r'^((?:v|n|adj|adv|vt|vi|prep|conj|pron|int|art|num|aux|abbr|pl|idiom)\.)\s+(.+)$', clean_line, re.IGNORECASE)
        if m_dot:
            pos = m_dot.group(1).lower()
            raw_meaning = m_dot.group(2).strip()

    # 3. 中日文显式词性：如 动词. 名词: 動詞. 形容詞:
    if not pos:
        m_cjk = re.match(r'^((?:名[词詞]|动[词詞]|動詞|形容[词詞]|形容動詞|副[词詞]|介[词詞]|连[词詞]|代[词詞]|感叹词|感動詞|及物[动词]?|不及物[动词]?)[\.：:]?)\s*(.+)$', clean_line)
        if m_cjk:
            raw_pos = m_cjk.group(1).strip('：:. ')
            pos = raw_pos + '.'
            raw_meaning = m_cjk.group(2).strip()

    # 4. 冒号分隔词性：如 v: n: adj:
    if not pos:
        m_colon = re.match(r'^((?:v|n|adj|adv|vt|vi|prep|conj|pron|int|art|num|aux|idiom)[:：])\s*(.+)$', clean_line, re.IGNORECASE)
        if m_colon:
            pos = m_colon.group(1).strip(':：').lower() + '.'
            raw_meaning = m_colon.group(2).strip()

    if not pos or not raw_meaning:
        return None

    # 分割 meaning 与 meaning_trans
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

    # 2. 智能西文/日文原释义与中文对照分界
    if not meaning_trans:
        m_cjk_sep = re.search(r'^([A-Za-z0-9\s,\.\?\!\'\"\-:;\(\)/]+?)\s+([\u4e00-\u9fa5\u3040-\u30ff].*)$', raw_meaning)
        if m_cjk_sep and len(m_cjk_sep.group(1).strip()) > 3:
            meaning = m_cjk_sep.group(1).strip()
            meaning_trans = m_cjk_sep.group(2).strip()
        else:
            m_ja_zh = re.search(r'^(.+?[\u3040-\u309f\u30a0-\u30ff][^。\n]*[。？！\s]+)([\u4e00-\u9fa5].+)$', raw_meaning)
            if m_ja_zh:
                tgt = m_ja_zh.group(2).strip()
                if not any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff' for ch in tgt):
                    meaning = m_ja_zh.group(1).strip()
                    meaning_trans = tgt

    return (pos, meaning, meaning_trans)


def _parse_example_line(clean_line: str) -> Optional[ExampleItem]:
    """Parses a single example line into an ExampleItem."""
    clean_line = re.sub(r'^[-*•\d\.]+\s*', '', clean_line).strip()
    if not clean_line or clean_line in ('[', ']', '|'):
        return None

    # 1. 优先使用标准分隔符
    for sep in ['|', '——', '—', '\t', '//', '::']:
        if sep in clean_line:
            parts = clean_line.split(sep, 1)
            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                return ExampleItem(source=parts[0].strip(), target=parts[1].strip())

    # 2. 智能检测日语原句与中文译文分界
    m_ja_zh = re.search(r'^(.+?[\u3040-\u309f\u30a0-\u30ff][^。\n]*[。？！\s]+)([\u4e00-\u9fa5].+)$', clean_line)
    if m_ja_zh:
        src_part = m_ja_zh.group(1).strip()
        tgt_part = m_ja_zh.group(2).strip()
        if not any('\u3040' <= ch <= '\u309f' or '\u30a0' <= ch <= '\u30ff' for ch in tgt_part):
            return ExampleItem(source=src_part, target=tgt_part)

    # 3. 智能检测西文原句与汉字/假名译文分界
    m_cjk = re.search(r'^([A-Za-z0-9\s,\.\?\!\'\"\-:;\(\)/]+?)\s+([\u4e00-\u9fa5\u3040-\u30ff].*)$', clean_line)
    if m_cjk and len(m_cjk.group(1).strip()) > 3:
        return ExampleItem(source=m_cjk.group(1).strip(), target=m_cjk.group(2).strip())

    return ExampleItem(source=clean_line, target="")


def _parse_tagged_protocol(raw: str, entry: DictionaryEntry):
    """Parses text structured with [TAG] markers."""
    entry.is_structured = True

    # 提取 [WORD]
    m_word = re.search(r'\[WORD\][ \t]*([^\n\r]+)', raw, re.I)
    if m_word:
        word_candidate = m_word.group(1).strip()
        # 防御性过滤：若模型误将释义或包含竖线 '|' 的内容直接输出在 [WORD] 行
        if '|' in word_candidate or '——' in word_candidate or len(word_candidate) > 40:
            parts = [p.strip() for p in re.split(r'[|——]', word_candidate) if p.strip()]
            found_word = ""
            for p in parts:
                w_list = p.split()
                if 1 <= len(w_list) <= 3 and all(w.isalnum() or w in ("-", "'") for w in w_list):
                    found_word = p
                    break
            entry.word = found_word
            # 将此误写在 [WORD] 行的释义回补进 definitions，确保内容不丢失
            if len(parts) >= 2:
                if any('\u4e00' <= ch <= '\u9fa5' for ch in parts[0]):
                    trans_part, mean_part = parts[0], parts[1]
                else:
                    mean_part, trans_part = parts[0], parts[1]
                entry.definitions.insert(0, DefinitionItem(pos="", meaning=mean_part, meaning_trans=trans_part))
        else:
            entry.word = word_candidate

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
                clean_line = re.sub(r'^[-*•\d\.]+\s*', '', line).strip()
                if not clean_line or clean_line in ('[', ']'):
                    continue

                extracted = _extract_pos_and_meaning(clean_line)
                if extracted:
                    pos, meaning, meaning_trans = extracted
                else:
                    pos = ""
                    meaning = clean_line
                    meaning_trans = ""
                    for sep in ['|', '——', '—', '\t', '//', '::']:
                        if sep in clean_line:
                            parts = clean_line.split(sep, 1)
                            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                                meaning = parts[0].strip()
                                meaning_trans = parts[1].strip()
                                break
                    if not meaning_trans:
                        m_cjk = re.search(r'^([A-Za-z0-9\s,\.\?\!\'\"\-:;\(\)/]+?)\s+([\u4e00-\u9fa5\u3040-\u30ff].*)$', clean_line)
                        if m_cjk and len(m_cjk.group(1).strip()) > 3:
                            meaning = m_cjk.group(1).strip()
                            meaning_trans = m_cjk.group(2).strip()
                        else:
                            m_ja_zh = re.search(r'^(.+?[\u3040-\u309f\u30a0-\u30ff][^。\n]*[。？！\s]+)([\u4e00-\u9fa5].+)$', clean_line)
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

                if clean_line.startswith('|'):
                    pipe_sub = clean_line.lstrip('| ').strip()
                    if pipe_sub and entry.examples and not entry.examples[-1].target:
                        entry.examples[-1].target = pipe_sub
                    continue

                ex_item = _parse_example_line(clean_line)
                if ex_item:
                    entry.examples.append(ex_item)

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


def _parse_fallback_freeform(raw: str, entry: DictionaryEntry, preserve_extracted: bool = False):
    """Fallback parser for unstructured, markdown-formatted, or non-tagged outputs."""
    lines = [line.strip() for line in raw.splitlines() if line.strip()]
    if not lines:
        return

    start_idx = 0

    # 1. 词头与读音解析
    if not preserve_extracted or not entry.word:
        first_line = lines[0].lstrip('#* -')
        first_clean = re.sub(r'^[-*•\d\.]+\s*', '', first_line).strip()
        if _extract_pos_and_meaning(first_clean):
            # 第一行即为词性与释义，直接从第 0 行开始解析释义
            start_idx = 0
        else:
            start_idx = 1
            # 优先提取带斜杠的国际音标 /.../
            m_slash = re.search(r'/([^/\n\r]+)/', first_line)
            if m_slash:
                pron_found = m_slash.group(0).strip()
                rem = first_line.replace(pron_found, '').strip()
                clean_word = re.sub(r'^[\[\(\*#\s]+|[\]\)\*#\s]+$', '', rem).strip().strip(':：')
                entry.pronunciation = pron_found
                entry.word = clean_word
            else:
                # 提取带方括号的音标或词头 [word] 或 [pron]
                m_bracket = re.search(r'\[([^\]\n\r]+)\]', first_line)
                if m_bracket:
                    rem = first_line.replace(m_bracket.group(0), '').strip().strip(':：')
                    if rem:
                        clean_word = re.sub(r'^[\[\(\*#\s]+|[\]\)\*#\s]+$', '', rem).strip()
                        entry.word = clean_word
                        entry.pronunciation = m_bracket.group(0).strip()
                    else:
                        entry.word = m_bracket.group(1).strip()
                else:
                    # 提取日文假名注音 （たべる） 或 【たべる】
                    m_kana = re.search(r'[（\(【]([\u3040-\u309f]+)[）\)】]', first_line)
                    if m_kana:
                        entry.pronunciation = f"/{m_kana.group(1)}/"
                        rem = first_line.replace(m_kana.group(0), '').strip()
                        entry.word = re.sub(r'^[\[\(\*#\s]+|[\]\)\*#\s]+$', '', rem).strip().strip(':：')
                    else:
                        entry.word = re.sub(r'^[\[\(\*#\s]+|[\]\)\*#\s]+$', '', first_line).strip().strip(':：')

    # 2. 遍历剩余行解析释义、例句与搭配近反义词
    current_section = "defs"

    for line in lines[start_idx:]:
        if _is_incomplete_tag_fragment(line):
            continue

        clean_line = re.sub(r'^[-*•\d\.]+\s*', '', line).strip()
        if not clean_line or clean_line in ('[', ']'):
            continue

        # 检查区域标题切换
        header_text = re.sub(r'^[#*\-\s]+|[#*\-\s]+$', '', line).strip()
        header_clean = header_text.strip(':：').lower()

        if any(header_clean.startswith(k) for k in ("例句", "典型例句", "双语例句", "example", "sample sentence", "例文")):
            current_section = "examples"
            m_inline = re.split(r'[:：]', header_text, 1)
            if len(m_inline) > 1 and m_inline[1].strip():
                clean_line = m_inline[1].strip()
            else:
                continue

        elif any(header_clean.startswith(k) for k in ("搭配", "常用搭配", "固定搭配", "短语", "phrase", "collocation")):
            current_section = "phrases"
            m_inline = re.split(r'[:：]', header_text, 1)
            if len(m_inline) > 1 and m_inline[1].strip():
                items = re.split(r'[,;，；\n]+', m_inline[1].strip())
                entry.phrases.extend([it.strip().lstrip('-*• ') for it in items if it.strip()])
            continue

        elif any(header_clean.startswith(k) for k in ("同义词", "近义词", "synonym")):
            current_section = "synonyms"
            m_inline = re.split(r'[:：]', header_text, 1)
            if len(m_inline) > 1 and m_inline[1].strip():
                items = re.split(r'[,;，；\n]+', m_inline[1].strip())
                entry.synonyms.extend([it.strip().lstrip('-*• ') for it in items if it.strip()])
            continue

        elif any(header_clean.startswith(k) for k in ("反义词", "antonym")):
            current_section = "antonyms"
            m_inline = re.split(r'[:：]', header_text, 1)
            if len(m_inline) > 1 and m_inline[1].strip():
                items = re.split(r'[,;，；\n]+', m_inline[1].strip())
                entry.antonyms.extend([it.strip().lstrip('-*• ') for it in items if it.strip()])
            continue

        elif any(header_clean.startswith(k) for k in ("释义", "核心释义", "基本释义", "definition", "meaning")):
            current_section = "defs"
            m_inline = re.split(r'[:：]', header_text, 1)
            if len(m_inline) > 1 and m_inline[1].strip():
                clean_line = m_inline[1].strip()
            else:
                continue

        # 按当前区域处理行内容
        if current_section == "phrases":
            items = re.split(r'[,;，；\n]+', clean_line)
            entry.phrases.extend([it.strip().lstrip('-*• ') for it in items if it.strip()])
        elif current_section == "synonyms":
            items = re.split(r'[,;，；\n]+', clean_line)
            entry.synonyms.extend([it.strip().lstrip('-*• ') for it in items if it.strip()])
        elif current_section == "antonyms":
            items = re.split(r'[,;，；\n]+', clean_line)
            entry.antonyms.extend([it.strip().lstrip('-*• ') for it in items if it.strip()])
        elif current_section == "examples":
            ex_item = _parse_example_line(clean_line)
            if ex_item:
                entry.examples.append(ex_item)
        else:
            # defs 区域
            extracted = _extract_pos_and_meaning(clean_line)
            if extracted:
                pos, meaning, meaning_trans = extracted
                entry.definitions.append(DefinitionItem(pos=pos, meaning=meaning, meaning_trans=meaning_trans))
            else:
                if re.match(r'^(?:例[：:]|e\.g\.|ex[：:]|for example)', clean_line, re.I):
                    ex_clean = re.sub(r'^(?:例[：:]|e\.g\.|ex[：:]|for example)\s*', '', clean_line, flags=re.I).strip()
                    ex_item = _parse_example_line(ex_clean)
                    if ex_item:
                        entry.examples.append(ex_item)
                else:
                    meaning = clean_line
                    meaning_trans = ""
                    for sep in ['|', '——', '—', '\t', '//', '::']:
                        if sep in clean_line:
                            parts = clean_line.split(sep, 1)
                            if len(parts) == 2 and parts[0].strip() and parts[1].strip():
                                meaning = parts[0].strip()
                                meaning_trans = parts[1].strip()
                                break
                    if not meaning_trans:
                        m_cjk = re.search(r'^([A-Za-z0-9\s,\.\?\!\'\"\-:;\(\)/]+?)\s+([\u4e00-\u9fa5\u3040-\u30ff].*)$', clean_line)
                        if m_cjk and len(m_cjk.group(1).strip()) > 3:
                            meaning = m_cjk.group(1).strip()
                            meaning_trans = m_cjk.group(2).strip()

                    entry.definitions.append(DefinitionItem(pos="", meaning=meaning, meaning_trans=meaning_trans))

    # 3. 结构化标记判定
    if entry.definitions or entry.examples or entry.phrases or entry.synonyms or entry.antonyms:
        entry.is_structured = True
    else:
        entry.is_structured = False
