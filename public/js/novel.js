'use strict';
// === 炼字工坊 (Novel Workshop) ===
let novelType='玄幻',novelOutline='',novelChars='',novelWorld='',novelHistory='';
let totalWordsWritten=parseInt(localStorage.getItem('nw')||'0'),chapterCountWritten=parseInt(localStorage.getItem('nc')||'0');
let novelBookTitle=localStorage.getItem('nbt')||'未开始';
let novelTab='outline';
// Initiative (hierarchical outline storage)
let outlineData={grand:'',volumes:[],chapters:[]};

function switchNovelTab(tab){
  novelTab=tab;
  document.querySelectorAll('#novelTabs .workshop-tab').forEach(b=>b.classList.remove('active'));
  document.querySelector(`#novelTabs .workshop-tab[onclick*="${tab}"]`)?.classList.add('active');
  ['outline','write','refine','manage'].forEach(t=>{const el=document.getElementById('novelTab'+t.charAt(0).toUpperCase()+t.slice(1));if(el)el.style.display=t===tab?'grid':'none'});
  if(tab==='manage')renderChapterList();
  if(tab==='outline'&&outlineData.grand)renderOutlineTree();
  updateNovelRightPanel();
}

function loadSavedOutline(){
  const saved=localStorage.getItem('nOutline');
  if(saved){try{outlineData=JSON.parse(saved)}catch(e){outlineData={grand:'',volumes:[],chapters:[]}}}
  const savedRaw=localStorage.getItem('nOutlineRaw');
  if(savedRaw)novelOutline=savedRaw;
  if(outlineData.grand)renderOutlineTree();
}

async function generateOutline(){
  const idea=document.getElementById('wizIdea')?.value?.trim();
  if(!idea){showToast('请先输入创意灵感');return}
  if(!spendCredits(5))return;
  const type=document.getElementById('wizType')?.value||'玄幻';
  novelType=type;
  const modelId=document.getElementById('wizOutlineModel')?.value||'deepseekr1';
  const tree=document.getElementById('outlineTree');
  tree.innerHTML='<div style="text-align:center;padding:60px"><span class="spinner"></span><p style="margin-top:8px">AI 正在规划三层大纲...</p></div>';
  const sys='你是顶级小说架构师。请按以下格式生成三层大纲:\n\n【全书大纲】(100-200字概括全书核心主线)\n\n【卷纲】(3-5卷,每卷标题+50字概要,格式:第一卷·卷名 | 概要)\n\n【章纲】(每卷3-5章,每章标题+20字概要,格式:第一章·章名 | 概要)';
  const prompt=`小说类型:${type}\n创意灵感:${idea}\n\n请生成完整的三层大纲结构。`;
  try{
    const r=await callModelAPI(modelId,prompt,sys);
    parseOutline(r.content);
    renderOutlineTree();
    usedTokensCount+=r.content.length;localStorage.setItem('utk',usedTokensCount);updateCreditDisplay();
  }catch(e){tree.innerHTML=`<span style="color:var(--red)">❌ ${e.message}</span>`}
}

function parseOutline(text){
  outlineData={grand:'',volumes:[],chapters:[]};
  const lines=text.split('\n');
  let section='',currentVol='';
  for(const l of lines){
    const t=l.trim();
    if(!t)continue;
    if(t.includes('全书大纲')||t.includes('总体大纲')){section='grand';continue}
    if(t.includes('卷纲')){section='vol';continue}
    if(t.includes('章纲')){section='chap';continue}
    if(section==='grand'&&!outlineData.grand){outlineData.grand=t.replace(/^[【\[\s\d\.、]+/,'').replace(/[】\]\s]+$/,'');continue}
    if(section==='vol'&&(t.includes('卷')||t.includes('·'))){
      const parts=t.split(/[|｜]/);currentVol=parts[0].trim();outlineData.volumes.push({name:currentVol,summary:parts[1]?.trim()||''});
      continue;
    }
    if(section==='chap'&&(t.includes('章')||t.includes('·'))){
      const parts=t.split(/[|｜]/);outlineData.chapters.push({name:parts[0].trim(),vol:currentVol,summary:parts[1]?.trim()||''});
      continue;
    }
  }
  if(!outlineData.grand)outlineData.grand=text.substring(0,200);
  // Save to localStorage
  localStorage.setItem('nOutline',JSON.stringify(outlineData));
  novelOutline=text;localStorage.setItem('nOutlineRaw',novelOutline);
}

function renderOutlineTree(){
  const tree=document.getElementById('outlineTree');
  let html='';
  if(outlineData.grand){
    html+=`<div class="outline-node level-0"><div class="node-label">📐 全书大纲</div><div class="node-content">${escapeHtml(outlineData.grand)}</div><div class="node-actions"><button class="btn-sm" onclick="editOutlineNode('grand')">✏️</button></div></div>`;
  }
  for(const v of outlineData.volumes){
    html+=`<div class="outline-node level-1"><div class="node-label">📚 ${escapeHtml(v.name)}</div><div class="node-content">${escapeHtml(v.summary)}</div><div class="node-actions"><button class="btn-sm" onclick="editOutlineNode('vol','${escapeHtml(v.name)}')">✏️</button></div></div>`;
  }
  for(const c of outlineData.chapters){
    html+=`<div class="outline-node level-2"><div class="node-label">📝 ${escapeHtml(c.name)}</div><div class="node-content">${escapeHtml(c.summary)}</div></div>`;
  }
  if(!html)html='<div style="text-align:center;color:var(--text-secondary);padding:60px"><div style="font-size:3rem">📐</div><p>输入创意灵感，AI 自动生成三层大纲</p><p style="font-size:0.75rem;margin-top:8px">大纲 → 卷纲 → 章纲</p></div>';
  tree.innerHTML=html;
}

function editOutlineNode(type,name){
  const t=type==='grand'?'全书大纲':(type==='vol'?`卷纲: ${name}`:'章纲');
  const old=type==='grand'?outlineData.grand:(type==='vol'?outlineData.volumes.find(v=>v.name===name)?.summary||'':'');
  const nv=prompt(`编辑 ${t}:`,old);
  if(nv!==null){
    if(type==='grand')outlineData.grand=nv;
    else if(type==='vol'){const v=outlineData.volumes.find(v=>v.name===name);if(v)v.summary=nv}
    localStorage.setItem('nOutline',JSON.stringify(outlineData));
    renderOutlineTree();showToast('已更新');
  }
}

// Chapter Writing
async function wizardAction(){
  const content=document.getElementById('wizWrite')?.value||'';
  if(!content){showToast('请输入本章要写的内容');return}
  if(!spendCredits(10))return;
  const modelId=document.getElementById('wizModel')?.value||'deepseekv3';
  novelChars=document.getElementById('wizChars')?.value||novelChars;
  novelWorld=document.getElementById('wizWorld')?.value||novelWorld;
  const type=document.getElementById('wizType')?.value||novelType;
  novelType=type;
  // Load outline if exists
  if(!novelOutline){
    const saved=localStorage.getItem('nOutlineRaw');
    if(saved)novelOutline=saved;
  }
  const sys=`你是专业${novelType}小说家。核心要求：
1. 文笔生动细腻，多用动作、神态、环境描写替代直白叙述
2. 对话自然不做作，有潜台词，符合人物性格
3. 节奏张弛有度，紧张场景与舒缓场景交替
4. 本章收尾要有完整段落感，不要"未完待续"
5. 避免AI腔：不滥用"然而""不过""可以看出来"等套话,多用具体描写
6. 不使用网络流行语和过于现代化的表达（现代背景除外）`;
  const prompt=`【小说类型】${novelType}
【全书大纲】${novelOutline||'根据类型自由发挥'}
【人物设定】${novelChars||'由你根据类型合理设计'}
【世界观】${novelWorld||'由你合理构建'}
【前情提要】${novelHistory||'故事开始'}
【本章要求】${content}

请写一章3500字左右的完整小说章节。`;
  const out=document.getElementById('novelOutput');out.innerHTML='<span class="spinner"></span> 创作中...';
  try{
    const r=await callModelAPI(modelId,prompt,sys);
    novelHistory+=(novelHistory?'\n':'')+r.content;
    out.innerHTML=escapeHtml(r.content);
    usedTokensCount+=r.content.length;localStorage.setItem('utk',usedTokensCount);updateCreditDisplay();
  }catch(e){out.innerHTML=`<span style="color:var(--red)">❌ ${e.message}</span>`}
}

// Refinement System
let refineMode='polish';
function switchRefineMode(mode){
  refineMode=mode;
  document.querySelectorAll('.refine-option').forEach(b=>b.classList.remove('active'));
  document.querySelector(`.refine-option[data-rmode="${mode}"]`)?.classList.add('active');
}
function refineText(mode){
  const txt=document.getElementById('novelOutput')?.textContent?.trim();
  if(!txt||txt.includes('创作中')){showToast('请先生成内容');return}
  switchNovelTab('refine');
  refineMode=mode;
  document.querySelectorAll('.refine-option').forEach(b=>{b.classList.remove('active');if(b.dataset.rmode===mode)b.classList.add('active')});
  document.getElementById('refineInput').value=txt;
  document.getElementById('refineBefore').textContent=txt;
}

async function executeRefine(){
  const input=document.getElementById('refineInput')?.value?.trim();
  if(!input){showToast('请粘贴需要润色的文本');return}
  if(!spendCredits(5))return;
  const modelId=document.getElementById('refineModel')?.value||'deepseekv3';
  document.getElementById('refineBefore').textContent=input;
  document.getElementById('refineAfter').innerHTML='<span class="spinner"></span> 炼字中...';
  const sysMap={
    polish:'你是顶级文学编辑。润色要求：1. 保留原文核心情节和角色语气 2. 提升文笔：增加细节描写,消除平铺直叙 3. 优化句式节奏,长短句交替 4. 删除冗余形容词和副词 5. 直接返回润色后文本,不解释修改',
    deai:'你是反AI检测专家。去AI痕迹要求：1. 删除"总的来说""值得注意的是""可以说"等AI高频词 2. 打碎过于工整的排比和对称结构 3. 插入口语化表达和不规则句式 4. 让段落长短不一,模仿人类写作节奏 5. 偶尔留一些小瑕疵(如口语化重复)增加人味 6. 直接返回处理后的文本',
    expand:'你是小说家。扩写要求：1. 在关键情节处增加细节描写 2. 丰富人物心理活动 3. 扩展环境氛围渲染 4. 字数扩充约50% 5. 直接返回扩写后文本',
    shorten:'你是精简编辑。缩写要求：1. 删除冗余描写但保留精华 2. 合并重复信息 3. 保持核心情节和情感不变 4. 字数缩减约40% 5. 直接返回缩写后文本'
  };
  try{
    const r=await callModelAPI(modelId,input,sysMap[refineMode]||sysMap.polish);
    document.getElementById('refineAfter').innerHTML=`<div style="margin-bottom:8px;display:flex;gap:6px"><button class="btn-sm primary" onclick="acceptRefine()">✅ 采用</button><button class="btn-sm" onclick="executeRefine()">🔄 重新炼字</button></div>`+escapeHtml(r.content);
    window._lastRefineResult=r.content;
    usedTokensCount+=r.content.length;localStorage.setItem('utk',usedTokensCount);updateCreditDisplay();
  }catch(e){document.getElementById('refineAfter').innerHTML=`❌ ${e.message}`}
}
function acceptRefine(){
  if(window._lastRefineResult){
    document.getElementById('novelOutput').innerHTML=escapeHtml(window._lastRefineResult);
    document.getElementById('refineInput').value=window._lastRefineResult;
    document.getElementById('refineBefore').textContent=window._lastRefineResult;
    document.getElementById('refineAfter').innerHTML='<span style="color:var(--green)">✅ 已采用！切换到"章节创作"标签页查看</span>';
    showToast('润色结果已应用到创作区');
  }
}

// Chapter Management
function saveChapter(){
  const c=document.getElementById('novelOutput').textContent.trim();if(!c||c.includes('创作中')){showToast('请先完成创作');return}
  if(novelBookTitle==='未开始'){const t=prompt('书名：','');if(!t)return;novelBookTitle=t;localStorage.setItem('nbt',t)}
  chapterCountWritten++;totalWordsWritten+=c.length;localStorage.setItem('nc',chapterCountWritten);localStorage.setItem('nw',totalWordsWritten);
  localStorage.setItem('novelHistory',novelHistory);
  const ch=JSON.parse(localStorage.getItem('nch')||'[]');ch.push({ch:chapterCountWritten,title:'',content:c,time:new Date().toISOString()});localStorage.setItem('nch',JSON.stringify(ch));
  updateNovelProgress2();updateNovelRightPanel();showToast(`第${chapterCountWritten}章已保存 (${c.length}字)`);
}

function renderChapterList(){
  const ch=JSON.parse(localStorage.getItem('nch')||'[]');
  const container=document.getElementById('chapterList');
  if(!ch.length){container.innerHTML='<div style="text-align:center;color:var(--text-secondary);padding:40px 20px"><p>还没有章节，先去创作吧~</p></div>';return}
  let html='';
  ch.forEach((c,i)=>{
    const preview=c.content.substring(0,60).replace(/\n/g,' ');
    html+=`<div class="chapter-item" onclick="previewChapter(${i})">
      <div class="chapter-num">${c.ch}</div>
      <div class="chapter-info">
        <div class="chapter-title">${escapeHtml(c.title||`第${c.ch}章`)}</div>
        <div class="chapter-meta">${c.content.length}字 · ${new Date(c.time).toLocaleDateString()}</div>
      </div>
      <div class="chapter-actions">
        <button class="btn-sm" onclick="event.stopPropagation();loadChapter(${i})">📖</button>
        <button class="btn-sm danger" onclick="event.stopPropagation();deleteChapter(${i})">🗑</button>
      </div>
    </div>`;
  });
  container.innerHTML=html;
}

function previewChapter(idx){
  const ch=JSON.parse(localStorage.getItem('nch')||'[]');
  if(ch[idx]){
    document.getElementById('chapterPreview').innerHTML=`<h3 style="margin-bottom:8px">第${ch[idx].ch}章</h3><div style="font-size:0.75rem;color:var(--text-secondary);margin-bottom:12px">${ch[idx].content.length}字 · ${new Date(ch[idx].time).toLocaleString()}</div>`+escapeHtml(ch[idx].content);
  }
}

function loadChapter(idx){
  const ch=JSON.parse(localStorage.getItem('nch')||'[]');
  if(ch[idx]){
    document.getElementById('novelOutput').innerHTML=escapeHtml(ch[idx].content);
    novelHistory=ch.slice(0,idx+1).map(c=>c.content).join('\n');
    localStorage.setItem('novelHistory',novelHistory);
    switchNovelTab('write');
    showToast('已加载到创作区');
  }
}

function deleteChapter(idx){
  if(!confirm('确定删除这一章？'))return;
  const ch=JSON.parse(localStorage.getItem('nch')||'[]');
  const removed=ch.splice(idx,1)[0];
  if(removed){totalWordsWritten=Math.max(0,totalWordsWritten-removed.content.length);chapterCountWritten--}
  localStorage.setItem('nch',JSON.stringify(ch));
  localStorage.setItem('nc',chapterCountWritten);localStorage.setItem('nw',totalWordsWritten);
  renderChapterList();updateNovelProgress2();
  document.getElementById('chapterPreview').innerHTML='<div style="text-align:center;color:var(--text-secondary);padding:60px"><div style="font-size:3rem">📖</div><p>点击章节查看内容</p></div>';
  showToast('已删除');
}

function exportAllChapters(){
  const ch=JSON.parse(localStorage.getItem('nch')||'[]');
  if(!ch.length){showToast('暂无章节');return}
  let txt=`《${novelBookTitle}》\n\n`;
  // Add outline if available
  const outline=localStorage.getItem('nOutlineRaw');
  if(outline){txt+=`【全书大纲】\n${outline}\n\n---\n\n`}
  ch.forEach(c=>{txt+=`第${c.ch}章\n\n${c.content}\n\n`});
  const b=new Blob([txt],{type:'text/plain;charset=utf-8'});const a=document.createElement('a');
  a.href=URL.createObjectURL(b);a.download=(novelBookTitle!=='未开始'?novelBookTitle:'小说')+'.txt';a.click();
  showToast('全书已导出');
}

// Reader Mode
function openReader(){
  const ch=JSON.parse(localStorage.getItem('nch')||'[]');
  if(!ch.length){showToast('暂无章节');return}
  let html=`<div class="reader-overlay" id="readerOverlay" onclick="if(event.target===this)closeReader()">
    <div class="reader-toolbar">
      <div style="display:flex;align-items:center;gap:12px">
        <strong style="font-size:1rem">📖 《${escapeHtml(novelBookTitle)}》</strong>
        <span style="font-size:0.78rem;color:var(--text-secondary)">${ch.length}章 · ${totalWordsWritten.toLocaleString()}字</span>
      </div>
      <div style="display:flex;gap:8px">
        <button class="btn-sm" onclick="changeReaderFont('sm')">A-</button>
        <button class="btn-sm" onclick="changeReaderFont('md')">A</button>
        <button class="btn-sm" onclick="changeReaderFont('lg')">A+</button>
        <button class="btn-sm" onclick="closeReader()">✕ 关闭</button>
      </div>
    </div>
    <div class="reader-content reader-font-md" id="readerContent">`;
  ch.forEach(c=>{html+=`<h3>第${c.ch}章</h3>${escapeHtml(c.content)}\n\n`});
  html+=`</div></div>`;
  document.body.insertAdjacentHTML('beforeend',html);
  document.body.style.overflow='hidden';
}

function closeReader(){const el=document.getElementById('readerOverlay');if(el)el.remove();document.body.style.overflow=''}
function changeReaderFont(size){
  const el=document.getElementById('readerContent');
  if(el){el.className='reader-content reader-font-'+size}
}

function copyNovelOutput(){navigator.clipboard.writeText(document.getElementById('novelOutput').textContent).then(()=>showToast('已复制'))}
function downloadNovel(){
  const ch=JSON.parse(localStorage.getItem('nch')||'[]');let t=novelBookTitle+'\n\n';
  if(ch.length)ch.forEach(c=>{t+=`第${c.ch}章\n\n${c.content}\n\n`});else t+=document.getElementById('novelOutput').textContent;
  const b=new Blob([t],{type:'text/plain;charset=utf-8'});const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download=(novelBookTitle!=='未开始'?novelBookTitle:'小说')+'.txt';a.click();
}

function updateNovelProgress2(){
  const tc=document.getElementById('totalWords');if(tc)tc.textContent=totalWordsWritten.toLocaleString();
  const cc=document.getElementById('chapterCount');if(cc)cc.textContent=chapterCountWritten;
  const bt=document.getElementById('novelBookTitle');if(bt)bt.textContent=novelBookTitle;
}

// Cross-module pipelines
function novelToMedia(){
  const txt=document.getElementById('novelOutput').textContent.trim();
  if(!txt||txt.includes('创作中')){showToast('请先完成小说创作');return}
  switchPage('media');setTimeout(()=>{
    document.getElementById('mediaInput').value=`将以下小说内容改编为${novelType}风格漫剧：\n\n${txt.substring(0,800)}`;
    showToast('小说内容已填充到漫剧输入框，选风格后点生成')
  },300);
}

function mediaToNovel(){
  const txt=document.getElementById('mediaOutput').textContent.trim();
  if(!txt||txt.includes('输入故事')){showToast('请先生成漫剧内容');return}
  switchPage('novel');switchNovelTab('write');setTimeout(()=>{
    const ta=document.getElementById('wizWrite');if(ta)ta.value=`基于漫剧脚本扩展：\n\n${txt.substring(0,500)}`;
    showToast('漫剧脚本已填充，设置后点创作')
  },300);
}

function novelToBrand(){
  const txt=document.getElementById('novelOutput')?.textContent?.trim()||'';
  if(!txt||txt.includes('创作中')){showToast('请先完成小说创作');return}
  switchPage('brand');setTimeout(()=>{
    const el=document.getElementById('brandInput');
    if(el)el.value=`为小说《${novelBookTitle}》（${novelType}类型）设计IP品牌。核心元素：${novelOutline.substring(0,200)}`;
    showToast('小说信息已填充，选品牌功能后点生成')
  },300);
}

function brandToMarket(){
  const txt=document.getElementById('brandOutput').textContent.trim();
  if(!txt||txt==='选择功能开始')switchPage('market');
  else{switchPage('market');setTimeout(()=>{document.getElementById('marketInput').value='基于以下品牌方案做营销：\n\n'+txt.substring(0,500);showToast('品牌方案已填充到营销页')},300)}
}

function marketToBrand(){
  const txt=document.getElementById('marketOutput').textContent.trim();
  if(txt&&txt!=='选择功能开始'){switchPage('brand');setTimeout(()=>{document.getElementById('brandInput').value=txt.substring(0,600);showToast('营销内容已填充到品牌页')},300)}
  else{switchPage('brand')}}

