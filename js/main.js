'use strict';
// ==== 🤖 统一模型选择器 + 智能推荐模块 ====
const PAGE_MODEL_RECOMMEND={
  novel:{id:'deepseekv3',name:'DeepSeek V3',reason:'长文本创作最佳，支持百万字上下文'},
  media:{id:'dmx_qwen3_max_free',name:'Qwen3 Max',reason:'中文理解力强，适合分镜脚本'},
  brand:{id:'deepseekv3',name:'DeepSeek V3',reason:'创意文案生成最佳'},
  market:{id:'ali_kimi_k26',name:'Kimi K2.6',reason:'社交媒体文案擅长'},
  office:{id:'deepseekv3',name:'DeepSeek V3',reason:'办公文件处理最优'},
  agents:{id:'deepseekr1',name:'DeepSeek R1',reason:'复杂推理任务首选'},
  studio:{id:'dmx_qwen3_max_free',name:'Qwen3 Max',reason:'生成任务最好配合'},
  music:{id:'deepseekv3',name:'DeepSeek V3',reason:'歌词创作最擅长'},
  d3:{id:'meshy_text',name:'Meshy 3D',reason:'3D模型生成最优',filter:'3d'},
};
function renderModelBar(pageId,containerId){
  const rec=PAGE_MODEL_RECOMMEND[pageId];
  const el=document.getElementById(containerId);
  if(!el||!rec)return;
  const saved=localStorage.getItem('pageModel_'+pageId)||rec.id;
  const allModels=rec.filter
    ? models.filter(m=>!m.hidden&&m.tags&&m.tags.includes(rec.filter))
    : models.filter(m=>!m.hidden);
  if(allModels.length<3){allModels.length=0;models.filter(m=>!m.hidden).forEach(x=>allModels.push(x))}
  var opts='';
  for(var i=0;i<allModels.length;i++){
    var m=allModels[i],c=getModelCost(m.id),sel=m.id===saved?' selected':'';
    var label=c===0?' [免费]':' ['+c+'积分]';
    opts+='<option value="'+m.id+'"'+sel+'>'+m.name+label+'</option>';
  }
  el.innerHTML=`
    <div class="feature-card" style="padding:8px 14px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:6px;margin-bottom:12px;background:linear-gradient(135deg,rgba(124,58,237,0.05),rgba(99,102,241,0.05))">
      <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
        <span style="font-size:0.75rem;font-weight:600;">🤖 模型选择</span>
        <select id="selPm_${pageId}" style="padding:5px 8px;border-radius:6px;border:1px solid var(--border);background:var(--bg-input);color:var(--accent);font-size:0.75rem;font-weight:600;cursor:pointer;max-width:260px" onchange="PAGE_MODEL_CHANGE('${pageId}',this.value)">${opts}</select>
        <span style="font-size:0.65rem;padding:2px 8px;background:rgba(245,158,11,0.15);color:#f59e0b;border-radius:10px;font-weight:600">✨ 推荐 ${rec.name}</span>
      </div>
      <div style="display:flex;align-items:center;gap:6px">
        <span id="pm_reason_${pageId}" style="font-size:0.65rem;color:var(--text-secondary)">💡 ${rec.reason}</span>
      </div>
    </div>
  `;
}
function PAGE_MODEL_CHANGE(pageId,val){
  localStorage.setItem('pageModel_'+pageId,val);
  showToast(`✅ ${pageId} 模型已切换`);
}
function getPageModel(pageId){
  const rec=PAGE_MODEL_RECOMMEND[pageId];
  if(!rec)return null;
  return localStorage.getItem('pageModel_'+pageId)||rec.id;
}
const PAGE_MODEL_RECOMMEND_OPTIONS=[
  {id:'deepseekv3',name:'DeepSeek V3'},{id:'deepseekr1',name:'DeepSeek R1'},
  {id:'gpt4o',name:'GPT-4o'},{id:'gemini25pro',name:'Gemini 2.5 Pro'},
  {id:'kimi2',name:'Kimi K2'},{id:'glm4plus',name:'GLM-4 Plus'},
  {id:'hunyuan',name:'腾讯混元'},{id:'ali_qwen37_max',name:'Qwen 3.7 Max（百炼）'},
  {id:'ark_dsv4p',name:'DeepSeek V4 Pro（火山免费）'},
  {id:'ark_dsv32',name:'DeepSeek V3.2（火山免费）'},
  {id:'sf_qwen35_397b',name:'Qwen 3.5 397B（硅基）'},
  {id:'ark_dbs2_pro',name:'豆包 Seed 2.0 Pro（火山）'},
  {id:'ali_kimi_k26',name:'Kimi K2.6（百炼）'},
  {id:'ark_glm47',name:'GLM-4.7（火山）'},
  {id:'nx_claude_sonnet',name:'Claude Sonnet 4.6'},
  {id:'nx_gpt5mini',name:'GPT-5 Mini'},
  {id:'nx_gemini_pro',name:'Gemini 2.5 Pro（Nexus）'},
];
