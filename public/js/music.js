'use strict';
// ==== 🎵 MUSIC MODULE ====
let MUSIC_SELECTED_STYLES=[];
let MUSIC_HISTORY=JSON.parse(localStorage.getItem('musicHistory')||'[]');
function MUSIC_SAVE_KEY(){
  const keyEl=document.getElementById('musicApiKey');
  const platformEl=document.getElementById('musicApiPlatform');
  if(!keyEl||!platformEl){showToast('配置界面未加载');return}
  const key=keyEl.value.trim();
  const platform=platformEl.value;
  if(platform==='suno'){localStorage.setItem('music_api_platform','suno');localStorage.removeItem('music_api_key');showToast('✅ 已切换为平台配置模式');return}
  if(!key){showToast('请输入 API Key');return}
  localStorage.setItem('music_api_key',key);
  localStorage.setItem('music_api_platform',platform);
  showToast(`✅ ${platform.toUpperCase()} API Key 已保存`);
}
function MUSIC_SET_MODE(mode,el){
  document.querySelectorAll('.workshop-tab').forEach(x=>x.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('musicLyricMode').style.display=mode==='lyric'?'block':'none';
  document.getElementById('musicIdeaMode').style.display=mode==='idea'?'block':'none';
  document.getElementById('musicGenMode').style.display=mode==='generate'?'block':'none';
  const labels={'lyric':'歌词模式','idea':'创意模式','generate':'歌词生成'};
  document.getElementById('musicModeDisplay').textContent=labels[mode]||'歌词模式';
  MUSIC_CURRENT_MODE=mode;
  const costEl=document.querySelector('#page-music .btn-send').previousElementSibling;
  if(costEl)costEl.innerHTML=`⚡ 本次消耗 <b style="color:var(--accent)">10 积分</b>`;
}
let MUSIC_CURRENT_MODE='lyric';
function MUSIC_TOGGLE_STYLE(el){
  const style=el.dataset.style;
  el.classList.toggle('active');
  if(MUSIC_SELECTED_STYLES.includes(style))MUSIC_SELECTED_STYLES=MUSIC_SELECTED_STYLES.filter(s=>s!==style);
  else MUSIC_SELECTED_STYLES.push(style);
}
function MUSIC_GENERATE(){
  const title=document.getElementById('musicTitle').value.trim()||'未命名歌曲';
  const lyric=document.getElementById('musicLyric').value.trim();
  const idea=document.getElementById('musicIdea').value.trim();
  const genText=document.getElementById('musicGenText').value.trim();
  const instrumental=document.getElementById('musicInstrumental').checked;
  const model=getPageModel('music')||'chirp-crow';
  const submitText=document.querySelector('#page-music .btn-send');
  const origText=submitText.textContent;
  submitText.disabled=true;submitText.textContent='⏳ 提交生成...';
  let content='';
  if(MUSIC_CURRENT_MODE==='lyric')content=lyric||`歌曲：${title}`;
  else if(MUSIC_CURRENT_MODE==='idea')content=idea||title;
  else content=genText||title;
  if(!content&&!title){showToast('请输入创作内容');submitText.disabled=false;submitText.textContent=origText;return}
  
  // 调用 Suno API 生成
  (async()=>{
    try {
      const r=await fetch(API_BASE+'/api/music/generate',{
        method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          prompt:content,
          title,
          instrumental,
          model:'chirp-crow'
        })
      });
      const d=await r.json();
      if(!d.data||!d.data.task_ids){
        showToast('生成失败: '+(d.error||'未知错误'));
        submitText.disabled=false;submitText.textContent=origText;
        return;
      }
      // 开始轮询结果
      const taskIds=d.data.task_ids;
      submitText.textContent='⏳ 生成歌曲中（约1-2分钟）...';
      
      for(const taskId of taskIds){
        pollMusicTask(taskId, title, content, MUSIC_SELECTED_STYLES, instrumental, model, submitText, origText);
      }
    } catch(e) {
      showToast('网络错误: '+e.message);
      submitText.disabled=false;submitText.textContent=origText;
    }
  })();
}

function pollMusicTask(taskId, title, content, styles, instrumental, model, submitText, origText){
  let attempts=0;
  const maxAttempts=30;
  const iv=setInterval(async()=>{
    attempts++;
    try{
      const r=await fetch(API_BASE+'/api/music/task?id='+taskId);
      const d=await r.json();
      if(d.data&&d.data.status==='completed'){
        clearInterval(iv);
        const result=d.data.result;
        const entry={
          id:Date.now()+taskId,
          title,
          content,
          styles:styles.join(',')||'流行',
          instrumental,
          model:model||'Suno',
          time:new Date().toISOString(),
          url:result.fileInfo.mp3Url,
          cover:result.fileInfo.cosUrl,
          customId:result.custom_id,
          duration:result.fileInfo.duration||0
        };
        MUSIC_HISTORY.unshift(entry);
        if(MUSIC_HISTORY.length>50)MUSIC_HISTORY.length=50;
        localStorage.setItem('musicHistory',JSON.stringify(MUSIC_HISTORY));
        MUSIC_RENDER_HISTORY();
        document.getElementById('musicCountDisplay').textContent=MUSIC_HISTORY.length;
        showToast('🎵 歌曲生成完成！');
        submitText.disabled=false;submitText.textContent=origText;
      } else if(d.data&&(d.data.status==='failed')){
        clearInterval(iv);
        showToast('生成失败: '+(d.data.result?.errormsg||'未知错误'));
        submitText.disabled=false;submitText.textContent=origText;
      }
      if(attempts>=maxAttempts){
        clearInterval(iv);
        showToast('⏰ 查询超时，请稍后刷新查看');
        submitText.disabled=false;submitText.textContent=origText;
      }
    }catch(e){
      clearInterval(iv);
      showToast('查询错误: '+e.message);
      submitText.disabled=false;submitText.textContent=origText;
    }
  },5000);
}

function MUSIC_PLAY(i){
  const s=MUSIC_HISTORY[i];
  if(!s||!s.url)return;
  const p=document.getElementById('musicPlayer');
  const a=document.getElementById('musicAudio');
  const n=document.getElementById('musicNowPlaying');
  a.src=s.url;
  a.play().catch(()=>{});
  if(s.duration&&s.duration>0){
    a.onloadedmetadata=()=>{};
    setTimeout(()=>{
      const min=Math.floor(s.duration/60);
      const sec=Math.floor(s.duration%60);
      n.innerHTML=`▶️ ${escapeHtml(s.title)} (${min}:${sec.toString().padStart(2,'0')})`;
    },500);
  }else{
    n.innerHTML=`▶️ ${escapeHtml(s.title)}`;
  }
  p.style.display='block';
  // 更新历史列表高亮
  document.querySelectorAll('#musicHistoryList .feature-card').forEach((el,idx)=>{
    el.style.border=idx===i?'2px solid var(--accent)':'1px solid var(--border)';
  });
}
function MUSIC_DOWNLOAD(i){
  const s=MUSIC_HISTORY[i];
  if(!s||!s.url)return;
  const a=document.createElement('a');
  a.href=s.url;
  a.download=(s.title||'song')+'.mp3';
  a.click();
  showToast('💾 下载已开始');
}
function MUSIC_RENDER_HISTORY(){
  const el=document.getElementById('musicHistoryList');
  if(!MUSIC_HISTORY||!MUSIC_HISTORY.length){
    el.innerHTML=`<div style="text-align:center;color:var(--text-secondary);padding:60px 20px"><div style="font-size:3rem;margin-bottom:8px">🎵</div><p style="font-size:0.85rem">还没有创作记录</p></div>`;
    return;
  }
  el.innerHTML=MUSIC_HISTORY.map((s,i)=>{
    const timeAgo=Math.floor((Date.now()-new Date(s.time))/(60000));
    const timeStr=timeAgo<1?'刚刚':Math.floor(timeAgo/60)<1?timeAgo+'分钟前':Math.floor(timeAgo/60)+'小时前';
    return `<div class="feature-card" style="padding:12px;margin-bottom:8px;cursor:pointer" onclick="MUSIC_PLAY(${i})">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">
        <div style="display:flex;align-items:center;gap:8px">
          ${s.cover?`<img src="${s.cover}" style="width:36px;height:36px;border-radius:6px;object-fit:cover">`:''}
          <div>
            <div style="font-weight:600;font-size:0.85rem;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${escapeHtml(s.title)}</div>
            <div style="font-size:0.68rem;color:var(--text-secondary)">${s.styles||'流行'} · ${s.instrumental?'纯音乐':'人声'} · ${timeStr}</div>
          </div>
        </div>
        <div style="display:flex;gap:6px">
          <button class="btn-sm" onclick="event.stopPropagation();MUSIC_PLAY(${i})" style="font-size:0.7rem;padding:4px 10px">▶</button>
          <button class="btn-sm primary" onclick="event.stopPropagation();MUSIC_DOWNLOAD(${i})" style="font-size:0.7rem;padding:4px 10px">💾</button>
        </div>
      </div>
    </div>`;
  }).join('');
}
function MUSIC_PLAY(i){
  const s=MUSIC_HISTORY[i];
  if(!s||!s.url)return;
  const existing=document.getElementById('musicPlayerTemp');
  if(existing)existing.remove();
  const audio=document.createElement('audio');
  audio.id='musicPlayerTemp';
  audio.src=s.url;
  audio.controls=true;
  audio.style.cssText='position:fixed;bottom:80px;right:20px;z-index:1000;width:320px;border-radius:12px';
  audio.play();
  document.body.appendChild(audio);
  audio.onended=()=>setTimeout(()=>audio.remove(),2000);
}
function MUSIC_DOWNLOAD(i){
  const s=MUSIC_HISTORY[i];
  if(!s||!s.url)return;
  const a=document.createElement('a');
  a.href=s.url;
  a.download=(s.title||'music')+'.mp3';
  a.click();
  showToast('已开始下载');
}
// 初始化音乐模块数据
if(document.getElementById('musicCountDisplay')&&MUSIC_HISTORY.length){
  document.getElementById('musicCountDisplay').textContent=MUSIC_HISTORY.length;
  MUSIC_RENDER_HISTORY();
}
// 更新音乐积分显示
function MUSIC_UPDATE_CREDITS(){const el=document.getElementById('musicCreditDisplay');if(el)el.textContent=userCredits||0}
setInterval(MUSIC_UPDATE_CREDITS,5000);

