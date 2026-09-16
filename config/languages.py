# -*- coding: utf-8 -*-
"""Language registry and metadata for Just Translate."""

# 常用核心语言
COMMON_LANGUAGES = [
    ("\u4e2d\u6587 (Chinese)", "Chinese"),
    ("\u82f1\u6587 (English)", "English"),
    ("\u65e5\u6587 (Japanese)", "Japanese")
]

# 扩展主流语言列表（13款主流语种）
EXTRA_LANGUAGES = [
    ("\u97e9\u6587 (Korean)", "Korean"),
    ("\u6cd5\u6587 (French)", "French"),
    ("\u5fb7\u6587 (German)", "German"),
    ("\u897f\u73ed\u7259\u6587 (Spanish)", "Spanish"),
    ("\u4fc4\u6587 (Russian)", "Russian"),
    ("\u8461\u8404\u7259\u6587 (Portuguese)", "Portuguese"),
    ("\u610f\u5927\u5229\u6587 (Italian)", "Italian"),
    ("\u963f\u62c9\u4f2f\u6587 (Arabic)", "Arabic"),
    ("\u8d8a\u5357\u6587 (Vietnamese)", "Vietnamese"),
    ("\u6cf0\u6587 (Thai)", "Thai"),
    ("\u5370\u5c3c\u6587 (Indonesian)", "Indonesian"),
    ("\u8377\u5170\u6587 (Dutch)", "Dutch"),
    ("\u571f\u8033\u5176\u6587 (Turkish)", "Turkish")
]

ALL_LANGUAGES = [("\u81ea\u52a8\u8bc6\u522b (Auto)", "Auto")] + COMMON_LANGUAGES + EXTRA_LANGUAGES

# 语言代码到展示名称的映射
LANG_LABELS = {code: label for label, code in ALL_LANGUAGES}

def get_language_label(code: str) -> str:
    """根据语言代码返回用户可见标签。"""
    return LANG_LABELS.get(code, code)
