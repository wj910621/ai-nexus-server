/**
 * Provider 选择器组件
 *
 * Task 26: 在首启向导与设置页中让用户选择偏好的 AI Provider。
 * 按引擎类型（image/video/llm/tts）分组展示，根据用户订阅层级过滤可选项。
 *
 * 商业化瘦身（2026-09-02）：选项与后端注册表/路由表严格对齐。
 * - 下线：video 全部 4 引擎（seedance/kling/wan/hunyuan）、image/kolors、
 *   llm/glm、llm/doubao、tts/volcano。
 * - 对齐命名：edge_tts（原 edge）、qwen_local（原 qwen-local）、新增 jarvis-gateway、
 *   pollinations、cosyvoice、llama_cpp。
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

/**
 * 保留的 Provider 清单（与 backend/app/engines/__init__.py 注册表一致）
 * - image: pollinations / seedream / flux(本地)
 * - llm:   deepseek / jarvis-gateway / qwen_local(本地) / llama_cpp(本地)
 * - tts:   edge_tts / cosyvoice(本地)
 * - video: 全部下线
 */
const DEFAULT_PROVIDER_OPTIONS: Record<EngineType, ProviderOption[]> = {
  image: [
    { name: 'pollinations', is_local: false, subscription_required: 'free', display_name: 'Pollinations' },
    { name: 'seedream', is_local: false, subscription_required: 'pro', display_name: '即梦 Seedream' },
    { name: 'flux', is_local: true, subscription_required: 'pro', display_name: 'FLUX.1-dev (本地)' },
  ],
  video: [], // 商业化瘦身：video 引擎全部下线
  llm: [
    { name: 'deepseek', is_local: false, subscription_required: 'free', display_name: 'DeepSeek API' },
    { name: 'jarvis-gateway', is_local: false, subscription_required: 'pro', display_name: 'Jarvis 网关' },
    { name: 'qwen_local', is_local: true, subscription_required: 'pro', display_name: 'Qwen2.5 (本地)' },
    { name: 'llama_cpp', is_local: true, subscription_required: 'pro', display_name: 'llama.cpp (本地)' },
  ],
  tts: [
    { name: 'edge_tts', is_local: false, subscription_required: 'free', display_name: 'edge-tts' },
    { name: 'cosyvoice', is_local: true, subscription_required: 'pro', display_name: 'CosyVoice (本地)' },
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
    image: initialPreference.image || 'pollinations',
    video: initialPreference.video || '',
    llm: initialPreference.llm || 'deepseek',
    tts: initialPreference.tts || 'edge_tts',
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
      {(['image', 'video', 'llm', 'tts'] as EngineType[]).map((engine) => {
        const options = filterByTier(DEFAULT_PROVIDER_OPTIONS[engine]);
        // video 全部下线或当前层级无可用选项时隐藏该分组
        if (options.length === 0) return null;
        // 当前偏好被层级过滤掉时回退到第一个可用项（避免 select 空值）
        const value = options.some((o) => o.name === preference[engine])
          ? preference[engine]
          : options[0].name;
        return (
          <div key={engine} className="provider-row">
            <label className="provider-label">{engine.toUpperCase()}</label>
            <select
              value={value}
              onChange={(e) => handleChange(engine, e.target.value)}
              className="provider-select"
            >
              {options.map((opt) => (
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
        );
      })}
    </div>
  );
}

export default ProviderSelector;
