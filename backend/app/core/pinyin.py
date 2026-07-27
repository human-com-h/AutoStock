"""拼音首字母生成，供零件名称检索使用（§4.2 零件四路检索：编号/OE号/名称/拼音首字母）。"""

from __future__ import annotations

from pypinyin import Style, pinyin


def pinyin_initials(text: str) -> str:
    """返回文本每个汉字的拼音首字母大写拼接，非汉字字符原样保留（大写）。"""
    if not text:
        return ""
    result: list[str] = []
    for ch in text:
        if "一" <= ch <= "鿿":
            py = pinyin(ch, style=Style.FIRST_LETTER, strict=False)
            if py and py[0]:
                result.append(py[0][0].upper())
        elif ch.strip():
            result.append(ch.upper())
    return "".join(result)
