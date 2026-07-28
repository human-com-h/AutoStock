const ORDER_TYPE_LABELS: Record<string, string> = {
  purchase: "采购入库",
  purchase_return: "采购退货",
  sale: "销售出库",
  sale_return: "销售退货",
};

export function orderTypeLabel(value: string): string {
  return ORDER_TYPE_LABELS[value] || "其他业务";
}

export function orderDirectionLabel(value: string): "入库" | "出库" {
  return value === "purchase" || value === "sale_return" ? "入库" : "出库";
}

export function orderAmountSign(value: string): number {
  return value === "purchase_return" || value === "sale_return" ? -1 : 1;
}
