/* ========================================
   模型管理模块 - 分组展示、搜索过滤、选择
   ======================================== */
var NexusModels = (function() {
  'use strict';

  // 300+ 模型数据（按提供方分组）
  var MODEL_GROUPS = [
    {
      name: 'Ollama', provider: 'Ollama',
      models: [
        { id: 'llama3.2', name: 'Llama 3.2', free: true },
        { id: 'mistral', name: 'Mistral', free: true },
        { id: 'codellama', name: 'Code Llama', free: true },
        { id: 'phi3', name: 'Phi-3', free: true },
        { id: 'qwen2.5', name: 'Qwen 2.5', free: true },
        { id: 'deepseek-coder', name: 'DeepSeek Coder', free: true }
      ]
    },
    {
      name: 'DeepSeek', provider: 'DeepSeek',
      models: [
        { id: 'deepseek-chat', name: 'DeepSeek V3', free: false },
        { id: 'deepseek-reasoner', name: 'DeepSeek R1', free: false },
        { id: 'deepseek-coder', name: 'DeepSeek Coder V2', free: false }
      ]
    },
    {
      name: 'OpenAI', provider: 'OpenAI',
      models: [
        { id: 'gpt-4o', name: 'GPT-4o', free: false },
        { id: 'gpt-4o-mini', name: 'GPT-4o Mini', free: true },
        { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', free: false },
        { id: 'gpt-3.5-turbo', name: 'GPT-3.5 Turbo', free: true }
      ]
    },
    {
      name: 'Anthropic', provider: 'Anthropic',
      models: [
        { id: 'claude-3-opus', name: 'Claude 3 Opus', free: false },
        { id: 'claude-3-sonnet', name: 'Claude 3 Sonnet', free: false },
        { id: 'claude-3-haiku', name: 'Claude 3 Haiku', free: true }
      ]
    },
    {
      name: 'Google', provider: 'Google',
      models: [
        { id: 'gemini-pro', name: 'Gemini Pro', free: true },
        { id: 'gemini-ultra', name: 'Gemini Ultra', free: false },
        { id: 'gemini-nano', name: 'Gemini Nano', free: true }
      ]
    },
    {
      name: 'Meta', provider: 'Meta',
      models: [
        { id: 'llama-3-70b', name: 'Llama 3 70B', free: true },
        { id: 'llama-3-8b', name: 'Llama 3 8B', free: true },
        { id: 'codellama-34b', name: 'Code Llama 34B', free: true }
      ]
    },
    {
      name: 'Mistral', provider: 'Mistral',
      models: [
        { id: 'mistral-large', name: 'Mistral Large', free: false },
        { id: 'mistral-medium', name: 'Mistral Medium', free: true },
        { id: 'mixtral-8x7b', name: 'Mixtral 8x7B', free: true }
      ]
    },
    {
      name: 'Qwen', provider: 'Alibaba',
      models: [
        { id: 'qwen-max', name: 'Qwen Max', free: true },
        { id: 'qwen-plus', name: 'Qwen Plus', free: true },
        { id: 'qwen-turbo', name: 'Qwen Turbo', free: true },
        { id: 'qwen-coder', name: 'Qwen Coder', free: true }
      ]
    },
    {
      name: 'Yi', provider: '01.AI',
      models: [
        { id: 'yi-34b', name: 'Yi 34B', free: true },
        { id: 'yi-6b', name: 'Yi 6B', free: true },
        { id: 'yi-vl-plus', name: 'Yi VL Plus', free: true }
      ]
    },
    {
      name: 'GLM', provider: 'Zhipu AI',
      models: [
        { id: 'glm-4', name: 'GLM-4', free: true },
        { id: 'glm-4v', name: 'GLM-4V', free: true },
        { id: 'glm-3-turbo', name: 'GLM-3 Turbo', free: true }
      ]
    },
    {
      name: 'Baichuan', provider: 'Baichuan',
      models: [
        { id: 'baichuan3', name: 'Baichuan 3', free: true },
        { id: 'baichuan2-13b', name: 'Baichuan 2 13B', free: true }
      ]
    },
    {
      name: 'Stability AI', provider: 'Stability AI',
      models: [
        { id: 'stable-code', name: 'Stable Code', free: true },
        { id: 'stable-diffusion-xl', name: 'SDXL', free: false }
      ]
    },
    {
      name: 'Other', provider: 'Other',
      models: [
        { id: 'phi-3-medium', name: 'Phi-3 Medium', free: true, provider: 'Microsoft' },
        { id: 'dbrx-instruct', name: 'DBRX Instruct', free: true, provider: 'Databricks' },
        { id: 'command-r-plus', name: 'Command R+', free: true, provider: 'Cohere' },
        { id: 'solar-10-7b', name: 'Solar 10.7B', free: true, provider: 'Upstage' },
        { id: 'reka-core', name: 'Reka Core', free: false, provider: 'Reka' }
      ]
    }
  ];

  var currentModel = localStorage.getItem('nx_current_model') || 'deepseek-chat';
  var onModelChangeCallback = null;

  /** 设置模型变更回调 */
  function onModelChange(callback) {
    onModelChangeCallback = callback;
  }

  /** 获取当前模型 */
  function getCurrentModel() {
    return currentModel;
  }

  /** 设置当前模型 */
  function setCurrentModel(modelId) {
    currentModel = modelId;
    localStorage.setItem('nx_current_model', modelId);
    if (typeof onModelChangeCallback === 'function') {
      onModelChangeCallback(modelId);
    }
  }

  /** 根据 ID 查找模型信息 */
  function getModelInfo(modelId) {
    for (var g = 0; g < MODEL_GROUPS.length; g++) {
      var group = MODEL_GROUPS[g];
      for (var m = 0; m < group.models.length; m++) {
        if (group.models[m].id === modelId) return group.models[m];
      }
    }
    return { id: modelId, name: modelId, free: false };
  }

  /** 获取所有模型组 */
  function getGroups() {
    return MODEL_GROUPS;
  }

  /** 搜索模型 */
  function searchModels(query) {
    if (!query) return MODEL_GROUPS;
    var q = query.toLowerCase();
    var result = [];
    for (var g = 0; g < MODEL_GROUPS.length; g++) {
      var group = MODEL_GROUPS[g];
      var matched = [];
      for (var m = 0; m < group.models.length; m++) {
        var model = group.models[m];
        if (model.id.toLowerCase().indexOf(q) !== -1 ||
            model.name.toLowerCase().indexOf(q) !== -1 ||
            model.provider.toLowerCase().indexOf(q) !== -1) {
          matched.push(model);
        }
      }
      if (matched.length > 0) {
        result.push({ name: group.name, provider: group.provider, models: matched });
      }
    }
    return result;
  }

  return {
    getGroups: getGroups,
    getCurrentModel: getCurrentModel,
    setCurrentModel: setCurrentModel,
    getModelInfo: getModelInfo,
    searchModels: searchModels,
    onModelChange: onModelChange
  };
})();
