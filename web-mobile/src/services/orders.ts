import { newUlid, weightedAverageCostAfterIn } from "@autostock/shared";
import {
  db,
  getMeta,
  getPrintSettings,
  setMeta,
  type BusinessRow,
  type NamedRow,
  type PartRow,
  type PurchaseItemRow,
  type PurchaseOrderRow,
  type SalesItemRow,
  type SalesOrderRow,
  type StockLedgerRow,
} from "../db/schema";

export type OrderKind = "purchase" | "sale";

export interface QuickOrderLineInput {
  partId: string;
  quantity: number;
  price: number;
  remark?: string | null;
}

export interface QuickOrderInput {
  kind: OrderKind;
  items: QuickOrderLineInput[];
  partnerId?: string | null;
  partnerName?: string | null;
  remark?: string | null;
}

export interface LocalOrderLine {
  item: PurchaseItemRow | SalesItemRow;
  part: PartRow | null;
}

export interface LocalOrderDetail {
  kind: OrderKind;
  order: PurchaseOrderRow | SalesOrderRow;
  partner: NamedRow | null;
  lines: LocalOrderLine[];
}

export interface RecentOrderRow {
  kind: OrderKind;
  order: PurchaseOrderRow | SalesOrderRow;
  item: PurchaseItemRow | SalesItemRow | null;
  itemCount: number;
  partName: string;
  partnerName: string;
}

function groupItemsByOrder<T extends { order_id: string }>(items: T[]): Map<string, T[]> {
  const grouped = new Map<string, T[]>();
  for (const item of items) {
    const group = grouped.get(item.order_id) || [];
    group.push(item);
    grouped.set(item.order_id, group);
  }
  return grouped;
}

async function effectiveLocalStock(partId: string): Promise<{
  quantity: number;
  avgCost: number;
}> {
  const [snapshot, pendingLedgers] = await Promise.all([
    db.stockSnapshot.get(partId),
    db.stockLedger
      .where("part_id")
      .equals(partId)
      .filter((row) => row.sync_status === "pending")
      .toArray(),
  ]);
  let quantity = Number(snapshot?.quantity || 0);
  let avgCost = Number(snapshot?.avg_cost || 0);
  pendingLedgers.sort((left, right) => left.occurred_at.localeCompare(right.occurred_at));
  for (const ledger of pendingLedgers) {
    const change = Number(ledger.quantity);
    if (change > 0) {
      avgCost = weightedAverageCostAfterIn({
        currentQuantity: quantity,
        currentAvgCost: avgCost,
        inQuantity: change,
        inUnitCost: Number(ledger.unit_cost),
      });
    }
    quantity += change;
  }
  return { quantity, avgCost };
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
  if (!input.items.length) throw new Error("请至少添加一个零件");
  if (
    input.items.some(
      (item) =>
        !Number.isFinite(item.quantity) ||
        item.quantity <= 0 ||
        Math.abs(item.quantity * 1000 - Math.round(item.quantity * 1000)) > 1e-9 ||
        !Number.isInteger(item.price) ||
        item.price < 0,
    )
  ) {
    throw new Error("单据中存在无效的数量或价格");
  }
  if (new Set(input.items.map((item) => item.partId)).size !== input.items.length) {
    throw new Error("同一张单据中不能重复添加同一零件");
  }

  const deviceId = (await getMeta("device_id")) || newUlid();
  const settings = await getPrintSettings();
  const now = new Date().toISOString();
  const orderFields = baseFields(deviceId, now);
  const lines = input.items.map((item) => ({
    input: item,
    itemFields: baseFields(deviceId, now),
    ledgerFields: baseFields(deviceId, now),
    amount: Math.round(item.quantity * item.price),
    unitCost: input.kind === "purchase" ? item.price : 0,
  }));
  const totalAmount = lines.reduce((total, line) => total + line.amount, 0);

  await db.transaction(
    "rw",
    [
      db.purchaseOrder,
      db.purchaseItem,
      db.salesOrder,
      db.salesItem,
      db.stockLedger,
      db.stockSnapshot,
      db.parts,
      db.syncQueue,
      db.meta,
    ],
    async () => {
      const orderNo = await nextOrderNo(input.kind);
      if (input.kind === "sale") {
        for (const line of lines) {
          const stock = await effectiveLocalStock(line.input.partId);
          line.unitCost = stock.avgCost;
          if (!settings.allow_negative_stock && line.input.quantity > stock.quantity) {
            const part = await db.parts.get(line.input.partId);
            throw new Error(
              `${part?.name || "所选零件"}库存不足，当前可用 ${stock.quantity}`,
            );
          }
        }
      }

      if (input.kind === "purchase") {
        await db.purchaseOrder.add({
          ...orderFields,
          order_no: orderNo,
          supplier_id: input.partnerId || null,
          order_date: now.slice(0, 10),
          total_amount: totalAmount,
          paid_amount: 0,
          order_type: "purchase",
          source_order_id: null,
          reversed_by: null,
          remark: input.remark || null,
          sync_status: "pending",
        });
        await db.purchaseItem.bulkAdd(
          lines.map((line) => ({
            ...line.itemFields,
            order_id: orderFields.id,
            part_id: line.input.partId,
            quantity: line.input.quantity,
            purchase_price: line.input.price,
            amount: line.amount,
            remark: line.input.remark || null,
            sync_status: "pending" as const,
          })),
        );
      } else {
        await db.salesOrder.add({
          ...orderFields,
          order_no: orderNo,
          customer_id: input.partnerId || null,
          customer_name: input.partnerName || null,
          order_date: now.slice(0, 10),
          total_amount: totalAmount,
          received_amount: 0,
          order_type: "sale",
          source_order_id: null,
          reversed_by: null,
          remark: input.remark || null,
          sync_status: "pending",
        });
        await db.salesItem.bulkAdd(
          lines.map((line) => ({
            ...line.itemFields,
            order_id: orderFields.id,
            part_id: line.input.partId,
            quantity: line.input.quantity,
            sale_price: line.input.price,
            amount: line.amount,
            cost_amount: Math.round(line.input.quantity * line.unitCost),
            remark: line.input.remark || null,
            sync_status: "pending" as const,
          })),
        );
      }
      await db.stockLedger.bulkAdd(
        lines.map((line) => ({
          ...line.ledgerFields,
          part_id: line.input.partId,
          change_type: input.kind,
          quantity:
            input.kind === "purchase"
              ? line.input.quantity
              : -line.input.quantity,
          unit_cost: line.unitCost,
          source_type: input.kind === "purchase" ? "purchase_item" : "sales_item",
          source_id: line.itemFields.id,
          occurred_at: now,
          remark: "手机端快速开单",
          sync_status: "pending" as const,
        })),
      );
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
  RecentOrderRow[]
> {
  const fromDate = new Date();
  fromDate.setDate(fromDate.getDate() - 89);
  const fromDateText = fromDate.toLocaleDateString("sv-SE");
  const [purchases, sales, purchaseItems, salesItems, parts, suppliers, customers] =
    await Promise.all([
    db.purchaseOrder.orderBy("order_date").reverse().toArray(),
    db.salesOrder.orderBy("order_date").reverse().toArray(),
    db.purchaseItem.toArray(),
    db.salesItem.toArray(),
    db.parts.toArray(),
    db.suppliers.toArray(),
    db.customers.toArray(),
  ]);
  const partsById = new Map(parts.map((part) => [part.id, part]));
  const suppliersById = new Map(suppliers.map((row) => [row.id, row]));
  const customersById = new Map(customers.map((row) => [row.id, row]));
  const purchaseItemsByOrder = groupItemsByOrder(purchaseItems);
  const salesItemsByOrder = groupItemsByOrder(salesItems);
  const rows: RecentOrderRow[] = [
    ...purchases
      .filter((order) => order.is_deleted === 0 && order.order_date >= fromDateText)
      .map((order) => {
      const items = purchaseItemsByOrder.get(order.id) || [];
      const item = items[0] || null;
      const part = item ? partsById.get(item.part_id) : null;
      return {
        kind: "purchase" as const,
        order,
        item,
        itemCount: items.length,
        partName: part?.name || "未知零件",
        partnerName: order.supplier_id
          ? suppliersById.get(order.supplier_id)?.name || ""
          : "",
      };
    }),
    ...sales
      .filter((order) => order.is_deleted === 0 && order.order_date >= fromDateText)
      .map((order) => {
      const items = salesItemsByOrder.get(order.id) || [];
      const item = items[0] || null;
      const part = item ? partsById.get(item.part_id) : null;
      return {
        kind: "sale" as const,
        order,
        item,
        itemCount: items.length,
        partName: part?.name || "未知零件",
        partnerName:
          order.customer_name ||
          (order.customer_id ? customersById.get(order.customer_id)?.name || "" : ""),
      };
    }),
  ];
  return rows.sort((a, b) => b.order.created_at.localeCompare(a.order.created_at));
}

export async function getLocalOrderDetail(
  kind: OrderKind,
  orderId: string,
): Promise<LocalOrderDetail | null> {
  const order =
    kind === "purchase"
      ? await db.purchaseOrder.get(orderId)
      : await db.salesOrder.get(orderId);
  if (!order) return null;

  const items =
    kind === "purchase"
      ? await db.purchaseItem.where("order_id").equals(orderId).toArray()
      : await db.salesItem.where("order_id").equals(orderId).toArray();
  const parts = await db.parts.bulkGet(items.map((item) => item.part_id));
  const partnerId =
    kind === "purchase"
      ? (order as PurchaseOrderRow).supplier_id
      : (order as SalesOrderRow).customer_id;
  const partner = partnerId
    ? kind === "purchase"
      ? await db.suppliers.get(partnerId)
      : await db.customers.get(partnerId)
    : null;

  return {
    kind,
    order,
    partner: partner || null,
    lines: items.map((item, index) => ({
      item,
      part: parts[index] || null,
    })),
  };
}
