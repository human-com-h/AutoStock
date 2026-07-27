/**
 * 移动加权平均成本计算（§5.1）。
 * 入库：新均价 = (原库存×原均价 + 入库量×入库价) / (原库存 + 入库量)
 * 出库：不改变均价，按当前均价固化到 sales_item.cost_amount，由调用方另行处理。
 * 后端 Python 侧等价实现见 backend/app/services/stock_service.py 的 weighted_average_cost，
 * 两端共用同一组测试用例（tests 目录），确保精度处理方式一致。
 */

export interface WeightedCostInput {
  /** 原库存数量 */
  currentQuantity: number;
  /** 原移动加权平均成本（分） */
  currentAvgCost: number;
  /** 本次入库数量，必须为正数 */
  inQuantity: number;
  /** 本次入库单价（分） */
  inUnitCost: number;
}

/**
 * 计算入库后的新移动加权平均成本（分），四舍五入到整数分。
 * 若原库存为负或零且本次入库量为正，新均价直接取本次入库单价。
 */
export function weightedAverageCostAfterIn(input: WeightedCostInput): number {
  const { currentQuantity, currentAvgCost, inQuantity, inUnitCost } = input;
  if (inQuantity <= 0) {
    throw new Error("入库数量必须为正数");
  }
  const newQuantity = currentQuantity + inQuantity;
  if (newQuantity <= 0) {
    return inUnitCost;
  }
  const totalCost = currentQuantity * currentAvgCost + inQuantity * inUnitCost;
  return Math.round(totalCost / newQuantity);
}
