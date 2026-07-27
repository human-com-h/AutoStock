"""系统设置表：店名、单位、负库存开关、预警阈值、登录密码哈希等键值对。"""

from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, BusinessMixin


class AppSetting(BusinessMixin, Base):
    __tablename__ = "app_setting"

    key: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    value: Mapped[str | None] = mapped_column(String, nullable=True)
