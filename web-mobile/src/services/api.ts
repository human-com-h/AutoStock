import { getMeta } from "../db/schema";

interface Envelope<T> {
  success: boolean;
  data: T;
  error?: { code: string; message: string };
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  timeoutMs = 10_000,
): Promise<T> {
  const token = await getMeta("device_token");
  const serverOrigin = (await getMeta("server_origin")) || window.location.origin;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${serverOrigin}${path}`, {
      ...init,
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
    const body = (await response.json()) as Envelope<T>;
    if (!response.ok || !body.success) {
      throw new Error(body.error?.message || `请求失败（${response.status}）`);
    }
    return body.data;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function probeHealth(): Promise<boolean> {
  if (!navigator.onLine) return false;
  try {
    await apiRequest("/api/health", {}, 2_000);
    return true;
  } catch {
    return false;
  }
}
