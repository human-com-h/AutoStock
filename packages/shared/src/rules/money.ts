/**
 * 金额换算纯函数（§4.1：金额一律用 INTEGER 存"分"，仅前端展示时除以 100）。
 * 后端 Python 侧等价实现见 backend/app/core/money.py，两端共用同一组测试用例。
 */

export function centsToYuan(cents: number): number {
  return Math.round(cents) / 100;
}

export function yuanToCents(yuan: number): number {
  return Math.round(yuan * 100);
}

export function formatYuan(cents: number): string {
  return centsToYuan(cents).toFixed(2);
}
