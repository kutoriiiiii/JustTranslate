# -*- coding: utf-8 -*-
"""Sentence segmentation and bi-directional cross-text alignment module.

Supports CJK punctuation, Latin/Western punctuation, quotes/brackets,
and provides proportional and paragraph-aware mapping between source and target sentences.
"""

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

@dataclass
class SentenceSpan:
    """Represents a segmented sentence with character boundary spans."""
    index: int          # 0-based sentence index
    text: str           # Clean sentence text
    start: int          # Start char index in original document
    end: int            # End char index in original document

# CJK punctuation that terminates sentences: 。 ！？ ； …
# Latin punctuation: . ! ? ;
# Trailing quotes/brackets: ” " ’ ' ） ) 」 』 ］ ] ｝ }
_CJK_ENDINGS = r"[。！？；…]+"
_LATIN_ENDINGS = r"[.!?]+"
_CLOSING_PUNCT = r"[\"”'’\)）\]］｝\}」』]*"

_PUNCT_SPLIT = re.compile(
    rf"({_CJK_ENDINGS}|{_LATIN_ENDINGS})({_CLOSING_PUNCT})"
)

_ABBREVIATIONS = {
    "e.g.", "i.e.", "etc.", "vs.", "mr.", "mrs.", "ms.", "dr.", "prof.", "dept.",
    "inc.", "ltd.", "co.", "approx.", "fig.", "no.", "jan.", "feb.", "mar.", "apr.",
    "jun.", "jul.", "aug.", "sep.", "sept.", "oct.", "nov.", "dec."
}

def split_sentences_with_spans(text: str) -> List[SentenceSpan]:
    """Splits full text into structured SentenceSpan items with exact character offsets.
    
    Handles multi-line paragraphs, markdown headers/lists, and diverse punctuations.
    """
    if not text:
        return []

    spans: List[SentenceSpan] = []
    line_start = 0
    lines = text.splitlines(keepends=True)
    
    for line in lines:
        stripped_line = line.strip()
        if not stripped_line:
            line_start += len(line)
            continue
            
        sub_spans = _split_line_into_spans(line, line_start, len(spans))
        spans.extend(sub_spans)
        line_start += len(line)

    # Re-index spans cleanly
    for i, s in enumerate(spans):
        s.index = i
        
    return spans

def _split_line_into_spans(line: str, line_offset: int, base_idx: int) -> List[SentenceSpan]:
    """Splits a single non-empty line into one or more sentence spans."""
    result: List[SentenceSpan] = []
    current_start = 0
    n = len(line)
    
    for match in _PUNCT_SPLIT.finditer(line):
        punct = match.group(1)
        end_pos = match.end()
        chunk = line[current_start:end_pos]
        
        # Check if the punctuation is a dot in an abbreviation or decimal (e.g. "3.14" or "e.g.")
        if punct == ".":
            # Check decimal like 3.14
            if match.start() > 0 and end_pos < n:
                if line[match.start() - 1].isdigit() and line[end_pos].isdigit():
                    continue
            # Check abbreviation
            words = chunk.strip().split()
            if words:
                last_word = words[-1].lower()
                if last_word in _ABBREVIATIONS:
                    continue

        if chunk.strip():
            leading_ws = len(chunk) - len(chunk.lstrip())
            trailing_ws = len(chunk) - len(chunk.rstrip())
            s_start = line_offset + current_start + leading_ws
            s_end = line_offset + end_pos - trailing_ws
            clean_text = line[current_start + leading_ws : end_pos - trailing_ws]
            
            if clean_text:
                result.append(SentenceSpan(
                    index=base_idx + len(result),
                    text=clean_text,
                    start=s_start,
                    end=s_end
                ))
            current_start = end_pos
        
    # Any trailing text on the line after the last punctuation
    if current_start < n:
        tail = line[current_start:]
        if tail.strip():
            leading_ws = len(tail) - len(tail.lstrip())
            trailing_ws = len(tail) - len(tail.rstrip())
            s_start = line_offset + current_start + leading_ws
            s_end = line_offset + n - trailing_ws
            clean_text = line[current_start + leading_ws : n - trailing_ws]
            if clean_text:
                result.append(SentenceSpan(
                    index=base_idx + len(result),
                    text=clean_text,
                    start=s_start,
                    end=s_end
                ))
                
    return result

def find_sentence_at_position(spans: List[SentenceSpan], char_pos: int) -> Optional[SentenceSpan]:
    """Finds the SentenceSpan enclosing or nearest to the given character offset."""
    if not spans:
        return None
        
    for s in spans:
        if s.start <= char_pos <= s.end:
            return s
            
    # If cursor is in whitespace between sentences, find nearest
    nearest = spans[0]
    min_dist = abs(char_pos - spans[0].start)
    for s in spans[1:]:
        dist = min(abs(char_pos - s.start), abs(char_pos - s.end))
        if dist < min_dist:
            min_dist = dist
            nearest = s
    return nearest

def map_sentence_index(src_idx: int, src_total: int, target_total: int) -> int:
    """Maps a sentence index from source sentence sequence to target sentence sequence.
    
    If src_total == target_total, mapping is 1-to-1 exact.
    Otherwise, uses proportional normalized projection.
    """
    if target_total <= 0:
        return 0
    if src_total <= 1 or target_total == 1:
        return 0
    if src_total == target_total:
        return max(0, min(src_idx, target_total - 1))
        
    ratio = src_idx / (src_total - 1)
    mapped = round(ratio * (target_total - 1))
    return max(0, min(mapped, target_total - 1))
