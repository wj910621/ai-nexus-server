/**
 * 模型管理 API 客户端
 *
 * Task 26: 与后端 /api/v1/models/* 端点交互。
 * 桌面环境下通过 window.electronAPI 代理；浏览器环境直接 fetch。
 */

export type HardwareProfile = 'low' | 'mid' | 'high' | 'cpu';
export type DeviceType = 'gpu' | 'cpu' | 'none';
export type ModelType = 'image' | 'llm' | 'tts' | 'character';

export interface LocalModel {
  name: string;
  model_type: ModelType;
  repo_id: string;
  local_path?: string;
  size_mb: number;
  is_downloaded: boolean;
  is_active: boolean;
  hardware_profile?: HardwareProfile;
  user_id?: number;
  md5?: string;
  download_url?: string;
  original_size_mb?: number;
}

export interface RuntimeInfo {
  device_type: DeviceType;
  vram_gb: number;
  ram_gb: number;
  gpu_name: string;
  local_inference_enabled: boolean;
  recommended_providers: {
    image: string | null;
    llm: string | null;
    tts: string | null;
  };
}

export interface ListModelsParams {
  model_type?: ModelType;
}

interface ApiResponse<T> {
  data: T;
}

/**
 * 获取 API 基础 URL
 * - 浏览器：相对路径（依赖 Vite 代理）
 * - Electron 桌面：通过 preload 桥接
 */
/**
 * 通用 fetch 封装：注入 Authorization 头（如可用）
 */
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
 * 按硬件档位获取推荐模型列表
 * GET /api/v1/models/local/{hardware_profile}
 */
export async function fetchLocalModels(
  hardwareProfile: HardwareProfile,
): Promise<ApiResponse<LocalModel[]>> {
  return apiFetch<ApiResponse<LocalModel[]>>(
    `/api/v1/models/local/${hardwareProfile}`,
  );
}

/**
 * 获取本地运行时检测结果
 * GET /api/v1/models/runtime
 */
export async function fetchRuntimeInfo(): Promise<ApiResponse<RuntimeInfo>> {
  return apiFetch<ApiResponse<RuntimeInfo>>('/api/v1/models/runtime');
}

/**
 * 下载指定模型
 * POST /api/v1/models/{name}/download
 */
export async function downloadModel(
  name: string,
  repoId?: string,
): Promise<ApiResponse<LocalModel>> {
  const query = repoId ? `?repo_id=${encodeURIComponent(repoId)}` : '';
  return apiFetch<ApiResponse<LocalModel>>(
    `/api/v1/models/${encodeURIComponent(name)}/download${query}`,
    { method: 'POST' },
  );
}

/**
 * 删除指定模型
 * DELETE /api/v1/models/{name}
 */
export async function deleteModel(
  name: string,
): Promise<ApiResponse<{ deleted: string }>> {
  return apiFetch<ApiResponse<{ deleted: string }>>(
    `/api/v1/models/${encodeURIComponent(name)}`,
    { method: 'DELETE' },
  );
}

/**
 * 列出所有已注册模型（可按类型过滤）
 * GET /api/v1/models?model_type=...
 */
export async function listModels(
  params: ListModelsParams = {},
): Promise<ApiResponse<LocalModel[]>> {
  const query = params.model_type
    ? `?model_type=${encodeURIComponent(params.model_type)}`
    : '';
  return apiFetch<ApiResponse<LocalModel[]>>(`/api/v1/models${query}`);
}
import { getApiUrl } from '@/utils/runtime';
