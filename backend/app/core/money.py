"""金额换算纯函数（§4.1）。与 packages/shared/src/rules/money.ts 保持算法一致，两端共用测试用例。

注意：不能用内置 round()——它对 .5 使用银行家舍入（四舍六入五取偶），
而 JS 的 Math.round 对 .5 恒向上取整。两端要在同一输入下得到同一输出，
必须用 round_half_up 统一舍入规则，而不是各自语言的默认行为。
"""

from __future__ import annotations

import math


def round_half_up(value: float) -> int:
    """等价于 JS 的 Math.round：对 .5 恒向上取整（含负数向正无穷方向）。"""
    return math.floor(value + 0.5)


def cents_to_yuan(cents: int) -> float:
    return cents / 100


def yuan_to_cents(yuan: float) -> int:
    return round_half_up(yuan * 100)


def format_yuan(cents: int) -> str:
    return f"{cents_to_yuan(cents):.2f}"
