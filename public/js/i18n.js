/**
 * TriGen AI - Internationalization Engine (i18n)
 * 支持中英文切换，可扩展更多语言
 * v1.0 - Phase 5
 */
(function(){
  'use strict';

  // ============================================================
  // 语言定义
  // ============================================================
  const LANGUAGES = { zh: '中文', en: 'English' };

  // ============================================================
  // 翻译字典
  // ============================================================
  const TRANSLATIONS = {
    zh: {
      /* ---- 侧边栏 ---- */
      'sidebar.home': '首页',
      'sidebar.chat': '聊天',
      'sidebar.models': '模型',
      'sidebar.compare': '对比',
      'sidebar.prompts': '提示词库',
      'sidebar.knowledge': '知识库',
      'sidebar.agents': '智能体',
      'sidebar.novel': 'AI 小说',
      'sidebar.media': 'AI 漫剧',
      'sidebar.code': 'AI 编程',
      'sidebar.studio': 'AI 创作工场',
      'sidebar.music': 'AI 音乐',
      "sidebar['3d']": '3D 生成',
      'sidebar.office': '办公',
      'sidebar.brand': '品牌',
      'sidebar.market': '营销',
      'sidebar.pricing': '充值/会员',
      'sidebar.tools': '工具箱',
      'sidebar.feedback': '反馈',
      'sidebar.admin': '⚙ 管理后台',
      'sidebar.upgrade': '🔥 开通会员',
      'sidebar.online': '在线',
      'sidebar.offline': '离线',
      'sidebar.unlogin': '未登录',
      'lang.switch': '语言切换',

      /* ---- 首页 Hero ---- */
      'hero.title': 'TriGen 智能创作平台',
      'hero.subtitle': '聚合全球 300+ AI 模型，一个 TriGen 全搞定。对话顶级模型、写小说做漫剧、AI 编程创作、16 个预制智能体一键使用。',
      'hero.free_trial': '🚀 免费体验',
      'hero.view_pricing': '💎 查看套餐',
      'hero.new_user_bonus': '✨ 新用户注册即送 <span style="font-size:1rem">30积分</span> 免费体验',
      'hero.online_users': '🟢 <span id="onlineUsers">128</span> 人在线 · 📈 今日已有 <span id="todayPurchases">47</span> 人充值 · ⭐ 4.9/5 好评',
      'hero.models_count': '收录模型',
      'hero.providers_count': '模型品牌',
      'hero.today_usage': '今日使用',
      'hero.encrypted': '🔒 数据加密传输',
      'hero.local_storage': '🗝️ 对话仅本地存储',
      'hero.no_save': '📡 不保存聊天内容',

      /* ---- 模型星球 ---- */
      'planet.tag': 'TriGen · 模型星云',

      /* ---- 定价页面 ---- */
      'pricing.title': '💎 选择你的套餐',
      'pricing.subtitle': '按需选择，灵活升级。所有套餐均包含基础模型免费使用。',
      'pricing.monthly': '月度会员',
      'pricing.quarterly': '季度会员',
      'pricing.yearly': '年度会员',
      'pricing.popular': '🔥 最受欢迎',
      'pricing.per_month': '/月',
      'pricing.per_quarter': '/季',
      'pricing.per_year': '/年',
      'pricing.credits': '积分/月',
      'pricing.discount': '折扣',
      'pricing.subscribe': '立即订阅',
      'pricing.current': '当前套餐',
      'pricing.top_up': '积分充值',
      'pricing.top_up_desc': '一次性充值积分，永不过期，可以用于高级模型和特色功能。',
      'pricing.starter': '体验包',
      'pricing.standard': '标准包',
      'pricing.premium': '进阶包',
      'pricing.pro': '专业包',
      'pricing.ultimate': '旗舰包',
      'pricing.buy': '立即购买',
      'pricing.credits_unit': '积分',
      'pricing.price_table': '积分消耗明细',
      'pricing.model': '模型类型',
      'pricing.cost': '消耗积分',
      'pricing.compare_title': '为什么选择 TriGen？',
      'pricing.compare_subtitle': '对比主流 AI 平台',

      /* ---- 聊天页面 ---- */
      'chat.title': 'AI 聊天',
      'chat.placeholder': '输入你的问题...',
      'chat.send': '发送',
      'chat.clear': '清空对话',
      'chat.new_chat': '新建对话',
      'chat.thinking': '思考中...',
      'chat.error': '请求失败，请重试',
      'chat.no_history': '暂无聊天记录',
      'chat.model_select': '选择模型',

      /* ---- 通用 ---- */
      'common.loading': '加载中...',
      'common.error': '出错了',
      'common.retry': '重试',
      'common.cancel': '取消',
      'common.confirm': '确认',
      'common.save': '保存',
      'common.close': '关闭',
      'common.search': '搜索',
      'common.filter': '筛选',
      'common.copy': '复制',
      'common.copied': '已复制',
      'common.login': '登录',
      'common.register': '注册',
      'common.logout': '退出登录',
      'common.settings': '设置',
      'common.username': '用户名',
      'common.password': '密码',
      'common.email': '邮箱',
      'common.back': '返回',
      'common.next': '下一步',
      'common.done': '完成',
      'common.delete': '删除',
      'common.edit': '编辑',
      'common.download': '下载',
      'common.upload': '上传',
      'common.share': '分享',
      'common.more': '更多',
      'common.all': '全部',
      'common.none': '无',
      'common.yes': '是',
      'common.no': '否',
      'common.tips': '提示',
      'common.success': '操作成功',
      'common.fail': '操作失败',

      /* ---- 会员弹窗 ---- */
      'member.title': '🔥 TriGen 会员',
      'member.upgrade': '开通会员',
      'member.benefits': '会员权益',
      'member.daily_calls': '每日免费调用',
      'member.model_discount': '高端模型折扣',
      'member.monthly_credits': '每月赠送积分',
      'member.unlimited': '不限次数',

      /* ---- 用户设置 ---- */
      'user.settings': '👤 用户设置',
      'user.profile': '个人信息',
      'user.credits': '我的积分',
      'user.membership': '我的会员',
      'user.history': '使用历史',
      'user.api_keys': 'API 密钥',

      /* ---- 桌面端 TriGenClaw ---- */
      'desktop.title': 'TriGenClaw 桌面端',
      'desktop.download': '下载桌面端',
      'desktop.desc': 'Windows / macOS / Linux 全平台支持，更流畅的 AI 体验',
      'desktop.win': 'Windows 版',
      'desktop.mac': 'macOS 版',
      'desktop.linux': 'Linux 版',
      'desktop.size': '~97 MB',
      'desktop.features': '功能特性',
      'desktop.feature1': '离线优先，数据本地存储',
      'desktop.feature2': '系统托盘，快捷呼出',
      'desktop.feature3': '全局快捷键，效率翻倍',
      'desktop.feature4': '自动更新，永不过时',

      /* ---- AI 漫剧 ---- */
      'media.title': 'AI 漫剧创作',
      'media.input_placeholder': '输入你的故事创意，AI 将为你生成漫画/短视频...',
      'media.generate': '生成漫剧',
      'media.generating': '创作中...',
      'media.script': '分镜剧本',
      'media.panels': '分镜画面',
      'media.video': '短视频',
      'media.view_as_manga': '查看漫画',
      'media.view_as_video': '播放视频',
      'media.no_content': '还没有创作内容，输入一个故事创意开始吧',

      /* ---- 积分系统 ---- */
      'credits.balance': '积分余额',
      'credits.insufficient': '积分不足',
      'credits.recharge': '去充值',
      'credits.cost': '消耗',
      'credits.earn': '获得',
      'credits.history': '积分明细',
      'credits.daily_bonus': '每日签到',
      'credits.register_bonus': '注册赠送',
      'credits.from_admin': '管理员充值',

      /* ---- 状态消息 ---- */
      'toast.first_chat': '首次聊天不扣积分，试试吧~',
      'toast.login_required': '请先登录',
      'toast.network_error': '网络连接错误',
      'toast.copy_success': '已复制到剪贴板',

      /* ---- 落地页 ---- */
      'landing.nav_features': '功能特性',
      'landing.nav_pricing': '定价',
      'landing.nav_faq': '常见问题',
      'landing.nav_login': '登录',
      'landing.nav_start': '免费开始',
      'landing.hero_title': 'All from Three · 三生万物',
      'landing.hero_desc': '聚合 135+ AI 模型，一个输入无限可能。对话、创作、编程、设计——一个平台全部搞定。',
      'landing.hero_cta': '🚀 免费开始使用',
      'landing.hero_stats': '135+ AI 模型 · 9 大品牌 · 全球用户',
      'landing.hero_stats_section': '功能模块',
      'landing.section_features': '强大功能',
      'landing.section_pricing': '灵活定价',
      'landing.section_faq': '常见问题',
      'landing.faq1_q': '免费用户可以做什么？',
      'landing.faq1_a': '免费用户每天可使用30次基础模型对话，无需任何付费。付费用户享受更多高级模型和积分。',
      'landing.faq2_q': '如何获取积分？',
      'landing.faq2_a': '注册即送30积分，每日签到也可获得积分。高级功能需要消耗积分，您也可以直接购买积分包。',
      'landing.faq3_q': '桌面端和网页端有什么区别？',
      'landing.faq3_a': '桌面端提供离线缓存、系统托盘、全局快捷键等增强体验。功能与网页端完全同步。',
      'landing.footer': '© 2026 TriGen. All rights reserved.',
    },

    en: {
      /* ---- Sidebar ---- */
      'sidebar.home': 'Home',
      'sidebar.chat': 'Chat',
      'sidebar.models': 'Models',
      'sidebar.compare': 'Compare',
      'sidebar.prompts': 'Prompts',
      'sidebar.knowledge': 'Knowledge',
      'sidebar.agents': 'Agents',
      'sidebar.novel': 'AI Novel',
      'sidebar.media': 'AI Manga',
      'sidebar.code': 'AI Code',
      'sidebar.studio': 'AI Studio',
      'sidebar.music': 'AI Music',
      'sidebar.3d': '3D Gen',
      'sidebar.office': 'Office',
      'sidebar.brand': 'Brand',
      'sidebar.market': 'Marketing',
      'sidebar.pricing': 'Premium',
      'sidebar.tools': 'Tools',
      'sidebar.feedback': 'Feedback',
      'sidebar.admin': '⚙ Admin',
      'sidebar.upgrade': '🔥 Upgrade',
      'sidebar.online': 'Online',
      'sidebar.offline': 'Offline',
      'sidebar.unlogin': 'Not logged in',
      'lang.switch': 'Language',

      /* ---- Hero ---- */
      'hero.title': 'TriGen AI Platform',
      'hero.subtitle': 'Aggregate 300+ AI models worldwide. Chat with top models, write novels, create manga, AI coding, 16 preset agents - all in one TriGen.',
      'hero.free_trial': '🚀 Free Trial',
      'hero.view_pricing': '💎 View Plans',
      'hero.new_user_bonus': '✨ New users get <span style="font-size:1rem">30 credits</span> free trial',
      'hero.online_users': '🟢 <span id="onlineUsers">128</span> online · 📈 <span id="todayPurchases">47</span> purchased today · ⭐ 4.9/5',
      'hero.models_count': 'Models',
      'hero.providers_count': 'Providers',
      'hero.today_usage': 'Today',
      'hero.encrypted': '🔒 Encrypted',
      'hero.local_storage': '🗝️ Local Only',
      'hero.no_save': '📡 No Storage',

      /* ---- Planet ---- */
      'planet.tag': 'TriGen · Model Nebula',

      /* ---- Pricing ---- */
      'pricing.title': '💎 Choose Your Plan',
      'pricing.subtitle': 'Flexible plans for every need. All plans include free basic models.',
      'pricing.monthly': 'Monthly',
      'pricing.quarterly': 'Quarterly',
      'pricing.yearly': 'Yearly',
      'pricing.popular': '🔥 Most Popular',
      'pricing.per_month': '/mo',
      'pricing.per_quarter': '/qtr',
      'pricing.per_year': '/yr',
      'pricing.credits': 'Credits/mo',
      'pricing.discount': 'Discount',
      'pricing.subscribe': 'Subscribe',
      'pricing.current': 'Current',
      'pricing.top_up': 'Credit Packs',
      'pricing.top_up_desc': 'One-time credit purchase, never expires. Use for premium models and features.',
      'pricing.starter': 'Starter',
      'pricing.standard': 'Standard',
      'pricing.premium': 'Premium',
      'pricing.pro': 'Pro',
      'pricing.ultimate': 'Ultimate',
      'pricing.buy': 'Buy Now',
      'pricing.credits_unit': 'Credits',
      'pricing.price_table': 'Credit Usage',
      'pricing.model': 'Model Type',
      'pricing.cost': 'Cost',
      'pricing.compare_title': 'Why TriGen?',
      'pricing.compare_subtitle': 'Compare with other AI platforms',

      /* ---- Chat ---- */
      'chat.title': 'AI Chat',
      'chat.placeholder': 'Type your question...',
      'chat.send': 'Send',
      'chat.clear': 'Clear',
      'chat.new_chat': 'New Chat',
      'chat.thinking': 'Thinking...',
      'chat.error': 'Request failed, please retry',
      'chat.no_history': 'No chat history',
      'chat.model_select': 'Select model',

      /* ---- Common ---- */
      'common.loading': 'Loading...',
      'common.error': 'Error',
      'common.retry': 'Retry',
      'common.cancel': 'Cancel',
      'common.confirm': 'Confirm',
      'common.save': 'Save',
      'common.close': 'Close',
      'common.search': 'Search',
      'common.filter': 'Filter',
      'common.copy': 'Copy',
      'common.copied': 'Copied',
      'common.login': 'Login',
      'common.register': 'Register',
      'common.logout': 'Logout',
      'common.settings': 'Settings',
      'common.username': 'Username',
      'common.password': 'Password',
      'common.email': 'Email',
      'common.back': 'Back',
      'common.next': 'Next',
      'common.done': 'Done',
      'common.delete': 'Delete',
      'common.edit': 'Edit',
      'common.download': 'Download',
      'common.upload': 'Upload',
      'common.share': 'Share',
      'common.more': 'More',
      'common.all': 'All',
      'common.none': 'None',
      'common.yes': 'Yes',
      'common.no': 'No',
      'common.tips': 'Tips',
      'common.success': 'Success',
      'common.fail': 'Failed',

      /* ---- Member Modal ---- */
      'member.title': '🔥 TriGen Membership',
      'member.upgrade': 'Upgrade',
      'member.benefits': 'Benefits',
      'member.daily_calls': 'Daily calls',
      'member.model_discount': 'Model discount',
      'member.monthly_credits': 'Monthly credits',
      'member.unlimited': 'Unlimited',

      /* ---- User Settings ---- */
      'user.settings': '👤 Settings',
      'user.profile': 'Profile',
      'user.credits': 'Credits',
      'user.membership': 'Membership',
      'user.history': 'History',
      'user.api_keys': 'API Keys',

      /* ---- Desktop ---- */
      'desktop.title': 'TriGenClaw Desktop',
      'desktop.download': 'Download Desktop',
      'desktop.desc': 'Windows / macOS / Linux. Smoother AI experience.',
      'desktop.win': 'Windows',
      'desktop.mac': 'macOS',
      'desktop.linux': 'Linux',
      'desktop.size': '~97 MB',
      'desktop.features': 'Features',
      'desktop.feature1': 'Offline-first, local storage',
      'desktop.feature2': 'System tray, quick access',
      'desktop.feature3': 'Global hotkeys',
      'desktop.feature4': 'Auto-updates',

      /* ---- AI Manga ---- */
      'media.title': 'AI Manga Creator',
      'media.input_placeholder': 'Enter your story idea, AI will create manga/video...',
      'media.generate': 'Generate',
      'media.generating': 'Creating...',
      'media.script': 'Script',
      'media.panels': 'Panels',
      'media.video': 'Video',
      'media.view_as_manga': 'View Manga',
      'media.view_as_video': 'Play Video',
      'media.no_content': 'No content yet. Enter a story idea to start!',

      /* ---- Credits ---- */
      'credits.balance': 'Balance',
      'credits.insufficient': 'Insufficient credits',
      'credits.recharge': 'Recharge',
      'credits.cost': 'Cost',
      'credits.earn': 'Earned',
      'credits.history': 'History',
      'credits.daily_bonus': 'Daily bonus',
      'credits.register_bonus': 'New user bonus',
      'credits.from_admin': 'Admin recharge',

      /* ---- Toast ---- */
      'toast.first_chat': 'First chat is free, try it!',
      'toast.login_required': 'Please login first',
      'toast.network_error': 'Network error',
      'toast.copy_success': 'Copied to clipboard',

      /* ---- Landing Page ---- */
      'landing.nav_features': 'Features',
      'landing.nav_pricing': 'Pricing',
      'landing.nav_faq': 'FAQ',
      'landing.nav_login': 'Login',
      'landing.nav_start': 'Get Started Free',
      'landing.hero_title': 'All from Three · Infinite Possibilities',
      'landing.hero_desc': '135+ AI models, one input for infinite possibilities. Chat, create, code, design - all in one platform.',
      'landing.hero_cta': '🚀 Get Started Free',
      'landing.hero_stats': '135+ AI Models · 9 Brands · Global Users',
      'landing.hero_stats_section': 'Modules',
      'landing.section_features': 'Powerful Features',
      'landing.section_pricing': 'Flexible Pricing',
      'landing.section_faq': 'FAQ',
      'landing.faq1_q': 'What can free users do?',
      'landing.faq1_a': 'Free users can access basic models 30 times per day. Paid users enjoy premium models and more credits.',
      'landing.faq2_q': 'How to get credits?',
      'landing.faq2_a': '30 free credits on signup. Daily check-in also rewards credits. Premium features consume credits, or buy credit packs.',
      'landing.faq3_q': 'Desktop vs Web?',
      'landing.faq3_a': 'Desktop offers offline cache, system tray, global hotkeys. Fully synced with web version.',
      'landing.footer': '© 2026 TriGen. All rights reserved.',
    }
  };

  // ============================================================
  // 核心引擎
  // ============================================================
  let currentLang = localStorage.getItem('trigen_lang') || 'zh';

  function t(key, fallback) {
    const dict = TRANSLATIONS[currentLang];
    if (dict && dict[key] !== undefined) return dict[key];
    if (TRANSLATIONS.zh && TRANSLATIONS.zh[key] !== undefined) return TRANSLATIONS.zh[key];
    return fallback || key;
  }

  // 转换整个页面：扫描所有 data-i18n 元素
  function translatePage() {
    document.querySelectorAll('[data-i18n]').forEach(function(el) {
      const key = el.getAttribute('data-i18n');
      const translated = t(key);
      if (translated && translated !== key) {
        // 对 HTML 内容保留 innerHTML（支持富文本），否则用 innerText
        if (el.hasAttribute('data-i18n-html')) {
          el.innerHTML = translated;
        } else {
          el.innerText = translated;
        }
      }
    });

    // 更新 HTML lang
    document.documentElement.lang = currentLang === 'en' ? 'en' : 'zh-CN';

    // 触发自定义事件
    document.dispatchEvent(new CustomEvent('languageChanged', { detail: { lang: currentLang } }));
  }

  // 切换语言
  function setLanguage(lang) {
    if (!TRANSLATIONS[lang]) return;
    currentLang = lang;
    localStorage.setItem('trigen_lang', lang);
    translatePage();
  }

  // 获取当前语言
  function getLanguage() { return currentLang; }

  // 获取所有支持的语言
  function getLanguages() { return Object.keys(TRANSLATIONS); }

  // ============================================================
  // 自动翻译新插入的动态内容
  // ============================================================
  function translateElement(el) {
    if (!el) return;
    // 如果元素有 data-i18n 属性，直接翻译
    if (el.hasAttribute && el.hasAttribute('data-i18n')) {
      const key = el.getAttribute('data-i18n');
      const translated = t(key);
      if (translated && translated !== key) {
        if (el.hasAttribute('data-i18n-html')) {
          el.innerHTML = translated;
        } else {
          el.innerText = translated;
        }
      }
    }
    // 递归翻译子元素
    const children = el.querySelectorAll ? el.querySelectorAll('[data-i18n]') : [];
    children.forEach(function(child) {
      const key = child.getAttribute('data-i18n');
      const translated = t(key);
      if (translated && translated !== key) {
        if (child.hasAttribute('data-i18n-html')) {
          child.innerHTML = translated;
        } else {
          child.innerText = translated;
        }
      }
    });
  }

  // ============================================================
  // 语言切换 UI 组件
  // ============================================================
  function createLanguageSwitcher(container) {
    if (!container) return;

    // 创建下拉框容器
    const wrapper = document.createElement('div');
    wrapper.className = 'lang-switcher';
    wrapper.style.cssText = 'display:flex;align-items:center;gap:6px;padding:6px 10px;margin:0 8px 4px;border-radius:6px;background:rgba(255,255,255,0.04);';

    const label = document.createElement('span');
    label.style.cssText = 'font-size:0.65rem;opacity:0.6;white-space:nowrap;';
    label.setAttribute('data-i18n', 'lang.switch');
    label.innerText = t('lang.switch');
    wrapper.appendChild(label);

    const select = document.createElement('select');
    select.style.cssText = 'flex:1;background:transparent;border:1px solid rgba(255,255,255,0.1);border-radius:4px;color:inherit;font-size:0.72rem;padding:3px 6px;cursor:pointer;outline:none;';

    // 添加语言选项
    Object.keys(TRANSLATIONS).forEach(function(lang) {
      const opt = document.createElement('option');
      opt.value = lang;
      opt.textContent = LANGUAGES[lang] || lang;
      if (lang === currentLang) opt.selected = true;
      select.appendChild(opt);
    });

    select.addEventListener('change', function(e) {
      setLanguage(e.target.value);
    });

    wrapper.appendChild(select);
    container.appendChild(wrapper);
  }

  // ============================================================
  // 页面加载时自动初始化
  // ============================================================
  function init() {
    // 如果已经初始化过，跳过
    if (window.__trigenI18nInited) return;
    window.__trigenI18nInited = true;

    // 延迟到 DOM 加载完成
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function() {
        translatePage();
        // 在侧边栏底部注入语言切换器
        injectSwitcher();
      });
    } else {
      translatePage();
      injectSwitcher();
    }
  }

  function injectSwitcher() {
    // 寻找侧边栏底部区域
    const sidebarBottom = document.querySelector('.sidebar-bottom');
    if (sidebarBottom) {
      // 插入到在线状态上方
      const conn = sidebarBottom.querySelector('.sidebar-conn');
      const insertBefore = conn || sidebarBottom.firstChild;
      const langContainer = document.createElement('div');
      insertBefore.parentNode.insertBefore(langContainer, insertBefore);
      createLanguageSwitcher(langContainer);
    }
  }

  // ============================================================
  // 暴露全局 API
  // ============================================================
  window.__ = t;
  window.t = t;
  window.trigenI18n = {
    t: t,
    setLanguage: setLanguage,
    getLanguage: getLanguage,
    getLanguages: getLanguages,
    translatePage: translatePage,
    translateElement: translateElement,
    createLanguageSwitcher: createLanguageSwitcher,
  };

  // 自动初始化
  init();

})();
