/**
 * P2 Task 16: 硬件基准测试 API 客户端
 *
 * 与后端 POST /api/v1/admin/benchmark 端点交互。
 * 桌面环境下通过 window.electronAPI 代理；浏览器环境直接 fetch。
 */

export interface DeviceInfo {
  vendor: 'nvidia' | 'amd' | 'intel' | 'none';
  device_name: string;
  vram_gb: number;
  backend?: string;
}

export interface BenchmarkMetric {
  name: string;
  value: number;
  unit: string;
  details?: Record<string, unknown>;
}

export interface BenchmarkResult {
  device: DeviceInfo;
  metrics: BenchmarkMetric[];
  timestamp: string;
}

interface ApiResponse<T> {
  data: T;
  success: boolean;
  message?: string;
}

async function apiFetch<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const url = getApiUrl(path);
  const headers = new Headers(init?.headers);
  const token =
    typeof window !== 'undefined'
      ? localStorage.getItem('access_token') || ''
      : '';
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  if (init?.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const resp = await fetch(url, { ...init, headers });
  if (!resp.ok) {
    const text = await resp.text().catch(() => '');
    throw new Error(`API ${path} failed: ${resp.status} ${text}`);
  }
  return resp.json() as Promise<T>;
}

/**
 * 运行硬件基准测试
 * POST /api/v1/admin/benchmark?force=true
 */
export async function runBenchmark(
  force: boolean = false,
): Promise<ApiResponse<BenchmarkResult>> {
  const query = force ? '?force=true' : '';
  return apiFetch<ApiResponse<BenchmarkResult>>(
    `/api/v1/admin/benchmark${query}`,
    { method: 'POST' },
  );
}
import { getApiUrl } from '@/utils/runtime';
