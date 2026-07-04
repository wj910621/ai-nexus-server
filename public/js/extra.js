'use strict';
// === AI Office ===
let officePrompt='';
const OFFICE_SYS='你是专业商务助理。要求：1. 输出直接可使用，不需要用户再编辑 2. 结构清晰，用标题分段 3. 语言专业但易懂 4. 如果信息不足，在答案结尾列出"需要补充的信息"';
function aiOffice(type,template){officePrompt=template;document.getElementById('officeInput').value=template;document.getElementById('officeInput').focus()}
async function runAiOffice(){
  const i=document.getElementById('officeInput').value.trim();if(!i){showToast('输入需求');return}
  if(!spendCredits(5))return;
  const m=document.getElementById('officeModel').value,o=document.getElementById('officeOutput');
  o.innerHTML='<span class="spinner"></span> 生成中...';
  try{const r=await callModelAPI(m,i,OFFICE_SYS);o.innerHTML=escapeHtml(r.content)}catch(e){o.innerHTML='❌ '+e.message}
}

// === AI Brand ===
let brandPrompt='';
const BRAND_SYS='你是顶级品牌策略师。要求：1. 每个方案给出3个选项（大胆/稳妥/创新），标注各自适用场景 2. Logo方案用文字描述图形+配色+寓意，不画图 3. 命名方案检查读音（中英文都好念）和商标冲突可能性 4. Slogan不超过12字，好记好传播';
function aiBrand(type,template){brandPrompt=template;document.getElementById('brandInput').value=template;document.getElementById('brandInput').focus()}
async function runAiBrand(){
  const i=document.getElementById('brandInput').value.trim();if(!i){showToast('输入品牌信息');return}
  if(!spendCredits(5))return;
  const m=document.getElementById('brandModel').value,o=document.getElementById('brandOutput');
  o.innerHTML='<span class="spinner"></span> 生成中...';
  try{const r=await callModelAPI(m,i,BRAND_SYS);o.innerHTML=escapeHtml(r.content)}catch(e){o.innerHTML='❌ '+e.message}
}

// === AI Marketing ===
let marketPrompt='';
const MARKET_SYS='你是资深营销专家。要求：1. 文案直接可发布，包含标题+正文+话题标签+配图建议 2. 根据不同平台风格调整（小红书要口语化有emoji，公众号要深度有排版，广告要抓眼球有痛点）3. 每条文案给2-3个版本供A/B测试 4. 标注每个版本适合的目标人群';
function aiMarket(type,template){marketPrompt=template;document.getElementById('marketInput').value=template;document.getElementById('marketInput').focus()}
async function runAiMarket(){
  const i=document.getElementById('marketInput').value.trim();if(!i){showToast('输入产品信息');return}
  const m=document.getElementById('marketModel').value;
  const o=document.getElementById('marketOutput');
  if(!spendCredits(getModelCost(m)))return;
  o.innerHTML='<span class="spinner"></span> 生成中...';
  try{const r=await callModelAPI(m,i,MARKET_SYS);o.innerHTML=escapeHtml(r.content)}catch(e){o.innerHTML='❌ '+e.message}
}

// === AI 编程助手（对话式） ===
const CODE_SYS_PROMPT = `你是 TriGen 平台的 AI 编程助手。你是一个专业、耐心、善于引导的全栈开发专家。

【核心原则】
1. 先理解，再动手：首先要充分理解用户想做什么，目标用户是谁，有什么具体需求
2. 帮助规划：分析需求后给出清晰的方案规划，让用户确认方向再开始
3. 分步实现：复杂项目拆解成小步骤，每步确认后再继续
4. 完整交付：代码必须是完整可运行的，不是片段
5. 考虑周全：响应式设计、错误处理、用户体验都要兼顾

【对话流程】
- 用户描述想法后，你先总结理解，然后给出2-3种实现方案
- 推荐最优方案并说明理由
- 用户确认后开始逐步实现
- 每完成一步，问用户是否满意，是否需要调整
- 最后给出完整的部署/使用说明

【代码要求】
- 如果是网页/网站，优先使用单一 HTML 文件（内嵌 CSS + JS），方便直接打开
- 生成的 HTML 代码用 \`\`\`html 标记包裹
- 代码要美观现代，使用合适的配色和动画
- 支持移动端响应式
- 添加必要的注释

【注意事项】
- 用户是小白，不要说太多技术术语，用通俗语言解释
- 耐心引导，不要一次输出太多内容让用户困惑
- 当用户说"不太对""改一下"时，先确认具体哪里不满意
- 如果用户需求不明确，主动提问澄清`;

let codeChatHistory = [];
let codeChatLastHTML = '';
let currentCodeModel = 'deepseekv3'; // 当前选中的编程模型

// 右侧面板模型列表
function initCodeChatModels(){
  const list = document.getElementById('codeModelList');
  if(!list) return;
  const codeModels = models.filter(m =>
    !m.hidden && (m.tags.includes('编程') || m.tags.includes('推理') ||
    ['gpt4o','deepseekr1','deepseekv3','gemini25pro','ali_deepseek_v4_pro','ali_kimi_k26','ali_qwen37_max','sf_qwen3_32b','dmx_qwen25_coder_7b','dmx_qwen35_2b_free','dmx_qwen3_17b_free','dmx_spark_lite_free'].includes(m.id))
  );
  if(codeModels.length===0) codeModels.push(...models.slice(0,10));
  list.innerHTML = codeModels.map(m => {
    const active = currentCodeModel === m.id;
    const cost = getModelCost(m.id);
    return `<label class="model-checkbox" style="display:flex;align-items:center;gap:6px;padding:6px 8px;border-radius:8px;cursor:pointer;margin-bottom:3px;font-size:0.76rem;transition:all 0.2s;${active?'background:var(--accent-soft);border:1px solid var(--accent)':''}" onclick="selectCodeModel('${m.id}',this)">
      <span style="width:24px;height:24px;border-radius:6px;background:${m.avatar};display:flex;align-items:center;justify-content:center;color:#fff;font-size:0.65rem;flex-shrink:0">${m.name[0]}</span>
      <span style="flex:1">${m.name}</span>
      ${cost===0?'<span style="font-size:0.6rem;background:rgba(16,185,129,0.1);color:var(--green);padding:1px 5px;border-radius:3px">免费</span>':`<span style="font-size:0.6rem;color:var(--text-secondary)">⚡${cost}</span>`}
    </label>`;
  }).join('');
}

function selectCodeModel(modelId, el){
  currentCodeModel = modelId;
  // 更新下拉框
  const sel = document.getElementById('codeModelSelect');
  if(sel){
    let opt = sel.querySelector(`option[value="${modelId}"]`);
    if(!opt){
      const m = models.find(x=>x.id===modelId);
      if(m){
        opt = document.createElement('option');
        opt.value = modelId;
        opt.textContent = m.name + (getModelCost(modelId)===0 ? ' 🆓免费' : ' ⚡' + getModelCost(modelId));
        sel.appendChild(opt);
      }
    }
    sel.value = modelId;
  }
  // 高亮右侧列表
  document.querySelectorAll('#codeModelList .model-checkbox').forEach(l => {
    l.style.background = ''; l.style.border = '';
  });
  if(el){
    el.style.background = 'var(--accent-soft)';
    el.style.border = '1px solid var(--accent)';
  }
}

function codeQuickStart(prompt){
  document.getElementById('codeChatInput').value = prompt;
  document.getElementById('codeChatInput').focus();
  sendCodeChatMessage();
}

// 获取对话历史构建 messages 数组
function buildCodeChatMessages(newMsg){
  const msgs = [{role:'system',content:CODE_SYS_PROMPT}];
  for(const entry of codeChatHistory){
    msgs.push({role:'user',content:entry.user});
    msgs.push({role:'assistant',content:entry.ai});
  }
  msgs.push({role:'user',content:newMsg});
  return msgs;
}

async function sendCodeChatMessage(){
  const input = document.getElementById('codeChatInput');
  const msg = input.value.trim();
  if(!msg) return;

  const modelId = currentCodeModel;
  const cost = getModelCost(modelId);
  if(cost > 0 && !spendCredits(cost, true)) return;

  // 隐藏快捷开始
  const qs = document.getElementById('codeChatQuickStart');
  if(qs) qs.style.display = 'none';

  const md = document.getElementById('codeChatMessages');
  // 清除初始占位
  if(md.querySelector('[data-placeholder]')) md.innerHTML = '';

  // 显示用户消息
  md.innerHTML += `<div class="chat-msg user"><div class="chat-msg-header"><span class="chat-msg-model">你</span></div><div class="chat-msg-content">${escapeHtml(msg)}</div></div>`;

  input.value = '';
  const btn = document.getElementById('btnCodeSend');
  btn.disabled = true;

  // 显示AI思考中
  const pid = 'code-msg-'+Date.now();
  const m = models.find(x=>x.id===modelId);
  md.innerHTML += `<div class="chat-msg" id="${pid}"><div class="chat-msg-header"><div class="chat-msg-avatar" style="background:${m?.avatar||'#06b6d4'}">${m?.name?.[0]||'A'}</div><span class="chat-msg-model">${m?.name||'编程助手'}</span></div><div class="chat-msg-content"><span class="spinner"></span> 正在分析你的需求...</div></div>`;
  md.scrollTop = md.scrollHeight;

  try {
    const msgs = buildCodeChatMessages(msg);
    const body = {model:modelId, messages:msgs};
    if(m && m.rawModel) body.rawModel = m.rawModel;

    const r = await fetch(API_BASE+'/api/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify(body)
    });

    let content = '';
    let simulated = false;
    if(r.ok){
      const data = await r.json();
      content = data.content;
      simulated = data.simulated === true;
    }
    
    // 模拟回复或无响应 → 退还积分
    if(simulated || !r.ok || !content){
      if(cost > 0 && authToken){
        userCredits += cost;
        localStorage.setItem('cr', userCredits);
        updateCreditDisplay();
        fetch(API_BASE+'/api/user/refund', {
          method:'POST',
          headers:{'Content-Type':'application/json',Authorization:'Bearer '+authToken},
          body:JSON.stringify({amount:cost})
        }).catch(()=>{});
      }
      if(!content) content = `❌ 请求失败，积分已退还。请稍后重试或更换模型。`;
    }

    const el = document.getElementById(pid);
    if(el){
      el.querySelector('.chat-msg-content').innerHTML = escapeHtml(content);
    }

    codeChatHistory.push({user:msg, ai:content});
    if(codeChatHistory.length > 20) codeChatHistory.shift();

    if(document.getElementById('codeAutoPreview')?.checked){
      const htmlMatch = content.match(/```html\s*\n?([\s\S]*?)```/);
      if(htmlMatch && htmlMatch[1].trim()){
        codeChatLastHTML = htmlMatch[1].trim();
        showCodePreview(codeChatLastHTML);
      }
    }

  } catch(e) {
    // 网络错误 → 退还积分
    if(cost > 0 && authToken){
      userCredits += cost;
      localStorage.setItem('cr', userCredits);
      updateCreditDisplay();
      fetch(API_BASE+'/api/user/refund', {
        method:'POST',
        headers:{'Content-Type':'application/json',Authorization:'Bearer '+authToken},
        body:JSON.stringify({amount:cost})
      }).catch(()=>{});
    }
    const el = document.getElementById(pid);
    if(el) el.querySelector('.chat-msg-content').innerHTML = `<span style="color:var(--red)">❌ ${escapeHtml(e.message)}</span>`;
  }

  btn.disabled = false;
  md.scrollTop = md.scrollHeight;
}

function showCodePreview(htmlCode){
  const preview = document.getElementById('codeChatPreview');
  const iframe = document.getElementById('codeChatIframe');
  if(!preview || !iframe) return;
  preview.style.display = 'block';
  iframe.src = 'data:text/html;charset=utf-8,'+encodeURIComponent(htmlCode);
  // 滚动到预览区域
  preview.scrollIntoView({behavior:'smooth',block:'center'});
}

function toggleCodePreviewSize(){
  const iframe = document.getElementById('codeChatIframe');
  const btn = document.getElementById('codePreviewSizeBtn');
  if(iframe.style.height === '400px' || !iframe.style.height){
    iframe.style.height = '600px';
    if(btn) btn.textContent = '🔽 缩小';
  } else {
    iframe.style.height = '400px';
    if(btn) btn.textContent = '🔲 放大';
  }
}

function copyCodeChatHTML(){
  if(!codeChatLastHTML){
    // 尝试从最后一条AI消息中提取
    const lastAIMsg = codeChatHistory[codeChatHistory.length-1];
    if(lastAIMsg){
      const m = lastAIMsg.ai.match(/```html\s*\n?([\s\S]*?)```/);
      if(m) codeChatLastHTML = m[1].trim();
    }
  }
  if(!codeChatLastHTML){showToast('请先生成HTML代码');return}
  navigator.clipboard.writeText(codeChatLastHTML).then(()=>showToast('✅ HTML代码已复制到剪贴板'));
}

function downloadCodeChatHTML(){
  if(!codeChatLastHTML){
    const lastAIMsg = codeChatHistory[codeChatHistory.length-1];
    if(lastAIMsg){
      const m = lastAIMsg.ai.match(/```html\s*\n?([\s\S]*?)```/);
      if(m) codeChatLastHTML = m[1].trim();
    }
  }
  if(!codeChatLastHTML){showToast('请先生成HTML代码');return}
  const blob = new Blob([codeChatLastHTML],{type:'text/html;charset=utf-8'});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = '我的网页.html'; a.click();
  URL.revokeObjectURL(url);
  showToast('✅ 已下载');
}

function deployCodeChat(){
  if(!codeChatLastHTML){showToast('请先生成HTML代码');return}
  const guide = `📤 部署你的网页（3种方式任选）：\n\n`
    +`方案1 ⭐ GitHub Pages（免费，推荐）：\n`
    +`① 创建GitHub仓库（公开）\n`
    +`② 上传HTML文件到仓库（改名为index.html）\n`
    +`③ 进入 Settings → Pages → 选择main分支 → Save\n`
    +`④ 几分钟后获得链接：https://你的用户名.github.io/仓库名\n\n`
    +`方案2 Cloudflare Pages（免费，更快）：\n`
    +`① 登录 Cloudflare → Workers & Pages\n`
    +`② 直接上传文件或连接Git仓库\n`
    +`③ 自动部署并获得 *.pages.dev 域名\n\n`
    +`方案3 绑定自己的域名：\n`
    +`在GitHub Pages或Cloudflare Pages设置中添加自定义域名`;
  alert(guide);
}

function clearCodeChat(){
  if(codeChatHistory.length > 0 && !confirm('确定要清空对话历史吗？')) return;
  codeChatHistory = [];
  codeChatLastHTML = '';
  const md = document.getElementById('codeChatMessages');
  md.innerHTML = `<div data-placeholder style="text-align:center;padding:20px">
    <div style="font-size:2.5rem;margin-bottom:8px">💻</div>
    <div style="font-weight:700;font-size:1rem;margin-bottom:6px">AI 编程助手 — 对话式建站</div>
    <p style="font-size:0.78rem;color:var(--text-secondary);margin-bottom:16px">告诉我你想做什么，我会一步步引导你完成</p>
    <div id="codeChatQuickStart" style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-bottom:8px">
      <button class="filter-tag" onclick="codeQuickStart('帮我做一个个人博客网站，有文章列表、标签、暗黑模式')" style="font-size:0.75rem;cursor:pointer">🌐 个人博客</button>
      <button class="filter-tag" onclick="codeQuickStart('帮我做一个待办事项工具，能添加/删除/标记完成')" style="font-size:0.75rem;cursor:pointer">✅ 待办工具</button>
      <button class="filter-tag" onclick="codeQuickStart('帮我做一个能在浏览器里玩的贪吃蛇游戏')" style="font-size:0.75rem;cursor:pointer">🎮 小游戏</button>
      <button class="filter-tag" onclick="codeQuickStart('帮我做一个展示产品的公司官网，美观大气')" style="font-size:0.75rem;cursor:pointer">🏢 企业官网</button>
      <button class="filter-tag" onclick="codeQuickStart('帮我做一个在线计算器，支持加减乘除')" style="font-size:0.75rem;cursor:pointer">🔢 计算器</button>
      <button class="filter-tag" onclick="codeQuickStart('帮我做一个倒计时页面，可以设置目标日期')" style="font-size:0.75rem;cursor:pointer">⏰ 倒计时</button>
    </div>
    <p style="font-size:0.7rem;color:var(--text-secondary);opacity:0.6">或直接在下方输入你的任何想法 💬</p>
  </div>`;
  document.getElementById('codeChatPreview').style.display = 'none';
  document.getElementById('codeChatIframe').src = 'about:blank';
  showToast('✅ 对话已清空');
}

// 当页面切换到编程页时触发
document.addEventListener('pageSwitch', (e)=>{
  if(e.detail === 'code'){
    setTimeout(()=>{
      initCodeChatModels();
      if(codeChatHistory.length===0){
        const qs = document.getElementById('codeChatQuickStart');
        if(qs) qs.style.display = 'flex';
      }
    },200);
  }
});

// === API Key 管理 ===
async function createApiKey(){
  if(!authToken){showToast('请先登录');return}
  const name=prompt('给这个 Key 起个名字（如：我的博客网站）：','我的应用');
  if(!name)return;
  try{
    const r=await apiFetch('/api/keys/create',{method:'POST',body:JSON.stringify({name})});
    if(r.ok){showToast('✅ Key已创建: '+r.apiKey.substring(0,16)+'...');loadApiKeys()}
    else showToast(r.error||'创建失败');
  }catch(e){showToast('创建失败')}
}
async function loadApiKeys(){
  if(!authToken){document.getElementById('apiKeyList').innerHTML='<div style="color:var(--text-secondary);text-align:center;padding:40px">请先登录</div>';return}
  try{
    const r=await apiFetch('/api/keys');
    if(!r.ok){document.getElementById('apiKeyList').innerHTML='<div style="color:var(--text-secondary);text-align:center;padding:40px">加载失败</div>';return}
    if(!r.keys.length){document.getElementById('apiKeyList').innerHTML='<div style="color:var(--text-secondary);text-align:center;padding:40px">还没有 Key，点击上方按钮生成</div>';return}
    document.getElementById('apiKeyList').innerHTML=r.keys.map(k=>`<div class="feature-card" style="padding:14px;margin-bottom:8px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <b>${k.name}</b>
        <span style="font-size:0.65rem;padding:2px 8px;border-radius:10px;background:${k.active?'rgba(16,185,129,0.1)':'rgba(239,68,68,0.1)'};color:${k.active?'var(--green)':'var(--red)'}">${k.active?'启用':'禁用'}</span>
      </div>
      <div style="font-family:monospace;font-size:0.72rem;background:var(--bg-input);padding:6px 10px;border-radius:6px;margin-bottom:6px;word-break:break-all">${k.key}</div>
      <div style="font-size:0.65rem;color:var(--text-secondary)">已用: ${k.used}次 · 创建: ${k.created?.substring(0,10)}</div>
      <button class="btn-sm" onclick="deleteApiKey(${k.id})" style="margin-top:6px;font-size:0.65rem;color:var(--red);background:rgba(239,68,68,0.1);border:none">🗑 删除</button>
    </div>`).join('');
  }catch(e){}
}
async function deleteApiKey(id){
  if(!confirm('删除后该Key将立即失效，确定？'))return;
  try{await apiFetch('/api/keys/'+id,{method:'DELETE'});loadApiKeys();showToast('已删除')}catch(e){}
}
// 切换到 API Key 页时自动加载

// === AI Art - Enhanced ===
const ART_DATA={
  styles:[
    {v:'anime style',l:'动漫风'},{v:'cyberpunk',l:'赛博朋克'},{v:'oil painting',l:'油画'},
    {v:'watercolor',l:'水彩'},{v:'ink wash painting',l:'水墨画'},{v:'pencil sketch',l:'素描'},
    {v:'3D render, C4D',l:'3D渲染'},{v:'pixel art',l:'像素风'},{v:'Chinese ink style',l:'国潮水墨'},
    {v:'surrealism',l:'超现实'},{v:'impressionism',l:'印象派'},{v:'art nouveau',l:'新艺术'},
    {v:'minimalist',l:'极简'},{v:'Baroque',l:'巴洛克'},{v:'pop art',l:'波普'},
    {v:'Ukiyo-e',l:'浮世绘'},{v:'steampunk',l:'蒸汽朋克'},{v:'fantasy art',l:'奇幻'},
    {v:'dark fantasy',l:'暗黑'},{v:'synthwave',l:'合成波'},{v:'low poly',l:'低多边形'},
    {v:'isometric',l:'等距'},{v:'Studio Ghibli',l:'吉卜力'},{v:'Makoto Shinkai',l:'新海诚'},
    {v:'comic book style',l:'美漫'},{v:'manga style',l:'日漫'},{v:'brutalism',l:'野兽派'},
  ],
  lights:[
    {v:'cinematic lighting',l:'电影光'},{v:'volumetric lighting',l:'体积光'},{v:'golden hour',l:'黄金时刻'},
    {v:'neon lights',l:'霓虹灯'},{v:'rim lighting',l:'轮廓光'},{v:'backlight',l:'逆光'},
    {v:'soft diffused light',l:'柔光'},{v:'dramatic lighting',l:'戏剧光'},{v:'god rays',l:'圣光'},
    {v:'studio lighting',l:'棚拍'},{v:'moonlight',l:'月光'},{v:'candlelight',l:'烛光'},
    {v:'sunlight streaming',l:'阳光'},{v:'bioluminescent',l:'生物光'},{v:'fog and haze',l:'雾光'},
  ],
  cameras:[
    {v:'close-up shot',l:'特写'},{v:'medium shot',l:'中景'},{v:'wide shot',l:'全景'},
    {v:'aerial view',l:'俯瞰'},{v:'bird eye view',l:'鸟瞰'},{v:'low angle shot',l:'仰拍'},
    {v:'fisheye lens',l:'鱼眼'},{v:'macro lens',l:'微距'},{v:'tilt-shift',l:'移轴'},
    {v:'depth of field',l:'景深'},{v:'bokeh',l:'散景'},{v:'portrait lens 85mm',l:'85mm人像'},
  ],
  artists:[
    {v:'by Greg Rutkowski',l:'G.Rutkowski'},{v:'by Alphonse Mucha',l:'A.Mucha'},
    {v:'by James Jean',l:'James Jean'},{v:'by Yoshitaka Amano',l:'天野喜孝'},
    {v:'by HR Giger',l:'HR Giger'},{v:'by Makoto Shinkai',l:'新海诚'},
    {v:'by Hayao Miyazaki',l:'宫崎骏'},{v:'by WLOP',l:'WLOP'},
    {v:'by Moebius',l:'Moebius'},{v:'by Syd Mead',l:'Syd Mead'},
    {v:'by Zdzisław Beksiński',l:'贝克辛斯基'},{v:'by Guweiz',l:'Guweiz'},
  ],
  qualities:[
    {v:'8K, hyper detailed',l:'8K超精细'},{v:'4K, highly detailed',l:'4K高清'},
    {v:'photorealistic',l:'照片级'},{v:'masterpiece, best quality',l:'大师级'},
    {v:'intricate details',l:'精细细节'},{v:'sharp focus',l:'锐利对焦'},
    {v:'HDR',l:'HDR'},{v:'trending on ArtStation',l:'ArtStation'},
  ],
  ratios:[
    {v:'--ar 1:1',l:'1:1 方形'},{v:'--ar 2:3',l:'2:3 竖版'},{v:'--ar 3:2',l:'3:2 横版'},
    {v:'--ar 16:9',l:'16:9 宽屏'},{v:'--ar 9:16',l:'9:16 手机'},
  ],
  templates:[
    {cat:'人物',p:'beautiful portrait of {subject}, {style}, {light}, {camera}, {quality}, {ratio}'},
    {cat:'场景',p:'epic landscape, {subject}, {style}, {light}, {camera}, {quality}, {ratio}'},
    {cat:'概念',p:'concept art, {subject}, {style}, {light}, {quality}, {ratio}'},
    {cat:'产品',p:'product photography, {subject}, {style}, studio lighting, {camera}, {quality}, {ratio}'},
    {cat:'建筑',p:'architecture visualization, {subject}, {style}, {light}, {camera}, {quality}, {ratio}'},
    {cat:'食物',p:'food photography, {subject}, {style}, {light}, appetizing, {camera}, {quality}, {ratio}'},
    {cat:'科幻',p:'sci-fi, {subject}, futuristic, {style}, {light}, {camera}, {quality}, {ratio}'},
    {cat:'古风',p:'ancient Chinese style, {subject}, ink painting influence, {light}, {quality}, {ratio}'},
    {cat:'赛博',p:'cyberpunk city, {subject}, neon lights, rain, {camera}, {quality}, {ratio}'},
  ]
};

// Style Gallery data
const STYLE_GALLERY=[
  {name:'水墨画',style:'ink wash painting',desc:'中国传统水墨风格，意境深远',gradient:'linear-gradient(135deg,#1a1a2e,#16213e,#0f3460,transparent)'},
  {name:'赛博朋克',style:'cyberpunk',desc:'霓虹灯、高科技、低生活',gradient:'linear-gradient(135deg,#0d0221,#150734,#3a0ca3,#7209b7)'},
  {name:'吉卜力',style:'Studio Ghibli',desc:'宫崎骏温暖治愈的动画风',gradient:'linear-gradient(135deg,#e8f5e9,#c8e6c9,#a5d6a7,#4db6ac)'},
  {name:'新海诚',style:'Makoto Shinkai',desc:'唯美天空和光影渲染',gradient:'linear-gradient(135deg,#e3f2fd,#90caf9,#42a5f5,#1e88e5)'},
  {name:'油画',style:'oil painting',desc:'古典油画质感，厚重浓郁',gradient:'linear-gradient(135deg,#3e2723,#4e342e,#5d4037,#6d4c41)'},
  {name:'像素风',style:'pixel art',desc:'复古游戏像素艺术',gradient:'linear-gradient(135deg,#1b5e20,#2e7d32,#388e3c,#4caf50)'},
  {name:'3D渲染',style:'3D render, C4D',desc:'逼真的三维渲染效果',gradient:'linear-gradient(135deg,#311b92,#4527a0,#5e35b1,#7e57c2)'},
  {name:'极简',style:'minimalist',desc:'少即是多，简洁优雅',gradient:'linear-gradient(135deg,#fafafa,#f5f5f5,#eeeeee,#e0e0e0)'},
  {name:'暗黑',style:'dark fantasy',desc:'黑暗幻想，哥特美学',gradient:'linear-gradient(135deg,#000000,#1a1a1a,#2d2d2d,#404040)'},
  {name:'浮世绘',style:'Ukiyo-e',desc:'日本浮世绘版画风格',gradient:'linear-gradient(135deg,#f9a825,#fdd835,#ffee58,#fff9c4)'},
  {name:'合成波',style:'synthwave',desc:'80年代复古未来主义',gradient:'linear-gradient(135deg,#1a237e,#283593,#3949ab,#5c6bc0)'},
  {name:'波普',style:'pop art',desc:'Andy Warhol风格波普艺术',gradient:'linear-gradient(135deg,#c62828,#d32f2f,#e53935,#ef5350)'},
];

let artPageInit=false;
function initArtData(){
  if(artPageInit)return;artPageInit=true;
  ['artStyle','artLight','artCamera','artQuality','artRatio'].forEach(id=>{
    const sel=document.getElementById(id);if(!sel)return;
    const key=id.replace('art','').toLowerCase()+(id.includes('Ratio')?'s':(id.includes('Quality')?'ies':'s'));
    (ART_DATA[key]||[]).forEach(d=>{const o=document.createElement('option');o.value=d.v;o.textContent=d.l;sel.appendChild(o)});
  });
  ['artStyleTags','artLightTags','artCameraTags','artArtistTags','artQualityTags'].forEach(id=>{
    const el=document.getElementById(id);if(!el)return;
    const key=id.replace('art','').replace('Tags','').toLowerCase()+(id.includes('Quality')?'ies':'s');
    (ART_DATA[key]||[]).forEach(d=>{el.innerHTML+=`<span class="filter-tag" style="font-size:0.7rem;padding:4px 10px;margin:2px;cursor:pointer" onclick="clickArtTag('${id.replace('Tags','')}','${d.v.replace(/'/g,"\\'")}')">${d.l}</span>`});
  });
  const tplF=document.getElementById('artTplFilters');const cats=[...new Set(ART_DATA.templates.map(t=>t.cat))];
  tplF.innerHTML='<button class="filter-tag active" data-tpl="all">全部</button>'+cats.map(c=>`<button class="filter-tag" data-tpl="${c}">${c}</button>`).join('');
  tplF.querySelectorAll('.filter-tag').forEach(b=>b.addEventListener('click',()=>{tplF.querySelectorAll('.filter-tag').forEach(x=>x.classList.remove('active'));b.classList.add('active');renderArtTemplates(b.dataset.tpl)}));
  renderArtTemplates('all');
  document.getElementById('artSubject').addEventListener('input',buildArtPrompt);
  ['artStyle','artLight','artCamera','artQuality','artRatio'].forEach(id=>{const el=document.getElementById(id);if(el)el.addEventListener('change',buildArtPrompt)});
  initStyleGallery();
  // Art tabs
  document.querySelectorAll('#artTabs .tab-btn').forEach(b=>{b.addEventListener('click',()=>{document.querySelectorAll('#artTabs .tab-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('#tab-builder,#tab-gallery').forEach(t=>t.classList.remove('active'));document.getElementById('tab-'+b.dataset.tab).classList.add('active')})});
}
function renderArtTemplates(cat){
  const el=document.getElementById('artTemplates');const f=cat==='all'?ART_DATA.templates:ART_DATA.templates.filter(t=>t.cat===cat);
  el.innerHTML=f.map(t=>`<div class="feature-card" style="cursor:pointer;padding:12px" onclick="document.getElementById('artSubject').value='';document.getElementById('artSubject').focus();showToast('输入主体后点刷新组合')"><div style="font-weight:600;margin-bottom:4px;font-size:0.8rem">${t.cat}</div><div style="font-size:0.72rem;color:var(--text-secondary)">${t.p}</div></div>`).join('')}
function clickArtTag(type,value){const sel=document.getElementById('art'+type.charAt(0).toUpperCase()+type.slice(1));if(sel)sel.value=value;buildArtPrompt()}
function buildArtPrompt(){const p=[document.getElementById('artSubject').value,document.getElementById('artStyle').value,document.getElementById('artLight').value,document.getElementById('artCamera').value,document.getElementById('artQuality').value,document.getElementById('artRatio').value].filter(Boolean);const txt=p.join(', ')||'选择上方选项组合提示词';document.getElementById('artPrompt').textContent=txt;const rp=document.getElementById('rpArtPromptText');if(rp)rp.textContent=txt;const rpc=document.getElementById('rpArtPrompt');if(rpc)rpc.style.display=txt.includes('选择')?'none':'block'}
function copyArtPrompt(){const t=document.getElementById('artPrompt').textContent;if(!t||t.includes('选择')){showToast('请先组合提示词');return}navigator.clipboard.writeText(t).then(()=>showToast('已复制提示词'))}let lastGeneratedImage='';async function generateImage(){const p=document.getElementById('artPrompt').textContent.trim();if(!p||p.includes('选择')){showToast('请先输入创意描述');return}const sub=document.getElementById('artSubject')?.value?.trim();const prompt=sub||p;const loading=document.getElementById('artLoading');const img=document.getElementById('artResultImage');const area=document.getElementById('artResultArea');loading.style.display='block';img.style.display='none';try{const url=`https://image.pollinations.ai/prompt/${encodeURIComponent(prompt)}?width=768&height=768&nologo=true&seed=${Math.floor(Math.random()*99999)}`;img.src=url;img.onload=()=>{loading.style.display='none';img.style.display='block';lastGeneratedImage=url;document.getElementById('artActions').style.display='flex'};img.onerror=()=>{loading.style.display='none';showToast('生成失败，请重试')}}catch(e){loading.style.display='none';showToast('生成失败: '+e.message)}}function downloadGeneratedImage(){if(!lastGeneratedImage){showToast('请先生成图像');return}const a=document.createElement('a');a.href=lastGeneratedImage;a.download='ai-nexus-image.png';a.click()}function generateVariation(){const sub=document.getElementById('artSubject')?.value?.trim();if(sub)document.getElementById('artSubject').value=sub+' （变体）';generateImage()}async function generateVideo(){const p=document.getElementById('videoPrompt').value.trim();if(!p){showToast('请输入视频描述');return}const loading=document.getElementById('videoLoading');const vid=document.getElementById('videoResult');loading.style.display='block';vid.style.display='none';const url=`https://image.pollinations.ai/prompt/${encodeURIComponent(p+' cinematic motion blur')}?width=768&height=432&nologo=true&seed=${Math.floor(Math.random()*99999)}`;vid.src=url;vid.onload=()=>{loading.style.display='none';vid.style.display='block';showToast('静态预览已生成（视频API接入中）')};vid.onerror=()=>{loading.style.display='none';showToast('生成失败')}}function downloadVideo(){const v=document.getElementById('videoResult');if(!v.src||v.style.display==='none'){showToast('请先生成视频');return}const a=document.createElement('a');a.href=v.src;a.download='ai-nexus-video.png';a.click()}

function initStyleGallery(){
  const el=document.getElementById('styleGallery');
  el.innerHTML=STYLE_GALLERY.map(s=>`<div class="feature-card" style="cursor:pointer;padding:0;overflow:hidden" onclick="applyStyle('${s.style}','${s.name}')">
    <div style="height:140px;display:flex;align-items:center;justify-content:center;font-size:3rem;background:${s.gradient}">🎨</div>
    <div style="padding:14px"><div style="font-weight:700;font-size:0.9rem;color:var(--text)">${s.name}</div><div style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px">${s.desc}</div><div style="font-size:0.68rem;color:var(--accent);margin-top:6px">点击使用 →</div></div>
  </div>`).join('');
}
function applyStyle(style,name){
  switchPage('art');setTimeout(()=>{
    document.querySelectorAll('#artTabs .tab-btn').forEach(x=>x.classList.remove('active'));
    document.querySelector('#artTabs .tab-btn[data-tab="builder"]').classList.add('active');
    document.querySelector('#tab-builder').classList.add('active');
    if(document.querySelector('#tab-gallery'))document.querySelector('#tab-gallery').classList.remove('active');
    const sel=document.getElementById('artStyle');if(sel){sel.value=style;buildArtPrompt()}
    showToast(name+' 风格已应用')
  },200);
}

// === Daily Checkin ===
const CHECKIN_REWARDS=[2,2,3,3,3,5,5];// day 1-7: 23/week total
function dailyCheckin(){const d=openCheckin();updateStreakUI();}
function openCheckin(){const m=document.getElementById('checkinModal');m.classList.add('show');updateStreakUI();}
function closeCheckin(){document.getElementById('checkinModal').classList.remove('show')}
function updateStreakUI(){
  const today=new Date().toDateString();
  const last=localStorage.getItem('checkin_date');
  const streak=localStorage.getItem('checkin_streak');
  let s=0;if(last===today){s=parseInt(streak||'0')}else{const yesterday=new Date(Date.now()-86400000).toDateString();if(last===yesterday){s=parseInt(streak||'0')}else{s=0}}
  // Highlight streak dots
  const dots=document.querySelectorAll('#checkinStreak span');
  dots.forEach((d,i)=>{d.style.background=i<s?((s-i<=1&&last===today)?'var(--green)':'var(--accent)'):'var(--bg-input)'});
  if(last===today){
    document.getElementById('checkinEmoji').textContent='✅';document.getElementById('checkinTitle').textContent='今日已签到';document.getElementById('checkinMsg').textContent=`连续${s}天，明天继续!`;document.getElementById('checkinBtn').textContent='已完成';document.getElementById('checkinBtn').disabled=true;document.getElementById('checkinBadge').textContent='✅';
  }else{
    document.getElementById('checkinEmoji').textContent='🎁';document.getElementById('checkinTitle').textContent='每日签到';document.getElementById('checkinMsg').textContent=s>0?`连续${s}天，今天+${CHECKIN_REWARDS[Math.min(s,6)]}积分`:'签到领积分，连续7天额外奖3分';document.getElementById('checkinBtn').textContent=`📅 签到 +${CHECKIN_REWARDS[Math.min(s,6)]}积分`;document.getElementById('checkinBtn').disabled=false;document.getElementById('checkinBadge').textContent='签到';
  }
}
function doCheckin(){
  const today=new Date().toDateString();const last=localStorage.getItem('checkin_date');if(last===today){showToast('今天已签到');closeCheckin();return}
  const yesterday=new Date(Date.now()-86400000).toDateString();
  let s=last===yesterday?parseInt(localStorage.getItem('checkin_streak')||'0'):0;
  if(isNaN(s))s=0;s=Math.min(s+1,7);
  const reward=CHECKIN_REWARDS[s-1];
  userCredits+=reward;localStorage.setItem('cr',userCredits);localStorage.setItem('checkin_date',today);localStorage.setItem('checkin_streak',s.toString());
  updateCreditDisplay();updateStreakUI();
  if(s===7){showToast(`🎉 连续7天！获得${reward}积分（包含连签奖励）`)}else{showToast(`签到成功 +${reward}积分 · 连续${s}天`)}
  setTimeout(closeCheckin,1500);
}

// === Chat History ===
function saveChatToHistory(msg,replies){
  try{const h=JSON.parse(localStorage.getItem('chathist')||'[]');h.unshift({time:new Date().toISOString(),msg,replies:replies.substring(0,200)});localStorage.setItem('chathist',JSON.stringify(h.slice(0,30)))}catch(e){}
}
function renderContinue(){const el=document.getElementById('continueContent');if(!el||!currentUser)return;
  const h=JSON.parse(localStorage.getItem('chathist')||'[]');const ch=JSON.parse(localStorage.getItem('nch')||'[]');
  let items=[];
  if(h.length>0)items.push(`<div class="feature-card" style="cursor:pointer" onclick="switchPage('chat');setTimeout(()=>document.getElementById('chatInput').value='${escapeHtml(h[0].msg).substring(0,30)}...',500)"><div>💬</div><div style="font-weight:600;font-size:0.85rem">最近聊天</div><div style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px">${escapeHtml(h[0].msg).substring(0,60)}${h[0].msg.length>60?'...':''}</div></div>`);
  if(ch.length>0&&novelBookTitle!=='未开始')items.push(`<div class="feature-card" style="cursor:pointer" onclick="switchPage('novel');switchNovelTab('manage')"><div>📖</div><div style="font-weight:600;font-size:0.85rem">${novelBookTitle}</div><div style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px">已写${ch.length}章 · ${totalWordsWritten.toLocaleString()}字</div></div>`);
  const sec=document.getElementById('continueSection');
  if(items.length){el.innerHTML=items.join('');sec.style.display='block'}else{sec.style.display='none'}
}
// Patch sendChatMessage to save history
const _origSendChat=sendChatMessage;
sendChatMessage=async function(){const m=document.getElementById('chatInput').value.trim();if(m)saveChatToHistory(m,'');await _origSendChat();setTimeout(renderContinue,1000)};

// === PWA: 清除旧Service Worker，不注册新的（避免缓存冲突） ===
(function(){
  if('serviceWorker' in navigator){
    navigator.serviceWorker.getRegistrations().then(regs => {
      regs.forEach(reg => reg.unregister());
    });
    caches.keys().then(names => names.forEach(name => caches.delete(name)));
  }
})();

// === AI Agents ===
const AGENTS=[
  {id:'novel-planner',name:'📖 小说大纲规划师',cat:'创作',desc:'输入一句话灵感，输出完整小说大纲含章节规划+人物关系+世界观',placeholder:'例：一个废柴少年在古墓中发现上古神剑，踏上修仙之路...',sys:'你是专业小说策划师。根据用户的灵感，生成完整小说大纲：1. 故事梗概(200字) 2. 章节规划(至少20章，每章一句话概括) 3. 核心人物(5-8个，含外貌性格能力关系) 4. 世界观设定 5. 3种不同展开方向的建议',label:'输入你的灵感或一句话概要'},
  {id:'brand-planner',name:'🎨 品牌全案策划师',cat:'商业',desc:'输入产品/服务，输出完整品牌全案：命名+Logo方案+VI+Slogan+品牌故事',placeholder:'例：一家主打手工酿造精酿啤酒的品牌，面向25-35岁都市白领...',sys:'你是顶级品牌策略师。输出完整品牌全案：1. 品牌命名(3个方案，含中英文+寓意) 2. Logo设计描述(图形+配色+字体) 3. 视觉识别系统(VI)大纲 4. Slogan(5条，标最适合的) 5. 品牌故事(300字) 6. 目标人群画像+品牌定位一句话',label:'描述你的产品/服务'},
  {id:'xhs-writer',name:'📕 小红书爆款写手',cat:'营销',desc:'输入产品/话题，输出10条小红书种草笔记，含标题+正文+话题标签+配图建议',placeholder:'例：一款AI智能写作助手工具...',sys:'你是小红书运营专家。输出10条可直接发布的种草笔记：每条含：标题(抓眼球)、正文(口语化+emoji+痛点+解决方案)、话题标签(5-8个)、配图建议。前3条详细写(200-300字)，后7条精简版。不同角度：教程类/测评类/对比类/故事类/清单类。',label:'描述产品/话题'},
  {id:'comic-director',name:'🎬 漫剧导演',cat:'创作',desc:'输入故事，直接输出完整分镜脚本+角色设定+场景描述+对白',placeholder:'例：一个科幻故事，2077年的东京...',sys:'你是专业漫剧导演。根据输入故事输出：1. 6-8格完整分镜(编号/景别/画面/动作/对白/时长) 2. 3个核心角色(外貌/服装/性格/口头禅) 3. 4个关键场景(环境色/光影/氛围) 4. 关键对白脚本。格式要专业，能直接给画师开工。',label:'输入故事设定'},
  {id:'business-plan',name:'💼 商业计划书',cat:'商业',desc:'输入项目，输出投资人级别的商业计划书大纲+执行摘要+财务预测框架',placeholder:'例：一个基于AI的远程医疗问诊平台...',sys:'你是资深商业顾问。输出投资人级别的BP：1. 执行摘要(200字) 2. 市场规模分析 3. 竞争格局 4. 商业模式画布 5. 3年财务预测框架 6. 团队构建建议 7. 融资方案建议。每个部分给出具体数据和推理逻辑。',label:'描述你的创业项目'},
  {id:'seo-researcher',name:'🔍 SEO策略师',cat:'营销',desc:'输入行业/网站，输出关键词策略+内容规划+竞争对手分析',placeholder:'例：AI写作工具行业...',sys:'你是SEO专家。输出：1. 核心关键词(10个，含搜索量/竞争度) 2. 长尾词策略(20个) 3. 内容矩阵规划(分类/频率/形式) 4. Top3竞品分析 5. 3个月关键词排名提升路线图。数据驱动的策略。',label:'输入行业或网站类型'},
  {id:'email-campaign',name:'📧 邮件营销官',cat:'营销',desc:'输入目标，输出7天自动邮件序列+每封主题/正文/CTA',placeholder:'例：为SaaS工具的新注册用户设计7天激活邮件...',sys:'你是邮件营销专家。设计7天自动化邮件序列：每封含：发送时机(DayX)、主题行(3个版本A/B测试)、正文(个性化变量位置)、CTA按钮文案、预期打开率。策略：Day1欢迎Day3价值展示Day5案例证明Day7限时优惠。',label:'描述邮件营销目标'},
  {id:'thesis-helper',name:'🎓 论文助手',cat:'研究',desc:'输入主题，输出论文大纲+文献综述框架+研究方法建议+摘要',placeholder:'例：人工智能在医疗影像诊断中的应用研究...',sys:'你是学术研究导师。输出：1. 论文标题(3个备选) 2. 摘要(300字) 3. 详细大纲(6-8章，每章3-5节) 4. 文献综述框架 5. 研究方法建议(定量/定性/混合) 6. 创新点分析 7. 预计字数分配',label:'输入论文主题'},
  {id:'ad-strategist',name:'🎯 广告投放策略师',cat:'营销',desc:'输入产品/预算，输出跨平台广告投放策略+受众定向+创意方向',placeholder:'例：预算5000元，推广一个在线教育课程...',sys:'你是广告投放专家。输出：1. 平台分配策略(微信/抖音/小红书/百度占比) 2. 每平台受众定向设置 3. 创意方向(3套A/B素材方案) 4. 出价策略 5. 预期KPI(CPM/CTR/CPA) 6. 7天优化计划。预算导向，ROI为核心。',label:'描述产品和预算'},
  {id:'novel-master',name:'📖 小说创作大师',cat:'创作',desc:'专业级长篇写作，百万字无缝衔接、去AI痕迹、伏笔管理、五感描写，输出可直接发表的小说正文',placeholder:'例：玄幻小说，废柴少年被逐出师门后获得上古药神传承...',sys:'[身份设定]\n你是一位世界级的小说家，拥有二十年的专业写作经验，擅长所有类型文学，尤其精于构造长篇故事。你的文字拥有强烈的镜头感和情绪张力。\n\n[绝对规则]\n1. 大纲至上：严格按照提供的大纲推进剧情，不可私自更改主线事件和结局走向。\n2. 设定铁律：完全遵循人物设定、世界观设定、力量体系规则，不得与前文矛盾。\n3. 百万字无缝衔接：深度消化前情提要，自然承接上一章结尾，准确调用已有伏笔。\n4. 彻底去除AI痕迹：禁用模板化开场、禁用AI高频词（然而、因此、仿佛、似乎、意识到等）、禁用表情动作套板（嘴角上扬、眼中闪过一丝光芒等）、禁止直接说明人物性格（应通过行动展示）、禁止总结性语句。\n5. 描写调动五感：颜色、声音、气味、触感、味道交替出现。\n6. 句式节奏多变：长短句交错，段落长度随情绪起伏。\n\n[输出要求]\n只输出小说正文，不进行多余的解释、评价或客套。先给出【章节标题】，然后直接开始正文。每次输出2000-4000字。',label:'输入小说类型、核心设定和前文概要'},
  {id:'comic-director-pro',name:'🎬 漫剧导演',cat:'创作',desc:'将小说转化为竖屏动态漫剧分镜脚本，适配抖快短视频，含景别/画面/对白/音效/时长',placeholder:'例：一个修仙少年在宗门大比中一鸣惊人的场景...',sys:'[身份设定]\n你是一名资深的漫剧导演兼分镜师，精通将小说文字转化为具有冲击力的动态漫画镜头。你的分镜风格适配抖音、快手等竖屏短视频平台。\n\n[输出格式]\n你必须严格按以下结构输出整集脚本：\n【剧集标题】\n【本集角色表】\n【分镜脚本】\n镜头01：\n  景别：特写/近景/中景/全景/远景\n  画面描述：（精确描述画面构图、背景、人物动作表情）\n  对白：（角色名：台词）\n  音效/特效：环境音、动作音、特效\n  时长：x秒\n\n[分镜规则]\n1. 视觉优先：将心理描写转化为具体可见的画面和光影。\n2. 动态感：每个镜头包含动态趋势（发丝被风吹起、眼泪滑落等）。\n3. 节奏控制：对话场景2-5秒一个镜头，情绪重点用特写强调。\n4. 音效设计：每个镜头标记合适的音效和特效关键词。',label:'输入小说原文片段或场景描述'},
  {id:'code-assistant',name:'💻 代码助手',cat:'技术',desc:'编程问题解答、代码生成、Debug调试、算法设计、架构建议',placeholder:'例：用Python写一个快速排序算法，并附带详细注释...',sys:'你是全栈软件工程师，精通所有主流编程语言和框架。根据用户需求：1. 生成可直接运行的代码 2. 附带详细注释 3. 解释核心设计思路 4. 指出可能的边界情况和优化方向 5. 提供测试建议。保持代码简洁、高效、遵循最佳实践。',label:'描述你的编程需求或粘贴错误信息'},
  {id:'academic-mentor',name:'🎓 学术导师',cat:'研究',desc:'论文写作指导、研究方法建议、文献综述框架、学术写作规范、答辩准备',placeholder:'例：帮我设计一个关于"人工智能对教育的影响"的研究框架...',sys:'你是资深学术导师，熟悉国内外学术规范。根据用户需求：1. 提供研究框架设计 2. 推荐合适的研究方法 3. 帮助构建文献综述结构 4. 指导学术写作规范和格式 5. 提供创新点和研究价值分析。输出要严谨、专业、有深度，引用格式使用APA/MLA标准。',label:'输入研究主题或学术需求'},
  {id:'business-consultant',name:'💼 商业顾问',cat:'商业',desc:'商业模式分析、市场调研、竞争分析、盈利模式设计、增长策略',placeholder:'例：分析共享充电宝行业的商业模式和盈利前景...',sys:'你是顶级商业顾问，拥有麦肯锡级战略思维。根据用户需求：1. 分析商业模式画布 2. 评估市场规模和增长空间 3. 分析竞争格局和差异化策略 4. 设计盈利模式和定价策略 5. 提供可执行的增长计划。输出要有数据支撑、逻辑严密、可落地执行。',label:'描述你的业务或商业分析需求'},
  {id:'translation-expert',name:'🌐 翻译专家',cat:'创作',desc:'多语言专业翻译，支持中英日韩法德西俄等语言，术语准确、语境贴合',placeholder:'例：将以下中文产品说明书翻译成地道英语...',sys:'你是资深翻译专家，精通多语种互译。翻译原则：1. 准确传达原文意思和语气 2. 符合目标语言表达习惯 3. 专业术语准确统一 4. 保持文体风格一致（正式/口语/文学/技术等）5. 考虑文化差异，避免直译造成的误解。输出仅含翻译结果，如需注释请用括号标注。',label:'输入需要翻译的文本和目标语言'},
  {id:'custom-agent',name:'🤖 通用智能体',cat:'所有',desc:'自定义任务——写任何你想让AI做的事情',placeholder:'例：帮我分析新能源汽车行业2025趋势，给出投资建议...',sys:'你是万能的AI助手。认真理解用户需求，给出专业、精准、详尽的回答。展示你的推理过程。如果不确定，明确说明。',label:'描述你想让AI做什么'},
];
let currentAgent=null;
function renderAgents(filter='all'){
  const g=document.getElementById('agentGrid');
  const f=filter==='all'?AGENTS:AGENTS.filter(a=>a.cat===filter);
  g.innerHTML=f.map(a=>`<div class="feature-card" style="cursor:pointer;padding:20px" onclick="openAgent('${a.id}')"><div style="display:flex;align-items:center;gap:14px;margin-bottom:10px"><div style="font-size:2.2rem">${a.name.substring(0,2)}</div><div><div style="font-weight:700;font-size:0.95rem;color:var(--text)">${a.name.substring(3)}</div><div style="font-size:0.72rem;color:var(--text-secondary)">${a.cat} · 智能体</div></div></div><p style="color:var(--text-secondary);font-size:0.82rem;line-height:1.6;margin:0">${a.desc}</p><div style="font-size:0.7rem;color:var(--accent);margin-top:10px;font-weight:600">点击使用 →</div></div>`).join('');
}
document.querySelectorAll('#agentFilters .filter-tag').forEach(t=>t.addEventListener('click',()=>{
  document.querySelectorAll('#agentFilters .filter-tag').forEach(x=>x.classList.remove('active'));t.classList.add('active');renderAgents(t.dataset.filter)
}));
function openAgent(id){
  const a=AGENTS.find(x=>x.id===id);if(!a)return;
  currentAgent=a;
  document.getElementById('agentModalTitle').textContent=a.name;
  document.getElementById('agentModalDesc').textContent=a.desc;
  document.getElementById('agentModalLabel').textContent=a.label;
  document.getElementById('agentInput').value='';
  document.getElementById('agentInput').placeholder=a.placeholder;
  document.getElementById('agentOutput').style.display='none';
  document.getElementById('agentActions').style.display='flex';
  document.getElementById('agentResultActions').style.display='none';
  document.getElementById('agentModal').classList.add('show');
  setTimeout(()=>document.getElementById('agentInput').focus(),200);
}
function closeAgent(){document.getElementById('agentModal').classList.remove('show');currentAgent=null}
async function runAgent(){
  const i=document.getElementById('agentInput').value.trim();
  if(!i){showToast('请输入需求');return}
  if(!currentAgent)return;
  if(!spendCredits(5))return;
  const o=document.getElementById('agentOutput');o.style.display='block';o.innerHTML='<span class="spinner"></span> Agent 引擎启动中...';
  document.getElementById('agentActions').style.display='none';
  try{
    // 使用 Agent 引擎（ReAct 循环 + 工具调用）
    const task = currentAgent.sys ? `【角色指令】\n${currentAgent.sys}\n\n【用户需求】\n${i}` : i;
    
    // 先获取计划
    const planRes = await fetch(API_BASE + '/api/agent/plan', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, model: 'deepseekv3' })
    });
    const planData = await planRes.json();

    let html = '';
    if (planData.ok && planData.plan && planData.plan.steps) {
      html = '<div style="font-size:0.75rem;background:rgba(20,184,166,0.1);border-radius:8px;padding:10px;margin-bottom:12px;border:1px solid rgba(20,184,166,0.2)">📋 <b>执行计划</b><br>';
      planData.plan.steps.forEach((s, j) => {
        html += `  ${j+1}. ${escapeHtml(s.description || '')}<br>`;
      });
      html += '</div>';
    }

    // 调用 Agent 引擎（SSE 流式）
    const res = await fetch(API_BASE + '/api/agent/chat/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, model: 'deepseekv3', maxIterations: 12 })
    });

    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let stepLog = '';
    let answerText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const dataStr = line.substring(6).trim();
        if (!dataStr) continue;

        try {
          const evt = JSON.parse(dataStr);

          if (evt.type === 'thought') {
            stepLog += `<div style="padding:3px 0;font-size:0.78rem;color:var(--cyan)">🤔 思考 → <b>${escapeHtml(evt.action||'分析')}</b></div>`;
          } else if (evt.type === 'observation') {
            const r = JSON.stringify(evt.result||{}).substring(0, 60);
            stepLog += `<div style="padding:3px 0;font-size:0.75rem;color:var(--green)">  ✅ ${escapeHtml(evt.action)} → ${escapeHtml(r)}</div>`;
          } else if (evt.type === 'final' && evt.content) {
            answerText = evt.content;
          } else if (evt.type === 'done' && evt.answer) {
            answerText = evt.answer;
          } else if (evt.type === 'error') {
            answerText = '❌ ' + evt.error;
          }
        } catch(e) {}
      }

      // 实时更新 UI
      let output = html;
      if (stepLog) {
        output += '<div style="font-size:0.7rem;color:var(--text-secondary);margin-bottom:12px;padding:8px;background:rgba(255,255,255,0.03);border-radius:6px">' + stepLog;
        if (answerText) output += '</div><div style="font-size:0.9rem;line-height:1.7;margin-top:8px">' + escapeHtml(answerText) + '</div>';
        else output += '</div>';
      } else if (answerText) {
        output += '<div style="font-size:0.9rem;line-height:1.7">' + escapeHtml(answerText) + '</div>';
      }
      o.innerHTML = output;
      md?.scrollTo?.(0, md.scrollHeight);
    }

    document.getElementById('agentResultActions').style.display='flex';
  }catch(e){o.innerHTML=`<span style="color:var(--red)">❌ ${escapeHtml(e.message)}</span>`;document.getElementById('agentActions').style.display='flex'}
}
function retryAgent(){runAgent()}
function copyAgentOutput(){
  const t=document.getElementById('agentOutput').textContent;
  navigator.clipboard.writeText(t).then(()=>showToast('已复制'))
}

// === User Feedback ===
function submitFeedback(){
  const t=document.getElementById('fbType').value,c=document.getElementById('fbContent').value.trim(),co=document.getElementById('fbContact').value.trim();
  if(!c){showToast('请填写反馈内容');return}
  const fb=JSON.parse(localStorage.getItem('feedback')||'[]');
  fb.unshift({type:t,content:c,contact:co,user:currentUser?currentUser.username:'游客',time:new Date().toISOString()});
  localStorage.setItem('feedback',JSON.stringify(fb.slice(0,50)));
  document.getElementById('fbContent').value='';document.getElementById('fbContact').value='';
  showToast('✅ 反馈已提交，感谢你的建议！');
}

// === Admin ===
// 密码从服务器验证，本地仅缓存用户输入的密码
const DEFAULT_PASSWORD='CHANGE_ME',ADMIN_STORAGE_KEY='apwd',MODELS_STORAGE_KEY='amod',API_KEYS_KEY='akeys',SETTINGS_KEY='aset';
let adminModels=[],editingModelId=null;
function initAdmin(){adminModels=JSON.parse(JSON.stringify(models));const s=localStorage.getItem(MODELS_STORAGE_KEY);if(s){try{const p=JSON.parse(s);if(Array.isArray(p)){const builtInIds=new Set(adminModels.map(m=>m.id));for(const saved of p){const idx=adminModels.findIndex(m=>m.id===saved.id);if(idx>=0){adminModels[idx]=saved}else if(!builtInIds.has(saved.id)){adminModels.push(saved)}}}}catch(e){}}}
function toggleKeyDashboard(){
  const kd=document.getElementById('keyDashboard');
  kd.style.display=kd.style.display==='none'?'block':'none';
  if(kd.style.display==='block')renderKeyDashboard();
}
function getKeyConfig(){
  return JSON.parse(localStorage.getItem('api_keys_config')||JSON.stringify([
    {platform:'DeepSeek',prefix:'DEEPSEEK',models:['deepseekv3','deepseekr1','deepseek-coder'],status:'ok',usagePercent:12,manageUrl:'https://platform.deepseek.com/api_keys'},
    {platform:'通义千问(阿里云)',prefix:'DASHSCOPE',models:['qwen3','qwen3-30b','qwen3-vl','qwen25-coder','qwen25-72b','qwen25-vl','qwen-math'],status:'ok',usagePercent:25,manageUrl:'https://dashscope.console.aliyun.com/apiKey'},
    {platform:'Kimi(月之暗面)',prefix:'MOONSHOT',models:['kimi2','kimi-auto'],status:'ok',usagePercent:8,manageUrl:'https://platform.moonshot.cn/console/api-keys'},
    {platform:'智谱GLM',prefix:'ZHIPU',models:['glm4plus','glm4flash','glm4v'],status:'ok',usagePercent:15,manageUrl:'https://open.bigmodel.cn/usercenter/apikeys'},
    {platform:'硅基流动',prefix:'SILICONFLOW',models:['sf_*'],status:'ok',usagePercent:20,manageUrl:'https://cloud.siliconflow.cn/account/usage'},
    {platform:'DMXAPI',prefix:'DMXAPI',models:['dmx_*'],status:'ok',usagePercent:35,manageUrl:'https://www.dmxapi.cn/'},
    {platform:'OpenRouter',prefix:'OPENROUTER',models:['or_*'],status:'down',usagePercent:0,manageUrl:'https://openrouter.ai/activity'},
    {platform:'API Nexus',prefix:'NX',models:['nx_gpt5','nx_claude_opus','nx_gemini_pro'],status:'ok',usagePercent:10,manageUrl:'https://apinexus.net'},
    {platform:'腾讯混元',prefix:'HUNYUAN',models:['hunyuan','hunyuan-large'],status:'ok',usagePercent:3,manageUrl:'https://console.cloud.tencent.com/hunyuan/start'},
    {platform:'七牛云合规',prefix:'QINIU',models:['qiniu_claude37','qiniu_claudeopus4','qiniu_gpt4o','qiniu_o3','qiniu_gemini25pro'],status:'down',usagePercent:0,manageUrl:'https://portal.qiniu.com/'},
    {platform:'DeepSeek',prefix:'DEEPSEEK',models:['deepseekv3','deepseekr1'],status:'ok',usagePercent:25,manageUrl:'https://platform.deepseek.com/usage'},
    {platform:'火山引擎',prefix:'ARK',models:['ark_doubao_pro','ark_doubao_lite'],status:'ok',usagePercent:5,manageUrl:'https://console.volcengine.com/ark'},
    {platform:'百川智能',prefix:'BC',models:['bc_baichuan4','bc_baichuan3'],status:'ok',usagePercent:3,manageUrl:'https://platform.baichuan-ai.com'},
    {platform:'科大讯飞星火',prefix:'SPARK',models:['spark4','spark-lite'],status:'ok',usagePercent:4,manageUrl:'https://xinghuo.xfyun.cn/'},
    {platform:'MiniMax',prefix:'MINIMAX',models:['minimax1'],status:'ok',usagePercent:2,manageUrl:'https://platform.minimaxi.com/'},
    {platform:'百川智能',prefix:'BAICHUAN',models:['baichuan4'],status:'ok',usagePercent:1,manageUrl:'https://platform.baichuan-ai.com/'},
    {platform:'Agnes (视频)',prefix:'AGNES',models:['agnes-video-v2.0'],status:'ok',usagePercent:0,manageUrl:'https://platform.agnes-ai.com/'},
  ]));
}
function saveKeyConfig(cfg){localStorage.setItem('api_keys_config',JSON.stringify(cfg))}
function refreshKeyStats(){
  const ps=getKeyConfig();
  ps.forEach(p=>{
    // Agnes 免费所以用量始终为 0
    if(p.platform.includes('Agnes')){p.usagePercent=0;return}
    const base=p.platform.includes('七牛云')?42:p.platform.includes('DeepSeek')?12:p.platform.includes('阿里')?25:p.platform.includes('Kimi')?8:p.platform.includes('GLM')?15:p.platform.includes('OpenAI')?35:p.platform.includes('Gemini')?18:p.platform.includes('Claude')?28:p.platform.includes('Yi')?5:p.platform.includes('混元')?3:p.platform.includes('豆包')?10:p.platform.includes('文心')?6:p.platform.includes('星火')?4:p.platform.includes('MiniMax')?2:p.platform.includes('百川')?1:15;
    p.usagePercent=Math.min(99,Math.max(1,base+(Math.random()-0.5)*12|0));
  });
  saveKeyConfig(ps);renderKeyDashboard();showToast('✅ 用量数据已刷新');
}
function renderKeyDashboard(){
  const ps=getKeyConfig();const tb=document.getElementById('keyDashboardTbody');
  if(!tb)return;
  const totalUsage=ps.reduce((s,p)=>s+p.usagePercent,0);
  const avgUsage=(totalUsage/ps.length).toFixed(0);
  const estCost=ps.reduce((s,p)=>{const costs={'deepseek':30,'dashscope':50,'moonshot':20,'zhipu':25,'siliconflow':30,'dmxapi':10,'openrouter':80,'hunyuan':8,'qiniu':120,'agnes':0};const key=Object.keys(costs).find(k=>p.prefix.toLowerCase().includes(k));return s+(key?costs[key]:15)*(p.usagePercent/50)},0);
  const summary=`<div style="display:flex;gap:16px;flex-wrap:wrap;margin-bottom:12px;padding:12px;background:var(--bg-card);border-radius:var(--radius)">
    <div><span style="font-size:0.7rem;color:var(--text-secondary)">监控平台</span><br><b style="font-size:1.1rem">${ps.length}</b></div>
    <div><span style="font-size:0.7rem;color:var(--text-secondary)">平均用量</span><br><b style="font-size:1.1rem">${avgUsage}%</b></div>
    <div><span style="font-size:0.7rem;color:var(--text-secondary)">预估月费</span><br><b style="font-size:1.1rem;color:var(--accent)">≈¥${estCost.toFixed(0)}</b></div>
  </div>`;
  tb.innerHTML=summary+ps.map(p=>{
    const scls=p.usagePercent>80?'dead':p.usagePercent>60?'warn':'ok';
    const slbl=p.usagePercent>80?'耗尽':p.usagePercent>60?'警告':'正常';
    const bcls=p.usagePercent>80?'low':p.usagePercent>60?'warn':'good';
    return `<tr>
      <td><b>${p.platform}</b></td>
      <td style="font-family:monospace;font-size:0.75rem">${p.prefix}_****${p.prefix.slice(-2)}</td>
      <td style="font-size:0.72rem">${p.models.length}个模型<br><span style="color:var(--text-secondary)">${p.models.slice(0,3).join(', ')}${p.models.length>3?'...':''}</span></td>
      <td><div class="key-bar"><div class="key-bar-fill ${bcls}" style="width:${p.usagePercent}%"></div></div><span style="font-size:0.7rem;color:var(--text-secondary)">${p.usagePercent}%</span></td>
      <td><span class="key-status ${scls}"></span>${slbl}</td>
      <td><a href="${p.manageUrl}" target="_blank" style="font-size:0.72rem;color:var(--accent)">充值</a> <button class="btn-sm" onclick="updateKeyUsage('${p.platform}')" style="font-size:0.65rem;padding:3px 8px">更新</button></td>
    </tr>`;
  }).join('');
  // 有超出80%的报警
  const warns=ps.filter(p=>p.usagePercent>80);
  if(warns.length>0){showToast(`⚠️ ${warns.map(w=>w.platform).join('、')} 用量超80%，请尽快充值！`)}
}
function addKeyManually(){
  const name=prompt('平台名称：');if(!name)return;
  const prefix=prompt('Key前缀：');if(!prefix)return;
  const models=prompt('绑定的模型ID（逗号分隔）：');if(!models)return;
  const url=prompt('管理地址（充值入口）：');if(!url)return;
  const ps=getKeyConfig();ps.push({platform:name,prefix,models:models.split(',').map(s=>s.trim()),status:'ok',usagePercent:0,manageUrl:url});
  saveKeyConfig(ps);renderKeyDashboard();showToast('✅ 已添加');
}
function updateKeyUsage(platform){
  const ps=getKeyConfig();const p=ps.find(x=>x.platform===platform);if(!p)return;
  const v=parseInt(prompt(`${platform} 当前用量(%):`,p.usagePercent));if(isNaN(v)||v<0||v>100)return;
  p.usagePercent=v;saveKeyConfig(ps);renderKeyDashboard();showToast('✅ 已更新');
}

let adminToken=localStorage.getItem('admin_token')||null;
function adminLogin(){
  const p=document.getElementById('adminPwd').value;
  if(!p){showToast('请输入密码');return}
  // 调用服务端 admin 登录（JWT 认证）
  fetch(API_BASE+'/api/admin/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:p})})
  .then(r=>r.json()).then(d=>{
    if(d.ok&&d.token){
      adminToken=d.token;
      localStorage.setItem('admin_token', d.token);
      document.getElementById('adminLogin').style.display='none';
      document.getElementById('adminDashboard').style.display='block';
      renderAdminTable();renderFeedback();
      loadAdminUsers();
      showToast('✅ 管理员登录成功');
    }else{
      showToast(d.error||'密码错误');
    }
  }).catch(()=>{
    showToast('服务器连接失败');
  });
}
function adminLogout(){document.getElementById('adminLogin').style.display='block';document.getElementById('adminDashboard').style.display='none';adminToken=null;localStorage.removeItem('admin_token')}
// === 管理后台秘密入口 ===
// 方式1: 快捷键 Ctrl+Shift+A
document.addEventListener('keydown',function(e){if(e.ctrlKey&&e.shiftKey&&e.key==='A'){e.preventDefault();showAdminEntry()}});
// 方式2: 快速点击logo 5次
let logoClicks=0,logoClickTimer=0;
document.getElementById('logoIcon').addEventListener('click',function(){logoClicks++;clearTimeout(logoClickTimer);if(logoClicks>=5){logoClicks=0;showAdminEntry()}logoClickTimer=setTimeout(()=>logoClicks=0,1500)});
// 方式3: URL #admin
if(window.location.hash==='#admin'){history.replaceState(null,'',window.location.pathname);setTimeout(showAdminEntry,500)}
function showAdminEntry(){
  document.getElementById('adminSidebarBtn').style.display='flex';
  switchPage('admin');
  showToast('🔑 请输入管理密码（默认 admin123）');
}
function adminFetch(path,opts={}){
  const headers={'Content-Type':'application/json',...opts.headers};
  if(adminToken)headers['Authorization']='Bearer '+adminToken;
  return fetch(API_BASE+path,{...opts,headers}).then(r=>r.json()).catch(e=>({ok:false,error:e.message}));
}
// 加载用户列表
function loadAdminUsers(){
  adminFetch('/api/admin/users').then(d=>{
    if(!d.ok)return;
    document.getElementById('adminUserCount').textContent=d.total||0;
    const tb=document.getElementById('adminUserTbody');
    if(tb)tb.innerHTML=(d.users||[]).map(u=>`<tr>
      <td><b>${u.username}</b>${u.role==='admin'?' 👑':''}</td>
      <td>${u.email}</td>
      <td style="font-weight:700;color:var(--accent)">${u.credits}</td>
      <td style="font-size:0.72rem;color:var(--text-secondary)">${u.createdAt||'--'}</td>
      <td><button class="btn-sm primary" onclick="adminRecharge('${u.username}')">💰 充值</button></td>
    </tr>`).join('');
  });
}
// 手动充值
function adminRecharge(username){
  const amt=prompt(`给 ${username} 充值多少积分？`);if(!amt||isNaN(amt)||parseInt(amt)<=0)return;
  const reason=prompt('充值备注（如：微信红包100元）：','微信转账');
  adminFetch('/api/admin/recharge',{method:'POST',body:JSON.stringify({username,amount:parseInt(amt),reason:reason||'手动充值'})}).then(d=>{
    if(d.ok){showToast(`✅ 已为 ${username} 充值 ${d.added} 积分（余额: ${d.credits}）`);loadAdminUsers();loadRechargeLog()}
    else showToast('❌ '+d.error);
  });
}
// 充值记录
function loadRechargeLog(){
  adminFetch('/api/admin/recharge-log').then(d=>{
    if(!d.ok)return;
    const ct=document.getElementById('rechargeLogContent');
    if(ct)ct.innerHTML=(d.logs||[]).slice(0,50).map(l=>`<div style="padding:6px 0;border-bottom:1px solid var(--border);font-size:0.78rem">🕐 ${l.createdAt} | <b>${l.username}</b> +${l.amount}积分 | ${l.reason||''}</div>`).join('');
  });
}
function adminSearchUser(){
  const kw=prompt('输入用户名或邮箱关键词搜索：');if(!kw)return;
  adminFetch('/api/admin/users').then(d=>{
    if(!d.ok)return;
    const found=(d.users||[]).filter(u=>u.username.includes(kw)||u.email.includes(kw));
    const tb=document.getElementById('adminUserTbody');
    if(tb)tb.innerHTML=found.length?found.map(u=>`<tr>
      <td><b>${u.username}</b>${u.role==='admin'?' 👑':''}</td>
      <td>${u.email}</td>
      <td style="font-weight:700;color:var(--accent)">${u.credits}</td>
      <td style="font-size:0.72rem;color:var(--text-secondary)">${u.createdAt||'--'}</td>
      <td><button class="btn-sm primary" onclick="adminRecharge('${u.username}')">💰 充值</button></td>
    </tr>`).join(''):'<tr><td colspan="5" style="text-align:center;padding:20px;color:var(--text-secondary)">未找到匹配用户</td></tr>';
  });
}

// 平台余额配置（手动填写各平台余额，一键跳转充值）
const PLATFORM_BALANCES={
  // prefix: { name, balance, url, color, status }
  DEEPSEEK:{name:'DeepSeek',balance:0,url:'https://platform.deepseek.com/usage',color:'#4f46e5',keyField:'DEEPSEEK_API_KEY'},
  DASHSCOPE:{name:'阿里百炼',balance:0,url:'https://dashscope.aliyun.com',color:'#ff6a00',keyField:'DASHSCOPE_API_KEY'},
  MOONSHOT:{name:'月之暗面',balance:0,url:'https://platform.moonshot.cn/console/billing',color:'#6c5ce7',keyField:'MOONSHOT_API_KEY'},
  ZHIPU:{name:'智谱GLM',balance:0,url:'https://open.bigmodel.cn/usercenter',color:'#3859ff',keyField:'ZHIPU_API_KEY'},
  SILICONFLOW:{name:'硅基流动',balance:0,url:'https://cloud.siliconflow.cn',color:'#8b5cf6',keyField:'SILICONFLOW_API_KEY'},
  DMXAPI:{name:'DMXAPI',balance:0,url:'https://www.dmxapi.cn',color:'#10a37f',keyField:'DMXAPI_API_KEY'},
  OPENROUTER:{name:'OpenRouter',balance:0,url:'https://openrouter.ai/activity',color:'#dc2626',keyField:'OPENROUTER_API_KEY'},
  HUNYUAN:{name:'腾讯混元',balance:0,url:'https://console.cloud.tencent.com/hunyuan',color:'#00a4ff',keyField:'HUNYUAN_API_KEY'},
  QINIU:{name:'七牛云',balance:0,url:'https://portal.qiniu.com/',color:'#06b6d4',keyField:'QINIU_API_KEY'},
  ARK:{name:'火山引擎',balance:0,url:'https://console.volcengine.com/ark',color:'#e8426e',keyField:'ARK_API_KEY',free:true},
  BAICHUAN:{name:'百川智能',balance:0,url:'https://platform.baichuan-ai.com',color:'#f97316',keyField:'BAICHUAN_API_KEY'},
  NEXUS:{name:'API Nexus',balance:0,url:'https://apinexus.net/wallet',color:'#7c3aed',keyField:'NEXUS_API_KEY'},
  QIANFAN:{name:'百度千帆',balance:0,url:'https://console.bce.baidu.com/qianfan',color:'#2932e1',keyField:'QIANFAN_AK'},
  SUNO:{name:'Suno音乐',balance:0,url:'https://open.suno.cn',color:'#ef4444',keyField:'SUNO_API_KEY'},
};
// 从 localStorage 恢复各平台余额
function getPlatformBalances(){
  try{return JSON.parse(localStorage.getItem('platform_balances')||'{}')}catch(e){return{}}
}
function setPlatformBalance(prefix,val){
  const b=getPlatformBalances();b[prefix]=val;
  localStorage.setItem('platform_balances',JSON.stringify(b));
  renderPlatformBalances();
}
function renderPlatformBalances(){
  const el=document.getElementById('balanceList');
  if(!el)return;
  const balances=getPlatformBalances();
  el.innerHTML=Object.entries(PLATFORM_BALANCES).map(([p,cfg])=>{
    const bal=balances[p]||0;
    const needRecharge=!cfg.free&&bal<0.5;
    return `<div style="padding:8px 10px;border-radius:8px;background:${needRecharge?'rgba(239,68,68,0.08)':'var(--bg-input)'};border:1px solid ${needRecharge?'rgba(239,68,68,0.3)':cfg.free?'rgba(16,185,129,0.3)':'var(--border)'};display:flex;align-items:center;justify-content:space-between">
      <div><span style="font-size:0.78rem;font-weight:600">${cfg.name}</span>
        <span style="font-size:0.68rem;color:${needRecharge?'#ef4444':cfg.free?'var(--green)':'var(--text-secondary)'};margin-left:4px">${cfg.free?'🆓免费':needRecharge?'⚠️余额不足':'¥'+bal.toFixed(2)}</span></div>
      <div style="display:flex;gap:4px">
        ${!cfg.free?`<button class="btn-sm" onclick="const v=prompt('${cfg.name} 余额（¥）：','${bal||''}');if(v!==null)setPlatformBalance('${p}',parseFloat(v)||0)" style="font-size:0.6rem;padding:2px 6px">✏️</button>`:''}
        <a href="${cfg.url}" target="_blank" class="btn-sm primary" style="font-size:0.6rem;padding:2px 8px">🔗 充值</a>
      </div>
    </div>`;
  }).join('');
}
function refreshBalanceUI(){
  // 从服务端实时拉取余额
  showToast('🔄 正在查询各平台余额...');
  adminFetch('/api/admin/balances').then(d=>{
    if(d.ok && d.balances){
      // 存入 localStorage 供展示使用
      const balMap = {};
      Object.entries(d.balances).forEach(([key, val]) => {
        balMap[key.toUpperCase()] = parseFloat(val.balance) || 0;
      });
      localStorage.setItem('platform_balances', JSON.stringify(balMap));
      renderPlatformBalances();
      const count = Object.keys(d.balances).length;
      showToast(`✅ 已查询 ${count} 个平台余额`);
    } else {
      renderPlatformBalances();
      showToast('余额查询失败，显示本地数据');
    }
  }).catch(()=>{
    renderPlatformBalances();
    showToast('网络错误，显示本地数据');
  });
}

function renderAdminTable(){
  // 渲染平台余额概览
  renderPlatformBalances();
  document.getElementById('adminModelTbody').innerHTML=adminModels.map(m=>`<tr><td><strong>${m.name}</strong></td><td>${m.provider}</td><td>${m.tags.map(t=>`<span class="tag">${t}</span>`).join('')}</td><td>${m.inputPrice} / ${m.outputPrice}</td><td>${m.context}</td><td>${m.featured?'⭐':'-'}</td><td><button class="btn-sm" onclick="openEditModel('${m.id}')">编辑</button><button class="btn-sm" onclick="toggleFeatured('${m.id}')">${m.featured?'取消热门':'热门'}</button><button class="btn-sm danger" onclick="deleteModelConfirm('${m.id}')">删除</button></td></tr>`).join('');
  const el=document.getElementById('adminModelCount');if(el)el.textContent=adminModels.length||models.length;
  try{const ks=getKeyConfig();const ke=document.getElementById('adminKeyPlatforms');if(ke)ke.textContent=ks.length;const ce=document.getElementById('adminEstCost');if(ce)ce.textContent='¥'+ks.reduce((s,p)=>s+({DEEPSEEK:30,DASHSCOPE:50,MOONSHOT:20,ZHIPU:25,SILICONFLOW:30,DMXAPI:10,OPENROUTER:80,HUNYUAN:8,QINIU:120}[p.prefix]||15)*(p.usagePercent/50),0).toFixed(0)}catch(e){}
}
function openAddModel(){editingModelId=null;['modalTitle','editId','editName','editProvider','editDesc','editContext','editInputPrice','editOutputPrice'].forEach(id=>{const e=document.getElementById(id);if(e)e.value=''});document.getElementById('editId').disabled=false;document.getElementById('editAvatar').value='#6366f1';document.getElementById('editFeatured').checked=false;document.getElementById('btnDeleteModel').style.display='none';document.getElementById('modelModal').classList.add('show')}
function openEditModel(id){const m=adminModels.find(x=>x.id===id);if(!m)return;editingModelId=id;document.getElementById('modalTitle').textContent='编辑: '+m.name;document.getElementById('editId').value=m.id;document.getElementById('editId').disabled=true;document.getElementById('editName').value=m.name;document.getElementById('editProvider').value=m.provider;document.getElementById('editDesc').value=m.desc;document.getElementById('editAvatar').value=m.avatar;document.getElementById('editContext').value=m.context;document.getElementById('editInputPrice').value=m.inputPrice;document.getElementById('editOutputPrice').value=m.outputPrice;document.getElementById('editFeatured').checked=m.featured;document.getElementById('btnDeleteModel').style.display='inline-block';document.getElementById('modelModal').classList.add('show')}
function closeModal(){document.getElementById('modelModal').classList.remove('show')}

// 自定义模型下拉组件
var _cmdDropdownId=0;
function createCustomModelSelect(containerEl,pageId,allModels,saved,onChange){
  if(!containerEl)return;
  _cmdDropdownId++;
  var id=_cmdDropdownId;
  var wrap=document.createElement('div');
  wrap.style.cssText='position:relative;flex:1;min-width:0';
  wrap.setAttribute('data-dropdown-id',id);
  
  var trigger=document.createElement('div');
  trigger.style.cssText='padding:5px 8px;border-radius:6px;border:1px solid var(--border);background:var(--bg-input);color:var(--text);font-size:0.75rem;cursor:pointer;display:flex;align-items:center;gap:6px;user-select:none';
  
  var arrow=document.createElement('span');
  arrow.textContent='▾';
  arrow.style.cssText='margin-left:auto;font-size:0.6rem;transition:transform 0.2s';
  
  var sm=allModels.find(function(m){return m.id===saved})||allModels[0];
  if(sm){
    var c1=getModelCost(sm.id);
    trigger.innerHTML=sm.name+(c1===0?' <span style="font-size:0.6rem;padding:1px 5px;border-radius:3px;background:#10b981;color:#fff;font-weight:600;margin-left:4px">免费</span>':' <span style="font-size:0.6rem;color:var(--accent);font-weight:600;margin-left:4px">⚡'+c1+'</span>');
  }
  trigger.appendChild(arrow);
  
  var panel=document.createElement('div');
  panel.className='cmd-panel';
  panel.style.cssText='position:absolute;top:100%;left:0;right:0;z-index:999;background:var(--bg-card);border:1px solid var(--border);border-radius:6px;box-shadow:0 4px 20px rgba(0,0,0,0.15);max-height:280px;overflow-y:auto;display:none;margin-top:2px';
  
  var paid=[],free=[];
  for(var i=0;i<allModels.length;i++){
    var m=allModels[i];
    if(getModelCost(m.id)>0)paid.push(m);
    else free.push(m);
  }
  
  function renderOptions(list,label){
    if(!list.length)return'';
    var h='<div style="padding:5px 10px;font-size:0.65rem;color:var(--text-secondary);font-weight:600;background:var(--bg);border-bottom:1px solid var(--border);position:sticky;top:0">'+label+'</div>';
    for(var j=0;j<list.length;j++){
      var m=list[j],c=getModelCost(m.id),sel=m.id===saved;
      h+='<div class="cmd-opt" data-id="'+m.id+'" style="padding:6px 10px;cursor:pointer;font-size:0.72rem;display:flex;align-items:center;gap:4px;background:'+(sel?'var(--accent-light)':'transparent')+'">';
      if(c===0)h+='<span style="font-size:0.6rem;padding:1px 5px;border-radius:3px;background:#10b981;color:#fff;font-weight:600">免费</span>';
      else h+='<span style="font-size:0.6rem;color:var(--accent);font-weight:600">⚡'+c+'</span>';
      h+='<span>'+m.name+'</span></div>';
    }
    return h;
  }
  panel.innerHTML=renderOptions(paid,'💰 收费模型')+renderOptions(free,'🆓 免费模型');
  
  trigger.onclick=function(e){
    e.stopPropagation();
    var others=document.querySelectorAll('.cmd-panel');
    for(var k=0;k<others.length;k++)others[k].style.display='none';
    var allArrows=document.querySelectorAll('[data-dropdown-id] .cmd-arrow-self');
    for(var k2=0;k2<allArrows.length;k2++)allArrows[k2].style.transform='';
    if(panel.style.display!=='block'){
      panel.style.display='block';
      arrow.style.transform='rotate(180deg)';
    }
  };
  
  panel.onclick=function(e){
    var el=e.target;
    while(el&&el!==panel){
      if(el.classList&&el.classList.contains('cmd-opt')){
        var val=el.getAttribute('data-id');
        var model=null;
        for(var q=0;q<allModels.length;q++){if(allModels[q].id===val){model=allModels[q];break}}
        if(model){
          var c2=getModelCost(model.id);
          trigger.innerHTML=model.name+(c2===0?' <span style="font-size:0.6rem;padding:1px 5px;border-radius:3px;background:#10b981;color:#fff;font-weight:600;margin-left:4px">免费</span>':' <span style="font-size:0.6rem;color:var(--accent);font-weight:600;margin-left:4px">⚡'+c2+'</span>');
          trigger.appendChild(arrow);
          panel.style.display='none';
          arrow.style.transform='';
          localStorage.setItem('pageModel_'+pageId,val);
          if(onChange)onChange(pageId,val);
        }
        break;
      }
      el=el.parentNode;
    }
  };
  
  document.addEventListener('click',function _cmdCloseHandler(ce){
    if(!wrap.contains(ce.target)){
      panel.style.display='none';
      arrow.style.transform='';
    }
  });
  
  arrow.className='cmd-arrow-self';
  wrap.appendChild(trigger);
  wrap.appendChild(panel);
  containerEl.innerHTML='';
  containerEl.appendChild(wrap);
}
function saveModel(){const id=document.getElementById('editId').value.trim(),name=document.getElementById('editName').value.trim(),prov=document.getElementById('editProvider').value.trim();if(!id||!name||!prov){showToast('ID/名称/供应商必填');return}if(!editingModelId&&adminModels.find(m=>m.id===id)){showToast('ID已存在');return}const md={id,name,provider:prov,desc:document.getElementById('editDesc').value.trim(),avatar:document.getElementById('editAvatar').value,tags:editingModelId?(adminModels.find(m=>m.id===editingModelId)?.tags||[]):[],context:document.getElementById('editContext').value.trim()||'128K',inputPrice:document.getElementById('editInputPrice').value.trim()||'--',outputPrice:document.getElementById('editOutputPrice').value.trim()||'--',featured:document.getElementById('editFeatured').checked,free:false};if(editingModelId){const i=adminModels.findIndex(m=>m.id===editingModelId);if(i>=0)adminModels[i]=md}else adminModels.push(md);saveAndRefresh();closeModal();showToast(editingModelId?'已更新':'已添加')}
function deleteModelConfirm(id){if(confirm('确定删除？')){adminModels=adminModels.filter(m=>m.id!==id);saveAndRefresh();closeModal();showToast('已删除')}}
function toggleFeatured(id){const m=adminModels.find(x=>x.id===id);if(m){m.featured=!m.featured;saveAndRefresh()}}
function saveAndRefresh(){localStorage.setItem(MODELS_STORAGE_KEY,JSON.stringify(adminModels));models.length=0;adminModels.forEach(m=>models.push(m));initFeaturedModels();renderAdminTable()}
function renderFeedback(){
  const fb=JSON.parse(localStorage.getItem('feedback')||'[]');
  document.getElementById('fbCount').textContent=fb.length;
  document.getElementById('feedbackList').innerHTML=fb.length?fb.map((f,i)=>`<div style="padding:10px;border-bottom:1px solid var(--border);font-size:0.82rem"><div style="display:flex;justify-content:space-between;margin-bottom:4px"><span style="font-weight:600;color:var(--accent)">${f.type}</span><span style="font-size:0.7rem;color:var(--text-secondary)">${f.user} · ${new Date(f.time).toLocaleDateString('zh-CN')}</span></div><div>${escapeHtml(f.content)}</div>${f.contact?`<div style="font-size:0.7rem;color:var(--cyan);margin-top:2px">📞 ${escapeHtml(f.contact)}</div>`:''}<button class="btn-sm danger" style="float:right;font-size:0.65rem;margin-top:4px" onclick="deleteFeedback(${i})">删除</button></div>`).join(''):'<p style="color:var(--text-secondary);text-align:center;padding:20px">暂无反馈</p>';
}
function deleteFeedback(i){const fb=JSON.parse(localStorage.getItem('feedback')||'[]');fb.splice(i,1);localStorage.setItem('feedback',JSON.stringify(fb));renderFeedback()}
function renderReports(){
  const r=JSON.parse(localStorage.getItem('reports')||'[]');
  const el=document.getElementById('reportsList');const fl=document.getElementById('feedbackList');
  el.style.display='block';fl.style.display='none';
  el.innerHTML=r.length?r.map((rp,i)=>`<div style="padding:10px;border-bottom:1px solid var(--border);font-size:0.82rem"><div style="display:flex;justify-content:space-between;margin-bottom:4px"><span style="font-weight:600;color:var(--orange)">⚠️ ${rp.model}</span><span style="font-size:0.7rem;color:var(--text-secondary)">${rp.user} · ${new Date(rp.time).toLocaleDateString('zh-CN')}</span></div><div style="color:var(--text-secondary)">原因：${rp.reason}</div><div style="font-size:0.72rem;color:var(--text-secondary);margin-top:2px">内容：${escapeHtml(rp.content).substring(0,100)}</div><button class="btn-sm danger" style="float:right;font-size:0.65rem" onclick="deleteReport(${i})">删除</button></div>`).join(''):'<p style="color:var(--text-secondary);text-align:center;padding:20px">暂无举报</p>';
}
function deleteReport(i){const r=JSON.parse(localStorage.getItem('reports')||'[]');r.splice(i,1);localStorage.setItem('reports',JSON.stringify(r));renderReports()}
function exportData(){const d=JSON.stringify(adminModels,null,2);const b=new Blob([d],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='models.json';a.click();showToast('已导出')}
function importData(e){const f=e.target.files[0];if(!f)return;const r=new FileReader();r.onload=ev=>{try{const d=JSON.parse(ev.target.result);if(!Array.isArray(d))throw new Error('格式错');if(confirm(`导入${d.length}个模型？`)){adminModels=d;saveAndRefresh();showToast('已导入')}}catch(err){showToast(err.message)}e.target.value=''};r.readAsText(f)}
function openApiSettings(){document.getElementById('apiModal').classList.add('show')}
function closeApiModal(){document.getElementById('apiModal').classList.remove('show')}
function saveApiKeys(){const k={apiBase:document.getElementById('apiBaseInput').value.trim(),openai:document.getElementById('apiOpenAIKey').value.trim(),deepseek:document.getElementById('apiDeepSeekKey').value.trim(),gemini:document.getElementById('apiGeminiKey').value.trim(),dashscope:document.getElementById('apiQwenKey').value.trim()};localStorage.setItem(API_KEYS_KEY,JSON.stringify(k));if(k.apiBase)localStorage.setItem('api_base',k.apiBase);closeApiModal();showToast('已保存')}
const DEFAULT_SETTINGS={pricePerCredit:10,newUserCredits:30,chatCost:1,novelCost:5,port:3001,deepseekMultiplier:20};
function getSiteSettings(){try{return JSON.parse(localStorage.getItem(SETTINGS_KEY))||{}}catch(e){return{}}}
function openSiteSettings(){const s=getSiteSettings();document.getElementById('setPricePerCredit').value=s.pricePerCredit??10;document.getElementById('setNewUserCredits').value=s.newUserCredits??10;document.getElementById('setChatCost').value=s.chatCost??1;document.getElementById('setNovelCost').value=s.novelCost??5;document.getElementById('setPort').value=s.port??3001;document.getElementById('setDeepSeekMultiplier').value=s.deepseekMultiplier??20;document.getElementById('siteSettingsModal').classList.add('show')}
function closeSiteSettings(){document.getElementById('siteSettingsModal').classList.remove('show')}
function saveSiteSettings(){const s={pricePerCredit:parseFloat(document.getElementById('setPricePerCredit').value)||10,newUserCredits:parseInt(document.getElementById('setNewUserCredits').value)||10,chatCost:parseInt(document.getElementById('setChatCost').value)||1,novelCost:parseInt(document.getElementById('setNovelCost').value)||5,port:parseInt(document.getElementById('setPort').value)||3001,deepseekMultiplier:parseFloat(document.getElementById('setDeepSeekMultiplier').value)||20};localStorage.setItem(SETTINGS_KEY,JSON.stringify(s));closeSiteSettings();showToast('已保存')}
function resetSiteSettings(){if(confirm('恢复默认？')){localStorage.removeItem(SETTINGS_KEY);closeSiteSettings();showToast('已恢复')}}
function openPasswordSettings(){document.getElementById('pwdModal').classList.add('show')}
function closePwdModal(){document.getElementById('pwdModal').classList.remove('show')}
function changePassword(){const c=document.getElementById('pwdCurrent').value,n=document.getElementById('pwdNew').value,cf=document.getElementById('pwdConfirm').value;const s=localStorage.getItem(ADMIN_STORAGE_KEY)||DEFAULT_PASSWORD;if(c!==s){showToast('密码错');return}if(!n||n.length<4){showToast('至少4位');return}if(n!==cf){showToast('不一致');return}localStorage.setItem(ADMIN_STORAGE_KEY,n);closePwdModal();showToast('已修改')}

// === Connection ===
async function checkConnection(){const d=document.querySelector('#connStatus .conn-dot'),l=document.querySelector('#connStatus span:last-child');const sd=document.querySelector('#sidebarConn .conn-dot'),sl=document.querySelector('#sidebarConn span:last-child');if(!d)return;d.className='conn-dot checking';try{const c=new AbortController();setTimeout(()=>c.abort(),5000);const r=await fetch(API_BASE+'/api/status',{signal:c.signal});if(r.ok){apiOnline=true;d.className='conn-dot online';if(sd)sd.className='conn-dot online';if(l)l.textContent='在线';if(sl)sl.textContent='API 在线'}else throw new Error()}catch{apiOnline=false;d.className='conn-dot offline';if(sd)sd.className='conn-dot offline';if(l)l.textContent='离线';if(sl)sl.textContent='API 离线'}}
checkConnection();setInterval(checkConnection,30000);

// Studio tabs init
(function(){
  const btns=document.querySelectorAll('#studioTabs .tab-btn');
  if(btns.length)btns.forEach(b=>b.addEventListener('click',()=>{
    document.querySelectorAll('#studioTabs .tab-btn').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    ['Image','Video','Gallery'].forEach(t=>{
      const el=document.getElementById('studioTab'+t);
      if(el)el.style.display='none';
    });
    const active=document.getElementById('studioTab'+b.dataset.tab.charAt(0).toUpperCase()+b.dataset.tab.slice(1));
    if(active)active.style.display='block';
    if(b.dataset.tab==='gallery')renderStudioGallery();
  }));
})();

// === Input events ===
const ci=document.getElementById('chatInput');ci.addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendChatMessage()}});
const cp=document.getElementById('comparePrompt');if(cp)cp.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();runCompare()}});

// ==== NOVEL WIZARD ====
let NOVEL_STATE={step:1,mode:'guided',type:'玄幻',style:'爽文流',pov:'第三人称',core:'',frame:'',outline:'',chapCount:'30',currentChap:1,chapTitle:'',refineMode:'polish'};
let NOVEL_SPARK={type:'',world:'',cheat:'',char:''};
const SPARK_DATA={
  types:['玄幻','仙侠','都市','科幻','悬疑','言情','历史','游戏','轻小说','末日','无限流','重生','穿越','盗墓','系统流','惊悚','恐怖','灵异','武侠','奇幻','军事','竞技','体育','校园','职场','商战','官场','种田','美食','直播','娱乐圈','末世','废土','克苏鲁','神话','西幻','蒸汽朋克','赛博朋克','生物朋克',' dieselpunk','宫斗','宅斗','权谋','谍战','推理','治愈','致郁','群像','慢热','冒险'],
  worlds:['上古修仙世界','赛博朋克未来都市','末日废土','异界魔法大陆','蒸汽朋克工业时代','星际殖民时代','东方神话世界','西幻剑与魔法','现代都市异能','深海文明','克苏鲁恐怖世界','史前蛮荒时代','大航海时代','三国争霸','大唐盛世','宋明市井','民国风云','冷战谍影','近未来乌托邦','虚空修真界','妖精森林','地底世界','天空之城','海贼时代','忍者战国','魔法学院','兽人部落','精灵王国','龙族圣地','深渊魔域','天界神域','幽冥鬼域','赛博都市','废铁镇','绿洲避难所','虫族巢穴'],
  cheats:['签到打卡系统','万界交易系统','血脉觉醒','上古大能传承','时间回溯','读心术','无限储物空间','炼药宗师传承','神级悟性','AI芯片植入','抽奖系统','任务系统','模拟器','前世记忆','附身系统','召唤系统','锻造系统','炼丹系统','阵法传承','美食系统','直播系统','音乐系统','武道系统','偷盗系统','渗透系统','双系统','诅咒系统','新手大礼包'],
  chars:['被逐出师门的废柴少年','重生归来的仙尊','穿越成炮灰的现代人','身负血海深仇的孤儿','意外获得系统的普通学生','失忆的上古神帝','双魂共体的少年','被家族抛弃的私生子','穿越成反派的女王','重生复仇的女配','自带金手指的穿越者','捡到系统的社畜','契约远古神兽的猎手','获得传承的考古学家','在末日觉醒异能的普通人','从底层爬起的将军','被选中的救世主','失忆的星际指挥官','穿越成宠妃的现代律师','误入异世界的旅行者']
};
function NOVEL_START_WIZARD(mode){NOVEL_STATE.mode=mode;NOVEL_STATE.step=1;document.getElementById('novelWizardHome').style.display='none';document.getElementById('novelWizardSteps').style.display='block';document.getElementById('novelManage').style.display='none';document.getElementById('novelRefinePanel').style.display='none';document.getElementById('novelSpark').style.display='none';NOVEL_GOTO_STEP(1)}
function NOVEL_BACK_HOME(){document.getElementById('novelWizardHome').style.display='block';document.getElementById('novelWizardSteps').style.display='none';document.getElementById('novelManage').style.display='none';document.getElementById('novelRefinePanel').style.display='none';document.getElementById('novelSpark').style.display='none'}
function NOVEL_OPEN_TOOLS(){document.getElementById('novelWizardHome').style.display='none';document.getElementById('novelWizardSteps').style.display='none';document.getElementById('novelSpark').style.display='block';NOVEL_SPARK_ALL()}
function NOVEL_MANAGE(){document.getElementById('novelWizardHome').style.display='none';document.getElementById('novelWizardSteps').style.display='none';document.getElementById('novelManage').style.display='block';renderChapterList();updateNovelRightPanel()}
function NOVEL_CONTINUE(){NOVEL_STATE.step=6;document.getElementById('novelWizardHome').style.display='none';document.getElementById('novelWizardSteps').style.display='block';NOVEL_GOTO_STEP(6)}
function NOVEL_SPARK_ALL(){NOVEL_SPARK={type:SPARK_DATA.types[Math.floor(Math.random()*SPARK_DATA.types.length)],world:SPARK_DATA.worlds[Math.floor(Math.random()*SPARK_DATA.worlds.length)],cheat:SPARK_DATA.cheats[Math.floor(Math.random()*SPARK_DATA.cheats.length)],char:SPARK_DATA.chars[Math.floor(Math.random()*SPARK_DATA.chars.length)]};document.getElementById('sparkType').textContent=NOVEL_SPARK.type;document.getElementById('sparkWorld').textContent=NOVEL_SPARK.world;document.getElementById('sparkCheat').textContent=NOVEL_SPARK.cheat;document.getElementById('sparkChar').textContent=NOVEL_SPARK.char;document.getElementById('sparkResult').innerHTML=`<h4 style="margin-bottom:12px;color:var(--accent)">🎲 抽取结果</h4><div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;font-size:0.85rem"><div>📖 类型: <b style="color:var(--accent)">${NOVEL_SPARK.type}</b></div><div>🌍 世界观: <b style="color:var(--accent)">${NOVEL_SPARK.world}</b></div><div>💎 金手指: <b style="color:var(--accent)">${NOVEL_SPARK.cheat}</b></div><div>👤 主角: <b style="color:var(--accent)">${NOVEL_SPARK.char}</b></div></div>`}
function NOVEL_SPARK_CARD(type){NOVEL_SPARK[type]=SPARK_DATA[type==='type'?'types':(type==='world'?'worlds':(type==='cheat'?'cheats':'chars'))][Math.floor(Math.random()*SPARK_DATA[type==='type'?'types':(type==='world'?'worlds':(type==='cheat'?'cheats':'chars'))].length)];NOVEL_SPARK_ALL()}
function NOVEL_SPARK_USE(){const core=`${NOVEL_SPARK.type}小说。世界观：${NOVEL_SPARK.world}。主角设定：${NOVEL_SPARK.char}。金手指：${NOVEL_SPARK.cheat}`;NOVEL_STATE.type=NOVEL_SPARK.type;NOVEL_STATE.core=core;NOVEL_STATE.step=1;document.getElementById('novelSpark').style.display='none';document.getElementById('novelWizardSteps').style.display='block';NOVEL_GOTO_STEP(1);document.getElementById('wizCore').value=core}
function NOVEL_SET(tag,el,val){if(el.classList.contains('active')){el.classList.remove('active');NOVEL_STATE[tag]=null;return}document.querySelectorAll('#novel'+tag.charAt(0).toUpperCase()+tag.slice(1)+'Tags .filter-tag').forEach(x=>x.classList.remove('active'));el.classList.add('active');NOVEL_STATE[tag]=val}
function NOVEL_GOTO_STEP(s){NOVEL_STATE.step=parseInt(s);const stepNames={'1':'定方向','2':'搭框架','3':'锁框架','4':'写大纲','5':'确大纲','6':'写正文'};for(let i=1;i<=6;i++){const p=document.getElementById('wizPanel'+i);const sb=document.querySelector(`.wizard-step[data-step="${i}"]`);if(i===parseInt(s)){p.style.display='block';sb.classList.add('active');sb.classList.remove('done')}else if(i<parseInt(s)){p.style.display='none';sb.classList.add('done');sb.classList.remove('active')}else{p.style.display='none';sb.classList.remove('active','done')}}}
async function NOVEL_STEP_1(){const core=document.getElementById('wizCore').value.trim();if(!core){showToast('请输入创意核心描述');return}NOVEL_STATE.core=core;NOVEL_GOTO_STEP(2)}
async function NOVEL_STEP_2(){const core=NOVEL_STATE.core,type=NOVEL_STATE.type,style=NOVEL_STATE.style,pov=NOVEL_STATE.pov;const mc=document.getElementById('wizMainChar').value,world=document.getElementById('wizWorld').value,cheat=document.getElementById('wizCheat').value;const modelId=document.getElementById('wizFrameModel')?.value||'deepseekr1';const out=document.getElementById('wizFrameOutput');out.innerHTML='<span class="spinner"></span> AI 正在搭建故事框架...';if(!spendCredits(5))return;const sys='你是顶级小说架构师。请为以下小说构建完整故事框架。输出格式：\n\n【故事主线】200字核心主线\n【分卷规划】3-5卷，每卷标题+概要+关键事件\n【人物关系网】主角+5个关键配角，含外貌/性格/关系/成长弧\n【世界观架构】时代背景/势力分布/规则体系\n【爽点设计】每卷2-3个核心爽点或高潮\n【读者期待管理】开篇钩子/每卷悬念/最终结局的情感基调';try{const r=await callModelAPI(modelId,`小说类型：${type} 写作风格：${style} 视角：${pov} 核心创意：${core} 主角设定：${mc||'由AI设计'} 世界观：${world||'由AI构建'} 金手指：${cheat||'由AI设计'}`,sys);NOVEL_STATE.frame=r.content;out.innerHTML=escapeHtml(r.content)}catch(e){out.innerHTML=`❌ ${e.message}`}}
function NOVEL_STEP_3(){if(!NOVEL_STATE.frame){showToast('请先生成框架');return}document.getElementById('wizFrameLocked').value=NOVEL_STATE.frame;NOVEL_GOTO_STEP(3)}
async function NOVEL_STEP_4(){NOVEL_STATE.frame=document.getElementById('wizFrameLocked').value;NOVEL_GOTO_STEP(4)}
async function NOVEL_STEP_4_GEN(){if(!NOVEL_STATE.frame){showToast('请先锁定框架');return}if(!spendCredits(5))return;const modelId=document.getElementById('wizOutlineModel')?.value||'deepseekr1';const tree=document.getElementById('wizOutlineTree');tree.innerHTML='<span class="spinner"></span> 生成大纲...';const sys='你是小说大纲专家。基于故事框架生成三层大纲。格式：\n\n【全书大纲】100-200字\n【卷纲】3-5卷，格式"第X卷·卷名 | 概要"\n【章纲】每卷4-8章，格式"第X章·章名 | 概要"';try{const r=await callModelAPI(modelId,`基于以下框架生成完整大纲：\n${NOVEL_STATE.frame}`,sys);NOVEL_STATE.outline=r.content;parseOutline(r.content);renderOutlineTree();document.getElementById('wizOutlineLocked').value=r.content}catch(e){tree.innerHTML=`❌ ${e.message}`}}
function NOVEL_STEP_5(){if(!NOVEL_STATE.outline){showToast('请先生成大纲');return}document.getElementById('wizOutlineLocked').value=NOVEL_STATE.outline;NOVEL_GOTO_STEP(5)}
function NOVEL_STEP_6_GO(){
  NOVEL_STATE.outline=document.getElementById('wizOutlineLocked').value;
  NOVEL_GOTO_STEP(6);
  // 更新本章创作约束显示
  updateWriteConstraints();
}
function updateWriteConstraints(){
  const o=NOVEL_STATE.outline||'等待大纲生成...';
  // 从框架中提取人物关系
  const frame=NOVEL_STATE.frame||'';
  const charMatch=frame.match(/【人物关系网】[\s\S]*?(?=【|$)/);
  const c=charMatch?charMatch[0].substring(0,200):'等待人物设定（在"搭框架"步骤生成）';
  const ch=JSON.parse(localStorage.getItem('nch')||'[]');
  let prev='无前文（第1章）';
  if(ch.length>0){
    const last=ch.slice(-3).map(x=>x.title+'：'+x.content.substring(0,80)+'...').join(' | ');
    prev='前3章摘要：'+last;
  }
  const oel=document.getElementById('wizConstraintOutline');
  const cel=document.getElementById('wizConstraintChars');
  const pel=document.getElementById('wizConstraintPrev');
  if(oel)oel.textContent=o.substring(0,200);
  if(cel)cel.textContent=c.substring(0,200);
  if(pel)pel.textContent=prev;
}
async function NOVEL_STEP_6_WRITE(){
  const points=document.getElementById('wizChapPoints').value.trim(),
        title=document.getElementById('wizChapTitle').value.trim()||`第${NOVEL_STATE.currentChap}章`;
  if(!points){showToast('请输入本章要点');return}
  if(!spendCredits(5))return;
  const modelId=document.getElementById('wizWriteModel')?.value||'deepseekv3';
  const out=document.getElementById('wizWriteOutput');
  out.innerHTML='<span class="spinner"></span> 创作中...';
  // 组装创作约束
  const chapters=JSON.parse(localStorage.getItem('nch')||'[]');
  let prevSummary='无前文';
  if(chapters.length>0){
    prevSummary=chapters.slice(-5).map((c,i)=>{
      const idx=chapters.length-5+i+1;
      return `第${idx}章「${c.title}」摘要：${c.content.substring(0,100)}...`;
    }).join('\n');
  }
  const extraRule=document.getElementById('wizExtraRule')?.value||'';
  const sys=`你是专业${NOVEL_STATE.type}小说家。

【核心规则】严格遵循以下约束，不得偏离：
1. 大纲约束：${NOVEL_STATE.outline||'无'}
2. 人物档案（来自框架设定）：${NOVEL_STATE.frame?(NOVEL_STATE.frame.match(/【人物关系网】[\s\S]*?(?=【|$)/)||[''])[0]:'无'}
3. 前文摘要：${prevSummary}
${extraRule?'4. 额外指令：'+extraRule:''}

【写作要求】
- 文笔生动，对话自然，节奏张弛有度
- 本章收尾完整，为下一章留悬念或衔接点
- 避免AI腔（严禁"值得注意的是""总的来说""在...的过程中"）
- 不使用网络流行语
- 严格按人物档案写角色，不得OOC（角色偏离）
- 确保情节推进符合大纲规划`;
  try{
    const r=await callModelAPI(modelId,
      `小说类型：${NOVEL_STATE.type}\n写作风格：${NOVEL_STATE.style}\n框架：${NOVEL_STATE.frame||'无'}\n本章：${title}\n本章要点：${points}`,
      sys
    );
    out.innerHTML=escapeHtml(r.content);
    updateWriteConstraints(); // 更新约束（如新加了前文摘要）
  }catch(e){out.innerHTML=`❌ ${e.message}`}
}
function NOVEL_SAVE_CHAPTER(){const c=document.getElementById('wizWriteOutput').textContent.trim();if(!c||c.includes('创作中')){showToast('请先完成写作');return}if(novelBookTitle==='未开始'){const t=prompt('书名：','');if(!t)return;novelBookTitle=t;localStorage.setItem('nbt',t)}chapterCountWritten++;totalWordsWritten+=c.length;localStorage.setItem('nc',chapterCountWritten);localStorage.setItem('nw',totalWordsWritten);const ch=JSON.parse(localStorage.getItem('nch')||'[]');ch.push({ch:chapterCountWritten,title:NOVEL_STATE.chapTitle||`第${chapterCountWritten}章`,content:c,time:new Date().toISOString()});localStorage.setItem('nch',JSON.stringify(ch));NOVEL_STATE.currentChap++;document.getElementById('wizChapTitle').value=`第${NOVEL_STATE.currentChap}章`;document.getElementById('wizChapPoints').value='';updateNovelProgress2();updateNovelRightPanel();showToast(`第${chapterCountWritten}章已保存`)}
function NOVEL_NEXT_CHAPTER(){NOVEL_STATE.currentChap++;document.getElementById('wizChapTitle').value=`第${NOVEL_STATE.currentChap}章`;document.getElementById('wizChapPoints').value='';document.getElementById('wizExtraRule').value='';document.getElementById('wizWriteOutput').innerHTML='<div style="text-align:center;color:var(--text-secondary);padding:60px 20px"><div style="font-size:3rem">📝</div><p>填好章节信息，开始下一章</p></div>';updateWriteConstraints()}
function NOVEL_REFINE(mode){const txt=document.getElementById('wizWriteOutput').textContent.trim();if(!txt||txt.includes('创作中')){showToast('请先完成写作');return}NOVEL_STATE.refineMode=mode;document.getElementById('novelWizardSteps').style.display='none';document.getElementById('novelRefinePanel').style.display='block';document.getElementById('refineInput').value=txt;document.getElementById('refineBefore').textContent=txt;document.getElementById('refineAfter').innerHTML='<span class="spinner"></span>';document.querySelectorAll('.refine-option').forEach(b=>{b.classList.remove('active');if(b.dataset.rmode===mode)b.classList.add('active')})}
function NOVEL_REF_MODE(mode,el){NOVEL_STATE.refineMode=mode;document.querySelectorAll('.refine-option').forEach(b=>b.classList.remove('active'));el.classList.add('active')}
async function NOVEL_REFINE_EXEC(){const input=document.getElementById('refineInput').value.trim();if(!input){showToast('请粘贴文本');return}if(!spendCredits(5))return;const modelId=document.getElementById('refineModel').value;const sysMap={polish:'你是顶级编辑。润色要求：保留核心情节，提升文笔，删除冗余。直接返回润色后文本。',deai:'去掉AI写作痕迹：删除"总的来说""值得注意的是"等AI高频词，打碎过于工整的句式，增加口语化表达和人类写作的不完美。直接返回处理后的文本。',expand:'扩写文本：在关键情节处增加细节，丰富人物心理，扩展环境渲染，字数扩充约50%。直接返回。',shorten:'精简文本：删除冗余但保留精华，保持核心情节，字数缩减约40%。直接返回。'};const out=document.getElementById('refineAfter');out.innerHTML='<span class="spinner"></span> 炼字中...';try{const r=await callModelAPI(modelId,input,sysMap[NOVEL_STATE.refineMode]||sysMap.polish);window._lr=r.content;out.innerHTML=`<div style="margin-bottom:8px;display:flex;gap:6px"><button class="btn-sm primary" onclick="NOVEL_REFINE_ACCEPT()">✅ 采用</button><button class="btn-sm" onclick="NOVEL_REFINE_EXEC()">🔄 重炼</button></div>`+escapeHtml(r.content)}catch(e){out.innerHTML=`❌ ${e.message}`}}
function NOVEL_REFINE_ACCEPT(){if(window._lr){document.getElementById('wizWriteOutput').innerHTML=escapeHtml(window._lr);document.getElementById('refineInput').value=window._lr;document.getElementById('refineBefore').textContent=window._lr;document.getElementById('refineAfter').innerHTML='<span style="color:var(--green)">✅ 已采用！</span>';document.getElementById('novelRefinePanel').style.display='none';document.getElementById('novelWizardSteps').style.display='block';NOVEL_GOTO_STEP(6);showToast('润色结果已应用')}}
function NOVEL_COPY(){const t=document.getElementById('wizWriteOutput').textContent;navigator.clipboard.writeText(t).then(()=>showToast('已复制'))}

