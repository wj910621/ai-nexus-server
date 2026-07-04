'use strict';
// ==== AI STUDIO 创作工场 ====
const GALLERY_SAMPLES=[
  {url:'https://picsum.photos/seed/cyber1/512/512',prompt:'赛博朋克城市夜景，霓虹灯，雨夜，街道倒影',full:'cyberpunk city night, neon lights, rain, street reflection, photorealistic, 8k',cat:'绘画',time:'2026-01-15T10:00:00Z'},
  {url:'https://picsum.photos/seed/anime1/512/512',prompt:'动漫少女，白发紫瞳，花园，柔光',full:'anime girl, white hair, purple eyes, flower garden, soft lighting, detailed',cat:'绘画',time:'2026-01-16T10:00:00Z'},
  {url:'https://picsum.photos/seed/fantasy1/512/512',prompt:'奇幻风景，浮空岛，魔法河流，史诗视角',full:'fantasy landscape, floating islands, magic glowing river, epic wide angle',cat:'绘画',time:'2026-01-17T10:00:00Z'},
  {url:'https://picsum.photos/seed/battle1/512/512',prompt:'漫画战斗场景，武士对决，动态线条',full:'manga comic style battle scene, samurai sword fight, dynamic action lines, black and white',cat:'漫画',time:'2026-01-18T10:00:00Z'},
  {url:'https://picsum.photos/seed/superhero1/512/512',prompt:'漫画风格超级英雄，城市天际线，波普艺术色彩',full:'comic strip style, superhero, city skyline, colorful, pop art',cat:'漫画',time:'2026-01-19T10:00:00Z'},
  {url:'https://picsum.photos/seed/robot1/512/512',prompt:'3D渲染可爱机器人，皮克斯风格，柔光',full:'3d render, cute robot, friendly droid, pixar style, soft lighting',cat:'3D',time:'2026-01-20T10:00:00Z'},
  {url:'https://picsum.photos/seed/elf1/512/512',prompt:'3D角色设计，精灵战士，盔甲细节，虚幻引擎渲染',full:'3d character design, fantasy elf warrior, armor, detailed, unreal engine render',cat:'3D',time:'2026-01-21T10:00:00Z'},
  {url:'https://picsum.photos/seed/cinema1/512/512',prompt:'电影级追逐场景，夜间公路，动态模糊，航拍',full:'cinematic movie scene, highway at night, car chase, motion blur, drone shot',cat:'视频',time:'2026-01-22T10:00:00Z'},
  {url:'https://picsum.photos/seed/water1/512/512',prompt:'水彩画，山间湖泊，日落，艺术笔触',full:'watercolor painting, mountain lake, sunset, artistic brush strokes',cat:'绘画',time:'2026-01-23T10:00:00Z'},
  {url:'https://picsum.photos/seed/steam1/512/512',prompt:'蒸汽朋克飞艇，天空之城，齿轮，维多利亚风格',full:'steampunk airship, sky city, gears, victorian style, detailed illustration',cat:'绘画',time:'2026-01-24T10:00:00Z'},
  {url:'https://picsum.photos/seed/nature1/512/512',prompt:'壮丽自然，高山湖泊，金色夕阳，全景',full:'majestic nature, alpine lake, golden sunset, panoramic view',cat:'绘画',time:'2026-01-25T10:00:00Z'},
  {url:'https://picsum.photos/seed/city1/512/512',prompt:'都市夜景，万家灯火，天际线，长曝光',full:'city skyline at night, millions of lights, long exposure',cat:'绘画',time:'2026-01-26T10:00:00Z'},
];
let STUDIO_GALLERY=JSON.parse(localStorage.getItem('stuGallery')||'[]');
let GALLERY_FILTER_CURRENT='all';
(function(){
  if(!localStorage.getItem('stuGallery')||JSON.parse(localStorage.getItem('stuGallery')).length===0){
    STUDIO_GALLERY=GALLERY_SAMPLES.map(s=>({...s}));
    localStorage.setItem('stuGallery',JSON.stringify(STUDIO_GALLERY));
  }
})();
function initStudioData(){
  document.querySelectorAll('#studioTabs .tab-btn').forEach(b=>{b.addEventListener('click',()=>{document.querySelectorAll('#studioTabs .tab-btn').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelectorAll('#studioTabImage,#studioTabVideo,#studioTabGallery').forEach(t=>t.style.display='none');document.getElementById('studioTab'+b.dataset.tab.charAt(0).toUpperCase()+b.dataset.tab.slice(1)).style.display='block';if(b.dataset.tab==='gallery')renderStudioGallery()})});
  ['stuPrompt','stuStyle','stuLight','stuCamera','stuRatio','stuRef'].forEach(id=>{const el=document.getElementById(id);if(el)el.addEventListener('input',STUDIO_BUILD_PROMPT)});
  STUDIO_BUILD_PROMPT();
  // 加载已保存的视频 API Key 和平台
  const savedKey=localStorage.getItem('vid_api_key');
  const savedPlatform=localStorage.getItem('vid_api_platform')||'agnes';
  const pe=document.getElementById('vidApiPlatform');
  if(pe)pe.value=savedPlatform;
  if(savedPlatform==='agnes'){
    // Agnes 模式：隐藏 Key 输入框
    document.getElementById('vidApiKey').style.display='none';
    document.getElementById('vidAgnesHint').style.display='block';
    // 隐藏保存按钮（Agnes 用平台 Key，无需用户操作）
    const saveBtn=document.querySelector('#vidApiRow .btn-sm');
    if(saveBtn)saveBtn.style.display='none';
    const costLabel=document.getElementById('vidCostLabel');
    if(costLabel)costLabel.textContent='⚡5积分';
  }else{
    document.getElementById('vidAgnesHint').style.display='none';
    if(savedKey){const ke=document.getElementById('vidApiKey');if(ke)ke.value=savedKey}
  }
  // 加载已保存的音乐 API Key
  const musicKey=localStorage.getItem('music_api_key');
  const musicPlatform=localStorage.getItem('music_api_platform')||'suno';
  const mpEl=document.getElementById('musicApiPlatform');
  const mkEl=document.getElementById('musicApiKey');
  if(mpEl)mpEl.value=musicPlatform;
  if(mkEl&&musicKey&&musicPlatform!=='suno')mkEl.value=musicKey;
}
function GALLERY_FILTER(cat,el){
  GALLERY_FILTER_CURRENT=cat;
  document.querySelectorAll('[data-gfilter]').forEach(x=>x.classList.remove('active'));
  if(el)el.classList.add('active');
  renderStudioGallery();
}
function GALLERY_UPLOAD(){
  const input=document.createElement('input');
  input.type='file';
  input.accept='image/*';
  input.onchange=function(e){
    const file=e.target.files[0];
    if(!file)return;
    const reader=new FileReader();
    reader.onload=function(ev){
      const name=prompt('作品名称：',file.name)||file.name;
      const cat=prompt('分类（绘画/漫画/3D/视频）：','绘画')||'绘画';
      STUDIO_GALLERY.unshift({url:ev.target.result,prompt:name,full:'',cat:cat,time:new Date().toISOString()});
      STUDIO_GALLERY=STUDIO_GALLERY.slice(0,100);
      localStorage.setItem('stuGallery',JSON.stringify(STUDIO_GALLERY));
      renderStudioGallery();
      showToast('✅ 作品已上传');
    };
    reader.readAsDataURL(file);
  };
  input.click();
}
function STUDIO_BUILD_PROMPT(){const p=[document.getElementById('stuPrompt')?.value,document.getElementById('stuStyle')?.value,document.getElementById('stuLight')?.value,document.getElementById('stuCamera')?.value,document.getElementById('stuRatio')?.value?'--ar '+document.getElementById('stuRatio').value:'',document.getElementById('stuRef')?.value?'reference: '+document.getElementById('stuRef').value:''].filter(Boolean);const txt=p.join(', ');const el=document.getElementById('stuPromptPreview'),ts=document.getElementById('stuPromptText');if(txt&&txt!=='不限制'){el.style.display='block';ts.textContent=txt}else{el.style.display='none'}}
function STUDIO_COPY_PROMPT(){const t=document.getElementById('stuPromptText').textContent;if(!t){showToast('请先输入描述');return}navigator.clipboard.writeText(t).then(()=>showToast('已复制'))}
function STUDIO_QUICK(type){const prompts={cyberpunk:'赛博朋克城市夜景,霓虹灯,雨雾,未来科技感',anime:'动漫风格角色,精致线条,柔和色调,日系',landscape:'壮丽自然风景,电影级光影,超广角,8K',product:'产品摄影,极简背景,柔和棚拍光线,高质量'};document.getElementById('stuPrompt').value=prompts[type]||'';STUDIO_BUILD_PROMPT()}
function STUDIO_SET(k,v){if(k==='ratio')document.getElementById('stuRatio').value=v;STUDIO_BUILD_PROMPT()}
async function STUDIO_GENERATE_IMAGE(){const prompt=document.getElementById('stuPromptText').textContent.trim();const subj=document.getElementById('stuPrompt').value.trim();const p=subj||prompt;if(!p){showToast('请输入创作描述');return}const load=document.getElementById('stuLoading'),img=document.getElementById('stuImage');load.style.display='block';img.style.display='none';document.getElementById('stuImgActions').style.display='none';try{const url=`https://image.pollinations.ai/prompt/${encodeURIComponent(p)}?width=768&height=768&nologo=true&seed=${Math.floor(Math.random()*99999)}`;img.src=url;img.onload=()=>{load.style.display='none';img.style.display='block';document.getElementById('stuImgActions').style.display='flex';window._stuLastImage={url,prompt:document.getElementById('stuPrompt').value,full:p,cat:'绘画',time:new Date().toISOString()}};img.onerror=()=>{load.style.display='none';showToast('生成失败')}}catch(e){load.style.display='none';showToast('出错')}}
function STUDIO_SAVE_IMAGE(){if(!window._stuLastImage){showToast('请先生成图像');return}const a=document.createElement('a');a.href=window._stuLastImage.url;a.download='ai-creation.png';a.click()}
function STUDIO_ADD_TO_GALLERY(){if(!window._stuLastImage){showToast('请先生成图像');return}STUDIO_GALLERY.unshift({...window._stuLastImage,cat:'绘画'});STUDIO_GALLERY=STUDIO_GALLERY.slice(0,100);localStorage.setItem('stuGallery',JSON.stringify(STUDIO_GALLERY));showToast('已加入画廊')}
function renderStudioGallery(){const g=document.getElementById('studioGalleryGrid');let items=STUDIO_GALLERY;if(GALLERY_FILTER_CURRENT!=='all')items=items.filter(i=>i.cat===GALLERY_FILTER_CURRENT);if(!items.length){g.innerHTML='<div style="text-align:center;color:var(--text-secondary);padding:60px;grid-column:1/-1"><div style="font-size:3rem">🎨</div><p>没有找到作品</p></div>';return}g.innerHTML=items.map((s,i)=>`<div class="feature-card" style="cursor:pointer;padding:0;overflow:hidden" onclick="STUDIO_GALLERY_USE(${STUDIO_GALLERY.indexOf(s)})"><div style="height:160px;display:flex;align-items:center;justify-content:center;background:var(--bg-input);position:relative;overflow:hidden"><div style="position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:2rem;opacity:0.3;pointer-events:none">🎨</div><img src="${s.url}" loading="lazy" style="max-width:100%;max-height:100%;object-fit:cover;position:relative;z-index:1" onload="this.previousElementSibling.style.display='none'" onerror="this.style.display='none';this.previousElementSibling.style.opacity='0.8';this.previousElementSibling.textContent='🖼️'"></div><div style="padding:12px"><div style="font-weight:600;font-size:0.82rem;margin-bottom:4px">${escapeHtml(s.prompt.substring(0,40))}...</div><div style="font-size:0.68rem;color:var(--text-secondary)">${s.cat||'绘画'} · ${new Date(s.time).toLocaleString('zh-CN')}</div></div></div>`).join('')}
function STUDIO_GALLERY_USE(i){if(!STUDIO_GALLERY[i])return;document.getElementById('stuPrompt').value=STUDIO_GALLERY[i].prompt;document.getElementById('studioTabs').querySelector('[data-tab=image]').click();document.getElementById('studioTabImage').style.display='block';document.getElementById('studioTabVideo').style.display='none';document.getElementById('studioTabGallery').style.display='none';STUDIO_BUILD_PROMPT();showToast('已加载到创作区')}
async function STUDIO_GENERATE_VIDEO(){const p=document.getElementById('stuVidPrompt').value.trim();if(!p){showToast('请输入视频描述');return}const platform=localStorage.getItem('vid_api_platform')||'agnes';const load=document.getElementById('stuVidLoading'),ph=document.getElementById('stuVidPlaceholder'),res=document.getElementById('stuVidResult'),img=document.getElementById('stuVideoImg'),bar=document.getElementById('vidProgressBar'),txt=document.getElementById('vidStatusText'),sub=document.getElementById('vidStatusSub');if(ph)ph.style.display='none';load.style.display='block';if(bar)bar.style.width='0%';if(txt)txt.textContent='🎨 AI 正在创作视频...';if(sub)sub.textContent='预计需要 1-3 分钟';if(img)img.style.display='none';if(res){res.style.display='none';res.innerHTML=''}const style=document.getElementById('vidStyle').value;const dur=document.getElementById('vidDuration').value;const ratio=document.getElementById('vidRatio').value;const quality=document.getElementById('vidQuality').value;if(!spendCredits(platform==='agnes'?5:10)){load.style.display='none';if(ph)ph.style.display='block';return}try{if(platform==='agnes'){const fullPrompt=p+(style&&style!=='不限制'?', '+style:'')+', cinematic, '+quality+', '+ratio;const body={prompt:fullPrompt,width:1152,height:768,num_frames:Math.min(81+Math.floor(parseInt(dur)/5)*40,241),frame_rate:24};if(style==='赛博朋克'){body.negative_prompt='blurry, low quality, cartoon, anime, pixelated'}const r=await fetch('/api/agnes-video',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const d=await r.json();if(!d.ok||!d.id){load.style.display='none';if(ph)ph.style.display='block';showToast('❌ 提交失败: '+(d.error||'未知错误'));return}const taskId=d.id;const statusMsgs=['🎬 正在构思画面...','🎨 绘制关键帧中...','✨ 渲染视频细节...','🎵 合成音频轨道...','🔮 即将完成...'];if(txt)txt.textContent=statusMsgs[0];if(bar)bar.style.width='10%';let result=null;for(let i=0;i<60;i++){await new Promise(rv=>setTimeout(rv,3000));const sr=await fetch('/api/agnes-video/'+taskId);const sd=await sr.json();const pct=Math.min(95,Math.floor((i+1)/60*95));if(bar)bar.style.width=pct+'%';const msgIdx=Math.min(4,Math.floor(i/12));if(txt&&(i===0||i%12===0))txt.textContent=statusMsgs[msgIdx];if(sub)sub.textContent='已等待 '+Math.floor((i+1)*3)+' 秒...';if(sd.status==='completed'){result=sd;if(bar)bar.style.width='100%';if(txt)txt.textContent='✅ 生成完成！';break}if(sd.status==='failed'){load.style.display='none';if(ph)ph.style.display='block';showToast('❌ 生成失败: '+(sd.error||'未知错误'));return}}if(!result){load.style.display='none';if(ph)ph.style.display='block';showToast('⏰ 生成超时，请稍后重试');return}const videoUrl=result.video_url||result.url||result.remixed_from_video_id;if(!videoUrl){load.style.display='none';if(ph)ph.style.display='block';showToast('❌ 未获取到视频链接');return}await new Promise(rv=>setTimeout(rv,400));load.style.display='none';res.style.display='block';res.innerHTML='<div style="padding:8px"><video id="stuVidPlayer" controls autoplay loop playsinline style="width:100%;max-height:400px;border-radius:12px;animation:vidPulse 2s ease 1" src="'+videoUrl+'" onloadeddata="this.closest(\'#stuVidResult\').querySelector(\'.vid-loading-overlay\').style.display=\'none\'"><div class="vid-loading-overlay" style="position:absolute;top:0;left:0;right:0;bottom:0;display:flex;align-items:center;justify-content:center;background:rgba(0,0,0,0.3);border-radius:12px;pointer-events:none"><div class="spinner"></div></div></video><div style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap;justify-content:center"><button class="btn-sm primary" onclick="window.open(\''+videoUrl+'\')" style="animation:vidReveal 0.4s ease 0.1s both">🔗 新窗口打开</button><button class="btn-sm" onclick="STUDIO_ADD_VIDEO_TO_GALLERY(\''+videoUrl+'\',\''+escapeHtml(p.substring(0,60))+'\')" style="animation:vidReveal 0.4s ease 0.2s both">💾 加入画廊</button><button class="btn-sm" onclick="STUDIO_SAVE_VIDEO()" style="animation:vidReveal 0.4s ease 0.3s both">📥 下载视频</button></div></div>';showToast('🎉 视频生成成功！')}else{const savedKey=localStorage.getItem('vid_api_key');if(!savedKey){showToast('⚠️ 请先在上方切换为自配模式并输入 '+platform+' API Key');load.style.display='none';if(ph)ph.style.display='block';return}const url='https://image.pollinations.ai/prompt/'+encodeURIComponent(p+' '+style+', cinematic, '+quality+', '+ratio)+'?width=768&height=432&nologo=true&seed='+Math.floor(Math.random()*99999);img.src=url;img.onload=()=>{load.style.display='none';img.style.display='block';showToast('🎬 视频预览生成完成（'+dur+'秒, '+platform+', '+quality+'）')};img.onerror=()=>{load.style.display='none';showToast('生成失败')}}}catch(e){load.style.display='none';if(ph)ph.style.display='block';showToast('出错: '+e.message)}}
function STUDIO_ADD_VIDEO_TO_GALLERY(url,prompt){STUDIO_GALLERY.unshift({url:url,prompt:prompt||'AI 视频',full:prompt||'',cat:'视频',time:new Date().toISOString()});STUDIO_GALLERY=STUDIO_GALLERY.slice(0,100);localStorage.setItem('stuGallery',JSON.stringify(STUDIO_GALLERY));showToast('✅ 已加入画廊')}
function VID_SAVE_KEY(){const platform=document.getElementById('vidApiPlatform').value;if(platform==='agnes'){localStorage.setItem('vid_api_platform','agnes');localStorage.removeItem('vid_api_key');showToast('✅ 已切换为平台免费模式');return}const key=document.getElementById('vidApiKey').value.trim();if(!key){showToast('请输入 API Key');return}localStorage.setItem('vid_api_key',key);localStorage.setItem('vid_api_platform',platform);showToast('✅ '+platform+' API Key 已保存')}
function VID_PLATFORM_CHANGE(){const platform=document.getElementById('vidApiPlatform').value;const keyEl=document.getElementById('vidApiKey');const hintEl=document.getElementById('vidAgnesHint');const saveBtn=document.querySelector('#vidApiRow .btn-sm');const costLabel=document.getElementById('vidCostLabel');if(platform==='agnes'){keyEl.style.display='none';hintEl.style.display='block';if(saveBtn)saveBtn.style.display='none';if(costLabel)costLabel.textContent='⚡5积分';localStorage.setItem('vid_api_platform','agnes')}else{keyEl.style.display='inline-block';hintEl.style.display='none';if(saveBtn)saveBtn.style.display='inline-block';if(costLabel)costLabel.textContent='⚡10积分';localStorage.setItem('vid_api_platform',platform);const savedKey=localStorage.getItem('vid_api_key');if(savedKey)keyEl.value=savedKey;else keyEl.value=''}}
function STUDIO_SAVE_VIDEO(){const v=document.getElementById('stuVidPlayer');if(v&&v.src){const a=document.createElement('a');a.href=v.src;a.download='ai-video.mp4';a.click();return}const img=document.getElementById('stuVideoImg');if(!img.src||img.style.display==='none'){showToast('请先生成视频');return}const a=document.createElement('a');a.href=img.src;a.download='ai-video-preview.png';a.click()}
function VID_PREVIEW_WITH_EDITS(){
  const v=document.getElementById('stuVidPlayer');
  const img=document.getElementById('stuVideoImg');
  const r=document.getElementById('stuVidResult');
  const txt=document.getElementById('vidSubtitle').value.trim();
  const start=parseFloat(document.getElementById('vidTrimStart').value)||0;
  const end=parseFloat(document.getElementById('vidTrimEnd').value)||0;
  // 如果是视频
  if(v&&v.src){
    const v2=document.getElementById('vidEditPlayer')||(()=>{const e=document.createElement('video');e.id='vidEditPlayer';e.controls=true;e.style.width='100%';e.style.maxHeight='280px';e.style.borderRadius='10px';r.after(e);return e})();
    v2.src=v.src;
    v2.currentTime=start;
    if(end>start)v2.play().then(()=>{setTimeout(()=>v2.pause(),(end-start)*1000)});
    // 字幕叠加
    const sc=document.getElementById('vidSubtitleOverlay')||(function(){const d=document.createElement('div');d.id='vidSubtitleOverlay';d.style.cssText='text-align:center;padding:8px;font-size:1rem;font-weight:700;color:#fff;text-shadow:0 0 8px rgba(0,0,0,0.8);background:rgba(0,0,0,0.4);border-radius:8px;margin-top:-50px;position:relative;z-index:10';r.after(d);return d})();
    if(txt){sc.textContent=txt;sc.style.display='block'}else sc.style.display='none';
  }
  showToast('✅ 已应用编辑设置');
}
function VID_SET_MODE(mode,el){document.querySelectorAll('#studioTabVideo .workshop-tab').forEach(x=>x.classList.remove('active'));el.classList.add('active');document.getElementById('vidTextMode').style.display=mode==='text'?'block':'none';document.getElementById('vidImageMode').style.display=mode==='image'?'block':'none'}
function VID_PREVIEW_IMAGE(input){const f=input.files[0];if(!f)return;const r=new FileReader();r.onload=function(e){const preview=document.getElementById('vidImagePreview');preview.style.display='block';preview.querySelector('img').src=e.target.result;document.getElementById('vidImageDrop').style.display='none'};r.readAsDataURL(f)}
function VID_CLEAR(){document.getElementById('stuVidPrompt').value='';document.getElementById('stuVideoImg').style.display='none';document.getElementById('stuVidLoading').style.display='none';const r=document.getElementById('stuVidResult');if(r){r.style.display='none';r.innerHTML=''}document.getElementById('stuVidPlaceholder').style.display='block';document.getElementById('vidImagePreview').style.display='none';document.getElementById('vidImageDrop').style.display='flex';const bar=document.getElementById('vidProgressBar');if(bar)bar.style.width='0%'}
// ==== 视频提示词模板 ====
const VID_TEMPLATES=[
  {cn:'赛博朋克：雨夜霓虹街道，孤独人影穿行，倒影闪烁，蒸汽升腾，慢镜头，电影感',en:'A lone figure walking through a rain-soaked neon street at night, reflections of pink and blue lights on wet pavement, slow cinematic pan, steam rising, cyberpunk',icon:'🌆',color:'#6366f1,#06b6d4',sec:5,video:'https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_ec52cf21df81389c82af51a35e99239b1b09cf4618ffb63f.mp4'},
  {cn:'自然风光：无人机飞越日出雪山，金色光芒穿透云层，原始高山湖泊，4K画质',en:'Drone shot flying over misty mountain peaks at sunrise, golden light breaking through clouds, pristine alpine lake, cinematic 4K, smooth aerial',icon:'🏔️',color:'#047857,#10b981',sec:5,video:'https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_b77afb78dd159653fea56e8b0ceda7e6bb5863ce0d2ae5da.mp4'},
  {cn:'趣味动物：橘猫在窗台安睡，午后阳光洒落，微风拂动窗帘，温暖治愈',en:'A fluffy orange cat sleeping peacefully on a sunny windowsill, warm afternoon light, gentle breeze, cozy atmosphere, shallow depth of field',icon:'🐱',color:'#f59e0b,#ef4444',sec:5,video:'https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_0e90988ac7475c6034bef9a16362c2d2678abceedd987af2.mp4'},
  {cn:'古风武侠：白衣剑客立于竹叶之上，风吹竹林，落叶环绕，慢动作，电影光影',en:'A swordsman in flowing white robes on bamboo leaf, slow motion, wind in bamboo forest, leaves swirling, cinematic lighting, martial arts',icon:'⚔️',color:'#1c1917,#f59e0b',sec:5,video:'https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_1a55609c81a23fb8a75c9e761356996f9d1e6d23305869c6.mp4'},
  {cn:'科幻大片：巨型星舰从紫色星云浮现，引擎蓝光，粒子漂浮，史诗级别',en:'A massive starship emerging from purple nebula, engine glow, cosmic particles, epic scale cinematic space shot, 4K',icon:'🚀',color:'#4c1d95,#a855f7',sec:5,video:'https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_ab5c0e0d8cbb18ca50a248f8d1c57b2ddd7028b839c8f1d4.mp4'},
  {cn:'海浪日落：海浪拍打暗礁，夕阳逆光，慢动作水花，海鸥远处，戏剧化天空',en:'Waves crashing against dark rocks at sunset, golden hour backlight, slow motion splashes, seagulls, dramatic sky, cinematic',icon:'🌊',color:'#0e7490,#06b6d4',sec:5,video:'https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_317d6380fdd50aa83b82e73a2941e45e46b6bd787668a859.mp4'},
  {cn:'魔法森林：发光蘑菇与萤火虫在古老森林闪烁，月光穿透树冠，魔幻仙境',en:'Glowing mushrooms and fireflies in enchanted ancient forest, moonlight through canopy, magical particles floating, fantasy cinematic',icon:'🌲',color:'#15803d,#34d399',sec:5,video:'https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_900511d41580b28bb81bfe3bf1fe9e6687043aaf8f1f9bad.mp4'},
  {cn:'蒸汽朋克：黄铜齿轮特写转动，铜管蒸汽嘶嘶声，钟表匠工作台温暖光',en:'Brass mechanical gears turning closeup, steam hissing from copper pipes, watchmaker workbench, warm lighting, steampunk, shallow depth',icon:'⚙️',color:'#92400e,#f59e0b',sec:5,video:'https://storage.googleapis.com/agnes-aigc/aigc/videos/2026/06/03/video_40a32719311384268bc8deb92736a50eaed2494c8e927d5e.mp4'},
];
let vidTmplLang='cn';
function VID_TMPL_LANG(lang){
  vidTmplLang=lang;
  document.getElementById('vidTmplBtnCN').style.background=lang==='cn'?'var(--accent)':'transparent';
  document.getElementById('vidTmplBtnCN').style.color=lang==='cn'?'#fff':'var(--text-secondary)';
  document.getElementById('vidTmplBtnEN').style.background=lang==='en'?'var(--accent)':'transparent';
  document.getElementById('vidTmplBtnEN').style.color=lang==='en'?'#fff':'var(--text-secondary)';
  VID_RENDER_TEMPLATES();
}
function VID_RENDER_TEMPLATES(){
  const grid=document.getElementById('vidTmplGrid');
  if(!grid)return;
  grid.innerHTML=VID_TEMPLATES.map((t,i)=>`<div class="feature-card vid-tmpl-card" style="padding:0;overflow:hidden;cursor:pointer;transition:all 0.2s;position:relative" onclick="VID_TMPL_USE(${i})" onmouseenter="VID_TMPL_HOVER(${i},true,this)" onmouseleave="VID_TMPL_HOVER(${i},false,this)">
    <div class="vid-tmpl-media" style="height:90px;position:relative;overflow:hidden;background:#1a1035">
      ${t.video?`<video class="vid-tmpl-video" src="${t.video}" muted loop playsinline preload="metadata" style="width:100%;height:100%;object-fit:cover;position:absolute;top:0;left:0" onloadedmetadata="this.currentTime=1"></video><div class="vid-tmpl-overlay" style="position:absolute;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,0.25);transition:opacity 0.3s;pointer-events:none"></div>`:'<div style="width:100%;height:100%;background:linear-gradient(135deg,'+t.color+');display:flex;align-items:center;justify-content:center;font-size:2rem">'+t.icon+'</div>'}
      <div class="vid-tmpl-play" style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:32px;height:32px;border-radius:50%;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;pointer-events:none;transition:transform 0.2s,opacity 0.2s">
        <div style="width:0;height:0;border-top:7px solid transparent;border-bottom:7px solid transparent;border-left:11px solid #fff;margin-left:2px"></div>
      </div>
    </div>
    <div style="position:absolute;bottom:6px;right:6px;background:rgba(0,0,0,0.65);color:#fff;font-size:0.6rem;padding:1px 6px;border-radius:3px;pointer-events:none">${t.sec||5}s</div>
    <div style="padding:8px">
      <div style="font-weight:600;font-size:0.72rem;line-height:1.3;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden">${vidTmplLang==='cn'?t.cn.split('：')[1]||t.cn:t.en.substring(0,36)}</div>
      <div style="margin-top:3px;display:flex;gap:4px;align-items:center">
        <span style="font-size:0.6rem;padding:1px 5px;background:var(--accent-soft);border-radius:3px;color:var(--accent)">点击使用</span>
        <span style="font-size:0.58rem;color:var(--text-secondary)">${vidTmplLang==='cn'?'中文':'English'}</span>
      </div>
    </div>
  </div>`).join('');
}
function VID_TMPL_HOVER(i,enter,el){
  const v=el.querySelector('video');
  const overlay=el.querySelector('.vid-tmpl-overlay');
  const play=el.querySelector('.vid-tmpl-play');
  if(!v||!v.src)return;
  if(enter){
    v.play().catch(()=>{});
    if(overlay)overlay.style.opacity='0';
    if(play){play.style.opacity='0';play.style.transform='translate(-50%,-50%) scale(1.3)'}
  }else{
    v.pause();
    v.currentTime=1;
    if(overlay)overlay.style.opacity='1';
    if(play){play.style.opacity='1';play.style.transform='translate(-50%,-50%) scale(1)'}
  }
}
function VID_TMPL_USE(i){
  const t=VID_TEMPLATES[i];
  if(!t)return;
  const prompt=vidTmplLang==='cn'?t.cn:t.en;
  document.getElementById('stuVidPrompt').value=prompt;
  document.getElementById('vidStyle').value=vidTmplLang==='cn'?'电影感':'cinematic';
  showToast('✅ 已加载「'+t.cn.substring(0,t.cn.indexOf('：')>=0?t.cn.indexOf('：'):8)+'」提示词');
}
// 页面初始化时渲染模板
setTimeout(()=>{if(document.getElementById('vidTmplGrid'))VID_RENDER_TEMPLATES()},200);

// ==== 🎎 3D 角色展示库（数据驱动 + 悬停预览） ====
const D3_TEMPLATES=[
  {name:'中国龙',prompt:'一只威武的中国龙，东方神话风格，盘旋姿态，鳞片细节丰富，低面数优化',icon:'🐉',color:'#7c2d12,#b45309,#d97706,#f59e0b',tags:['神话','低面数'],thumb:'https://image.pollinations.ai/prompt/A%20majestic%20Chinese%20dragon,%20oriental%20mythical%20style,%20coiled%20pose,%20detailed%20scales,%20low-poly%20game%20asset%20on%20dark%20background?width=400&height=300&nologo=true&seed=1000'},
  {name:'机甲战士',prompt:'未来机甲战士，合金装甲，蓝色能量核心，战斗姿态，高精度模型，关节可动',icon:'🤖',color:'#1e3a5f,#1d4ed8,#3b82f6,#06b6d4',tags:['科幻','高精度'],thumb:'https://image.pollinations.ai/prompt/Futuristic%20mecha%20warrior,%20alloy%20armor,%20blue%20energy%20core,%20battle%20stance,%20high%20detail%203D%20render?width=400&height=300&nologo=true&seed=1001'},
  {name:'古代宫殿',prompt:'中国古代宫殿建筑群，唐代风格，红墙金瓦，飞檐翘角，对称布局，低多边形场景模型',icon:'🏯',color:'#4a1d96,#6d28d9,#8b5cf6,#a78bfa',tags:['建筑','场景'],thumb:'https://image.pollinations.ai/prompt/Ancient%20Chinese%20palace%20architecture,%20Tang%20dynasty%20style,%20red%20walls%20golden%20tiles,%20symmetrical%20layout,%20low-poly%203D%20scene?width=400&height=300&nologo=true&seed=1002'},
  {name:'九尾狐',prompt:'九尾狐妖，白色毛发，九条尾巴飘逸灵动，红宝石般的眼睛，卡通渲染风格，半写实',icon:'🦊',color:'#9d174d,#db2777,#f472b6,#f9a8d4',tags:['卡通','角色'],thumb:'https://image.pollinations.ai/prompt/Nine-tailed%20fox%20spirit,%20white%20fur,%20nine%20flowing%20tails,%20ruby%20eyes,%20cel-shaded%20game%20character%20style?width=400&height=300&nologo=true&seed=1003'},
  {name:'星际飞船',prompt:'科幻星际驱逐舰，流线型设计，金属装甲外壳，引擎喷口蓝色火焰，高精度细节，太空场景',icon:'🚀',color:'#0f172a,#1e40af,#2563eb,#38bdf8',tags:['科幻','载具'],thumb:'https://image.pollinations.ai/prompt/Sci-fi%20starship%20destroyer,%20streamlined%20design,%20metallic%20armor,%20blue%20engine%20glow,%203D%20model%20on%20black?width=400&height=300&nologo=true&seed=1004'},
  {name:'像素角色',prompt:'像素风格游戏角色，8-bit复古风格，色彩鲜艳，体素方块构建，Q版可爱大头造型',icon:'👾',color:'#064e3b,#059669,#10b981,#6ee7b7',tags:['体素','游戏'],thumb:'https://image.pollinations.ai/prompt/Pixel%20art%20game%20character,%208-bit%20retro%20style,%20bright%20colors,%20voxel%20block%20built,%20chibi%20cute%20big%20head?width=400&height=300&nologo=true&seed=1005'},
  {name:'精灵弓箭手',prompt:'奇幻精灵弓箭手，尖耳朵，银色长发，翠绿斗篷，手持精灵长弓，轻盈姿态，PBR材质',icon:'🧝',color:'#14532d,#166534,#16a34a,#86efac',tags:['奇幻','角色'],thumb:'https://image.pollinations.ai/prompt/Fantasy%20elf%20archer,%20pointed%20ears,%20silver%20long%20hair,%20emerald%20cloak,%20holding%20elf%20bow,%203D%20game%20character%20concept?width=400&height=300&nologo=true&seed=1006'},
  {name:'赛博武士',prompt:'赛博朋克日本武士，霓虹灯管武士刀，全息面甲，碳纤维护甲，雨夜街头站立，高模',icon:'⚔️',color:'#1e1b4b,#312e81,#6366f1,#a855f7',tags:['赛博','角色'],thumb:'https://image.pollinations.ai/prompt/Cyberpunk%20samurai,%20neon%20katana,%20holographic%20face%20mask,%20carbon%20fiber%20armor,%20standing%20in%20rain,%203D%20render?width=400&height=300&nologo=true&seed=1007'},
  {name:'机甲恐龙',prompt:'机械暴龙，金属骨骼外露，液压关节，红色电子眼，科幻武器化改装，大型生物机甲',icon:'🦖',color:'#7c2d12,#c2410c,#f97316,#fdba74',tags:['科幻','生物'],thumb:'https://image.pollinations.ai/prompt/Mechanical%20tyrannosaurus%20rex,%20exposed%20metal%20skeleton,%20hydraulic%20joints,%20red%20electronic%20eye,%20sci-fi%20weaponized,%20large%20bio-mecha?width=400&height=300&nologo=true&seed=1008'},
  {name:'魔法书',prompt:'漂浮的古老魔法书，皮革封面金色符文，书页自动翻动，魔法粒子环绕，低多边形游戏资产',icon:'📖',color:'#4a044e,#86198f,#c026d3,#e879f9',tags:['魔法','道具'],thumb:'https://image.pollinations.ai/prompt/Floating%20ancient%20spellbook,%20leather%20cover%20golden%20runes,%20pages%20turning,%20magic%20particles,%20low-poly%20game%20asset?width=400&height=300&nologo=true&seed=1009'},
];
function D3_RENDER_SHOWCASE(){
  const grid=document.getElementById('d3Showcase');
  if(!grid)return;
  grid.innerHTML=D3_TEMPLATES.map((t,i)=>`<div class="feature-card vid-tmpl-card d3-card" style="padding:0;overflow:hidden;cursor:pointer;position:relative;perspective:600px" onclick="D3_TMPL_USE(${i})">
    <div class="d3-card-inner" style="width:100%;height:200px;position:relative;transform-style:preserve-3d;transition:transform 0.8s cubic-bezier(0.4,0,0.2,1)"><div class="d3-card-front" style="position:absolute;inset:0;backface-visibility:hidden;border-radius:8px;overflow:hidden"><div style="width:100%;height:100%;background:linear-gradient(135deg,${t.color});display:flex;align-items:center;justify-content:center;font-size:2.5rem;position:absolute;inset:0;z-index:0">${t.icon}</div>${t.thumb?`<img src="${t.thumb}" loading="lazy" style="width:100%;height:100%;object-fit:cover;position:absolute;inset:0;z-index:1;opacity:1" onload="this.style.opacity='1'" onerror="this.remove()">`:''}<div style="position:absolute;bottom:0;left:0;right:0;padding:10px;background:linear-gradient(transparent,rgba(0,0,0,0.8));z-index:2;pointer-events:none"><div style="font-weight:700;font-size:0.85rem;color:#fff">${t.name}</div><div style="display:flex;gap:3px;margin-top:3px">${t.tags.map(tag=>`<span style="font-size:0.6rem;padding:1px 6px;background:rgba(255,255,255,0.15);border-radius:3px;color:#fff">${tag}</span>`).join('')}</div></div></div><div class="d3-card-back" style="position:absolute;inset:0;backface-visibility:hidden;border-radius:8px;overflow:hidden;transform:rotateY(180deg);background:linear-gradient(135deg,#1a1035,#261652)">${t.thumb?`<img src="${t.thumb}" loading="lazy" style="width:100%;height:100%;object-fit:cover;position:absolute;inset:0;opacity:0.35" onerror="this.remove()">`:''}<div style="position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:16px;z-index:1"><div style="font-weight:700;font-size:0.9rem;color:var(--accent);margin-bottom:8px">${t.name}</div><div style="font-size:0.7rem;color:var(--text-secondary);text-align:center;line-height:1.5;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden">${t.prompt.substring(0,60)}...</div><button onclick="event.stopPropagation();D3_AUTO_GENERATE(${i})" class="d3-gen-btn" style="padding:5px 14px;border:none;border-radius:14px;background:linear-gradient(135deg,var(--accent),var(--cyan));color:#fff;cursor:pointer;font-size:0.7rem;font-weight:700;transition:all 0.3s;box-shadow:0 2px 8px rgba(155,89,247,0.4)">🎨 一键生成 3D</button><span id="d3Status${i}" style="font-size:0.6rem;color:var(--text-secondary);margin-top:6px;display:none"></span></div></div></div></div>
  </div>`).join('');
  // 鼠标悬停旋转
  document.querySelectorAll('.d3-card').forEach(card=>{
    card.addEventListener('mouseenter',function(){this.querySelector('.d3-card-inner').style.transform='rotateY(180deg)'});
    card.addEventListener('mouseleave',function(){this.querySelector('.d3-card-inner').style.transform='rotateY(0deg)'});
  });
}
function D3_TMPL_USE(i){
  const t=D3_TEMPLATES[i];if(!t)return;
  document.getElementById('d3TextPrompt').value=t.prompt;
  document.getElementById('d3TextStyle').value='realistic';
  showToast('✅ 已加载「'+t.name+'」提示词，点击"生成3D模型"开始');
  switchPage('3d');
  setTimeout(()=>document.getElementById('d3TextPrompt').scrollIntoView({behavior:'smooth'}),200);
}
// 卡通背面一键生成 3D 模型
async function D3_AUTO_GENERATE(i){
  const t=D3_TEMPLATES[i];if(!t)return;
  if(!spendCredits(12))return;
  const btn=document.querySelectorAll('.d3-card .d3-gen-btn')[i];
  const status=document.getElementById('d3Status'+i);
  btn.textContent='⏳ 提交中...';btn.style.opacity='0.8';status.style.display='none';
  document.getElementById('d3TextPrompt').value=t.prompt;
  try{
    const resp=await fetch(API_BASE+'/api/meshy/txt2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt:t.prompt,style:'realistic'})});
    const data=await resp.json();
    if(data.id||data.result){
      const taskId=data.id||data.result;
      D3_TEMPLATES[i].taskId=taskId;
      btn.textContent='⏳ 生成中...';btn.style.background='#f59e0b';
      status.textContent='任务: '+taskId.substring(0,10)+'... 约5-15分钟';status.style.display='block';
      D3_POLL_PROGRESS(i,taskId,btn,status);
    }else{btn.textContent='❌ 失败';status.textContent=data.error||data.message||'重试';status.style.display='block';setTimeout(()=>{btn.textContent='🎨 一键生成 3D';btn.style.opacity='1';btn.style.background=''},4000)}
  }catch(e){btn.textContent='❌ 网络错误';status.textContent=e.message;status.style.display='block';setTimeout(()=>{btn.textContent='🎨 一键生成 3D';btn.style.opacity='1';btn.style.background=''},4000)}
}
// 轮询 3D 生成进度（每15秒查一次）
async function D3_POLL_PROGRESS(i,taskId,btn,status){
  let done=false;let attempts=0;
  while(!done&&attempts<80){
    await new Promise(r=>setTimeout(r,15000));attempts++;
    try{const r=await fetch(API_BASE+'/api/meshy/result/'+taskId);const d=await r.json();
      if(d.status==='SUCCEEDED'||(d.progress&&d.progress>=100)){
        const url=d.model_urls?.glb||d.preview_url||'';
        D3_TEMPLATES[i].model3d=url;
        btn.textContent='✅ 查看3D';btn.style.background='#10b981';btn.style.cursor='pointer';
        btn.onclick=function(e){e.stopPropagation();
          document.getElementById('d3ModelViewer').style.display='block';
          document.getElementById('d3Viewer').src=url;
          document.getElementById('d3DownloadBtn').onclick=()=>window.open(url,'_blank');
          document.getElementById('d3ModelViewer').scrollIntoView({behavior:'smooth'});
        };
        status.innerHTML='点击查看或<a href="'+url+'" target="_blank" style="color:var(--cyan)">📥 下载</a>';
        done=true;
      }else if(d.status==='FAILED'){btn.textContent='❌ 失败';status.textContent='生成失败';done=true;
      }else{btn.textContent='⏳ '+Math.round(d.progress||0)+'%';status.textContent='预计还需约'+(Math.max(1,Math.ceil((100-(d.progress||0))/8)))+'分钟'}
    }catch(e){}
  }
  if(!done){btn.textContent='⏰ 轮询超时';btn.style.background='';status.textContent='可稍后刷新查看'}
}
// 批量生成全部 10 个 3D 模型
async function D3_BATCH_GENERATE(){
  if(!confirm('将为全部10个角色生成3D模型，共需120积分。继续?'))return;
  if(!spendCredits(120))return;
  showToast('🚀 开始批量生成，请耐心等待...');
  for(let i=0;i<D3_TEMPLATES.length;i++){
    const card=document.querySelectorAll('.d3-card')[i];
    card.querySelector('.d3-card-inner').style.transform='rotateY(180deg)';
    await D3_AUTO_GENERATE(i);
    await new Promise(r=>setTimeout(r,3000)); // 间隔3秒提交下一个
  }
}
setTimeout(()=>{if(document.getElementById('d3Showcase'))D3_RENDER_SHOWCASE()},250);

// ==== PROMPT LIBRARY ====
const PROMPTS=[
  // === 写作 ===
  {cat:'writing',icon:'📝',name:'续写',desc:'根据前文智能续写，保持文风一致',users:12580,prompt:'请续写以下内容，保持一致的文风、人物和语气：\n\n{text}'},
  {cat:'writing',icon:'✨',name:'润色',desc:'提升文笔，优化用词和句式',users:23800,prompt:'请润色以下文本，提升文学性：保留核心内容，优化用词和句式，增强描写。\n\n{text}'},
  {cat:'writing',icon:'🔍',name:'去AI痕迹',desc:'消除机器味，增加人类写作特点',users:18900,prompt:'请消除以下文本的AI痕迹：删除AI高频词、打碎过于工整的句式、增加口语化和不规则表达、偶尔留小瑕疵增加"人味"。\n\n{text}'},
  {cat:'writing',icon:'📈',name:'扩写',desc:'增加细节，扩充内容和字数',users:8760,prompt:'请将以下内容扩写约50%：增加细节描写、丰富心理活动、扩展环境渲染，保持原有风格。\n\n{text}'},
  {cat:'writing',icon:'📉',name:'缩写',desc:'精简内容，保留精华',users:5430,prompt:'请将以下内容缩减约40%：删除冗余但保留精华，保持核心情节和情感不变。\n\n{text}'},
  {cat:'writing',icon:'💎',name:'金句提炼',desc:'从文本中提炼金句和经典语录',users:7420,prompt:'请从以下小说中提炼5-10条具有传播价值的金句，每条标注章节和角色。\n\n{text}'},
  {cat:'writing',icon:'🎭',name:'对话生成',desc:'根据人物性格生成自然对话',users:6310,prompt:'请为以下情节生成一段自然对话：\n人物设定：{chars}\n场景：{scene}\n情节要点：{plot}\n\n要求：对话有潜台词，符合人物性格，推动情节发展。'},
  {cat:'writing',icon:'📄',name:'小说简介',desc:'根据大纲生成吸引人的书简介',users:5120,prompt:'请为以下小说生成200字简介：\n类型：{genre} 大纲：{outline}\n\n要求：抓人眼球、设置悬念、突出看点、展示金手指。'},
  {cat:'writing',icon:'🖌',name:'人工风格改写',desc:'将机器生成的文本改写成自然的人类写作风格',users:4210,prompt:'请将以下机器生成的文本改写成自然的人类写作风格：\n1. 增加语气变化和情感起伏\n2. 使用更口语化和自然的表达\n3. 加入适当的停顿和递进\n4. 删除过于工整的排比和套路化句式\n\n{text}'},
  {cat:'writing',icon:'🔎',name:'抄袭检查',desc:'检查文本原创度，识别重复内容和抄袭风险',users:3890,prompt:'请检查以下文本的原创度：\n1. 标注可能是抄袭或过度借鉴的段落\n2. 指出与常见模板相似的表达\n3. 给出原创度评分（0-100）\n4. 提供改写建议\n\n{text}'},
  // === 小说 ===
  {cat:'novel',icon:'📐',name:'大纲生成',desc:'输入灵感，AI自动生成三层大纲',users:15600,prompt:'请为以下创意生成完整三层大纲（全书纲要→卷纲→章纲）：\n小说类型：{genre}\n核心创意：{idea}\n预计字数：{words}字'},
  {cat:'novel',icon:'📋',name:'细纲生成',desc:'明细到每章情节点的详细大纲',users:9230,prompt:'请为以下章节生成详细纲要：\n全书框架：{frame}\n本章要求：{req}\n\n输出：时间线、场景切换点、关键对话节点、情感弧线。'},
  {cat:'novel',icon:'🔖',name:'书名生成',desc:'生成多个有吸引力的备用书名',users:7890,prompt:'请为以下小说生成5个书名（3-8字），每个附解析：\n类型：{genre} 核心设定：{core}\n\n要求：好记、有意境、有记忆点。'},
  {cat:'novel',icon:'📖',name:'开篇写法',desc:'生成抓人眼球的小说黄金开篇',users:11200,prompt:'请为以下小说生成"黄金三章"：\n类型：{genre} 设定：{settings}\n\n要求：第一章建立悬念、第二章展示金手指、第三章确立故事方向。每章3000字纲要。'},
  {cat:'novel',icon:'👤',name:'角色生成',desc:'AI帮你设计鲜活的人物形象',users:6780,prompt:'请为以下小说设计5-8个核心角色：\n类型：{genre} 世界观：{world}\n\n每个角色包含：姓名、年龄、外貌、性格标签、背景故事、成长弧线、人际关系。'},
  {cat:'novel',icon:'⚔️',name:'金手指设计',desc:'为小说主角设计独特能力系统',users:5430,prompt:'请为{genre}小说设计3个独特的金手指/系统方案：\n\n每个方案包含：名称、能力等级体系、升级条件、限制/代价、成长潜力。要求有创意、不重复市面常见设定。'},
  {cat:'novel',icon:'🗺️',name:'世界观构建',desc:'设计完整的异世界体系',users:4890,prompt:'请为{genre}构建完整世界观：\n\n1. 时代背景 2. 地理/版图 3. 势力分布 4. 力量体系/规则 5. 种族/职业 6. 历史关键事件 7. 社会阶层。'},
  {cat:'novel',icon:'📚',name:'拆书分析',desc:'分析热门网文的成功要素',users:3560,prompt:'请分析以下小说的成功要素：\n书名：{book}\n\n输出：1.核心卖点 2.节奏设计 3.爽点分布 4.人物塑造手法 5.可借鉴的写作技巧。'},
  {cat:'novel',icon:'🎯',name:'爽点设计',desc:'规划全书的高潮与爽点分布',users:4670,prompt:'请为{genre}小说设计爽点分布图：\n\n每卷列出2-3个核心爽点（装逼打脸/逆袭翻盘/扮猪吃虎/宝藏发现/实力突破等），标注触发条件和读者期待值。'},
  {cat:'novel',icon:'🖋',name:'文风模仿',desc:'模仿知名作家的写作风格',users:3120,prompt:'请用{t}的风格重写/仿写以下段落：{text}。'},
  {cat:'novel',icon:'📜',name:'百万字小说创作',desc:'专业级长篇写作系统提示词，支持百万字无缝衔接、去AI痕迹、伏笔管理、五感描写',users:2890,prompt:`[身份设定]
你是一位世界级的小说家，拥有二十年的专业写作经验，擅长所有类型文学，尤其精于构造长篇故事。你的文字拥有强烈的镜头感和情绪张力，能让读者忘记作者的存在，彻底沉浸于故事。你的唯一任务就是根据我提供的全部材料，以最高标准续写小说正文，并确保与前文完全连贯。

[绝对规则]
1. 大纲至上：你必须严格按照我给你的"当前章节大纲"和"整体故事走向"推进剧情，不可私自更改主线事件、重要转折和结局走向。细节可以丰满，但事件节点必须服从大纲。
2. 设定铁律：你须完全遵循我提供的"人物设定""世界观设定""力量体系规则"等一切设定。任何行为、对话、环境描写都不得与前文设定矛盾。若需要引入新设定，必须先呼应用户提供的设定框架，并获得许可。
3. 百万字无缝衔接：你在落笔前，必须深度消化我给出的"前情提要"或"前文关键记忆"，其中包含最近数章的事件、主角当前状态、人物关系变化、已有伏笔和情感基调。写作时必须：
   - 自然承接上一章的结尾，时间、空间、情绪绝对连续。
   - 准确调用已有伏笔，在合适时机暗示或回收，并如同一位真正记住百万字的作者，让一切因果自洽。
   - 人物性格发展须有逐步过渡，若出现重大转变，必须在内心活动或对话中给出符合过往经历的合理动因。
4. 彻底去除AI痕迹：这是最核心的创作要求，你的文风必须如人类顶尖作家一样，完全消除机械感，具体禁止以下所有行为：
   - 禁用模板化开场：不得出现"这是一个关于……的故事""他从未想过，这一天会改变一切"等万能开头或旁白。
   - 禁用AI高频词与句式：避免频繁使用"然而""因此""与此同时""仿佛""似乎""不知为何""他意识到""内心深处"等套话。段落结尾禁止反复使用问句制造悬念。
   - 禁用表情动作套板：禁止"嘴角微微上扬""眼中闪过一丝光芒""眉头紧皱""瞳孔收缩""愣在原地"等过于通用的描写。人物的反应必须独特、符合性格，并用具体细节替代。
   - 禁止直接说明人物性格和情感：不要写"他是一个勇敢而内心柔软的人"，应通过语言、行动、抉择、细节来"展示"，让读者自己感受。
   - 禁止总结性语句：严禁在段尾或章尾进行"人生感悟""升华主题"式的作者旁白。故事的意义由情节本身承载。
   - 对话必须口语化、个性化：不同身份、年龄、性格的人说话方式严格区分，拒绝书面气、说教气、解释性对话。
   - 描写要调动五感：颜色、声音、气味、触感、味道交替出现，细节具体而非堆砌形容词。
   - 句式节奏多变：长短句交错，适时使用短句制造紧张感，长句铺陈氛围，段落长度随情绪起伏。
5. 伏笔与记忆管理：你需要在写作时留意前文伏笔，适时发展或回收。每章结尾，你必须在正文之后，用"【伏笔状态】"标签列出：
   - 已回收的伏笔（简要说明）
   - 本章新埋的伏笔（简要说明）
   - 待后续解决的伏笔清单更新

[输出要求]
- 除非我特别要求，否则你只输出小说正文和伏笔状态，不进行任何多余的解释、评价或客套。
- 正文格式：先给出【章节标题】（如果我未指定，则根据内容自动生成），然后直接开始正文。
- 字数根据我的要求决定，如未指定，每次输出2000-4000字。
`},
  // === 漫剧 ===
  {cat:'media',icon:'🎞',name:'分镜脚本',desc:'将文字转化为漫画分镜',users:4560,prompt:'请将以下内容转为6-8格漫画分镜脚本：\n{text}\n\n格式：格号 | 景别 | 画面描述 | 角色动作 | 对白 | 时长'},
  {cat:'media',icon:'👥',name:'角色外观',desc:'为角色设计可视化外观描述',users:3890,prompt:'请为以下角色设计详细外观（供画师参考）：\n{text}\n\n包含：身高体型、面部特征、发型发色、服装风格、标志性配饰、配色方案。'},
  {cat:'media',icon:'🏞',name:'场景设计',desc:'设计漫画/动画场景描述',users:2340,prompt:'请设计{name}的场景（供画师参考）：\n\n环境色调、光影氛围、空间结构、关键道具、画面构图建议。'},
  {cat:'media',icon:'💬',name:'对白润色',desc:'让角色对话更生动自然',users:3450,prompt:'请润色以下角色对白，使对话更有潜台词和性格色彩：\n{text}'},
  {cat:'media',icon:'🎬',name:'AI 漫剧生成',desc:'将小说转化为竖屏动态漫剧分镜脚本，适配抖快短视频，含景别/画面/对白/音效/时长',users:1980,prompt:`[身份设定]
你是一名资深的漫剧导演兼分镜师，精通将小说文字转化为具有冲击力的动态漫画镜头。你的分镜风格适配抖音、快手等竖屏短视频平台，单集时长控制在1-3分钟，节奏紧凑，爽点密集。你必须完全忠实于原著的故事脉络和人物关系，但可以为了视觉表现力适当丰富细节。
[输入格式]
我会给你一段小说原文（或一整章内容），以及必要的人物外观设定和场景说明。你需要将其转化为完整的漫剧分镜头脚本。

[输出格式]
你必须严格按以下结构输出整集脚本，每个镜头用"---"分隔：
【剧集标题】 （提炼本集亮点，吸引点击）
【本集角色表】 - 角色名：性别/年龄，简明外貌特征，服饰要点
【分镜脚本】
镜头01：景别 | 画面描述 | 对白 | 音效/特效 | 时长
`},
  // === 办公 ===
  {cat:'work',icon:'📄',name:'文章写作',desc:'报告、方案、合同起草',users:8900,prompt:'请写一篇专业文章：{text}\n\n要求：结构清晰、语言专业、可直接使用。'},
  {cat:'work',icon:'📧',name:'邮件起草',desc:'商务/求职/客户邮件',users:7650,prompt:'请写一封专业邮件：{text}\n\n要求：语气得体、格式规范、重点突出。'},
  {cat:'work',icon:'📊',name:'PPT大纲',desc:'结构化演示文稿大纲',users:6540,prompt:'请为以下主题设计PPT大纲：{text}\n\n输出：每页标题+要点+演讲备注。'},
  {cat:'work',icon:'🌐',name:'翻译',desc:'中英日韩多语言互译',users:12300,prompt:'请将以下内容翻译：{text}'},
  {cat:'work',icon:'📋',name:'会议纪要',desc:'自动整理会议重点',users:4320,prompt:'请整理以下会议内容：{text}\n\n输出：讨论主题、关键决策、待办事项、责任人。'},
  {cat:'work',icon:'📝',name:'工作总结',desc:'周报/月报/年终总结',users:5670,prompt:'请根据以下要点生成工作总结：{text}\n\n要求：数据量化、成果突出、下步计划清晰。'},
  {cat:'work',icon:'💻',name:'代码生成',desc:'根据需求生成可直接运行的代码',users:9870,prompt:'请根据以下需求生成代码：{text}\n\n要求：可直接运行、包含注释、指出关键逻辑。语言和框架根据需求自动选择。'},
  {cat:'work',icon:'🐛',name:'代码Debug',desc:'分析错误信息，定位Bug并修复',users:6540,prompt:'请分析以下代码并修复Bug：\n\n错误信息：{err}\n代码：{code}\n\n输出：错误原因分析、修复方案、修复后代码。'},
  {cat:'work',icon:'📖',name:'技术文档',desc:'生成API文档、使用手册、技术方案',users:3210,prompt:'请为以下内容生成技术文档：{text}\n\n格式：概述、环境要求、安装/配置、使用方法、API参考、常见问题。'},
  {cat:'work',icon:'📝',name:'学术论文大纲',desc:'论文结构设计、文献综述框架',users:2980,prompt:'请为以下学术主题设计论文大纲：{text}\n\n包含：研究背景、文献综述、研究方法、预期结果、讨论与结论。每个部分标注核心论点。'},
  {cat:'work',icon:'📊',name:'数据分析报告',desc:'数据解读、趋势分析、可视化建议',users:2340,prompt:'请分析以下数据并生成报告：{text}\n\n包含：核心发现、趋势分析、异常说明、可视化建议、业务建议。'},
  // === 品牌 ===
  {cat:'brand',icon:'🔣',name:'Logo方案',desc:'AI生成Logo创意描述',users:5430,prompt:'请为品牌{text}设计3个Logo方案：\n\n每个方案包含：图形描述、配色方案、字体建议、设计寓意。'},
  {cat:'brand',icon:'✏️',name:'品牌命名',desc:'中英文品牌名称生成',users:4560,prompt:'请为以下业务起10个品牌名（中英文各5个）：{text}\n\n每个名称附含义解析和读音检查。'},
  {cat:'brand',icon:'💬',name:'Slogan',desc:'朗朗上口的品牌口号',users:6780,prompt:'请为品牌{text}创作5条Slogan（不超过12字）：\n\n每条标注适用场景和记忆度评分。'},
  {cat:'brand',icon:'🎨',name:'配色方案',desc:'主色辅色点缀色设计',users:3120,prompt:'请为品牌{text}设计配色方案：\n\n主色/辅色/点缀色 + 色值 + 应用场景 + 情感联想。'},
  {cat:'brand',icon:'📖',name:'品牌故事',desc:'有温度的品牌叙事',users:2890,prompt:'请为品牌{text}创作300字品牌故事：\n\n要求：有温度、有情怀、能引发共鸣。'},
  // === 营销 ===
  {cat:'market',icon:'📕',name:'小红书',desc:'小红书种草笔记',users:12340,prompt:'请为{text}创作小红书种草笔记：\n\n标题（抓眼球）+ 正文（口语化+emoji）+ 话题标签（5-8个）+ 配图建议。'},
  {cat:'market',icon:'💚',name:'公众号',desc:'公众号推文生成',users:9870,prompt:'请为{text}写一篇公众号推文：\n\n标题+摘要+正文(深度有排版)+尾部CTA。'},
  {cat:'market',icon:'📺',name:'广告文案',desc:'多版本投放广告文案',users:7650,prompt:'请为{text}撰写广告文案：\n\n输出3个版本（痛点/情感/数据），每版本含标题+正文+CTA。'},
  {cat:'market',icon:'🔍',name:'SEO优化',desc:'搜索优化内容生成',users:4320,prompt:'请为{text}生成SEO优化内容：\n\n核心关键词(5个) + 长尾词(10个) + Meta描述(3版) + 标题优化建议。'},
  {cat:'market',icon:'🛒',name:'电商详情',desc:'产品详情页文案',users:5430,prompt:'请为{text}写电商详情页文案：\n\n卖点提炼+使用场景+用户痛点+规格参数+售后保障。'},
  {cat:'market',icon:'📱',name:'短视频脚本',desc:'抖音/快手短视频脚本创作',users:8760,prompt:'请创作一个短视频脚本：{text}\n\n包含：开头钩子（3秒）+ 内容主体（15-30秒）+ 引导互动（5秒）+ 画面建议 + 口播文案。'},
  // === 图像 ===
  {cat:'ai-art',icon:'🖼',name:'图片提示词',desc:'优化图片生成提示词',users:10230,prompt:'请将以下创意转化为高质量的图片生成提示词（英文）：\n{text}\n\n包含：主体描述、风格、光照、构图、画质关键词。'},
  {cat:'ai-art',icon:'🎬',name:'视频提示词',desc:'视频生成提示词优化',users:5430,prompt:'请将以下创意转化为视频生成提示词：\n{text}\n\n包含：动态描述、运镜方式、节奏、光影变化、氛围。'},
  {cat:'ai-art',icon:'🎯',name:'风格迁移',desc:'将创意转化为指定风格',users:3210,prompt:'请用{style}风格重新描述以下画面：{text}'},
  {cat:'ai-art',icon:'🎨',name:'AI绘画灵感',desc:'生成多样化的AI绘画创意灵感',users:6540,prompt:'请根据关键词生成5个不同的AI绘画创意：\n关键词：{text}\n\n每个创意包含：画面描述、风格建议、配色方案、构图说明。'},
];
const PROMPT_TEMPLATES={
  '玄幻':{type:'玄幻',style:'爽文流',idea:'废柴逆袭、扮猪吃虎、上古传承'},
  '仙侠':{type:'仙侠',style:'热血战斗',idea:'剑道飞升、因果轮回、道心试炼'},
  '都市':{type:'都市',style:'权谋',idea:'商战、家族恩怨、隐藏身份'},
  '科幻':{type:'科幻',style:'硬核',idea:'星际殖民、AI觉醒、基因改造'},
  '悬疑':{type:'悬疑',style:'推理',idea:'密室杀人、人格分裂、连环案件'},
};
function renderPromptCards(cat='all'){
  const s=document.getElementById('promptSearch')?.value?.toLowerCase()||'';
  let f=PROMPTS;
  if(cat!=='all')f=f.filter(p=>p.cat===cat);
  if(s)f=f.filter(p=>p.name.includes(s)||p.desc.includes(s)||p.cat.includes(s));
  const grid=document.getElementById('promptCardsGrid');const nr=document.getElementById('promptNoResults');
  if(!f.length){grid.innerHTML='';nr.style.display='block';return}
  nr.style.display='none';
  grid.innerHTML=f.map(p=>`<div class="prompt-card" data-cat="${p.cat}">
    <div style="display:flex;align-items:flex-start;gap:10px;margin-bottom:8px"><span style="font-size:1.3rem;margin-top:2px">${p.icon}</span><div style="flex:1"><div style="font-weight:700;font-size:0.9rem">${p.name}</div><div style="font-size:0.7rem;color:var(--text-secondary)">${({'writing':'写作','novel':'小说','media':'漫剧','work':'办公','brand':'品牌','market':'营销','ai-art':'图像'})[p.cat]||p.cat}</div></div><span style="font-size:0.62rem;color:var(--text-secondary);white-space:nowrap;padding:2px 6px;background:var(--accent-soft);border-radius:10px">👥 ${(p.users||0).toLocaleString()}</span></div>
    <p style="font-size:0.8rem;color:var(--text-secondary);line-height:1.5;margin-bottom:8px">${p.desc}</p>
    <button class="prompt-use" onclick="event.stopPropagation();PROMPT_USE('${escapeHtml(p.name)}')">使用</button>
  </div>`).join('')}
function PROMPT_USE(name){
  const p=PROMPTS.find(x=>x.name===name);if(!p)return;
  const catMap={writing:'novel',novel:'novel',media:'media',work:'office',brand:'brand',market:'market','ai-art':'studio'};
  const page=catMap[p.cat]||'chat';
  const promptText=p.prompt.replace(/{text}/g,'[请在此输入内容]').replace(/{genre}/g,'').replace(/{idea}/g,'').replace(/{style}/g,'').replace(/{t}/g,'[目标风格]').replace(/{book}/g,'[书名]');
  switchPage(page);
  setTimeout(()=>{
    if(page==='novel'){NOVEL_START_WIZARD('quick');document.getElementById('wizCore').value=promptText}
    else if(page==='office'){document.getElementById('officeInput').value=promptText;document.getElementById('officeInput').focus()}
    else if(page==='brand'){document.getElementById('brandInput').value=promptText;document.getElementById('brandInput').focus()}
    else if(page==='market'){document.getElementById('marketInput').value=promptText;document.getElementById('marketInput').focus()}
    else if(page==='studio'){document.getElementById('stuPrompt').value=promptText;STUDIO_BUILD_PROMPT()}
    else if(page==='media'){document.getElementById('mediaInput').value=promptText;document.getElementById('mediaInput').focus()}
    else{document.getElementById('chatInput').value=promptText;document.getElementById('chatInput').focus()}
    showToast(`已加载「${name}」工具`)
  },300)
}
function filterPromptCards(){renderPromptCards(document.querySelector('#page-prompts .filter-tag.active')?.dataset?.pcat||'all')}
function filterPromptByCat(cat,el){document.querySelectorAll('#page-prompts .filter-tag[data-pcat]').forEach(x=>x.classList.remove('active'));el.classList.add('active');renderPromptCards(cat)}
function scrollToCategory(cat){document.querySelector('#page-prompts .filter-tag[data-pcat="'+cat+'"]')?.click();setTimeout(()=>{const g=document.getElementById('promptCardsGrid');g.scrollIntoView({behavior:'smooth'})},100)}

// ==== KNOWLEDGE BASE ====
let KNOWLEDGE_ITEMS=JSON.parse(localStorage.getItem('knowledge')||'[]');
let KNOWLEDGE_FOLDER='all';
function KNOWLEDGE_SELECT_FOLDER(name,el){
  KNOWLEDGE_FOLDER=name;
  document.querySelectorAll('.know-folder').forEach(x=>x.classList.remove('active'));el.classList.add('active');
  document.getElementById('knowledgeCurrentFolder').textContent='📁 '+(name==='all'?'全部':({'settings':'故事设定','notes':'创作笔记','outline':'故事大纲','chapters':'章节纲要','chars':'人物设定','brand':'品牌资料','other':'其他'})[name]||name);
  renderKnowledgeCards()
}
function renderKnowledgeCards(){
  let items=KNOWLEDGE_ITEMS;const s=document.getElementById('knowSearch')?.value?.toLowerCase()||'';
  if(KNOWLEDGE_FOLDER!=='all')items=items.filter(i=>i.folder===KNOWLEDGE_FOLDER);
  if(s)items=items.filter(i=>i.title.toLowerCase().includes(s)||i.content.toLowerCase().includes(s)||(i.tags||'').toLowerCase().includes(s));
  const grid=document.getElementById('knowledgeCardGrid');
  document.getElementById('knowledgeStats').textContent=items.length+' 个知识点';
  if(!items.length){grid.innerHTML='<div style="grid-column:1/-1;text-align:center;color:var(--text-secondary);padding:60px"><div style="font-size:3rem">📭</div><p>还没有知识点</p><button class="btn-sm primary" style="margin-top:10px" onclick="KNOWLEDGE_ADD()">新建知识点</button></div>';return}
  grid.innerHTML=items.map((k,i)=>{
    const idx=KNOWLEDGE_ITEMS.indexOf(k);
    const tags=(k.tags||'').split(',').filter(Boolean);
    const preview=k.content.substring(0,120);
    return `<div class="know-card" onclick="KNOWLEDGE_EDIT(${idx})">
      <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:8px">
        <div style="font-weight:700;font-size:0.85rem">${escapeHtml(k.title)}</div>
        <span style="font-size:0.68rem;color:var(--text-secondary)">${new Date(k.time).toLocaleDateString('zh-CN')}</span>
      </div>
      <div style="font-size:0.78rem;color:var(--text-secondary);line-height:1.5;margin-bottom:6px">${escapeHtml(preview)}${k.content.length>120?'...':''}</div>
      ${tags.length?`<div class="know-tags">${tags.map(t=>`<span class="know-tag">${t.trim()}</span>`).join('')}</div>`:''}
    </div>`;
  }).join('')}
function KNOWLEDGE_ADD(){document.getElementById('knowModalTitle').textContent='新建知识';document.getElementById('knowTitle').value='';document.getElementById('knowContent').value='';document.getElementById('knowTags').value='';document.getElementById('knowEditId').value='';document.getElementById('knowDeleteBtn').style.display='none';document.getElementById('knowModal').classList.add('show')}
function KNOWLEDGE_EDIT(idx){const k=KNOWLEDGE_ITEMS[idx];if(!k)return;document.getElementById('knowModalTitle').textContent='编辑知识';document.getElementById('knowTitle').value=k.title;document.getElementById('knowFolder').value=k.folder;document.getElementById('knowContent').value=k.content;document.getElementById('knowTags').value=k.tags||'';document.getElementById('knowEditId').value=idx;document.getElementById('knowDeleteBtn').style.display='inline-block';document.getElementById('knowModal').classList.add('show')}
function KNOWLEDGE_SAVE(){
  const title=document.getElementById('knowTitle').value.trim(),folder=document.getElementById('knowFolder').value,content=document.getElementById('knowContent').value.trim(),tags=document.getElementById('knowTags').value.trim(),editId=document.getElementById('knowEditId').value;
  if(!title||!content){showToast('标题和内容必填');return}
  const item={title,folder,content,tags,time:new Date().toISOString()};
  if(editId!==''){KNOWLEDGE_ITEMS[parseInt(editId)]=item}else{KNOWLEDGE_ITEMS.unshift(item)}
  KNOWLEDGE_ITEMS=KNOWLEDGE_ITEMS.slice(0,100);localStorage.setItem('knowledge',JSON.stringify(KNOWLEDGE_ITEMS));
  document.getElementById('knowModal').classList.remove('show');renderKnowledgeCards();showToast(editId!==''?'已更新':'已创建')
}
function KNOWLEDGE_DELETE(){const editId=document.getElementById('knowEditId').value;if(editId===''||!confirm('确定删除？'))return;KNOWLEDGE_ITEMS.splice(parseInt(editId),1);localStorage.setItem('knowledge',JSON.stringify(KNOWLEDGE_ITEMS));document.getElementById('knowModal').classList.remove('show');renderKnowledgeCards();showToast('已删除')}
function KNOWLEDGE_SEARCH(){renderKnowledgeCards()}
function renderKnowledgeTree(){renderKnowledgeCards()}

// === Patch old novel functions ===
const _origSwitchNovelTab=switchNovelTab;
switchNovelTab=function(){/* deprecated: using wizard system */};
const _origWizardAction=wizardAction;
wizardAction=function(){/* use NOVEL_STEP_6_WRITE instead */};
const _origRefineText=refineText;
refineText=function(mode){NOVEL_REFINE(mode)};
const _origExecuteRefine=executeRefine;
executeRefine=function(){NOVEL_REFINE_EXEC()};

function toggleMobileMenu(){const m=document.getElementById('mobileMenu');m.style.display=m.style.display==='none'||!m.style.display?'block':'none'}
if(currentUser){userCredits=parseInt(localStorage.getItem('cr_'+currentUser.username)||'30');localStorage.setItem('cr',userCredits);novelHistory=localStorage.getItem('novelHistory')||''}
// 设备自动登录：如果本设备已有绑定账号，直接登录
if(!currentUser){
  const boundUser=getDeviceBoundUser();
  if(boundUser){
    currentUser={username:boundUser.username,email:boundUser.email||'',phone:boundUser.phone||''};
    localStorage.setItem('cuser',JSON.stringify(currentUser));
    userCredits=parseInt(localStorage.getItem('cr_'+boundUser.username)||'30');
    localStorage.setItem('cr',userCredits);
    setTimeout(()=>showToast(`👋 欢迎回来，${boundUser.username}！设备已自动登录`),1500);
  }
}
updateCreditDisplay();
renderUserNav();
initAdmin();
// 安全校验：如果模型列表异常少（<10个），清除本地缓存重建
if(models.length<10 && localStorage.getItem(MODELS_STORAGE_KEY)){
  console.warn('[TriGen] 检测到模型列表异常（仅'+models.length+'个），清除缓存重建');
  localStorage.removeItem(MODELS_STORAGE_KEY);
  initAdmin(); // 重新初始化
}
// 支持 ?reset-models 参数强制重建模型列表
if(location.search.includes('reset-models')){
  localStorage.removeItem(MODELS_STORAGE_KEY);
  console.log('[TriGen] 已强制重建模型列表');
  setTimeout(()=>location.href=location.pathname,100);
}
updateStreakUI();
setTimeout(renderContinue,500);
// First visit welcome
if(!localStorage.getItem('visited')){
  setTimeout(()=>{
    const c=parseInt(localStorage.getItem('cr')||'30');
    if(c>0)showToast(`🎉 欢迎！已赠送您 ${c} 积分免费体验额度`);
    localStorage.setItem('visited','1');
  },800);
}

// ==== 🔧 TOOLS MODULE ====
async function TOOLS_VIDEO_DOWNLOAD(){
  const url=document.getElementById('toolsVideoUrl').value.trim();
  const r=document.getElementById('toolsVideoResult');
  if(!url){showToast('请粘贴视频链接');return}
  r.style.display='block';r.innerHTML='<span class="spinner"></span> 正在解析...';
  try{
    // 使用免费 API 解析视频
    const apiUrl=`https://api.0x3.uk/douyin?url=${encodeURIComponent(url)}`;
    const resp=await fetch(apiUrl);
    const data=await resp.json();
    if(data&&data.video_url){
      r.innerHTML=`<div style="text-align:center"><a href="${data.video_url}" target="_blank" class="btn-sm primary" download>💾 点击下载无水印视频</a><p style="font-size:0.7rem;color:var(--text-secondary);margin-top:6px">如无法下载，请右键链接选择"另存为"</p></div>`;
    } else {
      r.innerHTML=`<p style="font-size:0.8rem;color:var(--orange)">⚠️ 无法解析该链接，请确认链接有效</p><p style="font-size:0.7rem;color:var(--text-secondary);margin-top:4px">目前支持：抖音 / 快手 / 小红书 / 微博</p>`;
    }
  }catch(e){r.innerHTML=`<p style="font-size:0.8rem;color:var(--orange)">❌ 解析失败：${e.message}</p><p style="font-size:0.7rem;color:var(--text-secondary);margin-top:4px">请检查网络或稍后重试</p>`}
}
async function TOOLS_MERGE(){
  const files=document.getElementById('toolsMergeInput').files;
  const dir=document.getElementById('toolsMergeDir').value;
  const r=document.getElementById('toolsMergeResult');
  if(files.length<2){showToast('请选择至少2张图片');return}
  r.style.display='block';document.getElementById('toolsMergeImg').style.display='none';
  try{
    const imgs=await Promise.all(Array.from(files).map(f=>new Promise((res,rej)=>{const img=new Image();img.onload=()=>res(img);img.onerror=rej;img.src=URL.createObjectURL(f)})));
    const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
    if(dir==='horizontal'){
      const tw=imgs.reduce((s,img)=>s+img.width,0),th=Math.max(...imgs.map(img=>img.height));
      canvas.width=tw;canvas.height=th;let x=0;
      imgs.forEach(img=>{ctx.drawImage(img,x,0);x+=img.width});
    }else{
      const tw=Math.max(...imgs.map(img=>img.width)),th=imgs.reduce((s,img)=>s+img.height,0);
      canvas.width=tw;canvas.height=th;let y=0;
      imgs.forEach(img=>{ctx.drawImage(img,0,y);y+=img.height});
    }
    document.getElementById('toolsMergeImg').src=canvas.toDataURL('image/png');
    document.getElementById('toolsMergeImg').style.display='block';
  }catch(e){showToast('拼接失败：'+e.message)}
}
async function TOOLS_COMPRESS(){
  const file=document.getElementById('toolsCompressInput').files[0];
  const q=parseInt(document.getElementById('toolsCompressQuality').value)/100;
  const r=document.getElementById('toolsCompressResult');
  if(!file){showToast('请选择图片');return}
  r.style.display='block';
  document.getElementById('toolsCompressOrigSize').textContent=(file.size/1024).toFixed(1)+'KB';
  try{
    const img=await new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=rej;i.src=URL.createObjectURL(file)});
    const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
    canvas.width=img.width;canvas.height=img.height;
    ctx.drawImage(img,0,0);
    canvas.toBlob(blob=>{
      document.getElementById('toolsCompressImg').src=URL.createObjectURL(blob);
      document.getElementById('toolsCompressNewSize').textContent=(blob.size/1024).toFixed(1)+'KB';
      window._toolsCompressBlob=blob;
    },'image/jpeg',q);
  }catch(e){showToast('压缩失败：'+e.message)}
}
// 图片取色器
let toolsColorLoaded=false;
document.getElementById('toolsColorInput')?.addEventListener('change',function(){
  const f=this.files[0];if(!f)return;
  const canvas=document.getElementById('toolsColorCanvas');
  const ctx=canvas.getContext('2d');
  const img=new Image();img.onload=()=>{
    canvas.style.display='block';
    const maxW=400;let w=img.width,h=img.height;
    if(w>maxW){h=h*maxW/w;w=maxW}
    canvas.width=w;canvas.height=h;
    ctx.drawImage(img,0,0,w,h);
    toolsColorLoaded=true;
  };img.src=URL.createObjectURL(f);
});
document.getElementById('toolsColorCanvas')?.addEventListener('click',function(e){
  if(!toolsColorLoaded)return;
  const rect=this.getBoundingClientRect(),x=e.clientX-rect.left,y=e.clientY-rect.top;
  const ctx=this.getContext('2d'),pixel=ctx.getImageData(x,y,1,1).data;
  const hex='#'+[pixel[0],pixel[1],pixel[2]].map(v=>v.toString(16).padStart(2,'0')).join('');
  const rgb=`rgb(${pixel[0]},${pixel[1]},${pixel[2]})`;
  document.getElementById('toolsColorPreview').style.backgroundColor=hex;
  document.getElementById('toolsColorHex').textContent=hex;
  document.getElementById('toolsColorRgb').textContent=rgb;
  document.getElementById('toolsColorInfo').style.display='block';
});
function TOOLS_SOLID(){
  const color=document.getElementById('toolsSolidColor').value;
  const w=parseInt(document.getElementById('toolsSolidWidth').value)||1920;
  const h=parseInt(document.getElementById('toolsSolidHeight').value)||1080;
  const r=document.getElementById('toolsSolidResult');
  const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
  canvas.width=w;canvas.height=h;
  ctx.fillStyle=color;ctx.fillRect(0,0,w,h);
  document.getElementById('toolsSolidImg').src=canvas.toDataURL('image/png');
  r.style.display='block';
}
function TOOLS_DOWNLOAD(imgId,name){
  const img=document.getElementById(imgId);
  if(!img||!img.src)return;
  const a=document.createElement('a');a.href=img.src;a.download=name;a.click();
  showToast('已开始下载')
}
// LSB 隐写
function TOOLS_STEGA_ENCODE(){
  const file=document.getElementById('toolsStegaInput').files[0];
  const text=document.getElementById('toolsStegaText').value.trim();
  const r=document.getElementById('toolsStegaResult');
  if(!file){showToast('请选择图片');return}
  if(!text){showToast('请输入要隐藏的秘密文本');return}
  r.style.display='block';r.innerHTML='<span class="spinner"></span> 正在编码...';
  const reader=new FileReader();
  reader.onload=function(e){
    const img=new Image();
    img.onload=function(){
      const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
      canvas.width=img.width;canvas.height=img.height;
      ctx.drawImage(img,0,0);
      const imageData=ctx.getImageData(0,0,canvas.width,canvas.height),data=imageData.data;
      const binary=text.split('').map(c=>c.charCodeAt(0).toString(2).padStart(8,'0')).join('')+'00000000';
      if(binary.length>data.length){r.innerHTML='<p style="color:var(--orange)">⚠️ 文本过长，请用更大的图片</p>';return}
      for(let i=0;i<binary.length;i++)data[i]=(data[i]&254)|parseInt(binary[i]);
      ctx.putImageData(imageData,0,0);
      const out=document.createElement('a');
      out.href=canvas.toDataURL('image/png');
      out.download='stego_encoded.png';
      out.click();
      r.innerHTML='<p style="color:var(--green)">✅ 已编码完成！隐写图已下载</p>';
    };
    img.src=e.target.result;
  };
  reader.readAsDataURL(file);
}
function TOOLS_STEGA_DECODE(){
  const file=document.getElementById('toolsStegaInput').files[0];
  const r=document.getElementById('toolsStegaResult');
  if(!file){showToast('请选择图片');return}
  r.style.display='block';r.innerHTML='<span class="spinner"></span> 正在解码...';
  const reader=new FileReader();
  reader.onload=function(e){
    const img=new Image();
    img.onload=function(){
      const canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
      canvas.width=img.width;canvas.height=img.height;
      ctx.drawImage(img,0,0);
      const imageData=ctx.getImageData(0,0,canvas.width,canvas.height),data=imageData.data;
      let binary='',chars=[];
      for(let i=0;i<Math.min(data.length,80000);i++){binary+=data[i]&1;if(binary.length===8){const code=parseInt(binary,2);if(code===0)break;chars.push(String.fromCharCode(code));binary=''}}
      const decoded=chars.join('');
      if(decoded)r.innerHTML=`<p style="color:var(--green);margin-bottom:4px">✅ 提取成功</p><div style="background:var(--bg-card);padding:10px;border-radius:8px;font-size:0.82rem">${escapeHtml(decoded)}</div>`;
      else r.innerHTML='<p style="color:var(--orange);">⚠️ 未检测到隐藏信息</p>';
    };
    img.src=e.target.result;
  };
  reader.readAsDataURL(file);
}

