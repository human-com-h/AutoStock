import { db, type PartRow, type StockLedgerRow, type StockSnapshotRow } from "../db/schema";

export interface PartWithStock {
  part: PartRow;
  snapshot: StockSnapshotRow | null;
  pendingQuantity: number;
  displayQuantity: number;
}

function matches(part: PartRow, keyword: string): boolean {
  const needle = keyword.trim().toLowerCase();
  if (!needle) return true;
  return [part.part_number, part.oe_number, part.name, part.pinyin]
    .filter(Boolean)
    .some((value) => String(value).toLowerCase().includes(needle));
}

export async function searchLocalParts(
  keyword = "",
  lowStockOnly = false,
): Promise<PartWithStock[]> {
  const [parts, snapshots, pendingLedgers] = await Promise.all([
    db.parts.toArray(),
    db.stockSnapshot.toArray(),
    db.stockLedger.where("sync_status").equals("pending").toArray(),
  ]);
  const snapshotsByPart = new Map(snapshots.map((row) => [row.part_id, row]));
  const pendingByPart = new Map<string, number>();
  for (const row of pendingLedgers) {
    pendingByPart.set(row.part_id, (pendingByPart.get(row.part_id) || 0) + Number(row.quantity));
  }
  return parts
    .filter((part) => part.is_deleted === 0 && part.is_active === 1 && matches(part, keyword))
    .map((part) => {
      const snapshot = snapshotsByPart.get(part.id) || null;
      const pendingQuantity = pendingByPart.get(part.id) || 0;
      return {
        part,
        snapshot,
        pendingQuantity,
        displayQuantity: Number(snapshot?.quantity || 0) + pendingQuantity,
      };
    })
    .filter((row) => !lowStockOnly || row.displayQuantity < Number(row.part.min_stock))
    .sort((a, b) => a.part.part_number.localeCompare(b.part.part_number, "zh-CN"));
}

export async function getPartWithStock(partId: string): Promise<PartWithStock | null> {
  const part = await db.parts.get(partId);
  if (!part) return null;
  const [snapshot, pendingLedgers] = await Promise.all([
    db.stockSnapshot.get(partId),
    db.stockLedger
      .where("part_id")
      .equals(partId)
      .filter((row) => row.sync_status === "pending")
      .toArray(),
  ]);
  const pendingQuantity = pendingLedgers.reduce((sum, row) => sum + Number(row.quantity), 0);
  return {
    part,
    snapshot: snapshot || null,
    pendingQuantity,
    displayQuantity: Number(snapshot?.quantity || 0) + pendingQuantity,
  };
}

export async function recentPartLedgers(
  partId: string,
  limit = 20,
): Promise<StockLedgerRow[]> {
  return db.stockLedger
    .where("part_id")
    .equals(partId)
    .reverse()
    .sortBy("occurred_at")
    .then((rows) => rows.slice(0, limit));
}
