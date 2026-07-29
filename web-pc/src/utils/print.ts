const CN_DIGITS = ["零", "壹", "贰", "叁", "肆", "伍", "陆", "柒", "捌", "玖"];
const CN_UNITS = ["", "拾", "佰", "仟"];
const CN_GROUP_UNITS = ["", "万", "亿", "兆"];

function integerGroupToChinese(group: number): string {
  const digits = String(group).padStart(4, "0").split("").map(Number);
  let result = "";
  let pendingZero = false;

  digits.forEach((digit, index) => {
    const unitIndex = 3 - index;
    if (digit === 0) {
      pendingZero = result.length > 0;
      return;
    }
    if (pendingZero) result += CN_DIGITS[0];
    result += `${CN_DIGITS[digit]}${CN_UNITS[unitIndex]}`;
    pendingZero = false;
  });
  return result;
}

export function moneyToChineseUpper(cents: number): string {
  if (!Number.isFinite(cents)) return "零元整";
  const normalized = Math.round(Math.abs(cents));
  const yuan = Math.floor(normalized / 100);
  const jiao = Math.floor((normalized % 100) / 10);
  const fen = normalized % 10;

  let integerText = "";
  if (yuan === 0) {
    integerText = CN_DIGITS[0];
  } else {
    const groups: number[] = [];
    let remaining = yuan;
    while (remaining > 0) {
      groups.push(remaining % 10000);
      remaining = Math.floor(remaining / 10000);
    }

    let zeroBetweenGroups = false;
    for (let index = groups.length - 1; index >= 0; index -= 1) {
      const group = groups[index];
      if (group === 0) {
        zeroBetweenGroups = integerText.length > 0;
        continue;
      }
      if (integerText && (zeroBetweenGroups || group < 1000)) integerText += CN_DIGITS[0];
      integerText += `${integerGroupToChinese(group)}${CN_GROUP_UNITS[index] || ""}`;
      zeroBetweenGroups = false;
    }
  }

  const sign = cents < 0 ? "负" : "";
  if (jiao === 0 && fen === 0) return `${sign}${integerText}元整`;
  const decimalText = `${jiao ? `${CN_DIGITS[jiao]}角` : fen ? "零" : ""}${
    fen ? `${CN_DIGITS[fen]}分` : ""
  }`;
  return `${sign}${integerText}元${decimalText}`;
}

export function formatMoney(cents: number): string {
  return (Number(cents || 0) / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function formatQuantity(value: number): string {
  return Number(value || 0).toLocaleString("zh-CN", {
    maximumFractionDigits: 3,
  });
}

