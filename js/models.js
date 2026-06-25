'use strict';
// === Models ===
const models=[
  {id:'gpt4o',name:'GPT-4o',provider:'OpenAI',desc:'最新旗舰多模态模型，文本/图像/音频全通。',avatar:'#10a37f',tags:['多模态','推理','编程','海外'],context:'128K',inputPrice:'$2.5/M',outputPrice:'$10/M',featured:true,free:false,backup:'or_gpt4o'},
  {id:'claude4',name:'Claude 4 Sonnet',provider:'Anthropic',desc:'Claude最新旗舰，编程和深度推理业界顶尖。',avatar:'#d97706',tags:['推理','编程','长文本','海外'],context:'200K',inputPrice:'$3/M',outputPrice:'$15/M',featured:true,free:false,backup:'nx_claude_sonnet'},
  {id:'gemini25pro',name:'Gemini 2.5 Pro',provider:'Google',desc:'Google最新旗舰，原生多模态。',avatar:'#4285f4',tags:['多模态','长文本','推理','海外'],context:'2M',inputPrice:'$1.25/M',outputPrice:'$5/M',featured:true,free:false,backup:'nx_gemini_pro'},
  {id:'deepseekv3',name:'DeepSeek-V3 (0324)',provider:'DeepSeek',desc:'国产最强大模型，671B MoE。',avatar:'#4f46e5',tags:['开源','推理','编程','写作','国内'],context:'128K',inputPrice:'¥1/M',outputPrice:'¥4/M',featured:true,free:false,backup:'ali_deepseek_v4_pro'},
  {id:'deepseekr1',name:'DeepSeek-R1',provider:'DeepSeek',desc:'深度推理专家，思维链超强。',avatar:'#4f46e5',tags:['推理','数学','开源','国内'],context:'128K',inputPrice:'¥4/M',outputPrice:'¥16/M',featured:true,free:false,backup:'sf_qwq_32b'},
  {id:'qwen3',name:'通义千问 3.0',provider:'阿里云',desc:'阿里最新旗舰，中文能力顶尖。',avatar:'#ff6a00',tags:['多模态','中文优化','国内'],context:'256K',inputPrice:'¥2/M',outputPrice:'¥8/M',featured:true,free:false,backup:'ali_qwen37_max'},
  {id:'kimi2',name:'Kimi K2',provider:'月之暗面',desc:'超长上下文200万字。',avatar:'#6c5ce7',tags:['长文本','中文优化','国内'],context:'2M',inputPrice:'¥12/M',outputPrice:'¥12/M',featured:true,free:false,backup:'ali_kimi_k26'},
  {id:'gpt4omini',name:'GPT-4o Mini',provider:'OpenAI',desc:'轻量高效版，性价比极高。',avatar:'#10a37f',tags:['快速','编程','海外'],context:'128K',inputPrice:'$0.15/M',outputPrice:'$0.6/M',featured:false,free:false,backup:'nx_gpt5mini'},
  {id:'glm4plus',name:'GLM-4 Plus',provider:'智谱AI',desc:'All-Tools智能体，中英双强。',avatar:'#3859ff',tags:['智能体','中文优化','国内'],context:'128K',inputPrice:'¥0.5/M',outputPrice:'¥0.5/M',featured:false,free:false,backup:'sf_glm5'},
  {id:'hunyuan',name:'混元 TurboS',provider:'腾讯',desc:'腾讯最快大模型。',avatar:'#00a4ff',tags:['多模态','中文优化','国内'],context:'256K',inputPrice:'¥1/M',outputPrice:'¥2/M',featured:false,free:false,backup:'sf_hunyuan_a13b'},
  {id:'llama4',name:'Llama 4 Scout',provider:'Meta',desc:'最新开源，109B参数。',avatar:'#0668e1',tags:['开源','通用','海外','免费'],context:'10M',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  // 硅基流动免费模型
  {id:'sf_qwen3_8b',name:'Qwen3-8B',provider:'通义千问',desc:'8B轻量级，快速响应。',avatar:'#ff6a00',tags:['中文优化','轻量','国内'],context:'32K',inputPrice:'¥0.5/M',outputPrice:'¥2/M',featured:false,free:false},
  {id:'sf_deepseek_v3_free',name:'DeepSeek-V3',provider:'DeepSeek',desc:'昇腾部署版，高性价比。',avatar:'#4f46e5',tags:['推理','编程','国内'],context:'128K',inputPrice:'¥1/M',outputPrice:'¥4/M',featured:true,free:false},
  {id:'mistral-large2',name:'Mistral Large 2',provider:'Mistral AI',desc:'欧洲最强开源。',avatar:'#ff6b35',tags:['开源','多语言','推理','海外'],context:'256K',inputPrice:'$2/M',outputPrice:'$6/M',featured:false,free:false},
  {id:'grok3',name:'Grok-3',provider:'xAI',desc:'马斯克xAI实时推理。',avatar:'#1d9bf0',tags:['推理','实时信息','海外'],context:'256K',inputPrice:'$2/M',outputPrice:'$8/M',featured:false,free:false},
  {id:'spark4',name:'讯飞星火 4.0',provider:'科大讯飞',desc:'语音识别领先。',avatar:'#2563eb',tags:['语音','多模态','国内'],context:'128K',inputPrice:'¥30/M',outputPrice:'¥30/M',featured:false,free:false},
  {id:'sf_glm5',name:'GLM-5',provider:'智谱',desc:'智谱最新旗舰，多模态全能。',avatar:'#3859ff',tags:['多模态','推理','国内'],context:'128K',inputPrice:'¥6/M',outputPrice:'¥28/M',featured:false,free:false},
  {id:'sf_qwen35_397b',name:'Qwen3.5-397B',provider:'通义千问',desc:'397B MoE巨无霸，推理能力极强。',avatar:'#ff6a00',tags:['推理','编程','国内'],context:'128K',inputPrice:'¥2/M',outputPrice:'¥8/M',featured:false,free:false},
  {id:'sf_qwq_32b',name:'QwQ-32B',provider:'通义千问',desc:'千问推理专家，思维链超强。',avatar:'#e17055',tags:['推理','数学','开源','国内'],context:'128K',inputPrice:'¥2/M',outputPrice:'¥6/M',featured:true,free:false},
  {id:'sf_hunyuan_a13b',name:'混元A13B',provider:'腾讯',desc:'腾讯混元开源版，支持thinking。',avatar:'#00a4ff',tags:['开源','推理','国内'],context:'128K',inputPrice:'¥0.5/M',outputPrice:'¥0.5/M',featured:false,free:false},
  // === 阿里云百炼 ===
  {id:'ali_qwen37_max',name:'Qwen3.7 Max',provider:'阿里云',desc:'阿里最新旗舰，中文能力登顶。',avatar:'#ff6a00',tags:['多模态','中文优化','国内'],context:'256K',inputPrice:'¥20/M',outputPrice:'¥80/M',featured:true,free:false},
  {id:'ali_qwen36_plus',name:'Qwen3.6 Plus',provider:'阿里云',desc:'均衡性能，性价比之选。',avatar:'#ff6a00',tags:['中文优化','编程','国内'],context:'256K',inputPrice:'¥4/M',outputPrice:'¥12/M',featured:false,free:false},
  {id:'ali_qwen36_flash',name:'Qwen3.6 Flash',provider:'阿里云',desc:'极速轻量版，秒级响应。',avatar:'#ff6a00',tags:['快速','中文优化','国内'],context:'128K',inputPrice:'¥0.5/M',outputPrice:'¥2/M',featured:false,free:false},
  {id:'ali_glm51',name:'GLM-5.1',provider:'阿里云',desc:'智谱最新，百炼平台直连。',avatar:'#3859ff',tags:['推理','智能体','国内'],context:'128K',inputPrice:'¥6/M',outputPrice:'¥28/M',featured:false,free:false},
  {id:'ali_kimi_k26',name:'Kimi-K2.6',provider:'阿里云',desc:'月之暗面最新，超长上下文。',avatar:'#6c5ce7',tags:['长文本','中文优化','国内'],context:'2M',inputPrice:'¥12/M',outputPrice:'¥12/M',featured:false,free:false},
  // === DMXAPI ===
  {id:'dmx_minimax_m27_free',name:'MiniMax-M2.7',provider:'MiniMax',desc:'万亿MoE多模态免费版。',avatar:'#fd79a8',tags:['多模态','对话','国内'],context:'256K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'dmx_minimax_m25_free',name:'MiniMax-M2.5',provider:'MiniMax',desc:'MiniMax轻量版免费使用。',avatar:'#fdcb6e',tags:['对话','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'dmx_glm_47_free',name:'GLM-4.7',provider:'智谱',desc:'智谱GLM-4.7免费版。',avatar:'#6c5ce7',tags:['对话','中文优化','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_glm_47_flash',name:'GLM-4.7 Flash',provider:'智谱',desc:'智谱GLM-4.7闪速版。',avatar:'#a29bfe',tags:['对话','快速','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_glm_5_free',name:'GLM-5',provider:'智谱',desc:'智谱GLM-5免费版。',avatar:'#6c5ce7',tags:['推理','中文优化','国内'],context:'256K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_glm_51_free',name:'GLM-5.1',provider:'智谱',desc:'智谱GLM-5.1免费版。',avatar:'#6c5ce7',tags:['推理','中文优化','国内'],context:'256K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_glm_5_turbo_free',name:'GLM-5 Turbo',provider:'智谱',desc:'智谱GLM-5涡轮加速版。',avatar:'#8b5cf6',tags:['推理','快速','国内'],context:'256K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_glm_45_flash',name:'GLM-4.5 Flash',provider:'智谱',desc:'智谱GLM-4.5闪速版。',avatar:'#a29bfe',tags:['对话','快速','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_glm_4_9b',name:'GLM-4 9B',provider:'智谱',desc:'智谱GLM-4 9B开源版。',avatar:'#7c3aed',tags:['对话','轻量','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_hunyuan_lite',name:'混元 Lite',provider:'腾讯',desc:'腾讯混元轻量免费版。',avatar:'#00b894',tags:['对话','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_qwen3_8b_free',name:'Qwen3-8B',provider:'通义千问',desc:'通义千问3-8B免费版。',avatar:'#0984e3',tags:['推理','中文优化','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'dmx_qwen_flash_free',name:'Qwen Flash',provider:'通义千问',desc:'通义千问闪速免费版。',avatar:'#74b9ff',tags:['对话','快速','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_qwen3_5_plus_free',name:'Qwen3-5 Plus',provider:'通义千问',desc:'通义千问3-5增强免费版。',avatar:'#0984e3',tags:['推理','中文优化','国内'],context:'256K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_qwen35_plus_free',name:'Qwen3.5 Plus',provider:'通义千问',desc:'通义千问3.5增强免费版。',avatar:'#0984e3',tags:['推理','中文优化','国内'],context:'256K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_qwen3_coder_plus_free',name:'Qwen3-Coder Plus',provider:'通义千问',desc:'通义千问编程增强免费版。',avatar:'#00cec9',tags:['编程','代码','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_qwen3_coder_next_free',name:'Qwen3-Coder Next',provider:'通义千问',desc:'通义千问下一代编程免费版。',avatar:'#00cec9',tags:['编程','代码','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_qwen35_2b_free',name:'Qwen3.5-2B',provider:'通义千问',desc:'通义千问3.5轻量版，快速入门。',avatar:'#74b9ff',tags:['对话','轻量','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:true,free:true},
  {id:'dmx_qwen35_35b_free',name:'Qwen3.5-35B',provider:'通义千问',desc:'通义千问3.5-35B免费版。',avatar:'#0984e3',tags:['推理','中文优化','国内'],context:'256K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_qwen3_17b_free',name:'Qwen3-1.7B',provider:'通义千问',desc:'通义千问迷你版，入门首选。',avatar:'#74b9ff',tags:['对话','轻量','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:true},
  {id:'dmx_qwen3_max_free',name:'Qwen3-Max',provider:'通义千问',desc:'通义千问3旗舰免费版。',avatar:'#0652DD',tags:['推理','中文优化','国内'],context:'256K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'dmx_qwen25_coder_7b',name:'Qwen2.5-Coder-7B',provider:'通义千问',desc:'通义千问编程7B开源版。',avatar:'#00cec9',tags:['编程','代码','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_kimi_k25_free',name:'Kimi-K2.5',provider:'Kimi',desc:'月之暗面K2.5免费版。',avatar:'#6c5ce7',tags:['长文本','中文优化','国内'],context:'2M',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'dmx_kimi_k26_free',name:'Kimi-K2.6',provider:'Kimi',desc:'月之暗面K2.6免费版。',avatar:'#a29bfe',tags:['长文本','中文优化','国内'],context:'2M',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_mimo_v2_pro_free',name:'MIMO-V2 Pro',provider:'MIMO',desc:'MIMO创意模型免费版。',avatar:'#d63031',tags:['创意','对话','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_mimo_v25_free',name:'MIMO-V2.5',provider:'MIMO',desc:'MIMO最新创意免费版。',avatar:'#e17055',tags:['创意','对话','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_code_free',name:'编程模型',provider:'合作伙伴',desc:'通用编程免费版。',avatar:'#00cec9',tags:['编程','代码','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_codex_free',name:'编程模型 Plus',provider:'合作伙伴',desc:'增强编程免费版。',avatar:'#00cec9',tags:['编程','代码','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_kat_coder_free',name:'KAT-Coder V2',provider:'KAT',desc:'KAT编程模型免费版。',avatar:'#636e72',tags:['编程','代码','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'dmx_qwen36_plus_free',name:'Qwen3.6 Plus',provider:'通义千问',desc:'通义千问3.6增强免费版。',avatar:'#0984e3',tags:['推理','中文优化','国内'],context:'256K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'dmx_code_free_x',name:'编程模型 Pro',provider:'合作伙伴',desc:'高级编程加速版。',avatar:'#00cec9',tags:['编程','代码','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  // === 百度千帆 ===
  // 百度千帆 ERNIE 系列已下线（配额不足），使用 DMXAPI/Ark 替代
  // - qf_ernie4, qf_ernie35, qf_ernie_speed (已移除)
  // === 火山引擎 Ark（全免费接入） ===
  {id:'ark_dsv4p',name:'DeepSeek-V4 Pro',provider:'DeepSeek',desc:'DeepSeek最新旗舰，火山直连免费。',avatar:'#4f46e5',tags:['推理','编程','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'ark_dsv4f',name:'DeepSeek-V4 Flash',provider:'DeepSeek',desc:'轻量极速版，火山直连免费。',avatar:'#4f46e5',tags:['快速','编程','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'ark_dsv32',name:'DeepSeek-V3.2',provider:'DeepSeek',desc:'671B MoE，火山直连免费。',avatar:'#4f46e5',tags:['开源','推理','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'ark_dbs2_pro',name:'豆包Seed 2.0 Pro',provider:'字节跳动',desc:'字节旗舰，火山直连免费。',avatar:'#e17055',tags:['多模态','中文优化','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'ark_dbs2_lite',name:'豆包Seed 2.0 Lite',provider:'字节跳动',desc:'轻量版，火山直连免费。',avatar:'#fab1a0',tags:['快速','中文优化','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'ark_dbs2_mini',name:'豆包Seed 2.0 Mini',provider:'字节跳动',desc:'迷你版，极速免费。',avatar:'#dfe6e9',tags:['快速','轻量','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'ark_dbs_code',name:'豆包Seed Code',provider:'字节跳动',desc:'编程专用，火山直连免费。',avatar:'#00cec9',tags:['编程','代码','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'ark_dbs1_8',name:'豆包Seed 1.8',provider:'字节跳动',desc:'豆包1.8版，火山直连免费。',avatar:'#e8426e',tags:['中文优化','对话','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'ark_dbs1_6',name:'豆包Seed 1.6',provider:'字节跳动',desc:'豆包1.6版，火山直连免费。',avatar:'#e8426e',tags:['对话','中文优化','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'ark_dbp15p',name:'豆包1.5 Pro',provider:'字节跳动',desc:'豆包1.5旗舰，火山直连免费。',avatar:'#e8426e',tags:['中文优化','内容创作','免费','国内'],context:'32K',inputPrice:'免费',outputPrice:'免费',featured:true,free:false},
  {id:'ark_dbp15l',name:'豆包1.5 Lite',provider:'字节跳动',desc:'豆包1.5轻量，极速免费。',avatar:'#fab1a0',tags:['快速','中文优化','免费','国内'],context:'32K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'ark_glm47',name:'GLM-4.7',provider:'智谱',desc:'智谱GLM-4.7，火山直连免费。',avatar:'#3859ff',tags:['推理','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  {id:'ark_dbs_char',name:'豆包角色扮演',provider:'字节跳动',desc:'角色扮演专用，火山直连免费。',avatar:'#a29bfe',tags:['角色扮演','创意','免费','国内'],context:'128K',inputPrice:'免费',outputPrice:'免费',featured:false,free:false},
  // === 百川智能 ===
  {id:'bc_baichuan4',name:'百川4',provider:'百川智能',desc:'国产大模型，中文能力强劲。',avatar:'#f97316',tags:['中文优化','推理','国内'],context:'32K',inputPrice:'¥4/M',outputPrice:'¥4/M',featured:true,free:false},
  {id:'bc_baichuan3',name:'百川3 Turbo',provider:'百川智能',desc:'高性价比对话模型。',avatar:'#f97316',tags:['中文优化','快速','国内'],context:'32K',inputPrice:'¥1/M',outputPrice:'¥2/M',featured:false,free:false},
  // === 3D 生成 ===
  {id:'meshy_text',name:'Meshy 文本→3D',provider:'Meshy',desc:'AI文本描述转3D模型，高质量PBR材质。',avatar:'#8b5cf6',tags:['3d','文本生成','PBR材质'],context:'N/A',inputPrice:'¥12/次',outputPrice:'¥12/次',featured:true,free:false},
  {id:'meshy_image',name:'Meshy 图片→3D',provider:'Meshy',desc:'上传图片生成3D模型，精准还原。',avatar:'#7c3aed',tags:['3d','图生3D','精准'],context:'N/A',inputPrice:'¥12/次',outputPrice:'¥12/次',featured:false,free:false},
  // === 海外模型 ===
  {id:'or_gpt4o',name:'GPT-4o',provider:'OpenAI',desc:'OpenAI旗舰，多模态全能。',avatar:'#10a37f',tags:['多模态','推理','编程'],context:'128K',inputPrice:'$2.5/M',outputPrice:'$10/M',featured:true,free:false},
  {id:'or_llama3_70b',name:'Llama 3 70B',provider:'Meta',desc:'Meta开源旗舰。',avatar:'#0668e1',tags:['开源','通用'],context:'8K',inputPrice:'$0.23/M',outputPrice:'$0.4/M',featured:false,free:false},
  {id:'or_mistral_large',name:'Mistral Large 2',provider:'Mistral',desc:'欧洲最强开源模型。',avatar:'#ff6b35',tags:['开源','多语言'],context:'256K',inputPrice:'$2/M',outputPrice:'$6/M',featured:false,free:false},
  {id:'or_perplexity',name:'Perplexity Online',provider:'Perplexity',desc:'联网搜索增强，实时信息。',avatar:'#6366f1',tags:['搜索','实时','推理'],context:'128K',inputPrice:'$1/M',outputPrice:'$1/M',featured:false,free:false},
  {id:'or_codeqwen',name:'Qwen 2.5 Coder',provider:'通义千问',desc:'代码生成专家。',avatar:'#06b6d4',tags:['编程','开源'],context:'128K',inputPrice:'$0.18/M',outputPrice:'$0.18/M',featured:false,free:false},
  // === API Nexus 海外旗舰（国内直连） ===
  {id:'nx_claude_sonnet',name:'Claude Sonnet 4.6',provider:'Anthropic',desc:'Claude最佳平衡，编程推理顶尖，国内直连。',avatar:'#d97706',tags:['推理','编程','海外'],context:'200K',inputPrice:'¥3/M',outputPrice:'¥15/M',featured:true,free:false},
  {id:'nx_claude_opus',name:'Claude Opus 4.7',provider:'Anthropic',desc:'最强深度分析，国内直连。',avatar:'#d97706',tags:['深度分析','推理','海外'],context:'200K',inputPrice:'¥5/M',outputPrice:'¥25/M',featured:true,free:false},
  {id:'nx_claude_haiku',name:'Claude Haiku 4.5',provider:'Anthropic',desc:'Claude轻量版，极速响应。',avatar:'#f59e0b',tags:['快速','编程','海外'],context:'200K',inputPrice:'¥0.5/M',outputPrice:'¥2/M',featured:false,free:false},
  {id:'nx_gpt5',name:'GPT-5 Pro',provider:'OpenAI',desc:'OpenAI最新旗舰，国内直连。',avatar:'#10a37f',tags:['多模态','推理','编程','海外'],context:'256K',inputPrice:'¥180/M',outputPrice:'¥1080/M',featured:true,free:false},
  {id:'nx_gpt5mini',name:'GPT-5 Mini',provider:'OpenAI',desc:'GPT-5轻量，极低价高性价比。',avatar:'#10a37f',tags:['快速','编程','海外'],context:'256K',inputPrice:'¥0.15/M',outputPrice:'¥1.2/M',featured:true,free:false},
  {id:'nx_gemini_pro',name:'Gemini 2.5 Pro（国内）',provider:'Google',desc:'Google旗舰，国内直连版。',avatar:'#4285f4',tags:['多模态','长文本','海外'],context:'1M',inputPrice:'¥3/M',outputPrice:'¥18/M',featured:true,free:false},
  {id:'nx_o3mini',name:'O3 Mini',provider:'OpenAI',desc:'OpenAI推理模型，国内直连。',avatar:'#10a37f',tags:['推理','数学','海外'],context:'200K',inputPrice:'¥2/M',outputPrice:'¥8/M',featured:false,free:false},
  {id:'nx_grok3',name:'Grok 3',provider:'xAI',desc:'马斯克xAI最强模型，国内直连。',avatar:'#1d9bf0',tags:['推理','编程','海外'],context:'256K',inputPrice:'¥5/M',outputPrice:'¥20/M',featured:false,free:false},
  {id:'nx_flux',name:'Flux Pro',provider:'图片',desc:'开源最强文生图，国内直连。',avatar:'#8b5cf6',tags:['图片生成','创意','海外'],context:'N/A',inputPrice:'¥0.1/次',outputPrice:'¥0.1/次',featured:false,free:false},
];

// === Provider Icons (厂商图标) ===
const PROVIDER_ICONS={
  'OpenAI':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#10a37f"/><path d="M12 4l2 4h4l1 2-3 3 1 4-3 1-2-3-2 3-3-1 1-4-3-3 1-2h4z" fill="none" stroke="#fff" stroke-width="1.5"/></svg>'),
  'Anthropic':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#d97706"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="13" font-weight="700" font-family="Arial">C</text></svg>'),
  'Google':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#4285f4"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="13" font-weight="700" font-family="Arial">G</text></svg>'),
  'DeepSeek':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><defs><linearGradient id="ds" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="#4f46e5"/><stop offset="100%" stop-color="#2dd4bf"/></linearGradient></defs><rect width="24" height="24" rx="6" fill="url(#ds)"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="13" font-weight="700" font-family="Arial">D</text></svg>'),
  '阿里云':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#ff6a00"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="12" font-weight="700" font-family="Arial">阿</text></svg>'),
  '通义千问':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#ff6a00"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="12" font-weight="700" font-family="Arial">Q</text></svg>'),
  '月之暗面':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#6c5ce7"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="13" font-weight="700" font-family="Arial">K</text></svg>'),
  'Kimi':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#6c5ce7"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="13" font-weight="700" font-family="Arial">K</text></svg>'),
  '智谱':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#3859ff"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="12" font-weight="700" font-family="Arial">智</text></svg>'),
  '智谱AI':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#3859ff"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="12" font-weight="700" font-family="Arial">智</text></svg>'),
  '字节跳动':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#e8426e"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="9" font-weight="700" font-family="Arial">豆包</text></svg>'),
  '腾讯':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#00a4ff"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="12" font-weight="700" font-family="Arial">腾</text></svg>'),
  'Meta':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#0668e1"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="12" font-weight="700" font-family="Arial">M</text></svg>'),
  'xAI':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#1d9bf0"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="13" font-weight="700" font-family="Arial">X</text></svg>'),
  '百度':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#2932e1"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="11" font-weight="700" font-family="Arial">B</text></svg>'),
  'Mistral':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#ff6b35"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="11" font-weight="700" font-family="Arial">M</text></svg>'),
  'Mistral AI':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#ff6b35"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="11" font-weight="700" font-family="Arial">M</text></svg>'),
  'MiniMax':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#fd79a8"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="10" font-weight="700" font-family="Arial">MX</text></svg>'),
  '科大讯飞':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#2563eb"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="12" font-weight="700" font-family="Arial">讯</text></svg>'),
  '讯飞':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#2563eb"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="10" font-weight="700" font-family="Arial">XF</text></svg>'),
  '百川智能':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#f97316"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="10" font-weight="700" font-family="Arial">百川</text></svg>'),
  'KAT':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#636e72"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="10" font-weight="700" font-family="Arial">KT</text></svg>'),
  'MIMO':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#d63031"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="10" font-weight="700" font-family="Arial">MI</text></svg>'),
  '合作伙伴':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#00cec9"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="9" font-weight="700" font-family="Arial">AI</text></svg>'),
  'Meshy':'data:image/svg+xml,'+encodeURIComponent('<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><rect width="24" height="24" rx="6" fill="#8b5cf6"/><text x="12" y="17" text-anchor="middle" fill="#fff" font-size="9" font-weight="700" font-family="Arial">3D</text></svg>'),
};
function getProviderIcon(provider){return PROVIDER_ICONS[provider]||null}

// === Render Models ===
function renderModelCard(m){const icon=getProviderIcon(m.provider);const avatar=m.avatar||('#'+Math.floor(Math.random()*16777215).toString(16));const desc=m.desc||`${m.provider} · 大语言模型`;const iconHtml=icon?`<div class="model-avatar" style="background:transparent"><img src="${icon}" width="34" height="34" style="border-radius:8px"></div>`:`<div class="model-avatar" style="background:${avatar}">${m.name[0]}</div>`;return`<div class="model-card${m.featured?' featured':''}" onclick="switchPage('chat');setTimeout(()=>{const cb=document.querySelector('#chatModelList input[value=\\'${m.id}\\']');if(cb)cb.checked=true},100)" style="cursor:pointer"><div class="model-header">${iconHtml}<div><div class="model-name">${m.name}</div></div></div><div class="model-desc">${desc}</div><div class="model-tags">${(m.tags||[]).map(t=>`<span class="tag${t==='免费'?' green':''}${t==='开源'?' orange':''}">${t}</span>`).join('')}</div><div class="model-meta"><span class="model-price">入:${m.inputPrice||'?'} | 出:${m.outputPrice||'?'}</span><span class="model-context">${m.context||'?'}</span></div></div>`}
function initFeaturedModels(){document.getElementById('featuredModels').innerHTML=models.filter(m=>m.featured&&!m.hidden).map(renderModelCard).join('')}
initFeaturedModels();

// ===== 首页 Hero 模型星球 =====
function initHeroPlanet(){
  const ids=['hpRing1','hpRing2','hpRing3'];
  if(!document.getElementById(ids[0]))return;
  if(document.getElementById(ids[0]).children.length>0)return;
  const featured=models.filter(m=>m.featured&&!m.hidden);
  const allM=featured.length>=24?featured:models.slice(0,24);
  const ring1=allM.slice(0,8);
  const ring2=allM.slice(8,16);
  const ring3=allM.slice(16,24);
  const colorMap={'#10a37f':'#10a37f','#d97706':'#d97706','#4285f4':'#4285f4','#4f46e5':'#4f46e5','#ff6a00':'#ff6a00','#6c5ce7':'#6c5ce7','#3859ff':'#3859ff','#00a4ff':'#00a4ff','#0668e1':'#0668e1','#e17055':'#e17055','#e8426e':'#e8426e','#2932e1':'#2932e1','#ff6b35':'#ff6b35','#1d9bf0':'#1d9bf0','#2563eb':'#2563eb','#fd79a8':'#fd79a8','#f43f5e':'#f43f5e','#059669':'#059669','#8b5cf6':'#8b5cf6','#ea580c':'#ea580c','#0891b2':'#0891b2','#7c3aed':'#7c3aed','#0284c7':'#0284c7','#0369a1':'#0369a1','#ff6b00':'#ff6b00','#e63946':'#e63946','#6366f1':'#6366f1','#0ea5e9':'#0ea5e9','#e11d48':'#e11d48','#6b21a8':'#6b21a8'};
  const radii=[120,180,240];
  const rings=[ring1,ring2,ring3];
  rings.forEach((items,ri)=>{
    const ring=document.getElementById(ids[ri]);if(!ring)return;
    const r=radii[ri];const count=items.length;const step=2*Math.PI/count;
    items.forEach((m,i)=>{
      const a=i*step;const x=r+r*Math.sin(a);const y=r-r*Math.cos(a);
      const n=document.createElement('div');n.className='hp-node';
      n.style.cssText=`left:${x-24}px;top:${y-24}px`;
      const c=colorMap[m.avatar]||m.avatar;const icon=m.name.charAt(0);
      n.innerHTML=`<div class="hp-ni" style="background:${c}">${icon}</div><div class="hp-nn">${m.name}</div>`;
      n.title=m.name;
      n.addEventListener('click',()=>{switchPage('chat');setTimeout(()=>{const cb=document.querySelector('#chatModelList input[value="${m.id}"]');if(cb)cb.checked=true},100)});
      ring.appendChild(n);
    });
  });
}
initHeroPlanet(); // 首页星球保留
// 动态获取模型总数 & 动态模型合并
(async function loadModelCount(){
  try{
    const r=await fetch(API_BASE+'/api/models-count');
    if(r.ok){const d=await r.json();const el=document.getElementById('modelCount');if(el&&d.count){el.textContent=d.count;el.dataset.apiLoaded='true'}}
  }catch(e){/* 静默失败，使用本地模型数 */}
  // 同时拉取动态模型并合并
  const existingIds=new Set(models.map(m=>m.id));
  async function fetchDynamic(url){
    try{
      const r=await fetch(API_BASE+url);if(!r.ok)return[];
      const d=await r.json();if(!d.data&&!d.models)return[];
      // 支持 {data:[...]} 和 {models:[...]} 两种响应格式
      const list=d.data||d.models||[];
      const added=[];
      list.forEach(m=>{if(!existingIds.has(m.id)){models.push(m);existingIds.add(m.id);added.push(m.id)}});
      return added;
    }catch(e){return[]}
  }
  const [bailian,sf,openrouter]=await Promise.all([fetchDynamic('/api/bailian-models'),fetchDynamic('/api/siliconflow-models'),fetchDynamic('/api/openrouter-models')]);
  const el=document.getElementById('modelCount');
  if(el){
    const cur=parseInt(el.textContent)||0;
    el.textContent=Math.max(cur,models.length);
    el.dataset.apiLoaded='true';
  }
})();

function initAllModels(){
  // renderPlanet(); // 已移除模型页星球
  const af=document.querySelector('#page-models .filter-tag.active')?.dataset?.filter||'all';
  const st=document.getElementById('modelSearch')?.value?.toLowerCase()||'';
  let f=models;
  if(af!=='all')f=f.filter(m=>m.tags.includes(af));
  if(st)f=f.filter(m=>m.name.toLowerCase().includes(st)||m.provider.toLowerCase().includes(st)||m.tags.some(t=>t.includes(st)));
  document.getElementById('allModels').innerHTML=f.map(renderModelCard).join('');
  document.getElementById('noResults').style.display=f.length?'none':'block';
  // 不覆盖 API 获取的模型数
  const mc=document.getElementById('modelCount');
  if(mc&&!mc.dataset.apiLoaded)mc.textContent=models.length;
}
// ===== 模型星球 =====
function renderPlanet(){
  if(document.getElementById('pRing1').children.length>0)return; // 只渲染一次
  const colorMap={
    '#10a37f':'#10a37f','#d97706':'#d97706','#4285f4':'#4285f4','#4f46e5':'#4f46e5',
    '#ff6a00':'#ff6a00','#6c5ce7':'#6c5ce7','#3859ff':'#3859ff','#00a4ff':'#00a4ff',
    '#0668e1':'#0668e1','#e17055':'#e17055','#e8426e':'#e8426e','#2932e1':'#2932e1',
    '#ff6b35':'#ff6b35','#1d9bf0':'#1d9bf0','#2563eb':'#2563eb','#fd79a8':'#fd79a8',
    '#f43f5e':'#f43f5e','#059669':'#059669','#8b5cf6':'#8b5cf6','#ea580c':'#ea580c',
    '#0891b2':'#0891b2','#7c3aed':'#7c3aed','#0284c7':'#0284c7','#0369a1':'#0369a1',
    '#ff6b00':'#ff6b00','#e63946':'#e63946','#6366f1':'#6366f1','#0ea5e9':'#0ea5e9',
    '#e11d48':'#e11d48','#6b21a8':'#6b21a8',
  };
  // 从models中提取星球数据（去重，取16个核心）
  const coreModels=models.filter(m=>!m.id.includes('qiniu')&&!m.hidden).slice(0,28);
  // 分轨道
  const ring1=coreModels.slice(0,8);
  const ring2=coreModels.slice(8,18);
  const ring3=coreModels.slice(18,28);
  // 渲染轨道节点
  function fillRing(ringId,items,radius){
    const ring=document.getElementById(ringId);
    const count=items.length;
    const step=2*Math.PI/count;
    items.forEach((m,i)=>{
      const a=i*step;
      const x=radius+radius*Math.sin(a);
      const y=radius-radius*Math.cos(a);
      const n=document.createElement('div');
      n.className='p-node';
      n.style.cssText=`left:${x-26}px;top:${y-26}px;animation-delay:${Math.random()*4}s`;
      const icon=m.name.charAt(0);
      const c=colorMap[m.avatar]||m.avatar;
      n.innerHTML=`<div class="pn-icon" style="background:${c}">${icon}</div><div class="pn-name">${m.name}</div>`;
      n.title=m.name;
      n.addEventListener('click',()=>{
        switchPage('chat');
        setTimeout(()=>{
          const cb=document.querySelector(`#chatModelList input[value="${m.id}"]`);
          if(cb)cb.checked=true;
        },100);
      });
      ring.appendChild(n);
    });
  }
  fillRing('pRing1',ring1,110);
  fillRing('pRing2',ring2,170);
  fillRing('pRing3',ring3,225);
}
document.getElementById('modelSearch').addEventListener('input',initAllModels);
document.querySelectorAll('#page-models .filter-tag').forEach(t=>t.addEventListener('click',()=>{document.querySelectorAll('#page-models .filter-tag').forEach(x=>x.classList.remove('active'));t.classList.add('active');initAllModels()}));

// === Agent 模式开关 ===
let AGENT_MODE = localStorage.getItem('agentMode') === 'true';
document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('agentModeToggle');
  if (toggle) toggle.checked = AGENT_MODE;
});

