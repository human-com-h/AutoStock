"""ULID 生成（26 位 Crockford Base32 字符串，按时间排序）。

结构：48 位毫秒时间戳 + 80 位随机数，共 128 位，编码为 26 个 Crockford Base32 字符。
不引入第三方 ULID 库，因为手机端 TS 侧要各自实现同一算法（packages/shared/src/ulid.ts），
两端必须能独立验证生成格式与排序性质一致，弄清楚算法比多一个依赖更重要。
"""

from __future__ import annotations

import os
import time

_ENCODING = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # Crockford Base32，共 32 个字符
_ENCODING_LEN = len(_ENCODING)
_TIME_LEN = 10  # 48 位时间戳编码为 10 个字符
_RANDOM_LEN = 16  # 80 位随机数编码为 16 个字符
_TIMESTAMP_MAX = (1 << 48) - 1


def _encode_base32(value: int, length: int) -> str:
    chars = ["0"] * length
    for i in range(length - 1, -1, -1):
        chars[i] = _ENCODING[value & 0x1F]
        value >>= 5
    return "".join(chars)


def new_ulid(timestamp_ms: int | None = None) -> str:
    """生成一个新的 ULID 字符串。timestamp_ms 仅供测试注入固定时间。"""
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    ts = min(max(ts, 0), _TIMESTAMP_MAX)
    randomness = int.from_bytes(os.urandom(10), byteorder="big")
    return _encode_base32(ts, _TIME_LEN) + _encode_base32(randomness, _RANDOM_LEN)


def is_valid_ulid(value: str) -> bool:
    if not isinstance(value, str) or len(value) != _TIME_LEN + _RANDOM_LEN:
        return False
    return all(ch in _ENCODING for ch in value.upper())


def extract_timestamp_ms(ulid_str: str) -> int:
    if not is_valid_ulid(ulid_str):
        raise ValueError(f"不是合法的 ULID: {ulid_str}")
    value = 0
    for ch in ulid_str[:_TIME_LEN].upper():
        value = (value << 5) | _ENCODING.index(ch)
    return value
