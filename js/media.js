'use strict';
// === 漫剧工厂 (Media Workshop) ===
let mediaModeType='storyboard',mediaTab='create';
let charLibrary=JSON.parse(localStorage.getItem('charLib')||'[]');

function switchMediaTab(tab){
  mediaTab=tab;
  document.querySelectorAll('#mediaTabs .workshop-tab').forEach(b=>b.classList.remove('active'));
  document.querySelector(`#mediaTabs .workshop-tab[onclick*="${tab}"]`)?.classList.add('active');
  ['create','storyboard','chars'].forEach(t=>{const el=document.getElementById('mediaTab'+t.charAt(0).toUpperCase()+t.slice(1));if(el)el.style.display=t===tab?'block':'none'});
  if(tab==='storyboard')renderStoryboardCards();
  if(tab==='chars')renderCharLibrary();
}

function mediaMode(b){document.querySelectorAll('#mediaModes .filter-tag').forEach(x=>x.classList.remove('active'));b.classList.add('active');mediaModeType=b.dataset.mode}

async function aiCreateMedia(){
  const i=document.getElementById('mediaInput').value.trim();if(!i){showToast('输入故事');return}
  const cost=mediaModeType==='batch'?20:12;
  if(!spendCredits(cost))return;const s=document.getElementById('mediaStyle').value;
  const o=document.getElementById('mediaOutput');o.innerHTML='<span class="spinner"></span> 生成中...';
  if(mediaModeType==='batch'){
    // Batch mode: generate all 4 modes at once
    const modes=[
      {t:`${s}漫画。8格分镜脚本（编号/景别/画面/动作/对白）：\n${i}`,s:`你是专业${s}漫画家和编剧。每个分镜必须包含：编号、景别(特写/中景/全景)、画面描述、角色动作、对白。画面描述要具象化。对白标注语气【】`},
      {t:`${s}风格角色设计。3个核心角色（外貌/服装/性格/能力/口头禅）：\n${i}`,s:'你是角色设计专家。每个角色描述要包含：外貌特征、标志性服装、性格标签、特殊能力、经典台词。'},
      {t:`${s}风格场景设计。4个场景（环境/色彩/光影/氛围）：\n${i}`,s:'你是场景设计师。每个场景包含：环境描述、主色调、光影效果、氛围关键词。'},
      {t:`${s}风格角色对白（角色名：对白内容【语气】）：\n${i}`,s:'你是专业编剧。对白要：符合角色性格、推动剧情、有潜台词、口语化自然。'}
    ];
    let result='';
    for(let m=0;m<modes.length;m++){
      const labels=['🎞 分镜脚本','👥 角色设计','🏞 场景构建','💬 对白生成'];
      o.innerHTML=`<span class="spinner"></span> 批量生成中 (${m+1}/4) ${labels[m]}...`;
      try{
        const r=await callModelAPI('deepseekv3',modes[m].t,modes[m].s);
        result+=`\n\n${'='.repeat(30)}\n${labels[m]}\n${'='.repeat(30)}\n\n${r.content}`;
        usedTokensCount+=r.content.length;
      }catch(e){result+=`\n\n${labels[m]}\n❌ ${e.message}`}
    }
    o.innerHTML=escapeHtml(result.trim());
    localStorage.setItem('utk',usedTokensCount);updateCreditDisplay();
    return;
  }
  const sys=`你是专业${s}漫画家和编剧。要求：\n1. 每个分镜必须包含：编号、景别(特写/中景/全景/远景)、画面描述、角色动作、对白\n2. 画面描述要具象化——读者能根据描述画出分镜图\n3. 对白要自然、有性格区分、推进剧情\n4. 每帧之间有节奏变化，不要全是同一景别\n5. 重要对白用【】标注语气（如【怒吼】【低声】）`;
  const pm={
    storyboard:{t:`${s}漫画。8格分镜脚本（编号/景别/画面/动作/对白）：\n${i}`,s:sys},
    chars:{t:`${s}风格角色设计。3个核心角色（外貌/服装/性格/能力/口头禅）：\n${i}`,s:'你是角色设计专家。每个角色描述要包含：外貌特征、标志性服装、性格标签、特殊能力、经典台词。描述要能让读者在脑中形成清晰形象。格式：角色名 | 外貌 | 服装 | 性格 | 能力 | 口头禅'},
    scene:{t:`${s}风格场景设计。4个场景（环境/色彩/光影/氛围/时代感）：\n${i}`,s:'你是场景设计师。每个场景要包含：环境描述、主色调、光影效果、氛围关键词、时代特征。描述要具有视觉冲击力。'},
    dialog:{t:`${s}风格角色对白（角色名：对白内容【语气】）：\n${i}`,s:'你是专业编剧。对白要：符合角色性格、推动剧情、有潜台词、口语化自然。避免说教和直白的情感表达。'}
  };
  const m=pm[mediaModeType]||pm.storyboard;
  try{const r=await callModelAPI('deepseekv3',m.t,m.s);o.innerHTML=escapeHtml(r.content);usedTokensCount+=r.content.length;localStorage.setItem('utk',usedTokensCount);updateCreditDisplay()}catch(e){o.innerHTML=`❌ ${e.message}`}
}

function renderStoryboardCards(){
  const txt=document.getElementById('mediaOutput').textContent.trim();
  const grid=document.getElementById('storyboardGrid');
  if(!txt||txt.includes('输入故事')){grid.innerHTML='<div style="text-align:center;color:var(--text-secondary);padding:60px;grid-column:1/-1"><div style="font-size:3rem">🎞</div><p>先在"创作"页生成分镜脚本</p></div>';return}
  // Parse storyboard content into cards
  const scenes=txt.split(/\n(?=\d+[\.\)、]\s*)/g).filter(s=>s.trim());
  if(scenes.length<2){grid.innerHTML=`<div style="text-align:center;color:var(--text-secondary);padding:40px;grid-column:1/-1"><p>无法解析分镜格式，请先在创作页生成分镜脚本</p></div>`;return}
  let html='';
  scenes.forEach((s,i)=>{
    const lines=s.trim().split('\n');
    const title=lines[0]||'';
    const rest=lines.slice(1).join('\n');
    // Extract camera info
    let camera='中景';
    if(title.includes('特写'))camera='特写';
    else if(title.includes('全景'))camera='全景';
    else if(title.includes('远景'))camera='远景';
    else if(title.includes('中景'))camera='中景';
    html+=`<div class="storyboard-card">
      <div class="sb-header">
        <div class="sb-num">${i+1}</div>
        <div class="sb-camera">${camera}</div>
      </div>
      <div class="sb-desc">${escapeHtml(title)}</div>
      <div class="sb-desc" style="font-size:0.78rem;color:var(--text-secondary);margin-top:4px">${escapeHtml(rest.substring(0,150))}${rest.length>150?'...':''}</div>
      <div class="sb-image">🎬 画面生成区域</div>
    </div>`;
  });
  grid.innerHTML=html;
}

function saveToCharLib(){
  const txt=document.getElementById('mediaOutput').textContent.trim();
  if(!txt||!txt.includes('角色')){showToast('请先生成角色设计');return}
  const entry={content:txt,style:document.getElementById('mediaStyle').value,time:new Date().toISOString()};
  charLibrary.push(entry);localStorage.setItem('charLib',JSON.stringify(charLibrary));
  showToast('已保存到角色库');
}

function renderCharLibrary(){
  const grid=document.getElementById('charLibGrid');
  if(!charLibrary.length){grid.innerHTML='<div style="text-align:center;color:var(--text-secondary);padding:60px;grid-column:1/-1"><div style="font-size:3rem">👥</div><p>还没有角色，去创作页生成后保存吧~</p></div>';return}
  let html='';
  charLibrary.forEach((c,i)=>{
    html+=`<div class="storyboard-card">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <span class="sb-camera">${escapeHtml(c.style)}</span>
        <span style="font-size:0.7rem;color:var(--text-secondary)">${new Date(c.time).toLocaleDateString()}</span>
      </div>
      <div class="sb-desc" style="max-height:200px;overflow-y:auto">${escapeHtml(c.content.substring(0,300))}</div>
      <div style="display:flex;gap:6px;margin-top:8px">
        <button class="btn-sm" onclick="loadFromCharLib(${i})">📋 加载</button>
        <button class="btn-sm danger" onclick="deleteFromCharLib(${i})">🗑</button>
      </div>
    </div>`;
  });
  grid.innerHTML=html;
}

function loadFromCharLib(idx){
  if(charLibrary[idx]){
    document.getElementById('mediaInput').value=charLibrary[idx].content.substring(0,500);
    document.getElementById('mediaStyle').value=charLibrary[idx].style;
    switchMediaTab('create');showToast('已加载到创作区');
  }
}

function deleteFromCharLib(idx){
  if(!confirm('删除该角色？'))return;
  charLibrary.splice(idx,1);localStorage.setItem('charLib',JSON.stringify(charLibrary));
  renderCharLibrary();showToast('已删除');
}

function generateComicImage(){
  const s=document.getElementById('mediaOutput').textContent.trim();
  if(!s||s.includes('输入故事')){showToast('先生成内容');return}
  if(!spendCredits(12))return;const st=document.getElementById('mediaStyle').value;
  usedImagesCount++;localStorage.setItem('uim',usedImagesCount);updateCreditDisplay();
  document.getElementById('mediaOutput').innerHTML+=`\n\n--- 🖼️ 画面提示词 (${st}) ---\n${st}, ${s.substring(0,300)}, professional comic art, detailed linework, --ar 16:9`;
}

function copyMediaOutput(){navigator.clipboard.writeText(document.getElementById('mediaOutput').textContent).then(()=>showToast('已复制'))}
function downloadMedia(){
  const t=document.getElementById('mediaOutput').textContent;const b=new Blob([t],{type:'text/plain;charset=utf-8'});
  const a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='漫剧_'+new Date().toISOString().slice(0,10)+'.txt';a.click()
}

// 桌面端直接下载 — 一键下载 ZIP 便携版（无安全警告，解压即用）
function downloadDesktopApp(){
  showToast('⏳ 正在开始下载 TriGenClaw 桌面端...');
  const zipUrl = 'https://github.com/wj910621/ai-nexus-server/releases/latest/download/TriGenClaw-Portable.zip';
  const a = document.createElement('a');
  a.href = zipUrl;
  a.download = 'TriGenClaw-Portable.zip';
  a.target = '_blank';
  a.rel = 'noopener';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => showToast('✅ 下载已开始！ZIP约155MB，解压后双击 TriGenClaw.exe 即可使用'), 1000);
}

