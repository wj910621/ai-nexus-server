'use strict';
// === Theme (default: dark) ===
const themeToggle=document.getElementById('themeToggle');
const savedTheme=localStorage.getItem('theme')||'dark';
document.documentElement.setAttribute('data-theme',savedTheme);
themeToggle.textContent=savedTheme==='light'?'☀️':'🌙';
themeToggle.addEventListener('click',()=>{
  const n=document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark';
  document.documentElement.setAttribute('data-theme',n);
  themeToggle.textContent=n==='light'?'☀️':'🌙';
  localStorage.setItem('theme',n);
});

// === Toast ===
function showToast(m){const t=document.getElementById('toast');t.textContent=m;t.style.display='block';setTimeout(()=>t.style.display='none',2500)}

// === PWA 安装 ===
let deferredPrompt=null;
window.addEventListener('beforeinstallprompt',(e)=>{
  e.preventDefault();
  deferredPrompt=e;
  document.getElementById('installBtn').style.display='inline-block';
  setTimeout(()=>{
    const toast=document.getElementById('pwaToast');
    if(toast && deferredPrompt) toast.style.display='flex';
  },5000);
});
function installPWA(){
  if(deferredPrompt){
    deferredPrompt.prompt();
    deferredPrompt.userChoice.then(r=>{
      document.getElementById('pwaToast').style.display='none';
      document.getElementById('installBtn').textContent='✅ 已添加到桌面';
      setTimeout(()=>document.getElementById('installBtn').style.display='none',3000);
      deferredPrompt=null;
    });
  } else {
    showToast('请通过浏览器菜单 → 更多工具 → 创建快捷方式 添加');
  }
}
document.getElementById('pwaInstallBtn').addEventListener('click',installPWA);

// === Nav (with sidebar + right panel updates) ===
function switchPage(name){
  document.querySelectorAll('.page').forEach(p=>p.classList.remove('active'));
  document.querySelectorAll('.sidebar-link').forEach(l=>l.classList.remove('active'));
  const pg=document.getElementById('page-'+name);if(pg)pg.classList.add('active');
  const nl=document.querySelector(`.sidebar-link[data-page="${name}"]`);if(nl)nl.classList.add('active');
  if(name==='models')initAllModels();
  if(name==='chat'){updateRightPanel('chat');setTimeout(initChatModels,200)}
  if(name==='compare')initCompareModels();
  if(name==='novel'){loadSavedOutline();switchNovelTab(novelTab);setTimeout(()=>renderModelBar('novel','modelBar_novel'),50)}
  if(name==='media'){loadSavedOutline();setTimeout(()=>renderModelBar('media','modelBar_media'),50)}
  if(name==='admin'){if(adminToken){document.getElementById('adminLogin').style.display='none';document.getElementById('adminDashboard').style.display='block';renderAdminTable()}else{document.getElementById('adminLogin').style.display='block';document.getElementById('adminDashboard').style.display='none'}}
  if(name==='agents'){renderAgents('all');setTimeout(()=>renderModelBar('agents','modelBar_agents'),50)}
  if(name!='chat'&&name!='studio'&&name!='prompts'&&name!='knowledge'&&name!='code')updateRightPanel(name);
  if(name==='studio'){updateRightPanel('studio');setTimeout(initStudioData,100);setTimeout(()=>{renderModelBar('studio','modelBar_studio');renderModelBar('studio','modelBar_studio_image')},50)}
  if(name==='prompts'){updateRightPanel('prompts');setTimeout(renderPromptCards,100)}
  if(name==='knowledge'){updateRightPanel('knowledge');setTimeout(renderKnowledgeTree,100)}
  if(name==='tools'){updateRightPanel('tools')}
  if(name==='3d'){updateRightPanel('3d');setTimeout(()=>renderModelBar('d3','modelBar_d3'),50)}
  if(name==='music'){updateRightPanel('music');setTimeout(()=>{MUSIC_RENDER_HISTORY();MUSIC_UPDATE_CREDITS();renderModelBar('music','modelBar_music')},100)}
  // 页面模型选择器渲染
  if(name==='office')setTimeout(()=>renderModelBar('office','modelBar_office'),50);
  if(name==='brand')setTimeout(()=>renderModelBar('brand','modelBar_brand'),50);
  if(name==='market')setTimeout(()=>renderModelBar('market','modelBar_market'),50);
  if(name==='code'){updateRightPanel('code');setTimeout(()=>{initCodeChatModels();if(codeChatHistory.length===0)document.getElementById('codeChatQuickStart').style.display='flex'},200)}
  if(name==='apikeys')setTimeout(loadApiKeys,200);
  // 重置所有滚动位置
  setTimeout(()=>{window.scrollTo(0,0);const mc=document.querySelector('.main-content');if(mc)mc.scrollTop=0},50);
  // Force CDN refresh v2
  // 隐私政策更新检测
  if(name==='privacy')markPolicyRead();
  // 促销组件
  if(name==='pricing'){setTimeout(()=>{initPromoTimer();initFirstPurchase();checkAchievement()},200)}
  if(name==='chat'){setTimeout(checkAchievement,5000)}
}
document.querySelectorAll('.sidebar-link[data-page]').forEach(l=>l.addEventListener('click',()=>switchPage(l.dataset.page)));

// ===== 隐私政策版本通知 =====
const POLICY_VERSION='v1.0';
const POLICY_STORAGE_KEY='ppv';
const POLICY_CHANGELOG_KEY='pcl';

// 更新日志
const policyChangelogs={
  'v1.0':'初始版本 - 2026年5月28日发布',
};
// 发布后添加新版本：
// 'v1.1':'更新内容：优化数据保护条款 - 2026年6月xx日',

// ===== Token 管理 & API 辅助 =====
let authToken=localStorage.getItem('auth_token')||null;
function setAuthToken(t){authToken=t;if(t)localStorage.setItem('auth_token',t);else localStorage.removeItem('auth_token')}
function getAuthHeader(){return authToken?{'Authorization':'Bearer '+authToken}:{}}
async function apiFetch(path,opts={}){
  const headers={'Content-Type':'application/json',...getAuthHeader(),...opts.headers};
  try{
    const r=await fetch(API_BASE+path,{...opts,headers});
    if(r.status===401&&authToken){setAuthToken(null);currentUser=null;localStorage.removeItem('cuser');renderUserNav();showToast('登录已过期，请重新登录');return{ok:false,error:'expired'}}
    return await r.json()
  }catch(e){return{ok:false,error:e.message}}
}
async function syncUserData(){
  if(!authToken||!currentUser)return;
  const d=await apiFetch('/api/user/data');
  if(d.ok&&d.data){
    if(d.data.credits!==undefined){userCredits=d.data.credits;localStorage.setItem('cr',userCredits);updateCreditDisplay()}
    if(d.data.history){localStorage.setItem('chathist',JSON.stringify(d.data.history))}
    if(d.data.redeems){localStorage.setItem('redeems',JSON.stringify(d.data.redeems))}
  }
}
async function syncChatHistory(){if(authToken){const h=JSON.parse(localStorage.getItem('chathist')||'[]');apiFetch('/api/user/history',{method:'POST',body:JSON.stringify({history:h})})}}
async function syncCredits(){if(authToken){apiFetch('/api/user/credits',{method:'POST',body:JSON.stringify({credits:userCredits,tokens:usedTokensCount,images:usedImagesCount})})}}

function getPolicyReadVersion(){return localStorage.getItem(POLICY_STORAGE_KEY)||''}
function setPolicyReadVersion(v){localStorage.setItem(POLICY_STORAGE_KEY,v)}

function markPolicyRead(){
  setPolicyReadVersion(POLICY_VERSION);
  // 显示更新日志
  const el=document.getElementById('policyChangelog');
  const ct=document.getElementById('changelogContent');
  if(el&&ct){
    const updates=[];
    const readVer=getPolicyReadVersion();
    // 收集所有未读的更新日志
    let showUpTo=false;
    Object.entries(policyChangelogs).reverse().forEach(([v,desc])=>{
      if(v===POLICY_VERSION)showUpTo=true;
      if(showUpTo){
        if(!readVer||!isVersionAtLeast(readVer,v)){
          updates.push(`<div style="margin:4px 0"><b>${v}</b>: ${desc}</div>`);
        }
      }
    });
    if(updates.length){
      el.style.display='block';
      ct.innerHTML=updates.join('');
    }
  }
}

function isVersionAtLeast(base,target){
  const b=base.replace('v','').split('.').map(Number);
  const t=target.replace('v','').split('.').map(Number);
  for(let i=0;i<Math.max(b.length,t.length);i++){
    const bn=b[i]||0,tn=t[i]||0;
    if(bn>tn)return true;
    if(bn<tn)return false;
  }
  return true;
}

function checkPolicyUpdate(){
  const readVer=getPolicyReadVersion();
  if(!readVer||!isVersionAtLeast(readVer,POLICY_VERSION)){
    // 有新版本，弹通知
    const verList=Object.keys(policyChangelogs);
    const latestChange=policyChangelogs[POLICY_VERSION]||'';
    setTimeout(()=>{
      const banner=document.createElement('div');
      banner.id='policyBanner';
      banner.style.cssText='position:fixed;bottom:80px;right:20px;z-index:1000;background:var(--bg-card);border:1px solid var(--accent);border-radius:12px;padding:14px 18px;max-width:320px;box-shadow:var(--shadow-lg);animation:fadeInUp 0.4s ease';
      banner.innerHTML=`
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
          <span style="font-size:1.3rem">📢</span>
          <b>隐私政策已更新</b>
          <span style="margin-left:auto;font-size:0.72rem;color:var(--text-secondary);background:var(--accent-soft);padding:2px 8px;border-radius:10px">${POLICY_VERSION}</span>
        </div>
        <div style="font-size:0.82rem;color:var(--text-secondary);line-height:1.5;margin-bottom:10px">
          ${latestChange.substring(0,60)}${latestChange.length>60?'…':''}
        </div>
        <div style="display:flex;gap:8px">
          <button class="btn-send" style="flex:1;font-size:0.78rem;padding:8px 0" onclick="switchPage('privacy');this.closest('#policyBanner').remove()">查看详情</button>
          <button class="btn-sm" style="font-size:0.78rem" onclick="markPolicyRead();this.closest('#policyBanner').remove()">我知道了</button>
        </div>
      `;
      // 确保不重复
      if(!document.getElementById('policyBanner')){
        document.body.appendChild(banner);
        setTimeout(()=>{
          const b=document.getElementById('policyBanner');
          if(b)b.style.animation='fadeOutDown 0.4s ease forwards';
          setTimeout(()=>b?.remove(),500);
        },10000); // 10秒后自动消失
      }
    },3000); // 页面加载3秒后弹出
  }
}
// 页面加载时检测
setTimeout(checkPolicyUpdate,1000);

// Right Panel update
function updateRightPanel(page){
  const title=document.getElementById('rightPanelTitle');
  const content=document.getElementById('rightPanelContent');
  const panels={
    'home':{title:'快捷操作',html:`
      <div class="right-panel-card" onclick="switchPage('chat')" style="cursor:pointer"><div style="font-size:1.2rem;margin-bottom:4px">💬</div><div style="font-weight:600;font-size:0.82rem">AI 聊天</div><div style="font-size:0.72rem;color:var(--text-secondary)">多模型同时对话</div></div>
      <div class="right-panel-card" onclick="switchPage('novel')" style="cursor:pointer"><div style="font-size:1.2rem;margin-bottom:4px">📖</div><div style="font-weight:600;font-size:0.82rem">AI 小说</div><div style="font-size:0.72rem;color:var(--text-secondary)">大纲→创作→润色</div></div>
      <div class="right-panel-card" onclick="switchPage('studio')" style="cursor:pointer"><div style="font-size:1.2rem;margin-bottom:4px">🖼</div><div style="font-weight:600;font-size:0.82rem">AI 创作工场</div><div style="font-size:0.72rem;color:var(--text-secondary)">图片+视频生成</div></div>
    `},
    'chat':{title:'选择模型',html:`
      <div id="chatModelList"></div>
    `},
    'compare':{title:'对比设置',html:`
      <div class="form-group"><label style="font-size:0.8rem">列数</label><select id="colSelect" class="col-select" onchange="updateCompareLayout()" style="width:100%"><option value="2">2列</option><option value="3">3列</option><option value="4">4列</option></select></div>
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.8rem;margin-bottom:6px">快捷预设</div>
        ${['量子计算通俗解释','写一首春天的诗','Python快速排序'].map(t=>`<div class="filter-tag" style="font-size:0.72rem;margin:2px;cursor:pointer" onclick="setComparePrompt('${t}')">${t}</div>`).join('')}
      </div>
    `},
    'code':{title:'选择编程模型',html:`
      <div id="codeModelList"></div>
      <div class="right-panel-card" style="margin-top:12px">
        <div style="font-weight:600;font-size:0.78rem;margin-bottom:8px">⚡ 快捷操作</div>
        <button class="btn-sm primary" style="width:100%;margin-bottom:6px" onclick="copyCodeChatHTML()">📋 复制HTML代码</button>
        <button class="btn-sm" style="width:100%;margin-bottom:6px" onclick="downloadCodeChatHTML()">⬇ 下载网页文件</button>
        <button class="btn-sm" style="width:100%;margin-bottom:6px" onclick="deployCodeChat()">📤 部署指南</button>
        <button class="btn-sm" style="width:100%;background:var(--red);color:#fff;border:none" onclick="clearCodeChat()">🔄 新建对话</button>
      </div>
      <div class="right-panel-card" style="margin-top:8px"><div style="font-weight:600;font-size:0.78rem;margin-bottom:6px">💡 使用技巧</div>
        <div style="font-size:0.68rem;color:var(--text-secondary);line-height:1.6">
          • 像聊天一样描述想法<br>
          • AI 会先分析需求再动手<br>
          • 不满意随时说"改一下XX"<br>
          • 生成网页后可实时预览<br>
          • 确认效果后一键复制/部署
        </div>
      </div>
    `},
    'novel':{title:'创作面板',html:`
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.8rem">📚 <span id="rpNovelTitle">未开始</span></div><div style="font-size:0.72rem;color:var(--text-secondary);margin-top:4px"><span id="rpChapterCount">0</span> 章 · <span id="rpTotalWords">0</span> 字</div></div>
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.78rem;margin-bottom:8px">📝 快捷操作</div>
        <button class="btn-sm primary" style="width:100%;margin-bottom:6px" onclick="downloadNovel()">⬇ 导出全书 (TXT)</button>
        <button class="btn-sm" style="width:100%;margin-bottom:6px" onclick="openReader()">📖 阅读模式</button>
        <button class="btn-sm" style="width:100%" onclick="exportAllChapters()">📋 复制全部章节</button>
      </div>
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.78rem;margin-bottom:6px">💡 写作技巧</div>
        <div style="font-size:0.68rem;color:var(--text-secondary);line-height:1.6">
          • 每章设2-3个情节要点<br>
          • 对话占比 > 30% 更生动<br>
          • 结尾留悬念 > 读者追更<br>
          • 写完用"去AI痕迹"润色<br>
          • 章节字数 1500-3000 最佳
        </div>
      </div>
    `},
    'media':{title:'漫剧工具',html:`
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:6px">🎬 风格参考</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          <div class="filter-tag" style="font-size:0.68rem;cursor:pointer" onclick="document.getElementById('mediaStyle').value='日系动漫'">日系</div>
          <div class="filter-tag" style="font-size:0.68rem;cursor:pointer" onclick="document.getElementById('mediaStyle').value='美式漫画'">美式</div>
          <div class="filter-tag" style="font-size:0.68rem;cursor:pointer" onclick="document.getElementById('mediaStyle').value='国风水墨'">国风</div>
          <div class="filter-tag" style="font-size:0.68rem;cursor:pointer" onclick="document.getElementById('mediaStyle').value='韩系条漫'">韩系</div>
        </div>
      </div>
      <div class="right-panel-card" style="cursor:pointer" onclick="renderStoryboardCards();switchMediaTab('storyboard')">
        <div style="font-size:1.2rem;margin-bottom:2px">🎞</div><div style="font-weight:600;font-size:0.82rem">分镜板</div><div style="font-size:0.72rem;color:var(--text-secondary)">可视化卡片</div>
      </div>
      <div class="right-panel-card" style="cursor:pointer" onclick="renderCharLibrary();switchMediaTab('chars')">
        <div style="font-size:1.2rem;margin-bottom:2px">👥</div><div style="font-weight:600;font-size:0.82rem">角色库</div><div style="font-size:0.72rem;color:var(--text-secondary)">保持角色一致性</div>
      </div>
    `},
    'studio':{title:'创作工场',html:`
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:6px">🎯 快速预设</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="STUDIO_QUICK('cyberpunk')">赛博朋克</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="STUDIO_QUICK('anime')">动漫角色</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="STUDIO_QUICK('landscape')">风景大片</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="STUDIO_QUICK('product')">产品展示</div>
        </div>
      </div>
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:6px">📐 画幅比例</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px">
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="STUDIO_SET('ratio','1:1')">1:1</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="STUDIO_SET('ratio','16:9')">16:9</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="STUDIO_SET('ratio','9:16')">9:16</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="STUDIO_SET('ratio','4:3')">4:3</div>
        </div>
      </div>
      <div id="studioHistory" class="right-panel-card" style="display:none"><div style="font-weight:600;font-size:0.82rem">🕐 历史记录</div></div>
    `},
    'prompts':{title:'提示词分类',html:`
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:6px">🔍 搜索</div>
        <input class="search-input" id="promptSearch" placeholder="搜索提示词..." oninput="filterPromptCards()" style="width:100%">
      </div>
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:6px">📂 快速跳转</div>
        <div style="display:flex;flex-wrap:wrap;gap:4px" id="promptCatJump">
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="scrollToCategory('writing')">写作</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="scrollToCategory('novel')">小说</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="scrollToCategory('media')">漫剧</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="scrollToCategory('work')">办公</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="scrollToCategory('brand')">品牌</div>
          <div class="filter-tag" style="font-size:0.7rem;cursor:pointer" onclick="scrollToCategory('market')">营销</div>
        </div>
      </div>
    `},
    'knowledge':{title:'知识库',html:`
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:6px">➕ 快速添加</div>
        <button class="btn-sm primary" style="width:100%" onclick="KNOWLEDGE_ADD()">📝 新建知识点</button>
      </div>
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:6px">📊 统计</div>
        <div style="font-size:0.78rem;color:var(--text-secondary)" id="knowledgeStats">加载中...</div>
      </div>
    `},
    'pricing':{title:'积分信息',html:`
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem">💎 当前积分</div><div style="font-size:1.5rem;font-weight:800;color:var(--accent);margin:8px 0" id="rpCredits">0</div></div>
      <div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:4px">💡 怎么用</div><div style="font-size:0.72rem;color:var(--text-secondary);line-height:1.6">聊天: 1分/次<br>对比: 3分/次<br>写小说: 5分/章<br>漫剧: 8分/次<br>办公/品牌/营销: 3分/次<br>绘画: 免费</div></div>
    `},
    'admin':{title:'管理快捷',html:`<div class="right-panel-card" onclick="openAddModel()" style="cursor:pointer"><div style="font-weight:600;font-size:0.82rem">+ 添加模型</div></div><div class="right-panel-card" onclick="openApiSettings()" style="cursor:pointer"><div style="font-weight:600;font-size:0.82rem">🔑 API Key</div></div><div class="right-panel-card" onclick="openSiteSettings()" style="cursor:pointer"><div style="font-weight:600;font-size:0.82rem">⚙ 系统设置</div></div>`},
    'tools':{title:'工具提示',html:`<div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:4px">🔧 使用说明</div><div style="font-size:0.72rem;color:var(--text-secondary);line-height:1.6">🎬 去水印：粘贴短视频链接解析<br>🖼 图片拼接：多图拼接长图<br>📦 图片压缩：调整质量减少文件体积<br>🎨 取色器：点击图片提取颜色<br>🟦 纯色图：生成指定纯色图片<br>🔐 LSB隐写：图片中隐藏秘密文本</div></div>`},
    '3d':{title:'3D生成',html:`<div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:4px">🧊 使用指南</div><div style="font-size:0.72rem;color:var(--text-secondary);line-height:1.6">1. 输入文字描述或上传参考图<br>2. 选择生成参数和风格<br>3. 点击生成等待完成<br>4. 下载 3D 模型文件</div></div>`},
    'music':{title:'音乐信息',html:`<div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:4px">💎 当前积分</div><div style="font-size:1.3rem;font-weight:800;color:var(--accent)" id="rpMusicCredits">0</div></div><div class="right-panel-card"><div style="font-weight:600;font-size:0.82rem;margin-bottom:4px">🎵 创作提示</div><div style="font-size:0.72rem;color:var(--text-secondary);line-height:1.6">• 歌词模式：输入完整歌词<br>• 创意模式：描述想要的氛围<br>• 歌词生成：AI自动写词<br>• 可多选风格混合<br>• 纯音乐模式生成伴奏</div></div>`}
  };
  const p=panels[page]||panels['home'];
  title.textContent=p.title;
  content.innerHTML=p.html;
  if(page==='novel'){updateNovelRightPanel()}
  if(page==='pricing'){setTimeout(()=>{const e=document.getElementById('rpCredits');if(e)e.textContent=userCredits},100)}
}
function updateNovelRightPanel(){
  const t=document.getElementById('rpNovelTitle');if(t)t.textContent=novelBookTitle;
  const c=document.getElementById('rpChapterCount');if(c)c.textContent=chapterCountWritten;
  const w=document.getElementById('rpTotalWords');if(w)w.textContent=totalWordsWritten.toLocaleString();
  // Also update the novel page progress if visible
  const tc=document.getElementById('totalWords');if(tc)tc.textContent=totalWordsWritten.toLocaleString();
  const cc=document.getElementById('chapterCount');if(cc)cc.textContent=chapterCountWritten;
  const bt=document.getElementById('novelBookTitle');if(bt)bt.textContent=novelBookTitle;
}

// === API Config ===
const API_BASE=(()=>{
  if(typeof window!=='undefined'&&window.location.hostname&&window.location.hostname==='localhost')return 'http://localhost:3001';
  // Electron 桌面端：使用远程 API
  if(window.location.protocol==='file:')return 'https://j3trisheng.com';
  const saved=localStorage.getItem('api_base');
  if(saved) return saved;
  return window.location.origin;
})();
let apiOnline=false;
let deviceFp=localStorage.getItem('dfp')||'';

// === 设备指纹生成（Canvas + Navigator + Screen，同步版） ===
function getDeviceFingerprint(){
  if(deviceFp&&deviceFp.length>8)return deviceFp;
  try{
    const canvas=document.createElement('canvas');canvas.width=256;canvas.height=128;
    const ctx=canvas.getContext('2d');
    ctx.textBaseline='top';ctx.font='14px Arial';ctx.fillStyle='#f60';ctx.fillRect(100,10,50,30);
    ctx.fillStyle='#069';ctx.font='16px monospace';ctx.fillText('Y·NEX FP',2,15);
    ctx.fillStyle='rgba(102,204,0,0.7)';ctx.font='18px serif';ctx.fillText('device',30,60);
    const b64=canvas.toDataURL().replace(/^data:image\/png;base64,/,'');
    // 用简单哈希代替SHA-256（保持同步）
    let hash=0;for(let i=0;i<b64.length;i++){const c=b64.charCodeAt(i);hash=((hash<<5)-hash)+c;hash|=0}
    const nav=navigator.userAgent.replace(/[^a-zA-Z0-9]/g,'').slice(0,10);
    const scr=screen.width+'x'+screen.height;
    deviceFp='tg'+Math.abs(hash).toString(36).slice(0,20)+btoa(nav+scr).slice(0,8).replace(/[^a-zA-Z0-9]/g,'');
    localStorage.setItem('dfp',deviceFp);
    localStorage.setItem('device_fp',deviceFp);
  }catch(e){
    deviceFp='tg_'+Math.random().toString(36).slice(2,14);
    localStorage.setItem('dfp',deviceFp);
    localStorage.setItem('device_fp',deviceFp);
  }
  return deviceFp;
}
// 生成指纹
getDeviceFingerprint();

