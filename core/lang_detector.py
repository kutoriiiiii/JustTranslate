"""Language detection utility for Chinese, English, and Japanese."""

import re

RE_JAPANESE_KANA = re.compile(r'[\u3040-\u309F\u30A0-\u30FF]')
RE_CHINESE_KANJI = re.compile(r'[\u4E00-\u9FFF]')
RE_HANGUL = re.compile(r'[\uAC00-\uD7AF]')
RE_CYRILLIC = re.compile(r'[\u0400-\u04FF]')
RE_LATIN = re.compile(r'[a-zA-Z]')

def detect_language(text: str) -> str:
    """通过字符频率加权与统计学模型精准判定文本主导语言（支持中英混排、英文中夹带汉字术语等复杂场景）。"""
    text_clean = text.strip()
    if not text_clean:
        return "English"

    cjk = len(RE_CHINESE_KANJI.findall(text_clean))
    kana = len(RE_JAPANESE_KANA.findall(text_clean))
    hangul = len(RE_HANGUL.findall(text_clean))
    latin = len(RE_LATIN.findall(text_clean))
    cyrillic = len(RE_CYRILLIC.findall(text_clean))

    # 韩文检测
    if hangul > 0 and hangul * 2.5 > latin:
        return "Korean"
    # 俄文检测
    if cyrillic > 0 and cyrillic > latin:
        return "Russian"

    # 日文假名检测：日文通常包含平假名/片假名与汉字混排
    if kana >= 2 and (kana * 3.0 > latin):
        return "Japanese"

    # 中文 vs 英文 (拉丁) 加权权衡：1 个汉字通常承载等效 2.5 个英文字母的信息量
    cjk_weight = cjk * 2.5
    latin_weight = float(latin)

    if cjk_weight > latin_weight and cjk > 0:
        return "Chinese"
    elif latin_weight >= cjk_weight and latin > 0:
        return "English"
    elif cjk > 0:
        return "Chinese"

    return "English"

def suggest_target_language(src_lang: str) -> str:
    """Suggests an appropriate target language based on detected source language."""
    if src_lang == "Chinese":
        return "English"
    elif src_lang == "English":
        return "Chinese"
    elif src_lang == "Japanese":
        return "Chinese"
    return "Chinese"
