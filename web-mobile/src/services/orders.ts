import { newUlid } from "@autostock/shared";
import {
  db,
  getMeta,
  setMeta,
  type BusinessRow,
  type PurchaseItemRow,
  type PurchaseOrderRow,
  type SalesItemRow,
  type SalesOrderRow,
  type StockLedgerRow,
} from "../db/schema";

export type OrderKind = "purchase" | "sale";

export interface QuickOrderInput {
  kind: OrderKind;
  partId: string;
  quantity: number;
  price: number;
  partnerId?: string | null;
  partnerName?: string | null;
}

function baseFields(deviceId: string, now: string): BusinessRow {
  return {
    id: newUlid(),
    created_at: now,
    updated_at: now,
    rev: 0,
    version: 1,
    device_id: deviceId,
    is_deleted: 0,
  };
}

async function nextOrderNo(kind: OrderKind): Promise<string> {
  const prefix = kind === "purchase" ? "CG" : "XS";
  const date = new Date().toLocaleDateString("sv-SE").replaceAll("-", "");
  const key = `order_seq:${prefix}:${date}`;
  const previous = Number((await getMeta(key)) || 0);
  const next = previous + 1;
  await setMeta(key, String(next));
  return `${prefix}${date}${String(next).padStart(4, "0")}`;
}

export async function createQuickOrder(input: QuickOrderInput): Promise<{
  orderId: string;
  uploaded: boolean;
}> {
  const deviceId = (await getMeta("device_id")) || newUlid();
  const now = new Date().toISOString();
  const orderNo = await nextOrderNo(input.kind);
  const orderFields = baseFields(deviceId, now);
  const itemFields = baseFields(deviceId, now);
  const ledgerFields = baseFields(deviceId, now);
  const amount = Math.round(input.quantity * input.price);
  const changeQuantity = input.kind === "purchase" ? input.quantity : -input.quantity;

  await db.transaction(
    "rw",
    [
      db.purchaseOrder,
      db.purchaseItem,
      db.salesOrder,
      db.salesItem,
      db.stockLedger,
      db.syncQueue,
    ],
    async () => {
      if (input.kind === "purchase") {
        await db.purchaseOrder.add({
          ...orderFields,
          order_no: orderNo,
          supplier_id: input.partnerId || null,
          order_date: now.slice(0, 10),
          total_amount: amount,
          paid_amount: 0,
          order_type: "purchase",
          source_order_id: null,
          reversed_by: null,
          remark: null,
          sync_status: "pending",
        });
        await db.purchaseItem.add({
          ...itemFields,
          order_id: orderFields.id,
          part_id: input.partId,
          quantity: input.quantity,
          purchase_price: input.price,
          amount,
          remark: null,
          sync_status: "pending",
        });
      } else {
        await db.salesOrder.add({
          ...orderFields,
          order_no: orderNo,
          customer_id: input.partnerId || null,
          customer_name: input.partnerName || null,
          order_date: now.slice(0, 10),
          total_amount: amount,
          received_amount: 0,
          order_type: "sale",
          source_order_id: null,
          reversed_by: null,
          remark: null,
          sync_status: "pending",
        });
        await db.salesItem.add({
          ...itemFields,
          order_id: orderFields.id,
          part_id: input.partId,
          quantity: input.quantity,
          sale_price: input.price,
          amount,
          cost_amount: 0,
          remark: null,
          sync_status: "pending",
        });
      }
      await db.stockLedger.add({
        ...ledgerFields,
        part_id: input.partId,
        change_type: input.kind,
        quantity: changeQuantity,
        unit_cost: input.kind === "purchase" ? input.price : 0,
        source_type: input.kind === "purchase" ? "purchase_item" : "sales_item",
        source_id: itemFields.id,
        occurred_at: now,
        remark: "手机端快速开单",
        sync_status: "pending",
      });
      await db.syncQueue.add({
        id: newUlid(),
        table_name: input.kind === "purchase" ? "purchase_order" : "sales_order",
        row_id: orderFields.id,
        op: "insert",
        created_at: now,
      });
    },
  );

  return { orderId: orderFields.id, uploaded: false };
}

export async function voidPendingOrder(kind: OrderKind, orderId: string): Promise<void> {
  await db.transaction(
    "rw",
    [
      db.purchaseOrder,
      db.purchaseItem,
      db.salesOrder,
      db.salesItem,
      db.stockLedger,
      db.syncQueue,
    ],
    async () => {
      if (kind === "purchase") {
        const order = await db.purchaseOrder.get(orderId);
        if (!order || order.sync_status !== "pending") throw new Error("只能撤销待同步单据");
        const items = await db.purchaseItem.where("order_id").equals(orderId).toArray();
        await db.stockLedger.where("source_id").anyOf(items.map((item) => item.id)).delete();
        await db.purchaseItem.where("order_id").equals(orderId).delete();
        await db.purchaseOrder.delete(orderId);
      } else {
        const order = await db.salesOrder.get(orderId);
        if (!order || order.sync_status !== "pending") throw new Error("只能撤销待同步单据");
        const items = await db.salesItem.where("order_id").equals(orderId).toArray();
        await db.stockLedger.where("source_id").anyOf(items.map((item) => item.id)).delete();
        await db.salesItem.where("order_id").equals(orderId).delete();
        await db.salesOrder.delete(orderId);
      }
      await db.syncQueue.where("row_id").equals(orderId).delete();
    },
  );
}

export async function pendingCount(): Promise<number> {
  return db.syncQueue.count();
}

export async function recentOrders(): Promise<
  Array<{
    kind: OrderKind;
    order: PurchaseOrderRow | SalesOrderRow;
    item: PurchaseItemRow | SalesItemRow | null;
    partName: string;
  }>
> {
  const [purchases, sales] = await Promise.all([
    db.purchaseOrder.orderBy("order_date").reverse().toArray(),
    db.salesOrder.orderBy("order_date").reverse().toArray(),
  ]);
  const rows = await Promise.all([
    ...purchases.map(async (order) => {
      const item = (await db.purchaseItem.where("order_id").equals(order.id).first()) || null;
      const part = item ? await db.parts.get(item.part_id) : null;
      return { kind: "purchase" as const, order, item, partName: part?.name || "未知零件" };
    }),
    ...sales.map(async (order) => {
      const item = (await db.salesItem.where("order_id").equals(order.id).first()) || null;
      const part = item ? await db.parts.get(item.part_id) : null;
      return { kind: "sale" as const, order, item, partName: part?.name || "未知零件" };
    }),
  ]);
  return rows.sort((a, b) => b.order.created_at.localeCompare(a.order.created_at));
}
