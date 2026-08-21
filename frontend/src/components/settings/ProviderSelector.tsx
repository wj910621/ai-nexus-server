/**
 * Provider 选择器组件
 *
 * Task 26: 在首启向导与设置页中让用户选择偏好的 AI Provider。
 * 按引擎类型（image/video/llm/tts）分组展示，根据用户订阅层级过滤可选项。
 */
import { useEffect, useState } from 'react';
import {
  fetchLocalModels,
  fetchRuntimeInfo,
  HardwareProfile,
  LocalModel,
  RuntimeInfo,
} from '../../api/models';

export type EngineType = 'image' | 'video' | 'llm' | 'tts';

export interface ProviderPreference {
  image: string;
  video: string;
  llm: string;
  tts: string;
}

interface ProviderOption {
  name: string;
  is_local: boolean;
  subscription_required: 'free' | 'pro' | 'enterprise';
  display_name?: string;
}

const DEFAULT_PROVIDER_OPTIONS: Record<EngineType, ProviderOption[]> = {
  image: [
    { name: 'seedream', is_local: false, subscription_required: 'pro', display_name: '即梦 Seedream' },
    { name: 'flux', is_local: true, subscription_required: 'pro', display_name: 'FLUX.1-dev (本地)' },
    { name: 'kolors', is_local: false, subscription_required: 'pro', display_name: '可图 Kolors' },
    { name: 'sdxl-cpu', is_local: true, subscription_required: 'free', display_name: 'SDXL (CPU)' },
  ],
  video: [
    { name: 'seedance', is_local: false, subscription_required: 'pro', display_name: '即梦 Seedance' },
    { name: 'kling', is_local: false, subscription_required: 'pro', display_name: '可灵 Kling' },
    { name: 'wan', is_local: true, subscription_required: 'pro', display_name: 'Wan2.1 (本地)' },
    { name: 'hunyuan', is_local: true, subscription_required: 'pro', display_name: '混元 Video (本地)' },
  ],
  llm: [
    { name: 'qwen-local', is_local: true, subscription_required: 'pro', display_name: 'Qwen2.5 (本地)' },
    { name: 'deepseek', is_local: false, subscription_required: 'free', display_name: 'DeepSeek API' },
    { name: 'glm', is_local: false, subscription_required: 'pro', display_name: '智谱 GLM-4' },
    { name: 'doubao', is_local: false, subscription_required: 'pro', display_name: '火山豆包' },
  ],
  tts: [
    { name: 'volcano', is_local: false, subscription_required: 'pro', display_name: '火山语音' },
    { name: 'cosyvoice', is_local: true, subscription_required: 'pro', display_name: 'CosyVoice (本地)' },
    { name: 'edge', is_local: false, subscription_required: 'free', display_name: 'edge-tts' },
  ],
};

interface ProviderSelectorProps {
  subscriptionTier: 'free' | 'pro' | 'enterprise';
  initialPreference?: Partial<ProviderPreference>;
  onChange?: (pref: ProviderPreference) => void;
  hardwareProfile?: HardwareProfile;
}

const TIER_RANK: Record<string, number> = { free: 0, pro: 1, enterprise: 2 };

export function ProviderSelector({
  subscriptionTier,
  initialPreference = {},
  onChange,
  hardwareProfile = 'cpu',
}: ProviderSelectorProps) {
  const [preference, setPreference] = useState<ProviderPreference>({
    image: initialPreference.image || 'seedream',
    video: initialPreference.video || 'seedance',
    llm: initialPreference.llm || 'deepseek',
    tts: initialPreference.tts || 'edge',
  });
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);
  const [localModels, setLocalModels] = useState<LocalModel[]>([]);

  useEffect(() => {
    fetchRuntimeInfo()
      .then((r) => setRuntime(r.data))
      .catch(() => {
        /* 静默失败：未登录或桌面模式下后端不可用 */
      });
  }, []);

  useEffect(() => {
    fetchLocalModels(hardwareProfile)
      .then((r) => setLocalModels(r.data))
      .catch(() => {
        /* 静默失败 */
      });
  }, [hardwareProfile]);

  function handleChange(engine: EngineType, provider: string) {
    const next = { ...preference, [engine]: provider };
    setPreference(next);
    onChange?.(next);
  }

  function filterByTier(options: ProviderOption[]): ProviderOption[] {
    const userRank = TIER_RANK[subscriptionTier] ?? 0;
    return options.filter(
      (o) => (TIER_RANK[o.subscription_required] ?? 0) <= userRank,
    );
  }

  const localModelNames = new Set(localModels.map((m) => m.name));

  return (
    <div className="provider-selector">
      {runtime && (
        <div className="runtime-banner">
          检测到 {runtime.gpu_name || runtime.device_type}（VRAM:{' '}
          {runtime.vram_gb.toFixed(1)} GB / RAM: {runtime.ram_gb.toFixed(1)} GB）
        </div>
      )}
      {(['image', 'video', 'llm', 'tts'] as EngineType[]).map((engine) => (
        <div key={engine} className="provider-row">
          <label className="provider-label">{engine.toUpperCase()}</label>
          <select
            value={preference[engine]}
            onChange={(e) => handleChange(engine, e.target.value)}
            className="provider-select"
          >
            {filterByTier(DEFAULT_PROVIDER_OPTIONS[engine]).map((opt) => (
              <option
                key={opt.name}
                value={opt.name}
                disabled={opt.is_local && !localModelNames.has(opt.name)}
              >
                {opt.display_name || opt.name}
                {opt.is_local && !localModelNames.has(opt.name)
                  ? ' (未下载)'
                  : ''}
              </option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}

export default ProviderSelector;
