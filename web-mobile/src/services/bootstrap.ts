import {
  db,
  setMeta,
  type MobilePrintSettings,
  type NamedRow,
  type PartRow,
  type StockLedgerRow,
} from "../db/schema";
import { apiRequest } from "./api";

interface PartsPage {
  items: Array<{ part: PartRow; snapshot: Record<string, unknown> }>;
  total: number;
  next_offset: number;
  has_more: boolean;
}

interface BootstrapOrders {
  purchase_orders: Array<Record<string, unknown>>;
  purchase_items: Array<Record<string, unknown>>;
  sales_orders: Array<Record<string, unknown>>;
  sales_items: Array<Record<string, unknown>>;
  stock_ledgers: Array<Record<string, unknown>>;
}

interface PairingResult {
  device_id: string;
  device_token: string;
  device_name: string;
  server_time: string;
  server_rev: number;
}

export async function exchangePairingCode(
  code: string,
  deviceName: string,
): Promise<PairingResult> {
  const result = await apiRequest<PairingResult>(
    "/api/auth/pair",
    {
      method: "POST",
      body: JSON.stringify({
        code,
        device_name: deviceName,
        client_time: new Date().toISOString(),
      }),
    },
  );
  await db.transaction("rw", db.meta, async () => {
    await setMeta("device_id", result.device_id);
    await setMeta("device_token", result.device_token);
    await setMeta("device_name", result.device_name);
    await setMeta("server_origin", window.location.origin);
    await setMeta("last_pull_rev", String(result.server_rev));
  });
  return result;
}

export async function initializeFromServer(
  onProgress: (current: number, total: number) => void,
): Promise<void> {
  let offset = 0;
  let total = 0;
  do {
    const page = await apiRequest<PartsPage>(
      `/api/mobile/bootstrap/parts?offset=${offset}&limit=500`,
    );
    total = page.total;
    await db.transaction("rw", db.parts, db.stockSnapshot, async () => {
      await db.parts.bulkPut(page.items.map((item) => item.part));
      await db.stockSnapshot.bulkPut(
        page.items.map((item) => ({
          ...item.snapshot,
          quantity: Number(item.snapshot.quantity || 0),
          avg_cost: Number(item.snapshot.avg_cost || 0),
        })) as never[],
      );
    });
    offset = page.next_offset;
    onProgress(offset, total);
    if (!page.has_more) break;
  } while (true);

  const [masterData, orders, printSettings] = await Promise.all([
    apiRequest<Record<string, NamedRow[]>>("/api/mobile/bootstrap/master-data"),
    apiRequest<BootstrapOrders>("/api/mobile/bootstrap/orders"),
    apiRequest<MobilePrintSettings>("/api/mobile/bootstrap/settings"),
  ]);

  await db.transaction(
    "rw",
    [
      db.suppliers,
      db.customers,
      db.brands,
      db.categories,
      db.purchaseOrder,
      db.purchaseItem,
      db.salesOrder,
      db.salesItem,
      db.stockLedger,
      db.meta,
    ],
    async () => {
      await db.suppliers.bulkPut(masterData.suppliers || []);
      await db.customers.bulkPut(masterData.customers || []);
      await db.brands.bulkPut(masterData.brands || []);
      await db.categories.bulkPut(masterData.categories || []);
      await db.purchaseOrder.bulkPut(
        orders.purchase_orders.map((row) => ({ ...row, sync_status: "synced" })) as never[],
      );
      await db.purchaseItem.bulkPut(
        orders.purchase_items.map((row) => ({ ...row, sync_status: "synced" })) as never[],
      );
      await db.salesOrder.bulkPut(
        orders.sales_orders.map((row) => ({ ...row, sync_status: "synced" })) as never[],
      );
      await db.salesItem.bulkPut(
        orders.sales_items.map((row) => ({ ...row, sync_status: "synced" })) as never[],
      );
      await db.stockLedger.bulkPut(
        orders.stock_ledgers.map((row) => ({
          ...row,
          sync_status: "synced",
        })) as StockLedgerRow[],
      );
      await setMeta("initialized_at", new Date().toISOString());
      await setMeta("last_sync_at", new Date().toISOString());
      await setMeta("print_settings", JSON.stringify(printSettings));
    },
  );
}
