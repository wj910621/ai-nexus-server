/**
 * models.ts API 客户端测试
 *
 * Task 26: 验证 /api/v1/models/local/{hardware_profile} 与 /api/v1/models/runtime 调用。
 * 使用 msw 拦截 fetch 请求，避免真实网络调用。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach, afterEach } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import {
  fetchLocalModels,
  fetchRuntimeInfo,
  downloadModel,
  deleteModel,
  listModels,
} from '../../src/api/models';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterAll(() => server.close());
afterEach(() => server.resetHandlers());

describe('models API client', () => {
  beforeEach(() => {
    server.resetHandlers();
  });

  it('fetchLocalModels returns models filtered by hardware_profile', async () => {
    server.use(
      http.get('/api/v1/models/local/high', () =>
        HttpResponse.json({
          data: [
            {
              name: 'Qwen2.5-14B-Instruct',
              model_type: 'llm',
              hardware_profile: 'high',
              size_mb: 9000,
              is_downloaded: false,
            },
            {
              name: 'FLUX.1-dev',
              model_type: 'image',
              hardware_profile: 'high',
              size_mb: 23000,
              is_downloaded: false,
            },
          ],
        }),
      ),
    );
    const result = await fetchLocalModels('high');
    expect(result.data).toHaveLength(2);
    expect(result.data[0].name).toBe('Qwen2.5-14B-Instruct');
    expect(result.data[1].hardware_profile).toBe('high');
  });

  it('fetchRuntimeInfo returns GPU/CPU detection result', async () => {
    server.use(
      http.get('/api/v1/models/runtime', () =>
        HttpResponse.json({
          data: {
            device_type: 'gpu',
            vram_gb: 12.0,
            ram_gb: 32.0,
            gpu_name: 'NVIDIA RTX 3060',
            local_inference_enabled: true,
            recommended_providers: {
              image: 'diffusers',
              llm: 'llama_cpp',
              tts: 'piper',
            },
          },
        }),
      ),
    );
    const result = await fetchRuntimeInfo();
    expect(result.data.device_type).toBe('gpu');
    expect(result.data.gpu_name).toBe('NVIDIA RTX 3060');
    expect(result.data.recommended_providers.image).toBe('diffusers');
  });

  it('downloadModel POSTs to /models/{name}/download', async () => {
    let capturedUrl = '';
    server.use(
      http.post('/api/v1/models/test-model/download', async ({ request }) => {
        capturedUrl = request.url;
        return HttpResponse.json({
          data: { name: 'test-model', is_downloaded: true },
        });
      }),
    );
    const result = await downloadModel('test-model');
    expect(capturedUrl).toContain('/api/v1/models/test-model/download');
    expect(result.data.is_downloaded).toBe(true);
  });

  it('deleteModel DELETEs /models/{name}', async () => {
    let method = '';
    server.use(
      http.delete('/api/v1/models/old-model', async ({ request }) => {
        method = request.method;
        return HttpResponse.json({ data: { deleted: 'old-model' } });
      }),
    );
    const result = await deleteModel('old-model');
    expect(method).toBe('DELETE');
    expect(result.data.deleted).toBe('old-model');
  });

  it('listModels returns all models with optional type filter', async () => {
    server.use(
      http.get('/api/v1/models', ({ request }) => {
        const url = new URL(request.url);
        const modelType = url.searchParams.get('model_type');
        expect(modelType).toBe('llm');
        return HttpResponse.json({
          data: [
            { name: 'deepseek', model_type: 'llm' },
            { name: 'qwen-local', model_type: 'llm' },
          ],
        });
      }),
    );
    const result = await listModels({ model_type: 'llm' });
    expect(result.data).toHaveLength(2);
  });
});
