"""库存一致性对账：逐件比较流水求和与库存快照。

退出码为 0 表示全部一致，1 表示存在差异或数据库不可用，供本地检查和 CI 使用。
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass(frozen=True)
class Mismatch:
    part_id: str
    part_name: str
    snapshot_quantity: Decimal
    ledger_quantity: Decimal

    @property
    def difference(self) -> Decimal:
        return self.snapshot_quantity - self.ledger_quantity


def _decimal(value: object) -> Decimal:
    return Decimal(str(value or 0))


def reconcile_database(db_path: str | Path) -> tuple[int, int, list[Mismatch]]:
    """在同一个 SQLite 只读事务中完成对账并返回汇总。"""
    path = Path(db_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"数据库文件不存在：{path}")

    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        connection.execute("BEGIN")
        rows = connection.execute(
            """
            WITH part_ids AS (
                SELECT id AS part_id FROM part
                UNION
                SELECT part_id FROM stock_ledger
                UNION
                SELECT part_id FROM stock_snapshot
            ),
            ledger_totals AS (
                SELECT part_id, COALESCE(SUM(quantity), 0) AS quantity
                FROM stock_ledger
                GROUP BY part_id
            )
            SELECT
                ids.part_id,
                COALESCE(part.name, ''),
                COALESCE(stock_snapshot.quantity, 0),
                COALESCE(ledger_totals.quantity, 0)
            FROM part_ids AS ids
            LEFT JOIN part ON part.id = ids.part_id
            LEFT JOIN stock_snapshot ON stock_snapshot.part_id = ids.part_id
            LEFT JOIN ledger_totals ON ledger_totals.part_id = ids.part_id
            """
        ).fetchall()
        connection.rollback()
    finally:
        connection.close()

    mismatches = [
        Mismatch(
            part_id=row[0],
            part_name=row[1],
            snapshot_quantity=_decimal(row[2]),
            ledger_quantity=_decimal(row[3]),
        )
        for row in rows
        if _decimal(row[2]) != _decimal(row[3])
    ]
    mismatches.sort(key=lambda row: abs(row.difference), reverse=True)
    return len(rows), len(mismatches), mismatches


def _default_db_path() -> Path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
    from app.core.config import settings

    return settings.db_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="核对库存快照与流水求和")
    parser.add_argument("--db", type=Path, help="SQLite 数据库路径；省略时使用应用数据库")
    args = parser.parse_args(argv)
    db_path = args.db or _default_db_path()

    try:
        total, mismatch_count, mismatches = reconcile_database(db_path)
    except (FileNotFoundError, sqlite3.DatabaseError) as exc:
        print(f"对账失败：{exc}")
        return 1

    ratio = (mismatch_count / total * 100) if total else 0
    if not mismatches:
        print(f"对账通过，0 处差异（共 {total} 件零件）")
        return 0

    print(
        f"对账失败：共 {total} 件零件，{mismatch_count} 件不一致，"
        f"不一致占比 {ratio:.2f}%"
    )
    for row in mismatches[:10]:
        name = row.part_name or "（零件档案缺失）"
        print(
            f"  part_id={row.part_id} 名称={name} "
            f"快照={row.snapshot_quantity} 流水求和={row.ledger_quantity} "
            f"差值={row.difference}"
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
