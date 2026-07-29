from app.services.order_print_service import (
    get_print_extra_fields,
    money_to_chinese_upper,
)


def test_money_to_chinese_upper_handles_zero_integer_and_decimal_values():
    assert money_to_chinese_upper(0) == "零元整"
    assert money_to_chinese_upper(100) == "壹元整"
    assert money_to_chinese_upper(105) == "壹元零伍分"
    assert money_to_chinese_upper(110) == "壹元壹角"
    assert money_to_chinese_upper(100_100) == "壹仟零壹元整"
    assert money_to_chinese_upper(1_000_100) == "壹万零壹元整"


def test_print_extra_fields_include_recommended_visible_and_handwritten_values():
    assert get_print_extra_fields(
        {
            "print_payment_account": "工商银行 1234",
            "print_wechat": "AUTO-PARTS",
            "print_warranty_period": "",
            "print_custom_fields": [
                {
                    "label": "运输方式",
                    "value": "",
                    "visible": True,
                    "handwritten": True,
                },
                {
                    "label": "物流单号",
                    "value": "SF123",
                    "visible": True,
                    "handwritten": False,
                },
                {
                    "label": "内部字段",
                    "value": "隐藏",
                    "visible": False,
                    "handwritten": False,
                },
            ],
        }
    ) == [
        ("收款账户", "工商银行 1234"),
        ("联系微信", "AUTO-PARTS"),
        ("运输方式", "________________"),
        ("物流单号", "SF123"),
    ]
