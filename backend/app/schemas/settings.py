from __future__ import annotations

from pydantic import BaseModel, Field


class PrintCustomField(BaseModel):
    label: str = Field(min_length=1, max_length=20)
    value: str = Field(default="", max_length=100)
    visible: bool = True
    handwritten: bool = False


def _default_print_custom_fields() -> list[PrintCustomField]:
    return [
        PrintCustomField(label="运输方式", handwritten=True),
        PrintCustomField(label="运费承担", handwritten=True),
        PrintCustomField(label="物流单号", handwritten=True),
    ]


class SettingsUpdate(BaseModel):
    shop_name: str = Field(min_length=1, max_length=100)
    default_unit: str = Field(min_length=1, max_length=20)
    allow_negative_stock: bool
    stale_days: int = Field(ge=1, le=3650)
    shop_phone: str = Field(default="", max_length=50)
    shop_address: str = Field(default="", max_length=200)
    business_scope: str = Field(default="", max_length=500)
    print_notice: str = Field(default="商品如有质量问题，请及时联系我们处理。", max_length=500)
    print_warehouse: str = Field(default="主仓库", max_length=50)
    print_operator: str = Field(default="管理员", max_length=50)
    settlement_method: str = Field(default="现结", max_length=50)
    print_payment_account: str = Field(default="", max_length=200)
    print_wechat: str = Field(default="", max_length=50)
    print_warranty_period: str = Field(default="", max_length=100)
    print_reviewer: str = Field(default="", max_length=50)
    print_custom_fields: list[PrintCustomField] = Field(
        default_factory=_default_print_custom_fields,
        max_length=5,
    )


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=4, max_length=128)
