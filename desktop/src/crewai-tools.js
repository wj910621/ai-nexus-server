/**
 * CrewAI 工具注册模块
 * 基于 CrewAI 开源工具灵感构建，提供 75 个内置工具定义。
 * 每个工具仅为定义（名称、描述、分类、参数、图标），不包含实际实现，
 * 实际实现由 Python 层或现有系统（如 UnifiedToolRegistry / MCP / YNEX）提供。
 *
 * 工具分类：
 *   search       - 搜索工具
 *   file         - 文件操作
 *   code         - 代码工具
 *   data         - 数据处理
 *   network      - 网络工具
 *   document     - 文档工具
 *   communication- 通信工具
 *   productivity - 生产力
 *   system       - 系统工具
 *   ai           - AI 工具
 *   database     - 数据库
 *   cloud        - 云服务
 *   devops       - DevOps
 */

'use strict';

/**
 * 内置工具定义列表
 * parameters 为参数描述数组，每项字段：name / type / description / required
 */
const CREWAI_TOOLS = [
  // ==================== 搜索工具 ====================
  {
    name: 'web_search',
    description: '在网络中搜索关键词，返回相关网页结果',
    category: 'search',
    icon: '🌐',
    parameters: [
      { name: 'query', type: 'string', description: '搜索关键词', required: true },
      { name: 'max_results', type: 'number', description: '返回结果最大数量', required: false },
      { name: 'language', type: 'string', description: '搜索语言（如 zh-CN、en）', required: false }
    ]
  },
  {
    name: 'wiki_search',
    description: '在维基百科中搜索条目并返回摘要',
    category: 'search',
    icon: '📚',
    parameters: [
      { name: 'query', type: 'string', description: '搜索关键词', required: true },
      { name: 'language', type: 'string', description: '维基语言版本（如 zh、en）', required: false },
      { name: 'max_results', type: 'number', description: '返回结果数量', required: false }
    ]
  },
  {
    name: 'news_search',
    description: '搜索新闻资讯，可按时间范围与来源过滤',
    category: 'search',
    icon: '📰',
    parameters: [
      { name: 'query', type: 'string', description: '新闻搜索关键词', required: true },
      { name: 'date_from', type: 'string', description: '起始日期（YYYY-MM-DD）', required: false },
      { name: 'date_to', type: 'string', description: '结束日期（YYYY-MM-DD）', required: false },
      { name: 'source', type: 'string', description: '新闻来源过滤', required: false }
    ]
  },
  {
    name: 'image_search',
    description: '搜索网络图片，支持尺寸与颜色过滤',
    category: 'search',
    icon: '🖼️',
    parameters: [
      { name: 'query', type: 'string', description: '图片搜索关键词', required: true },
      { name: 'count', type: 'number', description: '返回图片数量', required: false },
      { name: 'size', type: 'string', description: '图片尺寸（small/medium/large）', required: false },
      { name: 'color', type: 'string', description: '主色调过滤', required: false }
    ]
  },
  {
    name: 'video_search',
    description: '搜索网络视频资源',
    category: 'search',
    icon: '🎬',
    parameters: [
      { name: 'query', type: 'string', description: '视频搜索关键词', required: true },
      { name: 'count', type: 'number', description: '返回视频数量', required: false },
      { name: 'duration', type: 'string', description: '时长过滤（short/medium/long）', required: false }
    ]
  },
  {
    name: 'academic_search',
    description: '在学术数据库中搜索论文与文献',
    category: 'search',
    icon: '🎓',
    parameters: [
      { name: 'query', type: 'string', description: '学术搜索关键词', required: true },
      { name: 'field', type: 'string', description: '学科领域', required: false },
      { name: 'year_from', type: 'number', description: '起始年份', required: false },
      { name: 'year_to', type: 'number', description: '结束年份', required: false }
    ]
  },

  // ==================== 文件操作 ====================
  {
    name: 'read_file',
    description: '读取本地文件内容',
    category: 'file',
    icon: '📄',
    parameters: [
      { name: 'path', type: 'string', description: '文件绝对路径', required: true },
      { name: 'encoding', type: 'string', description: '文件编码（默认 utf-8）', required: false }
    ]
  },
  {
    name: 'write_file',
    description: '将内容写入本地文件',
    category: 'file',
    icon: '✏️',
    parameters: [
      { name: 'path', type: 'string', description: '目标文件路径', required: true },
      { name: 'content', type: 'string', description: '写入内容', required: true },
      { name: 'encoding', type: 'string', description: '文件编码', required: false }
    ]
  },
  {
    name: 'list_files',
    description: '列出指定目录下的文件与子目录',
    category: 'file',
    icon: '📂',
    parameters: [
      { name: 'path', type: 'string', description: '目录路径', required: true },
      { name: 'recursive', type: 'boolean', description: '是否递归列出', required: false },
      { name: 'pattern', type: 'string', description: 'glob 匹配模式', required: false }
    ]
  },
  {
    name: 'move_file',
    description: '移动或重命名文件',
    category: 'file',
    icon: '🔀',
    parameters: [
      { name: 'source', type: 'string', description: '源路径', required: true },
      { name: 'destination', type: 'string', description: '目标路径', required: true }
    ]
  },
  {
    name: 'copy_file',
    description: '复制文件到指定位置',
    category: 'file',
    icon: '📋',
    parameters: [
      { name: 'source', type: 'string', description: '源文件路径', required: true },
      { name: 'destination', type: 'string', description: '目标路径', required: true }
    ]
  },
  {
    name: 'delete_file',
    description: '删除文件或空目录',
    category: 'file',
    icon: '🗑️',
    parameters: [
      { name: 'path', type: 'string', description: '目标路径', required: true },
      { name: 'force', type: 'boolean', description: '是否强制删除', required: false }
    ]
  },
  {
    name: 'search_files',
    description: '在目录中按文件名或内容匹配搜索文件',
    category: 'file',
    icon: '🔎',
    parameters: [
      { name: 'path', type: 'string', description: '搜索根目录', required: true },
      { name: 'pattern', type: 'string', description: '文件名匹配模式', required: true },
      { name: 'content_match', type: 'string', description: '内容匹配关键词', required: false }
    ]
  },

  // ==================== 代码工具 ====================
  {
    name: 'execute_python',
    description: '在沙箱中执行 Python 代码并返回结果',
    category: 'code',
    icon: '🐍',
    parameters: [
      { name: 'code', type: 'string', description: '要执行的 Python 代码', required: true },
      { name: 'timeout', type: 'number', description: '执行超时时间（秒）', required: false }
    ]
  },
  {
    name: 'execute_javascript',
    description: '在沙箱中执行 JavaScript 代码并返回结果',
    category: 'code',
    icon: '🟨',
    parameters: [
      { name: 'code', type: 'string', description: '要执行的 JavaScript 代码', required: true },
      { name: 'timeout', type: 'number', description: '执行超时时间（秒）', required: false }
    ]
  },
  {
    name: 'execute_shell',
    description: '在系统 Shell 中执行命令',
    category: 'code',
    icon: '💻',
    parameters: [
      { name: 'command', type: 'string', description: '要执行的 Shell 命令', required: true },
      { name: 'timeout', type: 'number', description: '执行超时时间（秒）', required: false },
      { name: 'cwd', type: 'string', description: '执行目录', required: false }
    ]
  },
  {
    name: 'code_lint',
    description: '对代码文件进行静态检查',
    category: 'code',
    icon: '🧹',
    parameters: [
      { name: 'file_path', type: 'string', description: '待检查文件路径', required: true },
      { name: 'rules', type: 'array', description: '启用的规则集', required: false }
    ]
  },
  {
    name: 'code_format',
    description: '按指定风格格式化代码文件',
    category: 'code',
    icon: '🎨',
    parameters: [
      { name: 'file_path', type: 'string', description: '待格式化文件路径', required: true },
      { name: 'style', type: 'string', description: '代码风格（如 prettier、standard）', required: false }
    ]
  },
  {
    name: 'code_review_tool',
    description: '对代码进行审查并给出改进建议',
    category: 'code',
    icon: '👁️',
    parameters: [
      { name: 'file_path', type: 'string', description: '待审查文件路径', required: true },
      { name: 'focus_areas', type: 'array', description: '关注领域（安全/性能/可读性）', required: false }
    ]
  },

  // ==================== 数据处理 ====================
  {
    name: 'csv_to_json',
    description: '将 CSV 文件转换为 JSON 数组',
    category: 'data',
    icon: '🔁',
    parameters: [
      { name: 'input_path', type: 'string', description: 'CSV 输入路径', required: true },
      { name: 'output_path', type: 'string', description: 'JSON 输出路径', required: false },
      { name: 'delimiter', type: 'string', description: '分隔符（默认 ,）', required: false }
    ]
  },
  {
    name: 'json_to_csv',
    description: '将 JSON 数组转换为 CSV 文件',
    category: 'data',
    icon: '🔣',
    parameters: [
      { name: 'input_path', type: 'string', description: 'JSON 输入路径', required: true },
      { name: 'output_path', type: 'string', description: 'CSV 输出路径', required: true }
    ]
  },
  {
    name: 'parse_xml',
    description: '解析 XML 字符串并返回结构化对象',
    category: 'data',
    icon: '🕸️',
    parameters: [
      { name: 'content', type: 'string', description: 'XML 内容', required: true },
      { name: 'xpath', type: 'string', description: '可选 XPath 表达式', required: false }
    ]
  },
  {
    name: 'parse_yaml',
    description: '解析 YAML 字符串并返回结构化对象',
    category: 'data',
    icon: '📦',
    parameters: [
      { name: 'content', type: 'string', description: 'YAML 内容', required: true }
    ]
  },
  {
    name: 'data_filter',
    description: '按条件过滤数据集合',
    category: 'data',
    icon: '🔍',
    parameters: [
      { name: 'data', type: 'array', description: '待过滤数据集合', required: true },
      { name: 'condition', type: 'string', description: '过滤条件表达式', required: true },
      { name: 'field', type: 'string', description: '目标字段', required: false }
    ]
  },
  {
    name: 'data_sort',
    description: '按指定键对数据集合排序',
    category: 'data',
    icon: '📊',
    parameters: [
      { name: 'data', type: 'array', description: '待排序数据集合', required: true },
      { name: 'key', type: 'string', description: '排序字段', required: true },
      { name: 'order', type: 'string', description: '排序方向（asc/desc）', required: false }
    ]
  },
  {
    name: 'data_aggregate',
    description: '对数据集合进行分组聚合',
    category: 'data',
    icon: '📈',
    parameters: [
      { name: 'data', type: 'array', description: '待聚合数据集合', required: true },
      { name: 'group_by', type: 'string', description: '分组字段', required: true },
      { name: 'agg_func', type: 'string', description: '聚合函数（sum/avg/count）', required: true },
      { name: 'field', type: 'string', description: '聚合目标字段', required: false }
    ]
  },

  // ==================== 网络工具 ====================
  {
    name: 'fetch_url',
    description: '抓取 URL 内容并返回响应文本',
    category: 'network',
    icon: '🌐',
    parameters: [
      { name: 'url', type: 'string', description: '目标 URL', required: true },
      { name: 'method', type: 'string', description: 'HTTP 方法（默认 GET）', required: false },
      { name: 'headers', type: 'object', description: '请求头', required: false },
      { name: 'body', type: 'string', description: '请求体', required: false }
    ]
  },
  {
    name: 'download_file',
    description: '从指定 URL 下载文件到本地',
    category: 'network',
    icon: '⬇️',
    parameters: [
      { name: 'url', type: 'string', description: '下载地址', required: true },
      { name: 'destination', type: 'string', description: '本地保存路径', required: true },
      { name: 'overwrite', type: 'boolean', description: '是否覆盖已存在文件', required: false }
    ]
  },
  {
    name: 'upload_file',
    description: '将本地文件上传到指定服务端点',
    category: 'network',
    icon: '⬆️',
    parameters: [
      { name: 'file_path', type: 'string', description: '待上传文件路径', required: true },
      { name: 'url', type: 'string', description: '上传目标 URL', required: true },
      { name: 'method', type: 'string', description: 'HTTP 方法（默认 POST）', required: false },
      { name: 'headers', type: 'object', description: '请求头', required: false }
    ]
  },
  {
    name: 'ping_host',
    description: '检测主机连通性与延迟',
    category: 'network',
    icon: '📡',
    parameters: [
      { name: 'host', type: 'string', description: '目标主机名或 IP', required: true },
      { name: 'count', type: 'number', description: '探测次数', required: false },
      { name: 'timeout', type: 'number', description: '超时时间（秒）', required: false }
    ]
  },
  {
    name: 'dns_lookup',
    description: '查询域名 DNS 记录',
    category: 'network',
    icon: '🧭',
    parameters: [
      { name: 'domain', type: 'string', description: '待查询域名', required: true },
      { name: 'record_type', type: 'string', description: '记录类型（A/AAAA/MX/TXT）', required: false }
    ]
  },
  {
    name: 'http_request',
    description: '发起通用 HTTP 请求并返回完整响应',
    category: 'network',
    icon: '🔌',
    parameters: [
      { name: 'url', type: 'string', description: '目标 URL', required: true },
      { name: 'method', type: 'string', description: 'HTTP 方法', required: false },
      { name: 'headers', type: 'object', description: '请求头', required: false },
      { name: 'body', type: 'string', description: '请求体', required: false },
      { name: 'timeout', type: 'number', description: '请求超时（秒）', required: false }
    ]
  },

  // ==================== 文档工具 ====================
  {
    name: 'pdf_read',
    description: '读取 PDF 文件文本内容',
    category: 'document',
    icon: '📕',
    parameters: [
      { name: 'file_path', type: 'string', description: 'PDF 文件路径', required: true },
      { name: 'page_from', type: 'number', description: '起始页码', required: false },
      { name: 'page_to', type: 'number', description: '结束页码', required: false }
    ]
  },
  {
    name: 'pdf_write',
    description: '生成或写入 PDF 文件',
    category: 'document',
    icon: '📗',
    parameters: [
      { name: 'output_path', type: 'string', description: '输出 PDF 路径', required: true },
      { name: 'content', type: 'string', description: '写入内容', required: true },
      { name: 'template', type: 'string', description: '使用的模板名', required: false }
    ]
  },
  {
    name: 'excel_read',
    description: '读取 Excel 表格数据',
    category: 'document',
    icon: '📊',
    parameters: [
      { name: 'file_path', type: 'string', description: 'Excel 文件路径', required: true },
      { name: 'sheet', type: 'string', description: '工作表名', required: false },
      { name: 'range', type: 'string', description: '读取范围（如 A1:C10）', required: false }
    ]
  },
  {
    name: 'excel_write',
    description: '将数据写入 Excel 表格',
    category: 'document',
    icon: '📝',
    parameters: [
      { name: 'output_path', type: 'string', description: '输出 Excel 路径', required: true },
      { name: 'data', type: 'array', description: '写入的二维数据', required: true },
      { name: 'sheet_name', type: 'string', description: '工作表名', required: false }
    ]
  },
  {
    name: 'word_read',
    description: '读取 Word 文档文本',
    category: 'document',
    icon: '📘',
    parameters: [
      { name: 'file_path', type: 'string', description: 'Word 文件路径', required: true }
    ]
  },
  {
    name: 'word_write',
    description: '生成或写入 Word 文档',
    category: 'document',
    icon: '📙',
    parameters: [
      { name: 'output_path', type: 'string', description: '输出 Word 路径', required: true },
      { name: 'content', type: 'string', description: '写入内容', required: true }
    ]
  },
  {
    name: 'markdown_to_html',
    description: '将 Markdown 文本转换为 HTML',
    category: 'document',
    icon: '🔣',
    parameters: [
      { name: 'content', type: 'string', description: 'Markdown 内容', required: true },
      { name: 'options', type: 'object', description: '渲染选项', required: false }
    ]
  },

  // ==================== 通信工具 ====================
  {
    name: 'send_email',
    description: '发送电子邮件',
    category: 'communication',
    icon: '✉️',
    parameters: [
      { name: 'to', type: 'string', description: '收件人地址（多个用逗号分隔）', required: true },
      { name: 'subject', type: 'string', description: '邮件主题', required: true },
      { name: 'body', type: 'string', description: '邮件正文', required: true },
      { name: 'attachments', type: 'array', description: '附件路径列表', required: false }
    ]
  },
  {
    name: 'read_email',
    description: '读取邮箱中的邮件',
    category: 'communication',
    icon: '📧',
    parameters: [
      { name: 'folder', type: 'string', description: '邮箱文件夹（默认 INBOX）', required: false },
      { name: 'limit', type: 'number', description: '返回邮件数量', required: false },
      { name: 'unread_only', type: 'boolean', description: '是否仅返回未读', required: false }
    ]
  },
  {
    name: 'send_sms',
    description: '发送短信消息',
    category: 'communication',
    icon: '📱',
    parameters: [
      { name: 'to', type: 'string', description: '目标手机号', required: true },
      { name: 'message', type: 'string', description: '短信内容', required: true }
    ]
  },
  {
    name: 'send_notification',
    description: '发送系统通知或推送消息',
    category: 'communication',
    icon: '🔔',
    parameters: [
      { name: 'title', type: 'string', description: '通知标题', required: true },
      { name: 'message', type: 'string', description: '通知内容', required: true },
      { name: 'level', type: 'string', description: '通知级别（info/warning/error）', required: false },
      { name: 'channel', type: 'string', description: '推送渠道', required: false }
    ]
  },

  // ==================== 生产力 ====================
  {
    name: 'create_task',
    description: '创建任务并加入待办列表',
    category: 'productivity',
    icon: '✅',
    parameters: [
      { name: 'title', type: 'string', description: '任务标题', required: true },
      { name: 'description', type: 'string', description: '任务描述', required: false },
      { name: 'due_date', type: 'string', description: '截止时间', required: false },
      { name: 'priority', type: 'string', description: '优先级（low/medium/high）', required: false }
    ]
  },
  {
    name: 'update_task',
    description: '更新任务状态或字段',
    category: 'productivity',
    icon: '🔄',
    parameters: [
      { name: 'id', type: 'string', description: '任务 ID', required: true },
      { name: 'title', type: 'string', description: '新标题', required: false },
      { name: 'status', type: 'string', description: '新状态', required: false },
      { name: 'due_date', type: 'string', description: '新截止时间', required: false }
    ]
  },
  {
    name: 'create_event',
    description: '在日历中创建事件',
    category: 'productivity',
    icon: '📅',
    parameters: [
      { name: 'title', type: 'string', description: '事件标题', required: true },
      { name: 'start_time', type: 'string', description: '开始时间', required: true },
      { name: 'end_time', type: 'string', description: '结束时间', required: false },
      { name: 'location', type: 'string', description: '事件地点', required: false },
      { name: 'attendees', type: 'array', description: '参与人列表', required: false }
    ]
  },
  {
    name: 'create_note',
    description: '创建笔记并保存',
    category: 'productivity',
    icon: '📝',
    parameters: [
      { name: 'title', type: 'string', description: '笔记标题', required: true },
      { name: 'content', type: 'string', description: '笔记内容', required: true },
      { name: 'tags', type: 'array', description: '标签列表', required: false }
    ]
  },
  {
    name: 'search_notes',
    description: '按关键词或标签搜索笔记',
    category: 'productivity',
    icon: '🔎',
    parameters: [
      { name: 'query', type: 'string', description: '搜索关键词', required: true },
      { name: 'tag', type: 'string', description: '标签过滤', required: false },
      { name: 'date_from', type: 'string', description: '起始日期', required: false }
    ]
  },
  {
    name: 'set_reminder',
    description: '设置定时提醒',
    category: 'productivity',
    icon: '⏰',
    parameters: [
      { name: 'title', type: 'string', description: '提醒标题', required: true },
      { name: 'time', type: 'string', description: '提醒触发时间', required: true },
      { name: 'repeat', type: 'string', description: '重复规则（如 daily）', required: false }
    ]
  },

  // ==================== 系统工具 ====================
  {
    name: 'get_system_info',
    description: '获取系统信息（CPU/内存/磁盘等）',
    category: 'system',
    icon: '💻',
    parameters: [
      { name: 'detail_level', type: 'string', description: '详情级别（summary/full）', required: false }
    ]
  },
  {
    name: 'get_process_list',
    description: '获取系统进程列表',
    category: 'system',
    icon: '📊',
    parameters: [
      { name: 'filter', type: 'string', description: '进程名过滤', required: false },
      { name: 'sort_by', type: 'string', description: '排序字段（cpu/memory）', required: false }
    ]
  },
  {
    name: 'kill_process',
    description: '终止指定进程',
    category: 'system',
    icon: '⛔',
    parameters: [
      { name: 'pid', type: 'number', description: '进程 ID', required: false },
      { name: 'name', type: 'string', description: '进程名', required: false },
      { name: 'force', type: 'boolean', description: '是否强制终止', required: false }
    ]
  },
  {
    name: 'start_service',
    description: '启动系统服务',
    category: 'system',
    icon: '▶️',
    parameters: [
      { name: 'name', type: 'string', description: '服务名', required: true },
      { name: 'args', type: 'array', description: '启动参数', required: false }
    ]
  },
  {
    name: 'stop_service',
    description: '停止系统服务',
    category: 'system',
    icon: '⏹️',
    parameters: [
      { name: 'name', type: 'string', description: '服务名', required: true }
    ]
  },

  // ==================== AI 工具 ====================
  {
    name: 'text_to_speech',
    description: '将文本转换为语音',
    category: 'ai',
    icon: '🔊',
    parameters: [
      { name: 'text', type: 'string', description: '待转换文本', required: true },
      { name: 'voice', type: 'string', description: '音色名', required: false },
      { name: 'language', type: 'string', description: '语言', required: false },
      { name: 'speed', type: 'number', description: '语速', required: false }
    ]
  },
  {
    name: 'speech_to_text',
    description: '将语音文件转写为文本',
    category: 'ai',
    icon: '🎤',
    parameters: [
      { name: 'audio_path', type: 'string', description: '音频文件路径', required: true },
      { name: 'language', type: 'string', description: '音频语言', required: false }
    ]
  },
  {
    name: 'image_generate',
    description: '根据文本提示生成图像',
    category: 'ai',
    icon: '🎨',
    parameters: [
      { name: 'prompt', type: 'string', description: '生成提示词', required: true },
      { name: 'size', type: 'string', description: '图像尺寸', required: false },
      { name: 'count', type: 'number', description: '生成数量', required: false },
      { name: 'style', type: 'string', description: '图像风格', required: false }
    ]
  },
  {
    name: 'image_analyze',
    description: '分析图像内容并返回描述或结果',
    category: 'ai',
    icon: '👁️',
    parameters: [
      { name: 'image_path', type: 'string', description: '图像路径', required: true },
      { name: 'task', type: 'string', description: '分析任务（describe/detect/ocr）', required: false },
      { name: 'prompt', type: 'string', description: '自定义提示词', required: false }
    ]
  },
  {
    name: 'translate_text',
    description: '将文本从一种语言翻译为另一种语言',
    category: 'ai',
    icon: '🌐',
    parameters: [
      { name: 'text', type: 'string', description: '待翻译文本', required: true },
      { name: 'source_lang', type: 'string', description: '源语言', required: false },
      { name: 'target_lang', type: 'string', description: '目标语言', required: true }
    ]
  },
  {
    name: 'summarize_text',
    description: '对长文本进行摘要',
    category: 'ai',
    icon: '📋',
    parameters: [
      { name: 'text', type: 'string', description: '待摘要文本', required: true },
      { name: 'max_length', type: 'number', description: '摘要最大长度', required: false },
      { name: 'style', type: 'string', description: '摘要风格', required: false }
    ]
  },

  // ==================== 数据库 ====================
  {
    name: 'sql_query',
    description: '在关系型数据库中执行查询语句并返回结果',
    category: 'database',
    icon: '🗃️',
    parameters: [
      { name: 'connection', type: 'string', description: '数据库连接名/DSN', required: true },
      { name: 'query', type: 'string', description: 'SQL 查询语句', required: true },
      { name: 'params', type: 'array', description: '绑定参数', required: false }
    ]
  },
  {
    name: 'sql_execute',
    description: '在关系型数据库中执行写操作语句',
    category: 'database',
    icon: '🛢️',
    parameters: [
      { name: 'connection', type: 'string', description: '数据库连接名/DSN', required: true },
      { name: 'query', type: 'string', description: 'SQL 执行语句', required: true },
      { name: 'params', type: 'array', description: '绑定参数', required: false }
    ]
  },
  {
    name: 'nosql_query',
    description: '在 NoSQL 数据库中执行查询',
    category: 'database',
    icon: '🍃',
    parameters: [
      { name: 'collection', type: 'string', description: '集合名', required: true },
      { name: 'filter', type: 'object', description: '查询过滤条件', required: false },
      { name: 'projection', type: 'object', description: '字段投影', required: false },
      { name: 'limit', type: 'number', description: '返回数量上限', required: false }
    ]
  },
  {
    name: 'redis_get',
    description: '从 Redis 读取指定键的值',
    category: 'database',
    icon: '🔴',
    parameters: [
      { name: 'key', type: 'string', description: '键名', required: true }
    ]
  },
  {
    name: 'redis_set',
    description: '向 Redis 写入键值对',
    category: 'database',
    icon: '🟥',
    parameters: [
      { name: 'key', type: 'string', description: '键名', required: true },
      { name: 'value', type: 'string', description: '键值', required: true },
      { name: 'ttl', type: 'number', description: '过期时间（秒）', required: false }
    ]
  },

  // ==================== 云服务 ====================
  {
    name: 'aws_s3_upload',
    description: '将本地文件上传到 AWS S3 存储桶',
    category: 'cloud',
    icon: '☁️',
    parameters: [
      { name: 'file_path', type: 'string', description: '本地文件路径', required: true },
      { name: 'bucket', type: 'string', description: 'S3 存储桶名', required: true },
      { name: 'key', type: 'string', description: '对象键名', required: true },
      { name: 'acl', type: 'string', description: '访问权限（private/public-read）', required: false }
    ]
  },
  {
    name: 'aws_s3_download',
    description: '从 AWS S3 存储桶下载对象到本地',
    category: 'cloud',
    icon: '🌧️',
    parameters: [
      { name: 'bucket', type: 'string', description: 'S3 存储桶名', required: true },
      { name: 'key', type: 'string', description: '对象键名', required: true },
      { name: 'destination', type: 'string', description: '本地保存路径', required: true }
    ]
  },
  {
    name: 'cloud_deploy',
    description: '部署服务到云平台',
    category: 'cloud',
    icon: '🚀',
    parameters: [
      { name: 'service', type: 'string', description: '服务名', required: true },
      { name: 'image', type: 'string', description: '镜像地址', required: true },
      { name: 'env', type: 'object', description: '环境变量', required: false },
      { name: 'region', type: 'string', description: '部署区域', required: false }
    ]
  },
  {
    name: 'cloud_status',
    description: '查询云服务运行状态',
    category: 'cloud',
    icon: '📈',
    parameters: [
      { name: 'service', type: 'string', description: '服务名', required: true },
      { name: 'region', type: 'string', description: '部署区域', required: false }
    ]
  },

  // ==================== DevOps ====================
  {
    name: 'docker_build',
    description: '构建 Docker 镜像',
    category: 'devops',
    icon: '🐳',
    parameters: [
      { name: 'context', type: 'string', description: '构建上下文目录', required: true },
      { name: 'tag', type: 'string', description: '镜像标签', required: true },
      { name: 'dockerfile', type: 'string', description: 'Dockerfile 路径', required: false },
      { name: 'no_cache', type: 'boolean', description: '是否禁用缓存', required: false }
    ]
  },
  {
    name: 'docker_run',
    description: '运行 Docker 容器',
    category: 'devops',
    icon: '📦',
    parameters: [
      { name: 'image', type: 'string', description: '镜像名', required: true },
      { name: 'command', type: 'string', description: '容器内执行命令', required: false },
      { name: 'ports', type: 'array', description: '端口映射列表', required: false },
      { name: 'volumes', type: 'array', description: '卷挂载列表', required: false },
      { name: 'env', type: 'object', description: '环境变量', required: false }
    ]
  },
  {
    name: 'docker_stop',
    description: '停止并清理 Docker 容器',
    category: 'devops',
    icon: '🛑',
    parameters: [
      { name: 'container', type: 'string', description: '容器 ID 或名称', required: true },
      { name: 'force', type: 'boolean', description: '是否强制停止', required: false },
      { name: 'timeout', type: 'number', description: '停止超时（秒）', required: false }
    ]
  },
  {
    name: 'git_log',
    description: '查看 Git 提交历史',
    category: 'devops',
    icon: '📜',
    parameters: [
      { name: 'repo', type: 'string', description: '仓库路径', required: true },
      { name: 'limit', type: 'number', description: '返回条数', required: false },
      { name: 'author', type: 'string', description: '作者过滤', required: false },
      { name: 'since', type: 'string', description: '起始时间', required: false }
    ]
  },
  {
    name: 'git_diff',
    description: '查看 Git 仓库差异',
    category: 'devops',
    icon: '⚖️',
    parameters: [
      { name: 'repo', type: 'string', description: '仓库路径', required: true },
      { name: 'file', type: 'string', description: '指定文件路径', required: false },
      { name: 'ref_a', type: 'string', description: '比较起始引用', required: false },
      { name: 'ref_b', type: 'string', description: '比较目标引用', required: false }
    ]
  },
  {
    name: 'git_branch',
    description: '管理 Git 分支（列出/创建/删除/切换）',
    category: 'devops',
    icon: '🌿',
    parameters: [
      { name: 'repo', type: 'string', description: '仓库路径', required: true },
      { name: 'action', type: 'string', description: '操作类型（list/create/delete/checkout）', required: true },
      { name: 'name', type: 'string', description: '分支名', required: false }
    ]
  }
];

/**
 * CrewAI 工具集
 * 提供工具定义的访问、查询与统一注册能力。
 * 工具本身不包含实际实现，实际执行由外部注册表（UnifiedToolRegistry 等）路由到
 * Python 层、MCP 服务或 YNEX 技能完成。
 */
class CrewAITools {
  constructor() {
    this.tools = CREWAI_TOOLS;
  }

  /**
   * 获取全部工具定义
   */
  all() {
    return this.tools;
  }

  /**
   * 工具数量
   */
  count() {
    return this.tools.length;
  }

  /**
   * 按名称获取工具定义
   */
  getTool(name) {
    return this.tools.find(t => t.name === name) || null;
  }

  /**
   * 按分类列出工具
   */
  listByCategory(category) {
    return this.tools.filter(t => t.category === category);
  }

  /**
   * 按关键词搜索工具（在 name 与 description 中匹配）
   */
  search(keyword) {
    const q = String(keyword || '').toLowerCase();
    if (!q) return [];
    return this.tools.filter(t =>
      t.name.toLowerCase().includes(q) ||
      (t.description || '').toLowerCase().includes(q)
    );
  }

  /**
   * 列出所有分类及统计信息
   */
  categories() {
    const map = new Map();
    for (const t of this.tools) {
      const c = t.category;
      if (!map.has(c)) {
        map.set(c, { name: c, count: 0, icon: t.icon || '🔧' });
      }
      map.get(c).count++;
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count);
  }

  /**
   * 将所有工具注册到统一工具注册表
   * 兼容 UnifiedToolRegistry（tools 为 Map，set 方法接受对象），
   * 也兼容其它具备 register/add 方法或数组形式的注册表。
   * @param {Object} registry 统一工具注册表实例
   * @returns {number} 成功注册的工具数量
   */
  registerAll(registry) {
    if (!registry) {
      console.warn('[CrewAITools] registerAll: 未提供注册表实例');
      return 0;
    }

    let success = 0;
    for (const tool of this.tools) {
      const toolKey = `crewai_${tool.name}`;
      const entry = {
        name: toolKey,
        displayName: tool.name,
        description: tool.description,
        category: tool.category,
        source: 'crewai',
        parameters: tool.parameters || [],
        icon: tool.icon || '🔧',
      };

      try {
        // 优先兼容 UnifiedToolRegistry：tools 字段为 Map，调用其 set 方法
        if (registry.tools instanceof Map && typeof registry.tools.set === 'function') {
          registry.tools.set(toolKey, entry);
        } else if (typeof registry.register === 'function') {
          registry.register(toolKey, entry);
        } else if (typeof registry.add === 'function') {
          registry.add(entry);
        } else if (Array.isArray(registry.tools) && typeof registry.tools.push === 'function') {
          registry.tools.push(entry);
        } else if (typeof registry.set === 'function') {
          registry.set(toolKey, entry);
        } else {
          console.warn(`[CrewAITools] 无法识别的注册表类型，跳过工具: ${tool.name}`);
          continue;
        }
        success++;
      } catch (e) {
        console.warn(`[CrewAITools] 注册工具 ${tool.name} 失败: ${e.message}`);
      }
    }

    if (typeof registry.sources !== 'undefined') {
      if (registry.sources instanceof Map) {
        registry.sources.set('crewai', { name: 'CrewAI工具', count: success });
      } else if (registry.sources && typeof registry.sources === 'object' && !Array.isArray(registry.sources)) {
        registry.sources.crewai = { name: 'CrewAI工具', count: success };
      }
    }

    console.log(`[CrewAITools] 已注册 ${success}/${this.tools.length} 个工具到统一注册表`);
    return success;
  }
}

module.exports = { CrewAITools };
