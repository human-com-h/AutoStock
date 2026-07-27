/**
 * ULID 生成（26 位 Crockford Base32 字符串，按时间排序）。
 *
 * 结构：48 位毫秒时间戳 + 80 位随机数，共 128 位，编码为 26 个 Crockford Base32 字符。
 * 必须与后端 app/core/ulid.py 的算法逐位一致（相同编码字母表、相同位宽切分），
 * 两端各自离线生成的 ID 才能保证格式统一、按时间可排序，且互不撞号（概率意义上）。
 */

const ENCODING = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"; // Crockford Base32，共 32 个字符
const TIME_LEN = 10; // 48 位时间戳编码为 10 个字符
const RANDOM_LEN = 16; // 80 位随机数编码为 16 个字符
const TIMESTAMP_MAX = 2 ** 48 - 1;

function encodeBase32(value: bigint, length: number): string {
  let v = value;
  const chars = new Array<string>(length).fill("0");
  for (let i = length - 1; i >= 0; i--) {
    chars[i] = ENCODING[Number(v & 0x1fn)];
    v >>= 5n;
  }
  return chars.join("");
}

function randomBytes(n: number): Uint8Array {
  const bytes = new Uint8Array(n);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(bytes);
  } else {
    for (let i = 0; i < n; i++) bytes[i] = Math.floor(Math.random() * 256);
  }
  return bytes;
}

function bytesToBigInt(bytes: Uint8Array): bigint {
  let value = 0n;
  for (const byte of bytes) {
    value = (value << 8n) | BigInt(byte);
  }
  return value;
}

export function newUlid(timestampMs?: number): string {
  const ts = BigInt(Math.min(Math.max(timestampMs ?? Date.now(), 0), TIMESTAMP_MAX));
  const randomness = bytesToBigInt(randomBytes(10));
  return encodeBase32(ts, TIME_LEN) + encodeBase32(randomness, RANDOM_LEN);
}

export function isValidUlid(value: unknown): boolean {
  if (typeof value !== "string" || value.length !== TIME_LEN + RANDOM_LEN) return false;
  const upper = value.toUpperCase();
  for (const ch of upper) {
    if (!ENCODING.includes(ch)) return false;
  }
  return true;
}

export function extractTimestampMs(ulid: string): number {
  if (!isValidUlid(ulid)) throw new Error(`不是合法的 ULID: ${ulid}`);
  let value = 0n;
  for (const ch of ulid.slice(0, TIME_LEN).toUpperCase()) {
    value = (value << 5n) | BigInt(ENCODING.indexOf(ch));
  }
  return Number(value);
}
