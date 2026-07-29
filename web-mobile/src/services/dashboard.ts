import { db } from "../db/schema";

export interface MobileBusinessOverview {
  salesAmount: number;
  purchaseAmount: number;
  orderCount: number;
}

export async function getMobileBusinessOverview(): Promise<MobileBusinessOverview> {
  const today = new Date().toLocaleDateString("sv-SE");
  const [sales, purchases] = await Promise.all([
    db.salesOrder.where("order_date").equals(today).toArray(),
    db.purchaseOrder.where("order_date").equals(today).toArray(),
  ]);
  const validSales = sales.filter((row) => row.is_deleted === 0);
  const validPurchases = purchases.filter((row) => row.is_deleted === 0);

  return {
    salesAmount: validSales.reduce(
      (total, row) =>
        total + (row.order_type === "sale_return" ? -1 : 1) * row.total_amount,
      0,
    ),
    purchaseAmount: validPurchases.reduce(
      (total, row) =>
        total + (row.order_type === "purchase_return" ? -1 : 1) * row.total_amount,
      0,
    ),
    orderCount: validSales.length + validPurchases.length,
  };
}
