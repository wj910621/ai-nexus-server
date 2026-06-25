'use strict';
// === Chat ===

// 当前聊天模式
let CHAT_MODE = 'chat'; // chat | explore | plan | code

// 初始化聊天模型列表
function initChatModels(){
  const list=document.getElementById('chatModelList');
  if(list)list.innerHTML=models.filter(m=>!m.hidden).map(m=>`<label class="model-checkbox" style="display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;cursor:pointer;margin-bottom:4px;font-size:0.8rem;transition:all 0.2s"><input type="checkbox" value="${m.id}" ${m.featured?'checked':''}><span>${m.name}</span>${getModelCostLabel(m.id)}</label>`).join('');
}

// 初始化会话系统
async function initSession() {
  if (window.SessionSystem) {
    await SessionSystem.init();
    // 尝试恢复上次会话
    const threads = SessionSystem.list();
    if (threads.length > 0) {
      await SessionSystem.load(threads[0].id);
    }
  }
}

// 保存消息到会话
function saveToSession(role, content, metadata = {}) {
  if (window.SessionSystem && SessionSystem.getHistory) {
    SessionSystem.addMessage(role, content, metadata);
  }
}
async function sendChatMessage(){
  const msg=document.getElementById('chatInput').value.trim();if(!msg)return;

  // Agent 模式：调用 Agent 引擎
  if (AGENT_MODE) {
    return await sendAgentMessage(msg);
  }

  // 探索模式：使用只读探索 Agent
  if (CHAT_MODE === 'explore') {
    return await sendExploreMessage(msg);
  }

  // 规划模式：先制定计划再执行
  if (CHAT_MODE === 'plan') {
    return await sendPlanMessage(msg);
  }

  const selList=document.getElementById('chatModelList');
  const sel=selList?[...selList.querySelectorAll('input:checked')].map(cb=>cb.value):['deepseekv3','qwen3'];
  if(!sel.length){showToast('请在右侧面板选择模型');return}
  // 取所选模型中最高的积分消耗
  const maxCost=Math.max(...sel.map(id=>getModelCost(id)));
  if(maxCost>0&&!spendCredits(maxCost,true))return;
  const md=document.getElementById('chatMessages');if(md.querySelector('[data-p]'))md.innerHTML='';
  md.innerHTML+=`<div class="chat-msg user"><div class="chat-msg-header"><span class="chat-msg-model">你</span></div><div class="chat-msg-content">${escapeHtml(msg)}</div></div>`;
  document.getElementById('chatInput').value='';const btn=document.getElementById('btnSend');btn.disabled=true;

  // 构建 RAG 增强 system prompt（使用新的提示词系统）
  const ragSysPrompt = await buildRAGSystemPrompt(msg);

  const ps=sel.map(async (id,i)=>{
    const m=models.find(x=>x.id===id);if(!m)return;
    const pid='m-'+id+'-'+i+'-'+Date.now();
    md.innerHTML+=`<div class="chat-msg" id="${pid}"><div class="chat-msg-header"><div class="chat-msg-avatar" style="background:${m.avatar}">${m.name[0]}</div><span class="chat-msg-model">${m.name}</span><span style="margin-left:auto;font-size:0.7rem;color:var(--text-secondary);cursor:pointer;opacity:0.5" title="举报此回复" onclick="event.stopPropagation();reportContent('${pid}','${escapeAttr(m.name)}')">⚠️</span></div><div class="chat-msg-content"><span class="spinner"></span>思考中…</div></div>`;
    md.scrollTop=md.scrollHeight;
    try{
      let r=await callModelAPI(id,msg,ragSysPrompt);
      // 多平台自动容灾切换：主渠道失败时自动切换到备用渠道
      const backup=m.backup;
      if((r.simulated||r.error)&&backup){
        const backupModel=models.find(x=>x.id===backup);
        r=await callModelAPI(backup,msg,ragSysPrompt);
        if(r&&!r.simulated&&!r.error){
        }
      }
      const el=document.getElementById(pid);if(el){el.querySelector('.chat-msg-content').innerHTML=escapeHtml(r.content);if(r.simulated)el.querySelector('.chat-msg-content').style.opacity='0.6'}
    }catch(e){const el=document.getElementById(pid);if(el)el.querySelector('.chat-msg-content').innerHTML=`<span style="color:var(--red)">❌ ${escapeHtml(e.message)}</span>`}
    md.scrollTop=md.scrollHeight;
  });
  await Promise.all(ps);btn.disabled=false;
}

/**
 * Agent 模式发送消息 — 使用 ReAct 循环引擎（SSE 流式）
 */
async function sendAgentMessage(msg) {
  const md = document.getElementById('chatMessages');
  if (md.querySelector('[data-p]')) md.innerHTML = '';
  md.innerHTML += `<div class="chat-msg user"><div class="chat-msg-header"><span class="chat-msg-model">你</span></div><div class="chat-msg-content">${escapeHtml(msg)}</div></div>`;

  const pid = 'agent-' + Date.now();
  const container = document.createElement('div');
  container.className = 'chat-msg';
  container.id = pid;
  container.innerHTML = `<div class="chat-msg-header"><div class="chat-msg-avatar" style="background:linear-gradient(135deg,#14b8a6,#06b6d4)">A</div><span class="chat-msg-model">🤖 Agent</span></div><div class="chat-msg-content" style="white-space:pre-wrap"><span class="spinner"></span>思考中…</div>`;
  md.appendChild(container);
  md.scrollTop = md.scrollHeight;

  document.getElementById('chatInput').value = '';
  const btn = document.getElementById('btnSend');
  btn.disabled = true;

  let planHtml = '';
  let currentContentEl = null;

  try {
    // 先获取任务计划
    const planRes = await fetch(API_BASE + '/api/agent/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task: msg, model: 'deepseekv3' })
    });
    const planData = await planRes.json();
    
    if (planData.ok && planData.plan && planData.plan.steps) {
      planHtml = '<div style="font-size:0.75rem;background:rgba(20,184,166,0.1);border-radius:8px;padding:10px;margin:8px 0;border:1px solid rgba(20,184,166,0.2)">📋 <b>计划</b><br>';
      planData.plan.steps.forEach((s, i) => {
        planHtml += `  ${i+1}. ${s.description}<br>`;
      });
      planHtml += '</div>';
    }

    // 空容器占位
    let sseHtml = planHtml + '<div id="agentSteps' + pid + '"></div><div id="agentAnswer' + pid + '" style="font-size:0.9rem;line-height:1.7;margin-top:8px"></div>';
    const el = document.getElementById(pid);
    if (el) el.querySelector('.chat-msg-content').innerHTML = sseHtml;
    currentContentEl = document.getElementById('agentAnswer' + pid);
    const stepsEl = document.getElementById('agentSteps' + pid);

    // 调用流式 Agent 引擎
    const res = await fetch(API_BASE + '/api/agent/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task: msg, model: 'deepseekv3', maxIterations: 10 })
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let iterationCount = 0;
    let stepLog = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop(); // 保留最后一个不完整的行

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const dataStr = line.substring(6).trim();
        if (!dataStr) continue;

        try {
          const evt = JSON.parse(dataStr);

          if (evt.type === 'thought') {
            // Agent 正在思考/执行工具
            if (stepsEl) {
              stepLog += `<div style="padding:4px 0;font-size:0.78rem;color:var(--cyan)">🤔 思考 → <b>${escapeHtml(evt.action||'分析')}</b></div>`;
              stepsEl.innerHTML = '<div style="font-size:0.7rem;color:var(--text-secondary);margin:8px 0;padding:8px;background:rgba(255,255,255,0.03);border-radius:6px">' + stepLog + '</div>';
            }
          } else if (evt.type === 'observation') {
            // 工具执行结果
            if (stepsEl) {
              const resultStr = JSON.stringify(evt.result||{}).substring(0, 80);
              stepLog += `<div style="padding:4px 0;font-size:0.75rem;color:var(--green)">  ✅ ${escapeHtml(evt.action)} → ${escapeHtml(resultStr)}</div>`;
              stepsEl.innerHTML = '<div style="font-size:0.7rem;color:var(--text-secondary);margin:8px 0;padding:8px;background:rgba(255,255,255,0.03);border-radius:6px">' + stepLog + '</div>';
            }
            iterationCount++;
          } else if (evt.type === 'final') {
            // 最终回答
            if (currentContentEl) {
              currentContentEl.innerHTML = escapeHtml(evt.content);
            }
          } else if (evt.type === 'done') {
            // 完成
            if (currentContentEl && evt.answer) {
              currentContentEl.innerHTML = escapeHtml(evt.answer);
            }
            if (stepsEl && evt.iterations) {
              stepLog += `<div style="padding:4px 0;font-size:0.65rem;color:var(--text-secondary);border-top:1px solid rgba(255,255,255,0.05);margin-top:4px">⚡ 执行 ${evt.iterations} 步</div>`;
              stepsEl.innerHTML = '<div style="font-size:0.7rem;color:var(--text-secondary);margin:8px 0;padding:8px;background:rgba(255,255,255,0.03);border-radius:6px">' + stepLog + '</div>';
            }
          } else if (evt.type === 'error') {
            if (currentContentEl) currentContentEl.innerHTML = `<span style="color:var(--red)">❌ ${escapeHtml(evt.error)}</span>`;
          }
        } catch(e) { /* skip parse errors */ }
      }
    }
  } catch (e) {
    const el = document.getElementById(pid);
    if (el) el.querySelector('.chat-msg-content').innerHTML = `<span style="color:var(--red)">❌ ${escapeHtml(e.message)}</span>`;
  }

  btn.disabled = false;
  md.scrollTop = md.scrollHeight;
}
function escapeHtml(t){const d=document.createElement('div');d.textContent=t;return d.innerHTML}
function escapeAttr(t){return (t||'').replace(/"/g,'&quot;').replace(/'/g,'&#39;')}
function reportContent(pid,modelName){
  const el=document.getElementById(pid);if(!el)return;
  const content=el.querySelector('.chat-msg-content')?.textContent?.substring(0,300)||'';
  const reason=prompt(`举报来自 ${modelName} 的回复：\n\n"${content.substring(0,80)}..."\n\n请选择或输入举报原因：\n1.虚假信息 2.有害内容 3.侵权内容 4.其他（请描述）`);
  if(!reason)return;
  const r=JSON.parse(localStorage.getItem('reports')||'[]');
  r.unshift({pid,model:modelName,reason,content:content.substring(0,200),time:new Date().toISOString(),user:currentUser?currentUser.username:'游客'});
  localStorage.setItem('reports',JSON.stringify(r.slice(0,50)));
  el.querySelector('.chat-msg-content').innerHTML='<span style="color:var(--orange)">⚠️ 此内容已被举报，我们将在24小时内审核处理。</span>';
  showToast('✅ 举报已提交，感谢你的监督');
}

async function callModelAPI(modelId,question,sysPrompt){
  const msgs=sysPrompt?[{role:'system',content:sysPrompt},{role:'user',content:question}]:[{role:'user',content:question}];
  const m=models.find(x=>x.id===modelId);
  const body={model:modelId,messages:msgs};
  if(m&&m.rawModel) body.rawModel=m.rawModel;
  try{
    const r=await fetch(API_BASE+'/api/chat',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+authToken},body:JSON.stringify(body)});
    if(r.ok) return await r.json();
    const errBody=await r.json().catch(()=>({}));
    const errMsg=errBody?.error?.message||errBody?.error||`服务器错误 ${r.status}`;
    return {model:modelId,content:`❌ ${errMsg}`,simulated:true,error:errMsg};
  }catch(e){
    return {model:modelId,content:`❌ 网络连接失败：${e.message}`,simulated:true,error:e.message};
  }
}

// ============================================================
// RAG 知识增强系统
// ============================================================
let RAG_ENABLED = localStorage.getItem('ragEnabled')!=='false'; // 默认开启

// 平台级 system prompt — 每次对话自动注入
const PLATFORM_SYSTEM_PROMPT = [
  '你是 TriGen 平台的 AI 助手。TriGen 是一个智能创作平台，聚合全球顶尖大语言模型，提供聊天、写作、绘图、视频、3D、音乐等全方位 AI 创作服务。',
  '',
  '【TriGen 核心能力】',
  '- 多模型聊天：同时对话多个模型，直观对比回答',
  '- AI 小说：六步创作流程，支持百万字长篇不崩人设',
  '- AI 漫剧：小说转漫画分镜脚本',
  '- 创作工场：文字生成图片、视频',
  '- 3D 模型生成：文字/图片转 3D 模型',
  '- AI 音乐：输入歌词一键生成歌曲',
  '- 智能办公：工作总结、PPT 大纲、邮件等',
  '- 品牌营销：命名、Slogan、小红书、公众号文案',
  '- RAG 知识增强：基于平台知识库的智能回答',
  '- 提示词库：50+ 专业写作工具',
  '',
  '【回答规范】',
  '- 直接回答，不回避',
  '- 推理过程展示完整逻辑链',
  '- 不确定的明确说"不确定"，不编造',
  '- 简洁完整，避免废话',
  '- 不提及底层技术、API、模型供应商',
  '',
  '【通信风格】(基于 Claude Code 设计)',
  '- 首次行动：一句话说清要做什么',
  '- 工作更新：关键节点简短说明（发现什么、转向、障碍）',
  '- 结束汇报：一两句话总结（做了什么、下一步）',
  '- 代码中默认不写注释，最多一行',
  '- 不主动创建文档文件',
  '',
  '【安全规范】',
  '- 不可逆操作先确认',
  '- 删除/覆盖前检查内容',
  '- 不引入安全漏洞（注入、XSS等）',
  '- 不协助恶意活动'
].join('\n');

// RAG 检索 + system prompt 构建
async function buildRAGSystemPrompt(userQuery){
  let sysPrompt = PLATFORM_SYSTEM_PROMPT;

  if(!RAG_ENABLED) return sysPrompt;

  try {
    const r = await fetch(API_BASE+'/api/knowledge/search', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({ query: userQuery, topK: 5 })
    });
    const data = await r.json();

    if(data.ok && data.results && data.results.length>0){
      const ragContext = data.results.map((item,i) =>
        '【知识片段'+(i+1)+'】'+item.title+'\n'+item.content
      ).join('\n\n');

      sysPrompt += '\n\n【TriGen 知识库】（优先参考以下信息回答）\n' + ragContext;

      const st = document.getElementById('ragStatus');
      if(st){ st.style.display='inline'; st.textContent = '已匹配 '+data.matched+' 条知识'; }
    } else {
      const st = document.getElementById('ragStatus');
      if(st) st.style.display='none';
    }
  } catch(e) {
    // RAG 检索失败不影响主流程
  }

  return sysPrompt;
}

// 初始化 RAG 开关
document.addEventListener('DOMContentLoaded', ()=>{
  const toggle = document.getElementById('ragToggle');
  if(toggle) toggle.checked = RAG_ENABLED;
});

// ============================================================
// 知识库管理（与后端同步）
// ============================================================
async function openKnowledgeManager(){
  document.getElementById('knowledgeManager').style.display='block';
  document.getElementById('kmEditor').style.display='none';
  await renderKnowledgeManager();
}

async function renderKnowledgeManager(){
  const search = (document.getElementById('kmSearchInput')?.value||'').toLowerCase();
  const category = document.getElementById('kmCategoryFilter')?.value||'';

  try {
    const url = API_BASE+'/api/knowledge'+(category?'?category='+encodeURIComponent(category):'');
    const r = await fetch(url);
    const data = await r.json();

    const catSel = document.getElementById('kmCategoryFilter');
    const currentVal = catSel.value;
    catSel.innerHTML = '<option value="">全部分类</option>' +
      (data.categories||[]).map(c => '<option value="'+c+'" '+(c===currentVal?'selected':'')+'>'+c+'</option>').join('');

    let items = data.items||[];
    if(search) items = items.filter(i =>
      i.title.toLowerCase().includes(search) ||
      i.content.toLowerCase().includes(search) ||
      (i.tags||'').toLowerCase().includes(search)
    );

    document.getElementById('kmStats').textContent = items.length+' 条知识';

    const list = document.getElementById('kmList');
    if(!items.length){
      list.innerHTML = '<div style="text-align:center;color:var(--text-secondary);padding:40px"><div style="font-size:2rem">📭</div><p>还没有知识条目。点击"+ 新建"添加第一条。</p></div>';
      return;
    }

    list.innerHTML = items.map(item => {
      let tagsHTML = '';
      if(item.tags){
        tagsHTML = '<div style="margin-top:4px">'+item.tags.split(',').filter(Boolean).map(t=>
          '<span style="font-size:0.65rem;background:var(--cyan-light);color:var(--cyan);padding:1px 6px;border-radius:3px;margin-right:4px">'+escapeHtml(t.trim())+'</span>'
        ).join('')+'</div>';
      }
      return '<div style="padding:10px 12px;border-radius:8px;border:1px solid var(--border);margin-bottom:6px;cursor:pointer;transition:all 0.2s" onmouseover="this.style.borderColor=\'var(--accent)\'" onmouseout="this.style.borderColor=\'var(--border)\'" onclick="knowledgeEdit('+item.id+')">'
        +'<div style="display:flex;justify-content:space-between;align-items:center">'
        +'<span style="font-weight:600;font-size:0.85rem">'+escapeHtml(item.title)+'</span>'
        +'<span style="font-size:0.7rem;color:var(--text-secondary);background:var(--accent-soft);padding:2px 8px;border-radius:4px">'+escapeHtml(item.category||'general')+'</span>'
        +'</div>'
        +'<div style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+escapeHtml(item.content.substring(0,100))+'</div>'
        +tagsHTML+'</div>';
    }).join('');
  } catch(e) {
    console.error('Knowledge load error:', e);
  }
}

async function knowledgeEdit(id){
  try {
    const r = await fetch(API_BASE+'/api/knowledge/'+id);
    const data = await r.json();
    if(!data.ok||!data.item) return;
    const item = data.item;
    document.getElementById('kmEditId').value = item.id;
    document.getElementById('kmEditTitle').value = item.title;
    document.getElementById('kmEditContent').value = item.content;
    document.getElementById('kmEditCategory').value = item.category||'';
    document.getElementById('kmEditTags').value = item.tags||'';
    document.getElementById('kmEditor').style.display='block';
    document.getElementById('kmDeleteBtn').style.display='inline-block';
    document.getElementById('kmEditor').scrollIntoView({behavior:'smooth'});
  } catch(e) { console.error(e); }
}

function knowledgeAddNew(){
  document.getElementById('kmEditId').value = '';
  document.getElementById('kmEditTitle').value = '';
  document.getElementById('kmEditContent').value = '';
  document.getElementById('kmEditCategory').value = 'general';
  document.getElementById('kmEditTags').value = '';
  document.getElementById('kmEditor').style.display='block';
  document.getElementById('kmDeleteBtn').style.display='none';
  document.getElementById('kmEditor').scrollIntoView({behavior:'smooth'});
}

async function knowledgeSave(){
  const id = document.getElementById('kmEditId').value;
  const title = document.getElementById('kmEditTitle').value.trim();
  const content = document.getElementById('kmEditContent').value.trim();
  const category = document.getElementById('kmEditCategory').value.trim()||'general';
  const tags = document.getElementById('kmEditTags').value.trim();

  if(!title||!content){ showToast('标题和内容必填'); return; }

  try {
    const method = id ? 'PUT' : 'POST';
    const url = id ? API_BASE+'/api/knowledge/'+id : API_BASE+'/api/knowledge';
    const r = await fetch(url, {
      method,
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({title,content,category,tags})
    });
    const data = await r.json();
    if(data.ok){
      showToast(id?'已更新':'已创建');
      document.getElementById('kmEditor').style.display='none';
      await renderKnowledgeManager();
    } else {
      showToast('保存失败: '+(data.error||''));
    }
  } catch(e) { showToast('保存失败: '+e.message); }
}

async function knowledgeDelete(){
  const id = document.getElementById('kmEditId').value;
  if(!id||!confirm('确定删除此知识条目？')) return;

  try {
    const r = await fetch(API_BASE+'/api/knowledge/'+id, { method:'DELETE' });
    const data = await r.json();
    if(data.ok){
      showToast('已删除');
      document.getElementById('kmEditor').style.display='none';
      await renderKnowledgeManager();
    }
  } catch(e) { showToast('删除失败: '+e.message); }
}

// === Compare ===
function initCompareModels(){updateCompareLayout()}
function updateCompareLayout(){
  const colsEl=document.getElementById('colSelect');const cols=colsEl?parseInt(colsEl.value):2;
  const g=document.getElementById('compareGrid');g.className='compare-grid cols-'+cols;g.innerHTML='';
  const defs=['gpt4o','deepseekv3','qwen3','kimi2'];
  for(let i=0;i<cols;i++){
    const dm=models.find(m=>m.id===defs[i]);
    g.innerHTML+=`<div class="compare-panel"><div class="compare-panel-header"><div class="compare-panel-avatar" style="background:${dm.avatar}">${dm.name[0]}</div><select class="col-select" style="flex:1" onchange="updateCompareModel(this,${i})">${models.map(m=>`<option value="${m.id}" ${m.id===defs[i]?'selected':''}>${m.name}</option>`).join('')}</select></div><div class="compare-panel-content" id="compareContent${i}">选模型，输问题，点对比</div></div>`;
  }
}
function updateCompareModel(s,i){const m=models.find(x=>x.id===s.value);const h=s.parentElement;const a=h.querySelector('.compare-panel-avatar');if(a){a.style.background=m.avatar;a.textContent=m.name[0]}}
async function runCompare(){
  const p=document.getElementById('comparePrompt').value.trim();if(!p){showToast('输入问题');return}
  const colsEl=document.getElementById('colSelect');const cols=colsEl?parseInt(colsEl.value):2;
  const ps=[];
  for(let i=0;i<cols;i++){
    const c=document.getElementById('compareContent'+i);c.innerHTML='<span class="spinner"></span>';const s=document.querySelectorAll('#compareGrid select')[i];
    ps.push(callModelAPI(s.value,p,'你是客观公正的AI。回答要：1. 直接回答问题，不回避 2. 需要推理的展示逻辑链 3. 不确定的明确说"不确定" 4. 尽量简洁但完整').then(r=>{c.innerHTML=escapeHtml(r.content);if(r.simulated)c.style.opacity='0.6'}).catch(e=>{c.innerHTML=`❌ ${e.message}`}));
  }
  await Promise.all(ps);
}
function setComparePrompt(t){document.getElementById('comparePrompt').value=t;runCompare()}

// ============================================================
// 探索模式发送消息（只读代码搜索）
// ============================================================
async function sendExploreMessage(msg) {
  const md = document.getElementById('chatMessages');
  if (md.querySelector('[data-p]')) md.innerHTML = '';

  md.innerHTML += `<div class="chat-msg user"><div class="chat-msg-header"><span class="chat-msg-model">你</span></div><div class="chat-msg-content">${escapeHtml(msg)}</div></div>`;

  const pid = 'explore-' + Date.now();
  const container = document.createElement('div');
  container.className = 'chat-msg';
  container.id = pid;
  container.innerHTML = `<div class="chat-msg-header"><div class="chat-msg-avatar" style="background:linear-gradient(135deg,#10b981,#06b6d4)">🔍</div><span class="chat-msg-model">代码探索</span></div><div class="chat-msg-content" style="white-space:pre-wrap"><span class="spinner"></span>正在分析代码...</div>`;
  md.appendChild(container);
  md.scrollTop = md.scrollHeight;

  document.getElementById('chatInput').value = '';
  const btn = document.getElementById('btnSend');
  if (btn) btn.disabled = true;

  try {
    const explorePrompt = `你是代码探索专家，只进行只读搜索。

【工作模式】
- 仅搜索和分析代码，不进行任何修改
- 禁止创建、修改、删除文件
- 允许的操作：grep、find、cat、ls、git status/diff

【搜索策略】
- 快速定位：glob 模式匹配文件
- 深度搜索：正则搜索关键词
- 多策略并行：同时尝试多种方式

【输出规范】
- 报告简洁，只说明关键发现
- 指出文件路径和代码位置
- 不创建任何文件

用户问题：${msg}

请直接回答代码位置和分析结果。`;

    const r = await callModelAPI('deepseekv3', msg, explorePrompt);

    const el = document.getElementById(pid);
    if (el) {
      el.querySelector('.chat-msg-content').innerHTML = escapeHtml(r.content);
    }
  } catch(e) {
    const el = document.getElementById(pid);
    if (el) {
      el.querySelector('.chat-msg-content').innerHTML = `<span style="color:var(--red)">❌ ${escapeHtml(e.message)}</span>`;
    }
  }

  if (btn) btn.disabled = false;
}

// ============================================================
// 规划模式发送消息（先计划再执行）
// ============================================================
async function sendPlanMessage(msg) {
  const md = document.getElementById('chatMessages');
  if (md.querySelector('[data-p]')) md.innerHTML = '';

  md.innerHTML += `<div class="chat-msg user"><div class="chat-msg-header"><span class="chat-msg-model">你</span></div><div class="chat-msg-content">${escapeHtml(msg)}</div></div>`;

  const pid = 'plan-' + Date.now();
  const container = document.createElement('div');
  container.className = 'chat-msg';
  container.id = pid;
  container.innerHTML = `<div class="chat-msg-header"><div class="chat-msg-avatar" style="background:linear-gradient(135deg,#f59e0b,#ef4444)">📋</div><span class="chat-msg-model">任务规划</span></div><div class="chat-msg-content" style="white-space:pre-wrap"><span class="spinner"></span>正在分析并制定计划...</div>`;
  md.appendChild(container);
  md.scrollTop = md.scrollHeight;

  document.getElementById('chatInput').value = '';
  const btn = document.getElementById('btnSend');
  if (btn) btn.disabled = true;

  try {
    const planPrompt = `你是任务规划专家，帮助分析需求并制定执行计划。

【规划流程】
1. 理解需求：明确目标、约束、优先级
2. 分析可行性：评估技术难度、风险、资源
3. 制定计划：分解为可执行步骤，标注依赖
4. 预估成本：估算时间、复杂度、工具需求
5. 获取确认：用户批准后再执行

【输出格式】
计划应包含：
- 目标概述（1-2句话）
- 步骤列表（每步简短描述 + 预估时间）
- 所需工具/资源
- 潜在风险和应对
- 确认提示：「请确认计划，我将开始执行」

用户需求：${msg}

请先制定计划。`;

    const r = await callModelAPI('deepseekr1', msg, planPrompt);

    const el = document.getElementById(pid);
    if (el) {
      el.querySelector('.chat-msg-content').innerHTML = escapeHtml(r.content) + `\n\n<button class="btn-sm primary" onclick="executePlan('${pid}')">确认执行</button>`;
    }

    // 保存计划供后续执行
    window._currentPlan = r.content;
  } catch(e) {
    const el = document.getElementById(pid);
    if (el) {
      el.querySelector('.chat-msg-content').innerHTML = `<span style="color:var(--red)">❌ ${escapeHtml(e.message)}</span>`;
    }
  }

  if (btn) btn.disabled = false;
}

// 执行已确认的计划
async function executePlan(planId) {
  const plan = window._currentPlan;
  if (!plan) {
    showToast('计划已过期，请重新发起');
    return;
  }

  showToast('开始执行计划...');

  const executePrompt = `你是任务执行专家。用户已确认以下计划，请开始执行。

【已确认计划】
${plan}

【执行规范】
- 按计划步骤顺序执行
- 每步完成后简短报告结果
- 遇到问题如实说明
- 完成后总结实际完成情况

请开始执行。`;

  const md = document.getElementById('chatMessages');
  const pid = 'execute-' + Date.now();
  md.innerHTML += `<div class="chat-msg" id="${pid}"><div class="chat-msg-header"><div class="chat-msg-avatar" style="background:linear-gradient(135deg,#10b981,#06b6d4)">⚡</div><span class="chat-msg-model">执行中</span></div><div class="chat-msg-content"><span class="spinner"></span>正在执行...</div></div>`;
  md.scrollTop = md.scrollHeight;

  try {
    const r = await callModelAPI('deepseekr1', '开始执行', executePrompt);
    const el = document.getElementById(pid);
    if (el) {
      el.querySelector('.chat-msg-content').innerHTML = escapeHtml(r.content);
    }
  } catch(e) {
    const el = document.getElementById(pid);
    if (el) {
      el.querySelector('.chat-msg-content').innerHTML = `<span style="color:var(--red)">❌ ${escapeHtml(e.message)}</span>`;
    }
  }
}

// 切换聊天模式
function switchChatMode(mode) {
  CHAT_MODE = mode;
  const btn = document.getElementById('modeToggle');
  if (btn) {
    const icons = { chat: '💬', explore: '🔍', plan: '📋', code: '💻' };
    const labels = { chat: '对话', explore: '探索', plan: '规划', code: '编程' };
    btn.innerHTML = `${icons[mode] || '💬'} ${labels[mode] || '对话'}`;
  }
  showToast(`已切换到${labels[mode] || '对话'}模式`);
}

// 初始化聊天模式切换
document.addEventListener('DOMContentLoaded', () => {
  const inputArea = document.querySelector('.chat-input-area') || document.getElementById('chatInput');
  if (inputArea && !document.getElementById('modeToggle')) {
    const modeToggle = document.createElement('button');
    modeToggle.id = 'modeToggle';
    modeToggle.className = 'btn-sm';
    modeToggle.style.cssText = 'margin-left:8px;background:var(--accent-soft)';
    modeToggle.innerHTML = '💬 对话';
    modeToggle.onclick = () => {
      const modes = ['chat', 'explore', 'plan', 'code'];
      const current = modes.indexOf(CHAT_MODE);
      const next = modes[(current + 1) % modes.length];
      switchChatMode(next);
    };
    inputArea.parentNode.appendChild(modeToggle);
  }
});

