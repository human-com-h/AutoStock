"""一致性还原点、整库恢复和可读迁移包。"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import sqlite3
import tempfile
import zipfile
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config as AlembicConfig
from openpyxl import Workbook

from app.core.version import APP_VERSION

PACKAGE_FORMAT_VERSION = 1
BACKUP_RETENTION_POLICY = {
    "pre_sync": {"days": 7, "max_count": 50, "label": "同步前保护点"},
    "daily": {"days": 30, "max_count": 30, "label": "每日自动还原点"},
    "pre_restore": {"days": 30, "max_count": 30, "label": "恢复前保护点"},
    "pre_import": {"days": 30, "max_count": 30, "label": "迁移前保护点"},
    "manual": {"days": 180, "max_count": 100, "label": "手动还原点"},
    "monthly": {"days": 1095, "max_count": 36, "label": "月度长期还原点"},
}


def _settings():
    from app.core.config import settings

    return settings


def _backup_dir() -> Path:
    path = _settings().data_dir / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _safe_path(root: Path, name: str, suffix: str) -> Path:
    candidate = (root / name).resolve()
    resolved_root = root.resolve()
    if candidate.parent != resolved_root or candidate.suffix.lower() != suffix:
        raise FileNotFoundError("备份文件不存在")
    return candidate


def _online_backup(source_path: Path, destination: Path) -> None:
    with (
        closing(sqlite3.connect(source_path)) as source,
        closing(sqlite3.connect(destination)) as target,
    ):
        source.backup(target)


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return (
        connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        ).fetchone()
        is not None
    )


def _database_summary(path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "parts": 0,
        "purchase_orders": 0,
        "sales_orders": 0,
        "stock_quantity": 0,
    }
    with closing(sqlite3.connect(path)) as connection:
        if _table_exists(connection, "part"):
            summary["parts"] = connection.execute(
                "SELECT COUNT(*) FROM part WHERE is_deleted=0"
            ).fetchone()[0]
        if _table_exists(connection, "purchase_order"):
            summary["purchase_orders"] = connection.execute(
                "SELECT COUNT(*) FROM purchase_order WHERE is_deleted=0"
            ).fetchone()[0]
        if _table_exists(connection, "sales_order"):
            summary["sales_orders"] = connection.execute(
                "SELECT COUNT(*) FROM sales_order WHERE is_deleted=0"
            ).fetchone()[0]
        if _table_exists(connection, "stock_snapshot"):
            summary["stock_quantity"] = float(
                connection.execute(
                    "SELECT COALESCE(SUM(quantity), 0) FROM stock_snapshot"
                ).fetchone()[0]
                or 0
            )
    return summary


def _schema_revision(path: Path) -> str | None:
    with closing(sqlite3.connect(path)) as connection:
        if not _table_exists(connection, "alembic_version"):
            return None
        row = connection.execute("SELECT version_num FROM alembic_version").fetchone()
        return row[0] if row else None


def _validate_database(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError("数据库文件不存在")
    with closing(sqlite3.connect(path)) as connection:
        quick_check = connection.execute("PRAGMA quick_check").fetchone()
        if not quick_check or quick_check[0] != "ok":
            raise ValueError("数据库完整性检查未通过")
        required = {"part", "stock_ledger", "stock_snapshot"}
        missing = [table for table in required if not _table_exists(connection, table)]
        if missing:
            raise ValueError(f"数据库缺少关键数据表：{', '.join(sorted(missing))}")
        mismatches = connection.execute(
            """
            WITH ledger AS (
                SELECT part_id, COALESCE(SUM(quantity), 0) AS quantity
                FROM stock_ledger GROUP BY part_id
            ),
            ids AS (
                SELECT part_id FROM ledger UNION SELECT part_id FROM stock_snapshot
            )
            SELECT COUNT(*)
            FROM ids
            LEFT JOIN ledger ON ledger.part_id=ids.part_id
            LEFT JOIN stock_snapshot ON stock_snapshot.part_id=ids.part_id
            WHERE COALESCE(ledger.quantity, 0) != COALESCE(stock_snapshot.quantity, 0)
            """
        ).fetchone()[0]
        if mismatches:
            raise ValueError(f"库存一致性检查未通过，共 {mismatches} 件零件存在差异")
    return {
        "integrity": "ok",
        "reconciliation": "ok",
        "summary": _database_summary(path),
        "schema_revision": _schema_revision(path),
    }


def _metadata_path(database_path: Path) -> Path:
    return database_path.with_suffix(".json")


def _write_metadata(database_path: Path, metadata: dict[str, Any]) -> None:
    _metadata_path(database_path).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_metadata(database_path: Path) -> dict[str, Any]:
    path = _metadata_path(database_path)
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def create_backup(
    prefix: str = "manual",
    *,
    label: str | None = None,
    reason: str | None = None,
    preserve_invalid: bool = False,
) -> dict[str, Any]:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    safe_prefix = "".join(
        character for character in prefix if character.isalnum() or character == "_"
    )
    destination = _backup_dir() / f"{safe_prefix or 'manual'}-{stamp}.db"
    _online_backup(_settings().db_path, destination)
    try:
        validation = _validate_database(destination)
    except (sqlite3.DatabaseError, ValueError) as exc:
        if not preserve_invalid:
            _remove_backup_files(destination)
            raise
        validation = {
            "integrity": "unverified",
            "reconciliation": "failed",
            "validation_error": str(exc),
            "summary": _database_summary(destination),
            "schema_revision": _schema_revision(destination),
        }
    metadata = {
        "label": (label or "").strip() or None,
        "reason": reason or prefix,
        "created_at": datetime.now().astimezone().isoformat(),
        "app_version": APP_VERSION,
        **validation,
    }
    _write_metadata(destination, metadata)
    apply_retention_policy()
    return _info(destination)


def _backup_created_at(path: Path) -> datetime:
    raw = _read_metadata(path).get("created_at")
    if raw:
        try:
            value = datetime.fromisoformat(raw)
            return value if value.tzinfo else value.astimezone()
        except (TypeError, ValueError):
            pass
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone()


def _remove_backup_files(path: Path) -> None:
    path.unlink(missing_ok=True)
    _metadata_path(path).unlink(missing_ok=True)


def apply_retention_policy() -> list[str]:
    """按类型同时执行时间和数量上限，防止高频同步造成备份无限增长。"""
    now = datetime.now().astimezone()
    removed: list[str] = []
    for prefix, policy in BACKUP_RETENTION_POLICY.items():
        paths = sorted(
            _backup_dir().glob(f"{prefix}-*.db"),
            key=_backup_created_at,
            reverse=True,
        )
        expires_before = now - timedelta(days=int(policy["days"]))
        for index, path in enumerate(paths):
            if index >= int(policy["max_count"]) or _backup_created_at(path) < expires_before:
                removed.append(path.name)
                _remove_backup_files(path)
    return removed


def retention_policy() -> list[dict[str, Any]]:
    return [
        {
            "type": prefix,
            "label": policy["label"],
            "days": policy["days"],
            "max_count": policy["max_count"],
        }
        for prefix, policy in BACKUP_RETENTION_POLICY.items()
    ]


def ensure_daily_backup() -> dict[str, Any] | None:
    apply_retention_policy()
    today = datetime.now().astimezone().date().isoformat()
    for path in [*_backup_dir().glob("daily-*.db"), *_backup_dir().glob("monthly-*.db")]:
        metadata = _read_metadata(path)
        if str(metadata.get("created_at", "")).startswith(today):
            return None
    if datetime.now().astimezone().day == 1:
        return create_backup(
            "monthly",
            label=f"{today} 月度长期还原点",
            reason="monthly_startup",
        )
    return create_backup("daily", label=f"{today} 每日自动还原点", reason="daily_startup")


def _info(path: Path) -> dict[str, Any]:
    stat = path.stat()
    metadata = _read_metadata(path)
    summary = metadata.get("summary")
    if summary is None:
        try:
            summary = _database_summary(path)
        except sqlite3.DatabaseError:
            summary = {}
    return {
        "name": path.name,
        "size": stat.st_size,
        "created_at": metadata.get("created_at")
        or datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(),
        "label": metadata.get("label"),
        "reason": metadata.get("reason", "legacy"),
        "app_version": metadata.get("app_version"),
        "schema_revision": metadata.get("schema_revision"),
        "summary": summary,
        "verified": metadata.get("integrity") == "ok"
        and metadata.get("reconciliation") == "ok",
    }


def list_backups() -> list[dict[str, Any]]:
    return [_info(path) for path in sorted(_backup_dir().glob("*.db"), reverse=True)]


def restore_backup(name: str) -> dict[str, Any]:
    source_path = _safe_path(_backup_dir(), name, ".db")
    if not source_path.is_file():
        raise FileNotFoundError("备份文件不存在")
    validation = _validate_database(source_path)
    safety_backup = create_backup(
        "pre_restore",
        label="恢复前自动保护点",
        reason=f"before_restore:{name}",
        preserve_invalid=True,
    )
    from app.db.session import engine

    engine.dispose()
    _online_backup(source_path, _settings().db_path)
    return {
        "restored": name,
        "safety_backup": safety_backup["name"],
        "validation": validation,
    }


def _query_dicts(connection: sqlite3.Connection, sql: str) -> list[dict[str, Any]]:
    connection.row_factory = sqlite3.Row
    return [dict(row) for row in connection.execute(sql).fetchall()]


def _human_datasets(connection: sqlite3.Connection) -> list[tuple[str, list[dict[str, Any]]]]:
    return [
        (
            "零件档案",
            _query_dicts(
                connection,
                """
                SELECT p.part_number AS 零件编号, p.oe_number AS OE号, p.name AS 零件名称,
                       p.spec AS 规格, b.name AS 品牌, c.name AS 分类, s.name AS 默认供应商,
                       p.unit AS 单位, p.purchase_price / 100.0 AS 参考进价_元,
                       p.sale_price / 100.0 AS 参考售价_元, p.min_stock AS 最低库存,
                       p.max_stock AS 最高库存, p.location AS 货位,
                       p.vehicle_models AS 适用车型,
                       CASE p.is_active WHEN 1 THEN '启用' ELSE '停用' END AS 状态,
                       p.remark AS 备注
                FROM part p
                LEFT JOIN brand b ON b.id=p.brand_id
                LEFT JOIN category c ON c.id=p.category_id
                LEFT JOIN supplier s ON s.id=p.supplier_id
                WHERE p.is_deleted=0 ORDER BY p.part_number
                """,
            ),
        ),
        (
            "当前库存",
            _query_dicts(
                connection,
                """
                SELECT p.part_number AS 零件编号, p.name AS 零件名称, p.location AS 货位,
                       COALESCE(ss.quantity, 0) AS 当前库存, p.unit AS 单位,
                       COALESCE(ss.avg_cost, 0) / 100.0 AS 平均成本_元,
                       COALESCE(ss.quantity, 0) * COALESCE(ss.avg_cost, 0) / 100.0 AS 库存金额_元,
                       ss.last_in_at AS 最近入库时间, ss.last_out_at AS 最近出库时间
                FROM part p LEFT JOIN stock_snapshot ss ON ss.part_id=p.id
                WHERE p.is_deleted=0 ORDER BY p.part_number
                """,
            ),
        ),
        (
            "采购单",
            _query_dicts(
                connection,
                """
                SELECT po.order_no AS 单号, po.order_date AS 日期,
                       CASE po.order_type WHEN 'purchase' THEN '采购入库'
                            WHEN 'purchase_return' THEN '采购退货' ELSE po.order_type END AS 类型,
                       s.name AS 供应商, po.total_amount / 100.0 AS 总金额_元,
                       po.remark AS 备注, po.created_at AS 创建时间
                FROM purchase_order po LEFT JOIN supplier s ON s.id=po.supplier_id
                WHERE po.is_deleted=0 ORDER BY po.order_date, po.order_no
                """,
            ),
        ),
        (
            "采购明细",
            _query_dicts(
                connection,
                """
                SELECT po.order_no AS 单号, p.part_number AS 零件编号, p.name AS 零件名称,
                       pi.quantity AS 数量, p.unit AS 单位,
                       pi.purchase_price / 100.0 AS 单价_元,
                       pi.amount / 100.0 AS 金额_元, pi.remark AS 备注
                FROM purchase_item pi
                JOIN purchase_order po ON po.id=pi.order_id
                JOIN part p ON p.id=pi.part_id
                WHERE po.is_deleted=0 AND pi.is_deleted=0 ORDER BY po.order_date, po.order_no
                """,
            ),
        ),
        (
            "销售单",
            _query_dicts(
                connection,
                """
                SELECT so.order_no AS 单号, so.order_date AS 日期,
                       CASE so.order_type WHEN 'sale' THEN '销售出库'
                            WHEN 'sale_return' THEN '销售退货' ELSE so.order_type END AS 类型,
                       COALESCE(c.name, so.customer_name) AS 客户,
                       so.total_amount / 100.0 AS 总金额_元,
                       so.remark AS 备注, so.created_at AS 创建时间
                FROM sales_order so LEFT JOIN customer c ON c.id=so.customer_id
                WHERE so.is_deleted=0 ORDER BY so.order_date, so.order_no
                """,
            ),
        ),
        (
            "销售明细",
            _query_dicts(
                connection,
                """
                SELECT so.order_no AS 单号, p.part_number AS 零件编号, p.name AS 零件名称,
                       si.quantity AS 数量, p.unit AS 单位,
                       si.sale_price / 100.0 AS 单价_元,
                       si.amount / 100.0 AS 金额_元,
                       si.cost_amount / 100.0 AS 成本_元,
                       (si.amount-si.cost_amount) / 100.0 AS 毛利_元, si.remark AS 备注
                FROM sales_item si
                JOIN sales_order so ON so.id=si.order_id
                JOIN part p ON p.id=si.part_id
                WHERE so.is_deleted=0 AND si.is_deleted=0 ORDER BY so.order_date, so.order_no
                """,
            ),
        ),
        (
            "库存流水",
            _query_dicts(
                connection,
                """
                SELECT sl.occurred_at AS 发生时间, p.part_number AS 零件编号,
                       p.name AS 零件名称,
                       CASE sl.change_type WHEN 'purchase' THEN '采购入库'
                            WHEN 'sale' THEN '销售出库'
                            WHEN 'purchase_return' THEN '采购退货'
                            WHEN 'sale_return' THEN '销售退货'
                            WHEN 'adjust' THEN '盘点调整'
                            WHEN 'opening' THEN '期初库存' ELSE sl.change_type END AS 变动类型,
                       sl.quantity AS 数量, p.unit AS 单位,
                       sl.unit_cost / 100.0 AS 单位成本_元, sl.remark AS 备注
                FROM stock_ledger sl JOIN part p ON p.id=sl.part_id
                ORDER BY sl.occurred_at, sl.rev
                """,
            ),
        ),
        (
            "客户",
            _query_dicts(
                connection,
                """
                SELECT name AS 客户名称, phone AS 电话, location AS 地区, remark AS 备注,
                       CASE is_active WHEN 1 THEN '启用' ELSE '停用' END AS 状态
                FROM customer WHERE is_deleted=0 ORDER BY name
                """,
            ),
        ),
        (
            "供应商",
            _query_dicts(
                connection,
                """
                SELECT name AS 供应商名称, contact AS 联系人, phone AS 电话,
                       address AS 地址, remark AS 备注,
                       CASE is_active WHEN 1 THEN '启用' ELSE '停用' END AS 状态
                FROM supplier WHERE is_deleted=0 ORDER BY name
                """,
            ),
        ),
    ]


def _workbook_bytes(datasets: list[tuple[str, list[dict[str, Any]]]]) -> bytes:
    workbook = Workbook()
    workbook.remove(workbook.active)
    for title, rows in datasets:
        sheet = workbook.create_sheet(title[:31])
        headers = list(rows[0]) if rows else ["说明"]
        sheet.append(headers)
        if rows:
            for row in rows:
                sheet.append([row.get(header) for header in headers])
        else:
            sheet.append(["暂无数据"])
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for column in sheet.columns:
            values = [str(cell.value or "") for cell in column[:200]]
            width = min(32, max(10, max((len(value) for value in values), default=10) + 2))
            sheet.column_dimensions[column[0].column_letter].width = width
    stream = io.BytesIO()
    workbook.save(stream)
    return stream.getvalue()


def _csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    text = io.StringIO(newline="")
    headers = list(rows[0]) if rows else ["说明"]
    writer = csv.DictWriter(text, fieldnames=headers)
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    else:
        writer.writerow({"说明": "暂无数据"})
    return ("\ufeff" + text.getvalue()).encode("utf-8")


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def create_migration_package() -> tuple[str, bytes]:
    now = datetime.now().astimezone()
    filename = f"AutoStock_{now.strftime('%Y-%m-%d_%H%M%S')}_经营数据.zip"
    with tempfile.TemporaryDirectory(dir=_settings().data_dir) as temp_dir:
        snapshot = Path(temp_dir) / "autostock.db"
        _online_backup(_settings().db_path, snapshot)
        validation = _validate_database(snapshot)
        database_content = snapshot.read_bytes()
        with closing(sqlite3.connect(snapshot)) as connection:
            datasets = _human_datasets(connection)

        files: dict[str, bytes] = {
            "autostock.db": database_content,
            "经营数据.xlsx": _workbook_bytes(datasets),
        }
        for title, rows in datasets:
            files[f"csv/{title}.csv"] = _csv_bytes(rows)

        readme = (
            "AutoStock 经营数据迁移包\r\n"
            f"导出时间：{now.isoformat()}\r\n"
            f"应用版本：{APP_VERSION}\r\n\r\n"
            "autostock.db 用于在 AutoStock 中无损恢复或迁移。\r\n"
            "经营数据.xlsx 和 csv 目录供用户直接查看、审计和长期归档。\r\n"
            "请勿单独修改数据库文件后再导入；导入前系统会校验完整性和库存一致性。\r\n"
            "本包不包含 HTTPS 证书和 CA 私钥，换电脑后需要重新进行手机配对。\r\n"
        ).encode("utf-8-sig")
        files["README.txt"] = readme
        manifest = {
            "package_format_version": PACKAGE_FORMAT_VERSION,
            "created_at": now.isoformat(),
            "app_version": APP_VERSION,
            "schema_revision": validation["schema_revision"],
            "summary": validation["summary"],
            "database_file": "autostock.db",
        }
        files["manifest.json"] = json.dumps(
            manifest, ensure_ascii=False, indent=2
        ).encode("utf-8")
        checksums = "\n".join(
            f"{_sha256(content)}  {name}" for name, content in sorted(files.items())
        )
        files["checksums.txt"] = (checksums + "\n").encode("utf-8")

        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        return filename, output.getvalue()


def _parse_checksums(content: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in content.decode("utf-8").splitlines():
        checksum, separator, name = line.partition("  ")
        if separator and checksum and name:
            result[name] = checksum
    return result


def _upgrade_database(path: Path) -> None:
    backend_root = Path(__file__).resolve().parents[2]
    config = AlembicConfig(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    config.attributes["database_url_override"] = f"sqlite:///{path.as_posix()}"
    command.upgrade(config, "head")


def import_migration_package(content: bytes) -> dict[str, Any]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise ValueError("所选文件不是有效的 AutoStock 迁移包") from exc
    with archive:
        names = set(archive.namelist())
        required = {"manifest.json", "checksums.txt", "autostock.db"}
        if not required.issubset(names):
            raise ValueError("迁移包缺少 manifest.json、checksums.txt 或 autostock.db")
        manifest = json.loads(archive.read("manifest.json"))
        if manifest.get("package_format_version") != PACKAGE_FORMAT_VERSION:
            raise ValueError("迁移包格式版本不受支持")
        checksums = _parse_checksums(archive.read("checksums.txt"))
        for name, expected in checksums.items():
            if name not in names or _sha256(archive.read(name)) != expected:
                raise ValueError(f"迁移包文件校验失败：{name}")
        database_content = archive.read("autostock.db")

    with tempfile.TemporaryDirectory(dir=_settings().data_dir) as temp_dir:
        imported_database = Path(temp_dir) / "imported.db"
        imported_database.write_bytes(database_content)
        _upgrade_database(imported_database)
        validation = _validate_database(imported_database)
        safety_backup = create_backup(
            "pre_import",
            label="迁移导入前自动保护点",
            reason="before_migration_import",
            preserve_invalid=True,
        )
        from app.db.session import engine

        engine.dispose()
        _online_backup(imported_database, _settings().db_path)
    return {
        "imported": True,
        "source_created_at": manifest.get("created_at"),
        "source_app_version": manifest.get("app_version"),
        "safety_backup": safety_backup["name"],
        "validation": validation,
    }
