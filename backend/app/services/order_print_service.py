"""采购/销售单的黑白 A4 PDF 生成。

PDF 与 PC 端预览使用同一组字段和每页 18 行的分页规则。库存与单据数据只读，
本服务不写业务表。
"""

from __future__ import annotations

from html import escape
from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Paragraph, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.master_data import Customer, Part, Supplier
from app.services import order_service
from app.services.settings_service import get_public_settings

PAGE_ROW_COUNT = 18
FONT_NAME = "AutoStockPrint"

_CN_DIGITS = ("零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖")
_CN_UNITS = ("", "拾", "佰", "仟")
_CN_GROUP_UNITS = ("", "万", "亿", "兆")


def _ensure_font() -> str:
    if FONT_NAME in pdfmetrics.getRegisteredFontNames():
        return FONT_NAME

    candidates = (
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/Deng.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
    )
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            pdfmetrics.registerFont(TTFont(FONT_NAME, str(candidate)))
            return FONT_NAME
        except Exception:
            continue

    fallback = "STSong-Light"
    if fallback not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(fallback))
    return fallback


def _integer_group_to_chinese(group: int) -> str:
    digits = [int(value) for value in str(group).zfill(4)]
    result = ""
    pending_zero = False
    for index, digit in enumerate(digits):
        unit_index = 3 - index
        if digit == 0:
            pending_zero = bool(result)
            continue
        if pending_zero:
            result += _CN_DIGITS[0]
        result += f"{_CN_DIGITS[digit]}{_CN_UNITS[unit_index]}"
        pending_zero = False
    return result


def money_to_chinese_upper(cents: int) -> str:
    normalized = abs(round(cents))
    yuan = normalized // 100
    jiao = normalized % 100 // 10
    fen = normalized % 10

    if yuan == 0:
        integer_text = _CN_DIGITS[0]
    else:
        groups: list[int] = []
        remaining = yuan
        while remaining > 0:
            groups.append(remaining % 10000)
            remaining //= 10000

        integer_text = ""
        zero_between_groups = False
        for index in range(len(groups) - 1, -1, -1):
            group = groups[index]
            if group == 0:
                zero_between_groups = bool(integer_text)
                continue
            if integer_text and (zero_between_groups or group < 1000):
                integer_text += _CN_DIGITS[0]
            group_unit = _CN_GROUP_UNITS[index] if index < len(_CN_GROUP_UNITS) else ""
            integer_text += f"{_integer_group_to_chinese(group)}{group_unit}"
            zero_between_groups = False

    sign = "负" if cents < 0 else ""
    if jiao == 0 and fen == 0:
        return f"{sign}{integer_text}元整"
    decimal_text = f"{_CN_DIGITS[jiao]}角" if jiao else ("零" if fen else "")
    if fen:
        decimal_text += f"{_CN_DIGITS[fen]}分"
    return f"{sign}{integer_text}元{decimal_text}"


def _format_money(cents: int | float) -> str:
    return f"{float(cents or 0) / 100:,.2f}"


def _format_quantity(value: int | float) -> str:
    rendered = f"{float(value or 0):,.3f}"
    return rendered.rstrip("0").rstrip(".")


def get_print_extra_fields(context: dict[str, Any]) -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for key, label in (
        ("print_payment_account", "收款账户"),
        ("print_wechat", "联系微信"),
        ("print_warranty_period", "售后期限"),
    ):
        value = str(context.get(key) or "").strip()
        if value:
            fields.append((label, value))

    for field in context.get("print_custom_fields") or []:
        if not field.get("visible", True):
            continue
        label = str(field.get("label") or "").strip()
        if not label:
            continue
        value = "________________" if field.get("handwritten") else str(field.get("value") or "—")
        fields.append((label, value))
    return fields


def _paragraph(
    value: Any,
    *,
    style: ParagraphStyle,
    empty_text: str = "-",
) -> Paragraph:
    text = escape(str(value if value not in (None, "") else empty_text)).replace("\n", "<br/>")
    return Paragraph(text, style)


def _draw_table(canvas: Canvas, table: Table, x: float, top: float, max_width: float) -> float:
    _, height = table.wrap(max_width, A4[1])
    table.drawOn(canvas, x, top - height)
    return top - height


def _table_style(font_name: str, font_size: float = 8) -> TableStyle:
    return TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), font_name),
            ("FONTSIZE", (0, 0), (-1, -1), font_size),
            ("TEXTCOLOR", (0, 0), (-1, -1), colors.black),
            ("GRID", (0, 0), (-1, -1), 0.7, colors.black),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 2.5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2.5),
            ("TOPPADDING", (0, 0), (-1, -1), 1.5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 1.5),
        ]
    )


def render_order_pdf(context: dict[str, Any]) -> bytes:
    """根据已整理的单据上下文生成 A4 黑白 PDF。"""
    font_name = _ensure_font()
    buffer = BytesIO()
    canvas = Canvas(buffer, pagesize=A4)
    canvas.setTitle(f"{context['order_no']} {context['document_title']}")
    canvas.setAuthor(context["shop_name"])
    page_width, page_height = A4
    margin_x = 11 * mm
    content_width = page_width - margin_x * 2

    cell_style = ParagraphStyle(
        "cell",
        fontName=font_name,
        fontSize=7.4,
        leading=8.5,
        alignment=TA_CENTER,
        wordWrap="CJK",
        textColor=colors.black,
    )
    cell_left_style = ParagraphStyle(
        "cell-left",
        parent=cell_style,
        alignment=TA_LEFT,
    )
    cell_right_style = ParagraphStyle(
        "cell-right",
        parent=cell_style,
        alignment=TA_RIGHT,
    )
    meta_style = ParagraphStyle(
        "meta",
        fontName=font_name,
        fontSize=8.5,
        leading=10.5,
        alignment=TA_LEFT,
        wordWrap="CJK",
        textColor=colors.black,
    )
    footer_style = ParagraphStyle(
        "footer",
        fontName=font_name,
        fontSize=7.8,
        leading=9.6,
        alignment=TA_LEFT,
        wordWrap="CJK",
        textColor=colors.black,
    )

    lines = context["lines"]
    pages = [
        lines[index : index + PAGE_ROW_COUNT] for index in range(0, len(lines), PAGE_ROW_COUNT)
    ]
    if not pages:
        pages = [[]]

    for page_index, page_lines in enumerate(pages):
        is_last_page = page_index == len(pages) - 1
        top = page_height - 10 * mm

        if context.get("is_reversed"):
            canvas.saveState()
            canvas.setFillColorRGB(0.87, 0.87, 0.87)
            canvas.setFont(font_name, 48)
            canvas.translate(page_width / 2, page_height / 2)
            canvas.rotate(28)
            canvas.drawCentredString(0, 0, "已红冲")
            canvas.restoreState()

        canvas.setFillColor(colors.black)
        canvas.setFont(font_name, 9)
        canvas.drawRightString(
            page_width - margin_x, top - 1 * mm, f"第 {page_index + 1}/{len(pages)} 页"
        )

        canvas.setFont(font_name, 17)
        canvas.drawCentredString(page_width / 2, top, context["shop_name"])
        top -= 7.5 * mm
        canvas.setFont(font_name, 14)
        canvas.drawCentredString(page_width / 2, top, context["document_title"])
        top -= 7 * mm

        partner_label = context["partner_label"]
        warehouse_label = "入库仓库" if context["is_purchase"] else "发货仓库"
        meta_data = [
            [
                _paragraph(f"{warehouse_label}：{context['warehouse']}", style=meta_style),
                _paragraph(f"录单日期：{context['order_date']}", style=meta_style),
                _paragraph(f"单据编号：{context['order_no']}", style=meta_style),
            ],
            [
                _paragraph(f"{partner_label}：{context['partner_name']}", style=meta_style),
                _paragraph(f"联系人：{context['partner_contact'] or '-'}", style=meta_style),
                _paragraph(f"联系电话：{context['partner_phone'] or '-'}", style=meta_style),
            ],
            [
                _paragraph(f"联系地址：{context['partner_address'] or '-'}", style=meta_style),
                "",
                "",
            ],
        ]
        meta_table = Table(
            meta_data,
            colWidths=[content_width * 0.35, content_width * 0.27, content_width * 0.38],
            rowHeights=[5.8 * mm, 5.8 * mm, 6.8 * mm],
        )
        meta_table.setStyle(
            TableStyle(
                [
                    ("SPAN", (0, 2), (-1, 2)),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 0),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                ]
            )
        )
        top = _draw_table(canvas, meta_table, margin_x, top, content_width) - 2 * mm

        header = ["序号", "商品编号", "商品全名", "规格", "单位", "数量", "单价", "金额", "备注"]
        table_data: list[list[Any]] = [[_paragraph(value, style=cell_style) for value in header]]
        for row in page_lines:
            table_data.append(
                [
                    _paragraph(row["sequence"], style=cell_style),
                    _paragraph(row["part_number"], style=cell_left_style),
                    _paragraph(row["name"], style=cell_left_style),
                    _paragraph(row["spec"], style=cell_style),
                    _paragraph(row["unit"], style=cell_style),
                    _paragraph(_format_quantity(row["quantity"]), style=cell_right_style),
                    _paragraph(_format_money(row["price"]), style=cell_right_style),
                    _paragraph(_format_money(row["amount"]), style=cell_right_style),
                    _paragraph(
                        row.get("remark") or "",
                        style=cell_left_style,
                        empty_text="",
                    ),
                ]
            )

        col_widths = [
            content_width * ratio
            for ratio in (0.05, 0.12, 0.22, 0.12, 0.07, 0.09, 0.10, 0.12, 0.11)
        ]
        detail_table = Table(
            table_data,
            colWidths=col_widths,
            rowHeights=[8 * mm] + [7.2 * mm] * len(page_lines),
        )
        detail_style = _table_style(font_name, 7.5)
        detail_style.add("ALIGN", (1, 1), (2, -1), "LEFT")
        detail_style.add("ALIGN", (5, 1), (7, -1), "RIGHT")
        detail_style.add("FONTNAME", (0, 0), (-1, 0), font_name)
        detail_style.add("FONTSIZE", (0, 0), (-1, 0), 8.3)
        detail_table.setStyle(detail_style)
        top = _draw_table(canvas, detail_table, margin_x, top, content_width)

        if is_last_page:
            total_data = [
                [
                    "合计",
                    _paragraph(
                        f"人民币（大写）：{money_to_chinese_upper(context['total_amount'])}",
                        style=meta_style,
                    ),
                    _format_quantity(context["total_quantity"]),
                    f"总金额：{_format_money(context['total_amount'])}",
                ]
            ]
            total_table = Table(
                total_data,
                colWidths=[12 * mm, content_width - 12 * mm - 24 * mm - 31 * mm, 24 * mm, 31 * mm],
                rowHeights=[10 * mm],
            )
            total_style = _table_style(font_name, 8.5)
            total_style.add("ALIGN", (1, 0), (1, 0), "LEFT")
            total_style.add("ALIGN", (3, 0), (3, 0), "RIGHT")
            total_table.setStyle(total_style)
            top = _draw_table(canvas, total_table, margin_x, top, content_width) - 3 * mm

            footer_rows: list[list[Any]] = [
                [
                    _paragraph("备注", style=footer_style),
                    _paragraph(context.get("remark") or "-", style=footer_style),
                ]
            ]
            if context.get("business_scope"):
                footer_rows.append(
                    [
                        _paragraph("经营项目", style=footer_style),
                        _paragraph(context["business_scope"], style=footer_style),
                    ]
                )
            if context.get("print_notice"):
                footer_rows.append(
                    [
                        _paragraph("说明", style=footer_style),
                        _paragraph(context["print_notice"], style=footer_style),
                    ]
                )
            footer_table = Table(footer_rows, colWidths=[18 * mm, content_width - 18 * mm])
            footer_table.setStyle(
                TableStyle(
                    [
                        ("FONTNAME", (0, 0), (-1, -1), font_name),
                        ("FONTSIZE", (0, 0), (-1, -1), 7.8),
                        ("LINEBELOW", (0, 0), (-1, -1), 0.6, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 3),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            top = _draw_table(canvas, footer_table, margin_x, top, content_width)

            contact_table = Table(
                [
                    [
                        _paragraph(
                            f"地址：{context.get('shop_address') or '-'}", style=footer_style
                        ),
                        _paragraph(f"电话：{context.get('shop_phone') or '-'}", style=footer_style),
                    ]
                ],
                colWidths=[content_width * 0.65, content_width * 0.35],
            )
            contact_table.setStyle(
                TableStyle(
                    [
                        ("LINEBELOW", (0, 0), (-1, -1), 0.6, colors.black),
                        ("LINEBEFORE", (1, 0), (1, 0), 0.6, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                        ("TOPPADDING", (0, 0), (-1, -1), 4),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            top = _draw_table(canvas, contact_table, margin_x, top, content_width)

            extra_fields = get_print_extra_fields(context)
            if extra_fields:
                extra_rows = []
                for index in range(0, len(extra_fields), 2):
                    row = extra_fields[index : index + 2]
                    rendered_row = [
                        _paragraph(f"{label}：{value}", style=footer_style) for label, value in row
                    ]
                    if len(rendered_row) == 1:
                        rendered_row.append("")
                    extra_rows.append(rendered_row)
                extra_table = Table(
                    extra_rows,
                    colWidths=[content_width / 2] * 2,
                )
                extra_table.setStyle(
                    TableStyle(
                        [
                            ("GRID", (0, 0), (-1, -1), 0.6, colors.black),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                            ("LEFTPADDING", (0, 0), (-1, -1), 3),
                            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                            ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                        ]
                    )
                )
                top = _draw_table(canvas, extra_table, margin_x, top, content_width)

            signature_label = "验收人" if context["is_purchase"] else "客户签字"
            signature_values = [
                f"制单：{context['operator']}",
                f"复核：{context.get('reviewer') or '________________'}",
                f"结算方式：{context['settlement_method']}",
                f"{signature_label}：________________",
            ]
            signature_table = Table(
                [[_paragraph(value, style=footer_style) for value in signature_values]],
                colWidths=[content_width / 4] * 4,
                rowHeights=[8 * mm],
            )
            signature_table.setStyle(
                TableStyle(
                    [
                        ("BOX", (0, 0), (-1, -1), 0.6, colors.black),
                        ("INNERGRID", (0, 0), (-1, -1), 0.6, colors.black),
                        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 3),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                    ]
                )
            )
            _draw_table(canvas, signature_table, margin_x, top, content_width)
        else:
            canvas.setFont(font_name, 8)
            canvas.drawRightString(
                page_width - margin_x,
                top - 5 * mm,
                f"本页小计 {len(page_lines)} 项，接下页",
            )

        canvas.showPage()

    canvas.save()
    return buffer.getvalue()


def build_order_pdf(db: Session, kind: str, order_id: str) -> tuple[bytes, str]:
    is_purchase = kind == "purchases"
    if is_purchase:
        order = order_service.get_purchase_order(db, order_id)
        items = order_service.get_purchase_items(db, order.id)
        partner = db.get(Supplier, order.supplier_id) if order.supplier_id else None
    else:
        order = order_service.get_sales_order(db, order_id)
        items = order_service.get_sales_items(db, order.id)
        partner = db.get(Customer, order.customer_id) if order.customer_id else None

    part_ids = [item.part_id for item in items]
    part_map = (
        {part.id: part for part in db.execute(select(Part).where(Part.id.in_(part_ids))).scalars()}
        if part_ids
        else {}
    )
    settings = get_public_settings(db)

    title_by_type = {
        "purchase": "采购入库单",
        "purchase_return": "采购退货单",
        "sale": "销货清单",
        "sale_return": "销售退货单",
    }
    lines = []
    for index, item in enumerate(items):
        part = part_map.get(item.part_id)
        price = item.purchase_price if is_purchase else item.sale_price
        lines.append(
            {
                "sequence": index + 1,
                "part_number": part.part_number if part else item.part_id,
                "name": part.name if part else "零件资料已停用",
                "spec": part.spec if part and part.spec else "-",
                "unit": part.unit if part else settings["default_unit"],
                "quantity": float(item.quantity),
                "price": price,
                "amount": item.amount,
                "remark": item.remark or "",
            }
        )

    if is_purchase:
        partner_name = partner.name if partner else "临时供应商"
        partner_contact = partner.contact if partner else ""
        partner_phone = partner.phone if partner else ""
        partner_address = partner.address if partner else ""
    else:
        partner_name = partner.name if partner else (order.customer_name or "散客")
        partner_contact = partner.name if partner else (order.customer_name or "")
        partner_phone = partner.phone if partner else ""
        partner_address = partner.location if partner else ""

    context = {
        "shop_name": settings["shop_name"] or "AutoStock 汽配店",
        "document_title": title_by_type.get(order.order_type, "业务单据"),
        "order_no": order.order_no,
        "order_date": order.order_date,
        "warehouse": settings["print_warehouse"] or "主仓库",
        "is_purchase": is_purchase,
        "partner_label": "供应商" if is_purchase else "客户名称",
        "partner_name": partner_name,
        "partner_contact": partner_contact,
        "partner_phone": partner_phone,
        "partner_address": partner_address,
        "lines": lines,
        "total_quantity": sum(float(item.quantity) for item in items),
        "total_amount": order.total_amount,
        "remark": order.remark or "",
        "business_scope": settings["business_scope"] or "",
        "print_notice": settings["print_notice"] or "",
        "shop_address": settings["shop_address"] or "",
        "shop_phone": settings["shop_phone"] or "",
        "operator": settings["print_operator"] or "管理员",
        "reviewer": settings["print_reviewer"] or "",
        "settlement_method": settings["settlement_method"] or "现结",
        "print_payment_account": settings["print_payment_account"] or "",
        "print_wechat": settings["print_wechat"] or "",
        "print_warranty_period": settings["print_warranty_period"] or "",
        "print_custom_fields": settings["print_custom_fields"],
        "is_reversed": bool(order.reversed_by),
    }
    return render_order_pdf(context), f"{order.order_no}_{context['document_title']}.pdf"
