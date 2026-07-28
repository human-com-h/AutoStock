from datetime import datetime, timedelta, timezone

BUSINESS_TIMEZONE = timezone(timedelta(hours=8), name="Asia/Shanghai")


def business_now() -> datetime:
    """返回门店本地时间；库存同步时间戳仍统一使用 UTC。"""
    return datetime.now(BUSINESS_TIMEZONE)


def business_date_str() -> str:
    return business_now().date().isoformat()
