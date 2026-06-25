'use strict';
// ==== 🧊 3D MODULE ====
function D3_SAVE_KEY(){
  const key=document.getElementById('d3ApiKey').value.trim();
  if(!key){showToast('请输入 API Key');return}
  localStorage.setItem('meshy_api_key',key);
  showToast('✅ Meshy API Key 已保存（本地存储）');
}
async function D3_TEXT_TO_3D(){
  const prompt=document.getElementById('d3TextPrompt').value.trim();
  const style=document.getElementById('d3TextStyle').value;
  const r=document.getElementById('d3TextResult');
  if(!prompt){showToast('请输入3D描述');return}
  if(!spendCredits(12))return;
  r.style.display='block';
  r.innerHTML='<span class="spinner"></span> 正在提交 3D 模型...<p style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px">生成需要5-15分钟，自动等待中…</p>';
  try{
    const resp=await fetch(API_BASE+'/api/meshy/txt2d',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,style})});
    const data=await resp.json();
    if(data.id||data.result){
      const taskId=data.id||data.result;
      r.innerHTML=`<div style="text-align:center"><div style="font-size:2rem">⏳</div><p>生成中...</p><p id="d3Progress" style="font-size:0.75rem;color:var(--text-secondary)">初始化中</p></div>`;
      D3_POLL_VIEWER(taskId,r);
    }else{r.innerHTML=`<p style="color:var(--orange)">⚠️ ${data.message||data.error||'提交失败，请稍后重试'}</p>`}
  }catch(e){r.innerHTML=`<p style="color:var(--orange)">❌ 连接失败：${e.message}</p>`}
}
// 轮询进度并自动显示 3D 查看器
async function D3_POLL_VIEWER(taskId,r){
  let done=false,attempts=0;
  while(!done&&attempts<80){await new Promise(x=>setTimeout(x,15000));attempts++;
    try{const resp=await fetch(API_BASE+'/api/meshy/result/'+taskId);const d=await resp.json();
      const pg=document.getElementById('d3Progress');if(pg)pg.textContent='进度 '+Math.round(d.progress||0)+'% · 约'+(Math.max(1,Math.ceil((100-(d.progress||0))/8)))+'分钟';
      if(d.status==='SUCCEEDED'||(d.progress&&d.progress>=100)){
        const url=d.model_urls?.glb||'';
        if(url){
          r.style.display='none';
          const v=document.getElementById('d3ModelViewer');v.style.display='block';
          document.getElementById('d3Viewer').src=url;
          document.getElementById('d3DownloadBtn').onclick=()=>window.open(url,'_blank');
          v.scrollIntoView({behavior:'smooth'});
          showToast('✅ 3D模型生成完成！');
        }else{r.innerHTML='<p style="color:var(--green)">✅ 生成完成，正在加载模型...</p>'}
        done=true;
      }else if(d.status==='FAILED'){r.innerHTML='<p style="color:var(--orange)">❌ 生成失败，请重试</p>';done=true}
    }catch(e){}
  }
  if(!done)r.innerHTML='<p style="color:var(--orange)">⏰ 轮询超时，请稍后手动刷新</p>';
}

// 3D 控制面板函数
function d3ViewerScale(v){
  const vw=document.getElementById('d3Viewer');
  vw.cameraOrbit && (vw.cameraOrbit='0deg 75deg '+v+'m');
}
function d3ViewerBg(c){
  document.getElementById('d3Viewer').style.background=c;
}

async function D3_IMAGE_TO_3D(){
  const file=document.getElementById('d3ImageInput').files[0];
  const r=document.getElementById('d3ImageResult');
  if(!file){showToast('请选择参考图片');return}
  if(!spendCredits(12))return;
  r.style.display='block';
  r.innerHTML='<span class="spinner"></span> 正在上传图片并提交 3D 模型...<p style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px">生成需要5-15分钟，自动等待中…</p>';
  try{
    // 将图片转为 base64
    const imgData = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result);
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
    const resp = await fetch(API_BASE + '/api/meshy/img2d', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_data: imgData, prompt: document.getElementById('d3TextPrompt').value.trim() })
    });
    const data = await resp.json();
    if(data.id || data.result){
      const taskId = data.id || data.result;
      r.innerHTML = `<div style="text-align:center"><div style="font-size:2rem">⏳</div><p>图生3D 生成中...</p><p id="d3ProgressImg" style="font-size:0.75rem;color:var(--text-secondary)">初始化中</p></div>`;
      D3_POLL_VIEWER(taskId, r);
    } else {
      r.innerHTML = `<p style="color:var(--orange)">⚠️ ${data.message || data.error || '提交失败，请稍后重试'}</p>`;
    }
  }catch(e){
    r.innerHTML = `<p style="color:var(--orange)">❌ 连接失败：${e.message}</p>`;
  }
}
function D3_TOGGLE_FAQ(el){
  const answer=el.querySelector('.d3FaqAnswer');
  if(answer)answer.style.display=answer.style.display==='none'?'block':'none';
}
// 图片预览
document.getElementById('d3ImageInput')?.addEventListener('change',function(){
  const f=this.files[0];if(!f)return;
  const p=document.getElementById('d3ImagePreview');
  const img=new Image();
  img.onload=()=>{p.innerHTML='';p.appendChild(img);img.style.maxWidth='100%';img.style.maxHeight='100%';img.style.borderRadius='6px';img.style.objectFit='contain'};
  img.src=URL.createObjectURL(f);
});

