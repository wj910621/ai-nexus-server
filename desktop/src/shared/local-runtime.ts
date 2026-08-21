// Local runtime detection shared between main and renderer processes.
// Mirrors backend `app/core/local_runtime.py` LocalRuntimeDetector output.

export type ProviderKind = 'local-gpu' | 'local-cpu' | 'remote'

export interface RuntimeInfo {
  hasGpu: boolean
  gpuName: string
  vramMB: number
  ramMB: number
  recommendedProvider: ProviderKind
  platform: NodeJS.Platform
}

/**
 * Detects local AI runtime capabilities by calling the backend
 * `/api/v1/models/runtime` endpoint. Falls back to a conservative
 * `remote` recommendation if the backend is unavailable.
 *
 * This module is safe to import from both the main process and the
 * renderer (via preload bridge). It performs no native module access.
 */
export class LocalRuntimeDetector {
  /**
   * Query the backend for runtime info. Returns a `RuntimeInfo` object.
   *
   * @param backendUrl Optional backend base URL. Defaults to BACKEND_URL constant
   *                   imported lazily to avoid circular deps in renderer.
   */
  static async detect(backendUrl?: string): Promise<RuntimeInfo> {
    const base = backendUrl || LocalRuntimeDetector.getDefaultBackendUrl()
    try {
      const resp = await fetch(`${base}/api/v1/models/runtime`, {
        method: 'GET',
        headers: { Accept: 'application/json' },
      })
      if (!resp.ok) {
        return LocalRuntimeDetector.fallback()
      }
      const data = (await resp.json()) as {
        has_gpu?: boolean
        gpu_name?: string
        vram_mb?: number
        ram_mb?: number
        recommended_provider?: string
      }
      const recommended = LocalRuntimeDetector.normalizeProvider(
        data.recommended_provider,
      )
      return {
        hasGpu: Boolean(data.has_gpu),
        gpuName: data.gpu_name || '',
        vramMB: data.vram_mb || 0,
        ramMB: data.ram_mb || 0,
        recommendedProvider: recommended,
        platform: process.platform as NodeJS.Platform,
      }
    } catch {
      return LocalRuntimeDetector.fallback()
    }
  }

  private static getDefaultBackendUrl(): string {
    // Lazy require to keep this module renderer-safe.
    // In main process, constants.ts is available; in renderer, fall back to env.
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const { BACKEND_URL } = require('../main/constants')
      return BACKEND_URL as string
    } catch {
      return (
        process.env.VITE_API_BASE_URL || 'http://localhost:8000'
      )
    }
  }

  private static normalizeProvider(value?: string): ProviderKind {
    if (value === 'local-gpu') return 'local-gpu'
    if (value === 'local-cpu') return 'local-cpu'
    return 'remote'
  }

  private static fallback(): RuntimeInfo {
    return {
      hasGpu: false,
      gpuName: '',
      vramMB: 0,
      ramMB: 0,
      recommendedProvider: 'remote',
      platform: process.platform as NodeJS.Platform,
    }
  }
}
