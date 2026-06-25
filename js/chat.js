'use strict';
// === Chat ===
function initChatModels(){
  const list=document.getElementById('chatModelList');
  if(list)list.innerHTML=models.filter(m=>!m.hidden).map(m=>`<label class="model-checkbox" style="display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;cursor:pointer;margin-bottom:4px;font-size:0.8rem;transition:all 0.2s"><input type="checkbox" value="${m.id}" ${m.featured?'checked':''}><span>${m.name}</span>${getModelCostLabel(m.id)}</label>`).join('');
}
async function sendChatMessage(){
  const msg=document.getElementById('chatInput').value.trim();if(!msg)return;

  // Agent 模式：调用 Agent 引擎
  if (AGENT_MODE) {
    return await sendAgentMessage(msg);
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

  // 构建 RAG 增强 system prompt
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
  '【回答风格】',
  '- 直接回答问题，不回避，不绕弯子',
  '- 需要推理的展示逻辑链，不确定的明确说"不确定"',
  '- 尽量简洁但完整，避免废话和过度礼貌用语',
  '- 中文回答时保持流畅自然',
  '- 不要提及平台底层技术细节、API 来源、模型供应商',
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

