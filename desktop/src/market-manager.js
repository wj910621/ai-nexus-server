/**
 * Y·NEX - 市场与模板系统
 * 
 * 统一管理：
 * - 技能包（.yskill）
 * - Agent/团队配置（.yagent）
 * - 工作流模板（.yflow）
 * 
 * 功能：
 * - 导入/导出
 * - 本地管理
 * - 预设模板库
 */

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

function uuidv4() {
  return crypto.randomUUID ? crypto.randomUUID() :
    'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
      const r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
      return v.toString(16);
    });
}

const SAFE_ID_PATTERN = /^[a-zA-Z0-9_-]+$/;

function sanitizeId(id, fallbackPrefix) {
  if (!id || typeof id !== 'string') {
    return fallbackPrefix + uuidv4().slice(0, 8);
  }
  if (SAFE_ID_PATTERN.test(id)) return id;
  const cleaned = id.replace(/[^a-zA-Z0-9_-]/g, '_');
  if (cleaned.length > 0 && SAFE_ID_PATTERN.test(cleaned)) return cleaned;
  return fallbackPrefix + uuidv4().slice(0, 8);
}

function safeJoin(baseDir, fileName) {
  const resolved = path.resolve(baseDir, fileName);
  const resolvedBase = path.resolve(baseDir);
  if (!resolved.startsWith(resolvedBase + path.sep) && resolved !== resolvedBase) {
    throw new Error('非法路径访问');
  }
  return resolved;
}

function safeString(str, maxLen = 200) {
  if (typeof str !== 'string') return '';
  const s = str.slice(0, maxLen);
  return s;
}

function safeArray(arr, maxLen = 50) {
  if (!Array.isArray(arr)) return [];
  return arr.slice(0, maxLen);
}

class MarketManager {
  constructor(dataDir) {
    this.dataDir = dataDir;
    this.skillsDir = path.join(dataDir, 'skills');
    this.agentsDir = path.join(dataDir, 'agents');
    this.workflowsDir = path.join(dataDir, 'workflows-templates');
    this._ensureDirs();
    this._initPresets();
  }

  _ensureDirs() {
    [this.skillsDir, this.agentsDir, this.workflowsDir].forEach(d => {
      if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
    });
  }

  _initPresets() {
    const skillPresetsFile = path.join(this.skillsDir, '.presets_init');
    if (!fs.existsSync(skillPresetsFile)) {
      this._installSkillPresets();
      fs.writeFileSync(skillPresetsFile, 'done', 'utf-8');
    }
    const agentPresetsFile = path.join(this.agentsDir, '.presets_init');
    if (!fs.existsSync(agentPresetsFile)) {
      this._installAgentPresets();
      fs.writeFileSync(agentPresetsFile, 'done', 'utf-8');
    }
    const wfPresetsFile = path.join(this.workflowsDir, '.presets_init');
    if (!fs.existsSync(wfPresetsFile)) {
      this._installWorkflowPresets();
      fs.writeFileSync(wfPresetsFile, 'done', 'utf-8');
    }
  }

  // ============================================================
  // 技能包管理
  // ============================================================
  _installSkillPresets() {
    const presets = [
      {
        id: 'skill_content_writer',
        name: '内容创作助手',
        icon: '✍️',
        category: '内容创作',
        description: '帮你写文章、公众号、小红书文案等',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['写作', '文案', '内容'],
        prompts: [
          { name: '写公众号文章', description: '写一篇吸引人的公众号推文', template: '请帮我写一篇关于{topic}的公众号文章，要求标题吸引人，结构清晰，字数在{words}字左右' },
          { name: '写小红书笔记', description: '写一篇小红书风格种草文案', template: '请帮我写一篇关于{product}的小红书种草文案，要接地气有代入感，加emoji' },
          { name: '写短视频脚本', description: '写一个60秒短视频口播脚本', template: '请帮我写一个关于{topic}的60秒短视频口播脚本' },
        ],
      },
      {
        id: 'skill_code_helper',
        name: '编程助手',
        icon: '💻',
        category: '编程开发',
        description: '写代码、调bug、代码优化',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['编程', '代码', '开发'],
        prompts: [
          { name: '代码解释', description: '解释一段代码的作用', template: '请详细解释以下代码的作用和实现原理：\n\n{code}' },
          { name: 'Bug修复', description: '帮你找bug并修复', template: '以下代码有bug，请帮我找出问题并修复：\n\n{code}\n\n错误信息：{error}' },
          { name: '代码优化', description: '优化代码性能和可读性', template: '请帮我优化以下代码，提升性能和可读性：\n\n{code}' },
        ],
      },
      {
        id: 'skill_translation',
        name: '翻译专家',
        icon: '🌍',
        category: '语言工具',
        description: '多语言翻译、润色、本地化',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['翻译', '英语', '多语言'],
        prompts: [
          { name: '中译英', description: '中文翻译成地道英文', template: '请将以下中文翻译成地道的英文：\n\n{text}' },
          { name: '英译中', description: '英文翻译成流畅中文', template: '请将以下英文翻译成流畅的中文：\n\n{text}' },
          { name: '文案润色', description: '润色文案让它更专业', template: '请帮我润色以下文案，让它更专业更有吸引力：\n\n{text}' },
        ],
      },
      {
        id: 'skill_data_analysis',
        name: '数据分析助手',
        icon: '📊',
        category: '数据处理',
        description: '数据分析、图表生成、报告撰写',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['数据', '分析', 'Excel'],
        prompts: [
          { name: '数据分析', description: '分析数据并给出洞察', template: '请分析以下数据，给出关键洞察和建议：\n\n{data}' },
          { name: 'Excel公式', description: '帮你写Excel公式', template: '我需要一个Excel公式来实现{requirement}，请给出公式和解释' },
          { name: '写分析报告', description: '撰写数据分析报告', template: '请根据以下数据写一份专业的数据分析报告：\n\n{data}' },
        ],
      },
      {
        id: 'skill_image_prompt',
        name: 'AI绘画提示词',
        icon: '🎨',
        category: '创意设计',
        description: '生成高质量AI绘画提示词',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['绘画', '提示词', '设计'],
        prompts: [
          { name: 'Midjourney提示词', description: '生成Midjourney风格提示词', template: '请帮我生成一个Midjourney风格的绘画提示词，主题是{topic}，风格是{style}' },
          { name: '头像生成', description: '生成个性化头像提示词', template: '请帮我生成一个个性化头像的提示词，人物特征是{features}' },
        ],
      },
      {
        id: 'skill_learning',
        name: '学习导师',
        icon: '📚',
        category: '教育学习',
        description: '知识讲解、题目解答、学习规划',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['学习', '教育', '考试'],
        prompts: [
          { name: '知识点讲解', description: '通俗易懂讲解知识点', template: '请用通俗易懂的方式讲解{topic}这个知识点，最好举例子' },
          { name: '解题步骤', description: '详细解答题目并给出步骤', template: '请帮我解答这道题，并给出详细步骤：\n\n{question}' },
          { name: '学习计划', description: '制定个性化学习计划', template: '请帮我制定一个{topic}的学习计划，我目前的基础是{level}，目标是{goal}' },
        ],
      },
      {
        id: 'skill_web_research',
        name: '网络研究助手',
        icon: '🔍',
        category: '效率工具',
        description: '深度网络调研、信息汇总、资料整理',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['研究', '调研', '信息检索'],
        prompts: [
          { name: '主题调研', description: '对指定主题进行深度调研', template: '请对{topic}进行深度调研，整理关键信息、发展现状和未来趋势' },
          { name: '竞品分析', description: '分析竞争对手产品', template: '请帮我分析{product}的竞品，从功能、定价、用户评价等维度对比' },
          { name: '资料汇总', description: '汇总多方资料形成摘要', template: '请将以下资料汇总成一份结构清晰的摘要：\n\n{content}' },
        ],
      },
      {
        id: 'skill_email_writer',
        name: '邮件写作助手',
        icon: '📧',
        category: '办公沟通',
        description: '商务邮件、客户沟通、内部邮件',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['邮件', '商务', '沟通'],
        prompts: [
          { name: '商务邮件', description: '撰写专业商务邮件', template: '请帮我写一封关于{topic}的商务邮件，收件人是{recipient}，语气要{tone}' },
          { name: '客户回复', description: '回复客户咨询邮件', template: '请帮我回复客户的咨询邮件，客户问题是：{question}，要体现专业和耐心' },
          { name: '催办邮件', description: '委婉催办事项', template: '请帮我写一封委婉的催办邮件，催办事项是{task}，对方是{recipient}' },
        ],
      },
      {
        id: 'skill_resume_builder',
        name: '简历优化师',
        icon: '📄',
        category: '职业发展',
        description: '简历撰写、优化、求职信',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['简历', '求职', '职业'],
        prompts: [
          { name: '简历优化', description: '优化现有简历', template: '请帮我优化以下简历，突出亮点，提升专业感：\n\n{resume}' },
          { name: '求职信', description: '撰写针对性求职信', template: '请帮我写一封应聘{position}的求职信，突出我的{skills}和相关经验' },
          { name: '自我介绍', description: '撰写面试自我介绍', template: '请帮我写一段面试{position}岗位的自我介绍，时长约{duration}分钟' },
        ],
      },
      {
        id: 'skill_business_plan',
        name: '商业计划书',
        icon: '📊',
        category: '商业策划',
        description: '商业计划书撰写、市场分析、财务预测',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['商业', '创业', '计划书'],
        prompts: [
          { name: '商业计划书', description: '撰写完整商业计划书', template: '请帮我写一份关于{project}的商业计划书，包含市场分析、商业模式、财务预测' },
          { name: '市场分析', description: '分析目标市场', template: '请对{industry}行业进行市场分析，包括市场规模、竞争格局和发展趋势' },
          { name: '盈利模式', description: '设计盈利模式', template: '请帮我设计{product}的盈利模式，给出多种变现路径' },
        ],
      },
      {
        id: 'skill_pitch_deck',
        name: '路演PPT',
        icon: '🎯',
        category: '商业策划',
        description: '融资路演PPT、投资人沟通',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['路演', '融资', 'PPT'],
        prompts: [
          { name: '路演大纲', description: '生成路演PPT大纲', template: '请帮我生成一份{project}的融资路演PPT大纲，约{slides}页' },
          { name: '电梯演讲', description: '撰写30秒电梯演讲', template: '请帮我写一段关于{project}的30秒电梯演讲稿' },
          { name: '投资人问答', description: '预演投资人提问', template: '请列出投资人可能对{project}提出的10个关键问题，并给出参考回答' },
        ],
      },
      {
        id: 'skill_marketing_copy',
        name: '营销文案',
        icon: '📣',
        category: '市场营销',
        description: '广告文案、促销活动、品牌故事',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['营销', '广告', '文案'],
        prompts: [
          { name: '广告文案', description: '撰写吸引人的广告文案', template: '请帮我写一份{product}的广告文案，目标人群是{audience}，主打卖点{selling_point}' },
          { name: '促销活动', description: '策划促销活动方案', template: '请帮我策划一个{festival}促销活动方案，产品是{product}，预算{budget}' },
          { name: '品牌故事', description: '撰写品牌故事', template: '请帮我写一个{brand}的品牌故事，要体现品牌价值观和情感共鸣' },
        ],
      },
      {
        id: 'skill_seo_optimizer',
        name: 'SEO优化',
        icon: '🌐',
        category: '市场营销',
        description: 'SEO关键词、内容优化、排名提升',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['SEO', '关键词', '优化'],
        prompts: [
          { name: '关键词研究', description: '研究行业关键词', template: '请帮我研究{industry}行业的SEO关键词，给出核心词和长尾词列表' },
          { name: '内容优化', description: '优化文章SEO', template: '请帮我优化以下文章的SEO，目标关键词是{keyword}：\n\n{content}' },
          { name: 'Meta标签', description: '生成Meta描述和标题', template: '请为以下网页生成SEO友好的title和description，目标关键词{keyword}：\n\n{content}' },
        ],
      },
      {
        id: 'skill_social_media',
        name: '社交媒体内容',
        icon: '📱',
        category: '市场营销',
        description: '微博、抖音、小红书多平台内容',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['社媒', '运营', '内容'],
        prompts: [
          { name: '微博文案', description: '撰写微博短文案', template: '请帮我写一条关于{topic}的微博文案，140字以内，带话题标签' },
          { name: '抖音脚本', description: '撰写抖音短视频脚本', template: '请帮我写一个关于{topic}的抖音短视频脚本，时长{duration}秒' },
          { name: '小红书笔记', description: '撰写小红书种草笔记', template: '请帮我写一篇{product}的小红书种草笔记，要接地气有真实感' },
        ],
      },
      {
        id: 'skill_video_script',
        name: '视频脚本',
        icon: '🎬',
        category: '内容创作',
        description: '短视频、宣传片、教程脚本',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['视频', '脚本', '短视频'],
        prompts: [
          { name: '短视频脚本', description: '撰写短视频分镜脚本', template: '请帮我写一个关于{topic}的短视频分镜脚本，包含画面描述和旁白' },
          { name: '宣传片脚本', description: '撰写企业宣传片脚本', template: '请帮我写一份{company}的宣传片脚本，时长约{duration}分钟' },
          { name: '教程脚本', description: '撰写教程类视频脚本', template: '请帮我写一个{topic}教程视频脚本，面向{level}学习者' },
        ],
      },
      {
        id: 'skill_podcast_outline',
        name: '播客大纲',
        icon: '🎙️',
        category: '内容创作',
        description: '播客选题、大纲、文案',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['播客', '音频', '大纲'],
        prompts: [
          { name: '播客选题', description: '生成播客选题', template: '请帮我生成{field}领域的5个播客选题，要有话题性和吸引力' },
          { name: '播客大纲', description: '撰写播客节目大纲', template: '请帮我写一期关于{topic}的播客节目大纲，时长约{duration}分钟' },
          { name: '主持人文案', description: '撰写主持人开场结尾', template: '请帮我写一段播客{topic}的开场白和结尾文案，风格要{style}' },
        ],
      },
      {
        id: 'skill_story_writer',
        name: '故事创作',
        icon: '📖',
        category: '创意写作',
        description: '短篇故事、小说片段、故事构思',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['故事', '创意', '写作'],
        prompts: [
          { name: '短篇故事', description: '创作短篇故事', template: '请帮我写一个关于{theme}的短篇故事，风格{style}，字数约{words}字' },
          { name: '故事构思', description: '提供故事创意构思', template: '请给我{count}个关于{theme}的故事创意构思，每个含主要冲突和转折' },
          { name: '人物小传', description: '撰写人物背景故事', template: '请帮我写一个角色的人物小传，角色名{name}，身份是{role}，性格特点{personality}' },
        ],
      },
      {
        id: 'skill_poem_writer',
        name: '诗歌创作',
        icon: '✨',
        category: '创意写作',
        description: '现代诗、古体诗、歌词',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['诗歌', '诗词', '创作'],
        prompts: [
          { name: '现代诗', description: '创作现代诗', template: '请帮我写一首关于{theme}的现代诗，风格{style}' },
          { name: '古体诗', description: '创作古风诗词', template: '请帮我写一首关于{theme}的{form}，要求押韵对仗' },
          { name: '歌词创作', description: '创作歌曲歌词', template: '请帮我写一首关于{theme}的歌词，曲风是{genre}，主歌副歌结构完整' },
        ],
      },
      {
        id: 'skill_novel_outline',
        name: '小说大纲',
        icon: '📚',
        category: '创意写作',
        description: '小说大纲、章节规划、人物设定',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['小说', '大纲', '创作'],
        prompts: [
          { name: '小说大纲', description: '生成小说整体大纲', template: '请帮我写一份{genre}类型小说的大纲，主题是{theme}，约{chapters}章' },
          { name: '章节规划', description: '规划具体章节内容', template: '请帮我规划小说第{chapter}章的内容，包括场景、冲突和推进' },
          { name: '人物设定', description: '设计小说人物设定', template: '请帮我设计一个小说人物，角色类型是{role}，背景是{background}' },
        ],
      },
      {
        id: 'skill_code_review',
        name: '代码审查',
        icon: '🔎',
        category: '编程开发',
        description: '代码质量、安全、规范审查',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['代码审查', '质量', '规范'],
        prompts: [
          { name: '代码审查', description: '全面审查代码', template: '请审查以下代码，从质量、规范、安全、性能四个维度给出建议：\n\n{code}' },
          { name: '规范检查', description: '检查代码规范', template: '请检查以下代码是否符合{language}的编码规范，并给出改进建议：\n\n{code}' },
          { name: '安全审查', description: '审查代码安全漏洞', template: '请审查以下代码的安全漏洞，给出修复建议：\n\n{code}' },
        ],
      },
      {
        id: 'skill_debug_helper',
        name: '调试助手',
        icon: '🐛',
        category: '编程开发',
        description: 'Bug定位、错误分析、调试技巧',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['调试', 'bug', '排错'],
        prompts: [
          { name: 'Bug定位', description: '定位代码bug', template: '以下代码出现了bug，现象是{symptom}，请帮我定位原因：\n\n{code}' },
          { name: '错误分析', description: '分析错误信息', template: '请分析以下错误信息的原因和解决方案：\n\n{error}' },
          { name: '调试思路', description: '提供调试思路', template: '我在{language}开发中遇到了{problem}问题，请给我一套系统的调试思路' },
        ],
      },
      {
        id: 'skill_api_designer',
        name: 'API设计',
        icon: '🔌',
        category: '编程开发',
        description: 'RESTful API设计、文档、规范',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['API', '接口', '设计'],
        prompts: [
          { name: 'API设计', description: '设计RESTful API', template: '请帮我设计{function}功能的RESTful API，包括路由、方法、参数和响应' },
          { name: 'API文档', description: '生成API文档', template: '请帮我为以下API生成详细的接口文档：\n\n{api_info}' },
          { name: '接口规范', description: '制定接口规范', template: '请帮我制定一套{project}项目的API设计规范，包含命名、版本、错误码等' },
        ],
      },
      {
        id: 'skill_sql_query',
        name: 'SQL查询',
        icon: '🗄️',
        category: '数据处理',
        description: 'SQL编写、优化、数据库设计',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['SQL', '数据库', '查询'],
        prompts: [
          { name: 'SQL编写', description: '编写SQL查询语句', template: '请帮我写一条SQL语句，需求是{requirement}，表结构是：\n\n{schema}' },
          { name: 'SQL优化', description: '优化SQL性能', template: '请帮我优化以下SQL语句的性能：\n\n{sql}' },
          { name: '表设计', description: '设计数据库表结构', template: '请帮我设计{function}功能的数据库表结构，要考虑{database}数据库的特性' },
        ],
      },
      {
        id: 'skill_regex_builder',
        name: '正则表达式',
        icon: '🔣',
        category: '编程开发',
        description: '正则编写、解释、测试',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['正则', 'regex', '匹配'],
        prompts: [
          { name: '正则编写', description: '编写正则表达式', template: '请帮我写一个正则表达式，用于匹配{pattern}，并给出解释和示例' },
          { name: '正则解释', description: '解释正则含义', template: '请解释以下正则表达式的含义和匹配规则：\n\n{regex}' },
          { name: '正则测试', description: '提供测试用例', template: '请为以下正则表达式提供测试用例，包含匹配和不匹配的例子：\n\n{regex}' },
        ],
      },
      {
        id: 'skill_unit_test',
        name: '单元测试',
        icon: '🧪',
        category: '编程开发',
        description: '单元测试编写、测试用例、Mock',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['测试', '单元测试', 'TDD'],
        prompts: [
          { name: '编写测试', description: '编写单元测试代码', template: '请帮我为以下{language}代码编写单元测试，使用{framework}框架：\n\n{code}' },
          { name: '测试用例', description: '设计测试用例', template: '请帮我为{function}函数设计测试用例，包含正常、边界和异常情况' },
          { name: 'Mock设计', description: '设计Mock数据', template: '请帮我为以下代码设计Mock数据，便于单元测试：\n\n{code}' },
        ],
      },
      {
        id: 'skill_legal_doc',
        name: '法律文书',
        icon: '⚖️',
        category: '专业文档',
        description: '法律文书起草、法律咨询',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['法律', '文书', '合规'],
        prompts: [
          { name: '文书起草', description: '起草法律文书', template: '请帮我起草一份{doc_type}，关键条款是{terms}' },
          { name: '法律咨询', description: '提供法律咨询意见', template: '请就{situation}这一情况提供法律咨询意见和风险提示' },
          { name: '合规检查', description: '检查内容合规性', template: '请检查以下内容是否符合{region}的{law}法规，并指出风险点：\n\n{content}' },
        ],
      },
      {
        id: 'skill_contract_review',
        name: '合同审查',
        icon: '📋',
        category: '专业文档',
        description: '合同审查、条款分析、风险提示',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['合同', '审查', '条款'],
        prompts: [
          { name: '合同审查', description: '审查合同条款', template: '请帮我审查以下合同，指出风险条款和修改建议：\n\n{contract}' },
          { name: '条款分析', description: '分析关键条款', template: '请帮我分析以下{clause_type}条款的法律含义和风险：\n\n{clause}' },
          { name: '合同起草', description: '起草合同', template: '请帮我起草一份{contract_type}合同，双方是{party_a}和{party_b}，主要事项{terms}' },
        ],
      },
      {
        id: 'skill_meeting_notes',
        name: '会议纪要',
        icon: '📝',
        category: '办公沟通',
        description: '会议纪要、议程、总结',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['会议', '纪要', '办公'],
        prompts: [
          { name: '会议纪要', description: '整理会议纪要', template: '请将以下会议记录整理成正式的会议纪要：\n\n{content}' },
          { name: '会议议程', description: '撰写会议议程', template: '请帮我写一份{topic}会议的议程，时长{duration}分钟，参会人数{count}人' },
          { name: '会议总结', description: '生成会议总结', template: '请根据以下会议内容生成一份会议总结和待办事项：\n\n{content}' },
        ],
      },
      {
        id: 'skill_project_plan',
        name: '项目计划',
        icon: '📋',
        category: '项目管理',
        description: '项目规划、进度管理、风险控制',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['项目', '计划', '管理'],
        prompts: [
          { name: '项目计划', description: '制定项目计划', template: '请帮我制定{project}项目的计划，包括阶段划分、时间节点和里程碑' },
          { name: 'WBS分解', description: '分解工作结构', template: '请帮我将{project}项目进行WBS分解，给出任务清单和依赖关系' },
          { name: '风险评估', description: '评估项目风险', template: '请帮我评估{project}项目的风险，给出风险等级和应对措施' },
        ],
      },
      {
        id: 'skill_productivity',
        name: '效率提升',
        icon: '⚡',
        category: '效率工具',
        description: '时间管理、工作流、效率方法',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['效率', '时间管理', '工作流'],
        prompts: [
          { name: '时间管理', description: '制定时间管理方案', template: '请帮我制定一套时间管理方案，我的工作内容是{work}，主要困扰是{problem}' },
          { name: '工作流优化', description: '优化工作流程', template: '请帮我优化以下工作流程，提升效率：\n\n{workflow}' },
          { name: '效率方法', description: '推荐效率提升方法', template: '请推荐适合{scenario}场景的效率提升方法和工具' },
        ],
      },
      {
        id: 'skill_brainstorm',
        name: '头脑风暴',
        icon: '💡',
        category: '创意思维',
        description: '创意发散、方案构思、思维拓展',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['创意', '头脑风暴', '思维'],
        prompts: [
          { name: '创意发散', description: '发散创意点子', template: '请围绕{topic}给我{count}个创意点子，要新颖有可行性' },
          { name: '方案构思', description: '构思解决方案', template: '请帮我构思{problem}的解决方案，给出多种思路对比' },
          { name: '思维拓展', description: '拓展思考维度', template: '请从多个维度拓展我对{topic}的思考，给出不同视角的观点' },
        ],
      },
      {
        id: 'skill_cooking_recipe',
        name: '烹饪食谱',
        icon: '🍳',
        category: '生活助手',
        description: '菜谱推荐、做法指导、营养搭配',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['烹饪', '食谱', '美食'],
        prompts: [
          { name: '菜谱推荐', description: '推荐菜谱', template: '请给我推荐几道用{ingredients}做的菜，要简单易做' },
          { name: '做法指导', description: '详细菜品做法', template: '请告诉我{dish}的详细做法，包括食材、步骤和技巧' },
          { name: '营养搭配', description: '设计营养餐', template: '请帮我设计一份{goal}的营养餐，每日热量{calories}卡' },
        ],
      },
      {
        id: 'skill_travel_plan',
        name: '旅行规划',
        icon: '✈️',
        category: '生活助手',
        description: '行程规划、攻略、预算',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['旅行', '攻略', '行程'],
        prompts: [
          { name: '行程规划', description: '制定旅行行程', template: '请帮我制定一份{destination}的{days}日旅行行程，预算{budget}' },
          { name: '旅行攻略', description: '撰写旅行攻略', template: '请帮我写一份{destination}的旅行攻略，包含交通、住宿、美食推荐' },
          { name: '行李清单', description: '生成行李清单', template: '请帮我生成去{destination}旅行{days}天的行李清单，季节是{season}' },
        ],
      },
      {
        id: 'skill_fitness_coach',
        name: '健身教练',
        icon: '💪',
        category: '生活助手',
        description: '健身计划、动作指导、饮食建议',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['健身', '运动', '健康'],
        prompts: [
          { name: '健身计划', description: '制定健身计划', template: '请帮我制定一份{goal}的健身计划，每周锻炼{days}天，每次{duration}分钟' },
          { name: '动作指导', description: '指导健身动作', template: '请详细指导{exercise}动作的标准姿势和常见错误' },
          { name: '饮食建议', description: '提供健身饮食建议', template: '请帮我提供{goal}期间的饮食建议，我的体重{weight}kg' },
        ],
      },
      {
        id: 'skill_language_teacher',
        name: '语言教师',
        icon: '🗣️',
        category: '教育学习',
        description: '语言学习、口语练习、语法讲解',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['语言', '外语', '口语'],
        prompts: [
          { name: '口语练习', description: '练习口语对话', template: '请和我用{language}进行{scenario}场景的口语对话练习，我的水平是{level}' },
          { name: '语法讲解', description: '讲解语法知识点', template: '请用通俗易懂的方式讲解{language}的{grammar}语法点' },
          { name: '词汇学习', description: '整理主题词汇', template: '请帮我整理{language}中关于{topic}的常用词汇和例句' },
        ],
      },
      {
        id: 'skill_exam_prep',
        name: '考试备考',
        icon: '🎓',
        category: '教育学习',
        description: '考试复习、真题解析、考点梳理',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['考试', '备考', '复习'],
        prompts: [
          { name: '复习计划', description: '制定复习计划', template: '请帮我制定{exam}考试的复习计划，距离考试还有{days}天' },
          { name: '真题解析', description: '解析真题', template: '请帮我解析以下{exam}真题，给出答案和解析：\n\n{question}' },
          { name: '考点梳理', description: '梳理考试考点', template: '请帮我梳理{subject}科目的{exam}考试重点考点' },
        ],
      },
      {
        id: 'skill_mental_health',
        name: '心理疏导',
        icon: '🧠',
        category: '生活助手',
        description: '情绪疏导、压力缓解、心理支持',
        version: '1.0.0',
        author: 'Y·NEX',
        tags: ['心理', '情绪', '健康'],
        prompts: [
          { name: '情绪疏导', description: '疏导负面情绪', template: '我最近感到{emotion}，主要因为{reason}，请帮我疏导情绪' },
          { name: '压力缓解', description: '提供减压方法', template: '我最近压力很大，来源是{source}，请给我一些减压方法' },
          { name: '心态调整', description: '帮助调整心态', template: '我在面对{situation}时容易{reaction}，请帮我调整心态' },
        ],
      },
    ];

    presets.forEach(p => {
      const filePath = path.join(this.skillsDir, `${p.id}.yskill`);
      if (!fs.existsSync(filePath)) {
        fs.writeFileSync(filePath, JSON.stringify({
          ...p,
          type: 'skill',
          preset: true,
          installedAt: Date.now(),
        }, null, 2), 'utf-8');
      }
    });
  }

  listSkills(keyword = '', category = '') {
    let files = fs.readdirSync(this.skillsDir).filter(f => f.endsWith('.yskill'));
    // 若预设被清空，自动重新安装
    if (files.length === 0) {
      try {
        this._installSkillPresets();
        files = fs.readdirSync(this.skillsDir).filter(f => f.endsWith('.yskill'));
      } catch (e) {
        console.warn('[MarketManager] 重新安装技能预设失败:', e.message);
      }
    }
    let skills = files.map(f => {
      try {
        return JSON.parse(fs.readFileSync(path.join(this.skillsDir, f), 'utf-8'));
      } catch (e) { return null; }
    }).filter(Boolean);

    if (keyword) {
      const kw = keyword.toLowerCase();
      skills = skills.filter(s =>
        s.name?.toLowerCase().includes(kw) ||
        s.description?.toLowerCase().includes(kw) ||
        (s.tags || []).some(t => t.toLowerCase().includes(kw))
      );
    }
    if (category && category !== 'all') {
      skills = skills.filter(s => s.category === category);
    }
    return skills;
  }

  getSkill(id) {
    const safeId = sanitizeId(id, 'skill_');
    const fileName = `${safeId}.yskill`;
    try {
      const filePath = safeJoin(this.skillsDir, fileName);
      if (!fs.existsSync(filePath)) return null;
      return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    } catch (e) { return null; }
  }

  installSkill(skillData) {
    if (!skillData || typeof skillData !== 'object') {
      throw new Error('无效的技能数据');
    }
    const id = sanitizeId(skillData.id, 'skill_');
    const fileName = `${id}.yskill`;
    const filePath = safeJoin(this.skillsDir, fileName);
    const data = {
      type: 'skill',
      id,
      name: safeString(skillData.name, 100) || '未命名技能',
      displayName: safeString(skillData.displayName, 100),
      description: safeString(skillData.description, 500),
      icon: safeString(skillData.icon, 20) || '⚡',
      category: safeString(skillData.category, 50),
      tags: safeArray(skillData.tags, 10).map(t => safeString(t, 30)),
      author: safeString(skillData.author, 50),
      version: safeString(skillData.version, 20) || '1.0.0',
      systemPrompt: safeString(skillData.systemPrompt, 5000),
      userPrompt: safeString(skillData.userPrompt, 2000),
      tools: safeArray(skillData.tools, 50).map(t => safeString(t, 100)),
      model: safeString(skillData.model, 50),
      temperature: typeof skillData.temperature === 'number' ? Math.max(0, Math.min(2, skillData.temperature)) : 0.7,
      installedAt: Date.now(),
      preset: false,
    };
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
    return data;
  }

  uninstallSkill(id) {
    const safeId = sanitizeId(id, 'skill_');
    const fileName = `${safeId}.yskill`;
    try {
      const filePath = safeJoin(this.skillsDir, fileName);
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
        return true;
      }
    } catch (e) {}
    return false;
  }

  exportSkill(id) {
    const skill = this.getSkill(id);
    if (!skill) return null;
    const { installedAt, preset, ...exportData } = skill;
    return exportData;
  }

  getSkillCategories() {
    const skills = this.listSkills();
    const cats = [...new Set(skills.map(s => s.category).filter(Boolean))];
    return cats;
  }

  // ============================================================
  // Agent 团队模板
  // ============================================================
  _installAgentPresets() {
    const presets = [
      {
        id: 'agent_content_team',
        name: '内容创作团队',
        icon: '📝',
        description: '专业内容创作团队，从选题到成稿一条龙',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        members: [
          { role: 'coordinator', name: '主编', prompt: '你是主编，负责内容选题规划和质量把控，协调团队完成内容创作任务。' },
          { role: 'researcher', name: '研究员', prompt: '你是资料研究员，负责收集整理相关资料和数据。' },
          { role: 'writer', name: '写手', prompt: '你是资深写手，负责撰写高质量的文章内容。' },
          { role: 'reviewer', name: '审核员', prompt: '你是审核编辑，负责内容的最终审核和润色。' },
        ],
      },
      {
        id: 'agent_dev_team',
        name: '软件开发团队',
        icon: '💻',
        description: '产品经理+程序员+测试的完整开发团队',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        members: [
          { role: 'coordinator', name: '项目经理', prompt: '你是项目经理，负责需求分析、任务拆解和进度把控。' },
          { role: 'researcher', name: '架构师', prompt: '你是技术架构师，负责技术方案设计和技术选型。' },
          { role: 'programmer', name: '程序员', prompt: '你是高级程序员，负责代码实现和技术攻关。' },
          { role: 'reviewer', name: '测试工程师', prompt: '你是测试工程师，负责代码审查和质量测试。' },
        ],
      },
      {
        id: 'agent_research_team',
        name: '市场调研团队',
        icon: '🔍',
        description: '深度调研行业、竞品、用户',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        members: [
          { role: 'coordinator', name: '调研组长', prompt: '你是调研组长，负责制定调研方案和统筹调研工作。' },
          { role: 'researcher', name: '行业研究员A', prompt: '你是行业研究员，负责行业趋势和政策分析。' },
          { role: 'researcher', name: '竞品分析师B', prompt: '你是竞品分析师，负责竞争对手的深度分析。' },
          { role: 'writer', name: '报告撰写', prompt: '你是报告撰写专家，负责将调研结果整理成专业报告。' },
        ],
      },
      {
        id: 'agent_solo',
        name: '全能助理',
        icon: '🤖',
        description: '单人全能型，什么都能干',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        members: [
          { role: 'executor', name: '全能助理', prompt: '你是一个全能AI助理，能够独立完成各种任务。遇到复杂任务时，先拆解再逐步完成。' },
        ],
      },
      {
        id: 'agent_startup',
        name: '创业合伙人',
        icon: '🚀',
        description: '从0到1帮你创业，产品+运营+技术',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        members: [
          { role: 'coordinator', name: 'CEO', prompt: '你是创业公司CEO，负责战略决策和整体方向把控。' },
          { role: 'researcher', name: '市场总监', prompt: '你是市场总监，负责市场分析、用户增长和营销策略。' },
          { role: 'programmer', name: '技术负责人', prompt: '你是技术负责人，负责产品的技术实现和架构设计。' },
          { role: 'reviewer', name: '财务顾问', prompt: '你是财务顾问，负责财务规划和商业模型验证。' },
        ],
      },
      {
        id: 'agent_seo',
        name: 'SEO优化团队',
        icon: '📈',
        description: 'SEO优化+内容营销+数据监测',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        members: [
          { role: 'coordinator', name: 'SEO主管', prompt: '你是SEO主管，负责制定SEO策略和优化方案。' },
          { role: 'researcher', name: '关键词分析师', prompt: '你是关键词分析师，负责关键词研究和竞品分析。' },
          { role: 'writer', name: '内容编辑', prompt: '你是SEO内容编辑，负责撰写优化后的内容。' },
          { role: 'reviewer', name: '数据分析师', prompt: '你是数据分析师，负责效果监测和数据报告。' },
        ],
      },
    ];

    presets.forEach(p => {
      const filePath = path.join(this.agentsDir, `${p.id}.yagent`);
      if (!fs.existsSync(filePath)) {
        fs.writeFileSync(filePath, JSON.stringify({
          ...p,
          type: 'agent-team',
          preset: true,
          installedAt: Date.now(),
        }, null, 2), 'utf-8');
      }
    });
  }

  listAgents(keyword = '') {
    let files = fs.readdirSync(this.agentsDir).filter(f => f.endsWith('.yagent'));
    if (files.length === 0) {
      try {
        this._installAgentPresets();
        files = fs.readdirSync(this.agentsDir).filter(f => f.endsWith('.yagent'));
      } catch (e) {
        console.warn('[MarketManager] 重新安装 Agent 预设失败:', e.message);
      }
    }
    let agents = files.map(f => {
      try {
        return JSON.parse(fs.readFileSync(path.join(this.agentsDir, f), 'utf-8'));
      } catch (e) { return null; }
    }).filter(Boolean);

    if (keyword) {
      const kw = keyword.toLowerCase();
      agents = agents.filter(a =>
        a.name?.toLowerCase().includes(kw) ||
        a.description?.toLowerCase().includes(kw)
      );
    }
    return agents;
  }

  getAgent(id) {
    const safeId = sanitizeId(id, 'agent_');
    const fileName = `${safeId}.yagent`;
    try {
      const filePath = safeJoin(this.agentsDir, fileName);
      if (!fs.existsSync(filePath)) return null;
      return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    } catch (e) { return null; }
  }

  installAgent(agentData) {
    if (!agentData || typeof agentData !== 'object') {
      throw new Error('无效的Agent数据');
    }
    const id = sanitizeId(agentData.id, 'agent_');
    const fileName = `${id}.yagent`;
    const filePath = safeJoin(this.agentsDir, fileName);
    const safeMembers = safeArray(agentData.members, 20).map(m => ({
      id: safeString(m.id, 50) || ('member_' + Math.random().toString(36).slice(2, 8)),
      name: safeString(m.name, 50) || '成员',
      role: safeString(m.role, 30),
      systemPrompt: safeString(m.systemPrompt, 5000),
      model: safeString(m.model, 50),
      icon: safeString(m.icon, 10),
    }));
    const data = {
      type: 'agent-team',
      id,
      name: safeString(agentData.name, 100) || '未命名团队',
      description: safeString(agentData.description, 500),
      icon: safeString(agentData.icon, 20) || '🤖',
      author: safeString(agentData.author, 50),
      version: safeString(agentData.version, 20) || '1.0.0',
      members: safeMembers,
      workflow: safeString(agentData.workflow, 500),
      installedAt: Date.now(),
      preset: false,
    };
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
    return data;
  }

  uninstallAgent(id) {
    const safeId = sanitizeId(id, 'agent_');
    const fileName = `${safeId}.yagent`;
    try {
      const filePath = safeJoin(this.agentsDir, fileName);
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
        return true;
      }
    } catch (e) {}
    return false;
  }

  exportAgent(id) {
    const agent = this.getAgent(id);
    if (!agent) return null;
    const { installedAt, preset, ...exportData } = agent;
    return exportData;
  }

  // ============================================================
  // 工作流模板
  // ============================================================
  _installWorkflowPresets() {
    const presets = [
      {
        id: 'wf_blog_pipeline',
        name: '博客文章工作流',
        icon: '📝',
        description: '选题→大纲→撰写→润色→发布',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        nodes: [
          { type: 'start', name: '开始', config: {} },
          { type: 'agent', name: '选题策划', config: { prompt: '请给出3个关于{topic}方向的文章选题' } },
          { type: 'agent', name: '大纲生成', config: { prompt: '根据选定的选题，生成详细的文章大纲' } },
          { type: 'agent', name: '内容撰写', config: { prompt: '根据大纲撰写完整文章，字数约{words}字' } },
          { type: 'agent', name: '润色优化', config: { prompt: '对文章进行润色优化，提升可读性' } },
          { type: 'end', name: '完成', config: {} },
        ],
      },
      {
        id: 'wf_code_review',
        name: '代码审查工作流',
        icon: '🔍',
        description: '自动审查代码质量、安全性、性能',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        nodes: [
          { type: 'start', name: '开始', config: {} },
          { type: 'parallel', name: '多维度审查', config: { branches: 3 } },
          { type: 'agent', name: '代码质量审查', config: { prompt: '审查代码质量和可维护性' } },
          { type: 'agent', name: '安全性审查', config: { prompt: '审查代码中的安全漏洞' } },
          { type: 'agent', name: '性能审查', config: { prompt: '审查代码性能问题' } },
          { type: 'agent', name: '汇总报告', config: { prompt: '汇总三个审查结果，生成最终报告' } },
          { type: 'end', name: '完成', config: {} },
        ],
      },
      {
        id: 'wf_social_media',
        name: '社媒内容工作流',
        icon: '📱',
        description: '一键生成多平台内容',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        nodes: [
          { type: 'start', name: '开始', config: {} },
          { type: 'agent', name: '核心文案', config: { prompt: '根据{topic}生成核心文案' } },
          { type: 'parallel', name: '多平台适配', config: { branches: 3 } },
          { type: 'agent', name: '小红书版', config: { prompt: '改写成小红书风格，加emoji和标签' } },
          { type: 'agent', name: '公众号版', config: { prompt: '改写成公众号深度长文' } },
          { type: 'agent', name: '微博版', config: { prompt: '改写成微博短文案，140字以内' } },
          { type: 'end', name: '完成', config: {} },
        ],
      },
      {
        id: 'wf_data_report',
        name: '数据分析报告',
        icon: '📊',
        description: '数据清洗→分析→可视化→报告',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        nodes: [
          { type: 'start', name: '开始', config: {} },
          { type: 'agent', name: '数据清洗', config: { prompt: '清洗和整理数据' } },
          { type: 'agent', name: '数据分析', config: { prompt: '分析数据，找出关键洞察' } },
          { type: 'agent', name: '可视化建议', config: { prompt: '给出数据可视化方案建议' } },
          { type: 'agent', name: '生成报告', config: { prompt: '撰写完整的数据分析报告' } },
          { type: 'end', name: '完成', config: {} },
        ],
      },
      {
        id: 'wf_daily_briefing',
        name: '每日早报',
        icon: '🌅',
        description: '自动生成每日资讯早报',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        nodes: [
          { type: 'start', name: '开始', config: {} },
          { type: 'delay', name: '等待', config: { delay: 0 } },
          { type: 'http', name: '获取资讯', config: { url: '', method: 'GET' } },
          { type: 'agent', name: '资讯摘要', config: { prompt: '将资讯整理成摘要' } },
          { type: 'agent', name: '生成早报', config: { prompt: '生成一份精美的每日早报' } },
          { type: 'end', name: '完成', config: {} },
        ],
      },
      {
        id: 'wf_translate_pipeline',
        name: '翻译流水线',
        icon: '🌍',
        description: '翻译→校对→润色→排版',
        version: '1.0.0',
        author: 'Y·NEX',
        preset: true,
        nodes: [
          { type: 'start', name: '开始', config: {} },
          { type: 'agent', name: '初译', config: { prompt: '将文本翻译成{lang}，保持原文风格' } },
          { type: 'agent', name: '校对', config: { prompt: '对照原文校对翻译准确性' } },
          { type: 'agent', name: '润色', config: { prompt: '对译文进行润色，使其更地道' } },
          { type: 'agent', name: '排版', config: { prompt: '对译文进行格式化排版' } },
          { type: 'end', name: '完成', config: {} },
        ],
      },
    ];

    presets.forEach(p => {
      const filePath = path.join(this.workflowsDir, `${p.id}.yflow`);
      if (!fs.existsSync(filePath)) {
        fs.writeFileSync(filePath, JSON.stringify({
          ...p,
          type: 'workflow-template',
          preset: true,
          installedAt: Date.now(),
        }, null, 2), 'utf-8');
      }
    });
  }

  listWorkflowTemplates(keyword = '') {
    let files = fs.readdirSync(this.workflowsDir).filter(f => f.endsWith('.yflow'));
    if (files.length === 0) {
      try {
        this._installWorkflowPresets();
        files = fs.readdirSync(this.workflowsDir).filter(f => f.endsWith('.yflow'));
      } catch (e) {
        console.warn('[MarketManager] 重新安装工作流预设失败:', e.message);
      }
    }
    let templates = files.map(f => {
      try {
        return JSON.parse(fs.readFileSync(path.join(this.workflowsDir, f), 'utf-8'));
      } catch (e) { return null; }
    }).filter(Boolean);

    if (keyword) {
      const kw = keyword.toLowerCase();
      templates = templates.filter(w =>
        w.name?.toLowerCase().includes(kw) ||
        w.description?.toLowerCase().includes(kw)
      );
    }
    return templates;
  }

  getWorkflowTemplate(id) {
    const safeId = sanitizeId(id, 'wf_');
    const fileName = `${safeId}.yflow`;
    try {
      const filePath = safeJoin(this.workflowsDir, fileName);
      if (!fs.existsSync(filePath)) return null;
      return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    } catch (e) { return null; }
  }

  installWorkflowTemplate(templateData) {
    if (!templateData || typeof templateData !== 'object') {
      throw new Error('无效的工作流数据');
    }
    const id = sanitizeId(templateData.id, 'wf_');
    const fileName = `${id}.yflow`;
    const filePath = safeJoin(this.workflowsDir, fileName);
    const safeNodes = safeArray(templateData.nodes, 100).map(n => ({
      id: safeString(n.id, 50) || ('node_' + Math.random().toString(36).slice(2, 8)),
      type: safeString(n.type, 50),
      name: safeString(n.name, 100),
      config: typeof n.config === 'object' ? n.config : {},
      position: n.position || { x: 0, y: 0 },
    }));
    const safeConnections = safeArray(templateData.connections, 200).map(c => ({
      id: safeString(c.id, 50),
      from: safeString(c.from, 50),
      to: safeString(c.to, 50),
      fromPort: safeString(c.fromPort, 50),
      toPort: safeString(c.toPort, 50),
    }));
    const data = {
      type: 'workflow-template',
      id,
      name: safeString(templateData.name, 100) || '未命名工作流',
      description: safeString(templateData.description, 500),
      icon: safeString(templateData.icon, 20) || '🔄',
      author: safeString(templateData.author, 50),
      version: safeString(templateData.version, 20) || '1.0.0',
      nodes: safeNodes,
      connections: safeConnections,
      variables: templateData.variables || {},
      installedAt: Date.now(),
      preset: false,
    };
    fs.writeFileSync(filePath, JSON.stringify(data, null, 2), 'utf-8');
    return data;
  }

  uninstallWorkflowTemplate(id) {
    const safeId = sanitizeId(id, 'wf_');
    const fileName = `${safeId}.yflow`;
    try {
      const filePath = safeJoin(this.workflowsDir, fileName);
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
        return true;
      }
    } catch (e) {}
    return false;
  }

  exportWorkflowTemplate(id) {
    const t = this.getWorkflowTemplate(id);
    if (!t) return null;
    const { installedAt, preset, ...exportData } = t;
    return exportData;
  }

  // ============================================================
  // 通用：从文件导入
  // ============================================================
  importFromFile(filePath) {
    try {
      const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      if (data.type === 'skill') return { type: 'skill', data: this.installSkill(data) };
      if (data.type === 'agent-team') return { type: 'agent', data: this.installAgent(data) };
      if (data.type === 'workflow-template') return { type: 'workflow', data: this.installWorkflowTemplate(data) };
      return { type: 'unknown', data };
    } catch (e) {
      return { error: e.message };
    }
  }
}

module.exports = { MarketManager };
