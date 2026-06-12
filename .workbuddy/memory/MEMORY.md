# AI Nexus 项目长期记忆

## 架构
- 单HTML文件架构（~205KB），所有CSS/JS内联
- 前端部署：Netlify + j3trisheng.com
- 后端：Netlify Functions（serverless），文件在 netlify/functions/chat.mjs
- GitHub → Netlify 自动部署（git push触发）
- 36个模型配置在 chat.mjs 中，5个有真实Key（DeepSeek/Qwen/Kimi/GLM/Yi）
- localStorage存储用户数据（积分/章节/角色库/设置）

## 页面结构
16个页面：home, models, chat, compare, novel(炼字工坊), media(漫剧工厂), agents, office, brand, market, art, video, pricing, admin, feedback, terms, privacy

## 炼字工坊 (novel)
- 4标签页：大纲工坊/章节创作/炼字润色/作品管理
- 大纲系统：全书大纲→卷纲→章纲，AI生成+内联编辑
- 润色4模式：润色/去AI痕迹/扩写/缩写，左右对比视图
- 存储：nOutline(大纲JSON), nOutlineRaw(大纲文本), nch(章节数组), novelHistory

## 漫剧工厂 (media)
- 3标签页：创作/分镜板/角色库
- 批量生成：一次出分镜+角色+场景+对白
- 分镜卡片：可视化解析+景别标注
- 角色库(charLib)：支持跨集次管理

## 关键状态变量
- userCredits: 积分（localStorage 'cr'）
- novelType/novelOutline/novelChars/novelWorld/novelHistory: 小说上下文
- novelBookTitle/chapterCountWritten/totalWordsWritten: 进度
- charLibrary: 角色库数组
