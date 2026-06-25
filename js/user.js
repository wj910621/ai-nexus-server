'use strict';
// === Credits ===
let userCredits=30,usedTokensCount=parseInt(localStorage.getItem('utk')||'0'),usedImagesCount=parseInt(localStorage.getItem('uim')||'0');
let guestProgressiveStatus='normal';
// 积分初始化：登录用户从服务器获取，访客从后端同步
(async function initCredits(){
  if(authToken){
    try{const r=await fetch(API_BASE+'/api/user/credits',{headers:getAuthHeader()});if(r.ok){const d=await r.json();if(d.credits!==undefined){userCredits=d.credits;localStorage.setItem('cr',userCredits);updateCreditDisplay()}}}catch(e){}
  }else{
    // 访客：从后端同步积分（防刷新重置）
    try{
      const fp=getDeviceFingerprint();
      const r=await fetch(API_BASE+'/api/guest/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({deviceFp:fp})});
      if(r.ok){const d=await r.json();if(d.credits!==undefined){userCredits=d.credits;guestProgressiveStatus=d.progressiveStatus||'normal';localStorage.setItem('cr',userCredits);updateCreditDisplay();if(d.progressiveStatus==='blocked')showGuestBlockedModal(d.used,d.max)}}
    }catch(e){/* 离线回退到本地存储 */userCredits=parseInt(localStorage.getItem('cr')||'30')}
  }
})();
function updateCreditDisplay(){const e=document.getElementById('creditDisplay');if(e){e.textContent=userCredits;if(userCredits<=5){e.style.color='#ef4444';e.parentElement.parentElement.title='积分即将用完';e.style.animation='pulse 1.5s infinite'}else{e.style.color='';e.style.animation=''}}const b=document.getElementById('creditBalance');if(b)b.textContent=userCredits}
async function refreshUserCredits(){
  if(authToken){
    try{const r=await fetch(API_BASE+'/api/user/credits',{headers:getAuthHeader()});if(r.ok){const d=await r.json();if(d.credits!==undefined){userCredits=d.credits;localStorage.setItem('cr',userCredits);updateCreditDisplay()}}}catch(e){}
  }
}
function showLowCreditHint(){if(userCredits>0&&userCredits<=5&&!document.getElementById('lowCreditHint')){const hint=document.createElement('div');hint.id='lowCreditHint';hint.style='position:fixed;top:70px;right:20px;z-index:400;background:rgba(239,68,68,0.1);border:1px solid rgba(239,68,68,0.3);border-radius:12px;padding:10px 16px;font-size:0.78rem;max-width:220px;animation:fadeIn 0.5s';hint.innerHTML='💡 <b>积分即将用完</b><br><span style="font-size:0.7rem;color:var(--text-secondary)">充值最低 ¥9.9 起 · GPT-4o 官方 ¥145/月</span><div style="margin-top:6px"><button class="btn-send" style="font-size:0.7rem;padding:3px 12px;background:linear-gradient(135deg,#f59e0b,#d97706)" onclick="switchPage(\'pricing\');hint.remove()">充值</button><button style="font-size:0.7rem;padding:3px 8px;background:none;border:none;color:var(--text-secondary);cursor:pointer;margin-left:4px" onclick="hint.remove()">✕</button></div>';document.body.appendChild(hint);setTimeout(()=>{if(hint.parentNode)hint.remove()},15000)}}
function spendCredits(a,t){
// 管理员不扣积分
if(authToken){try{const p=JSON.parse(atob(authToken));if(p.role==='admin')return true}catch(e){}}
if(userCredits<a){const f=document.getElementById('creditLow');if(f){f.querySelector('span').textContent=a;document.getElementById('creditLowBal').textContent=userCredits;f.style.display='flex'};return false}
// 访客渐进式检查
if(!authToken&&guestProgressiveStatus==='blocked'){
  showGuestBlockedModal();
  return false;
}
userCredits-=a;localStorage.setItem('cr',userCredits);updateCreditDisplay();if(t)showToast(`-${a}积分，剩余${userCredits}`);if(userCredits<=5)showLowCreditHint();
// 同步到服务器
if(authToken){
  fetch(API_BASE+'/api/user/spend',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+authToken},body:JSON.stringify({amount:a})}).catch(()=>{})
}else if(deviceFp&&deviceFp.length>8){
  // 访客积分同步到后端
  fetch(API_BASE+'/api/guest/spend',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({deviceFp,amount:a})})
    .then(r=>r.json()).then(d=>{
      if(d.ok&&d.progressiveStatus){guestProgressiveStatus=d.progressiveStatus}
      if(d.progressiveStatus==='suggest_register'){
        if(!document.getElementById('guestRegHint')){
          const h=document.createElement('div');h.id='guestRegHint';
          h.style='position:fixed;bottom:80px;right:20px;z-index:400;background:var(--bg-card);border:1px solid var(--accent);border-radius:12px;padding:12px 16px;font-size:0.78rem;max-width:240px;box-shadow:var(--shadow-lg);animation:fadeIn 0.5s';
          h.innerHTML='💡 <b>注册可获更多积分</b><br><span style="font-size:0.7rem;color:var(--text-secondary)">免费注册即送额外积分，解锁全部功能</span><div style="margin-top:8px"><button class="btn-sm primary" onclick="showRegisterModal();document.getElementById(\'guestRegHint\')?.remove()">立即注册</button><button style="font-size:0.7rem;padding:2px 6px;background:none;border:none;color:var(--text-secondary);cursor:pointer;margin-left:4px" onclick="document.getElementById(\'guestRegHint\')?.remove()">✕</button></div>';
          document.body.appendChild(h);
          setTimeout(()=>{document.getElementById('guestRegHint')?.remove()},20000);
        }
      }else if(d.progressiveStatus==='must_register'){
        showGuestBlockedModal(d.used||30,d.max||30);
      }else if(d.progressiveStatus==='blocked'){
        showGuestBlockedModal(d.used||30,d.max||30);
      }
    }).catch(()=>{});
}
return true}

function showGuestBlockedModal(used,max){
  const m=document.getElementById('guestRegModal');if(m){m.style.display='flex';return}
  const modal=document.createElement('div');modal.id='guestRegModal';
  modal.style='position:fixed;top:0;left:0;right:0;bottom:0;z-index:1000;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;backdrop-filter:blur(4px);animation:fadeIn 0.3s';
  modal.innerHTML=`
    <div style="background:var(--bg-card);border:1px solid var(--accent);border-radius:16px;padding:32px;max-width:400px;width:90%;text-align:center;box-shadow:var(--shadow-lg)">
      <div style="font-size:3rem;margin-bottom:12px">🔒</div>
      <h3 style="margin-bottom:8px;color:var(--text)">今日访客积分已用完</h3>
      <p style="font-size:0.85rem;color:var(--text-secondary);margin-bottom:4px">今日已使用 ${used||30}/${max||30} 积分</p>
      <p style="font-size:0.8rem;color:var(--text-secondary);margin-bottom:20px">注册账号即可继续使用！注册即送 30 积分</p>
      <button class="cta-btn" style="width:100%;justify-content:center;margin-bottom:8px" onclick="showRegisterModal();document.getElementById('guestRegModal')?.remove()">📝 免费注册</button>
      <button style="font-size:0.8rem;padding:8px 20px;background:none;border:1px solid var(--border);border-radius:8px;color:var(--text-secondary);cursor:pointer;width:100%" onclick="document.getElementById('guestRegModal')?.remove()">稍后再说</button>
    </div>`;
  document.body.appendChild(modal);
}

// === 模型积分分级 ===
const MODEL_COST={
  // 🆓 免费模型（对应平台免费供应）
  dmx_qwen35_2b_free:0, dmx_qwen3_17b_free:0, dmx_spark_lite_free:0,
  sf_qwen3_8b:0, sf_deepseek_v3_free:0, dmx_qwen3_8b_free:0, dmx_qwen_flash_free:0,
  sf_glm47:0,
  dmx_minimax_m25_free:0, dmx_glm_47_free:0, dmx_glm_47_flash:0, dmx_glm_45_flash:0,
  dmx_glm_4_9b:0, dmx_hunyuan_lite:0, dmx_qwen35_plus_free:0,
  dmx_qwen3_5_plus_free:0, dmx_qwen35_35b_free:0, dmx_qwen25_coder_7b:0,
  dmx_doubao_seed_lite:0, dmx_mimo_v25_free:0, sf_qwen3_32b:0,
  dmx_minimax_m27_free:0, dmx_glm_5_turbo_free:0, dmx_qwen3_coder_plus_free:0,
  dmx_qwen3_coder_next_free:0, dmx_doubao_seed_code:0, dmx_mimo_v2_pro_free:0,
  dmx_code_free:0, dmx_codex_free:0, dmx_kat_coder_free:0,
  dmx_qwen36_plus_free:0, dmx_code_free_x:0,
  dmx_kimi_k25_free:0, dmx_kimi_k26_free:0, dmx_doubao_seed_pro:0, dmx_qwen3_max_free:0,
  ark_dbs2_mini:0, ark_dbp15l:0, ark_dbs2_lite:0,
  ark_dsv4f:0, ark_dbs1_6:0, ark_dbs1_8:0, ark_dbs_code:0,
  ark_dsv32:0, ark_dsv4p:0, ark_dbs2_pro:0, ark_glm47:0,
  ark_dbp15p:0, ark_dbs_char:0,
  ark_doubao_pro:0, ark_doubao_lite:0,
  dmx_glm_5_free:0, dmx_glm_51_free:0, dmx_glm_5_turbo_free:0,
  // 🟢 1积分（入门级）
  deepseekv3:1, glm4:1, kimi:1, ali_qwen36_flash:1,
  glm4plus:1, minimax:1, spark4:1, ali_qwen36_plus:1, ali_deepseek_v4_flash:1,
  sf_hunyuan_a13b:1, sf_qwen35_397b:1, sf_qwq_32b:1,
  sf_deepseek_v32:1, bc_baichuan3:1,
  or_codeqwen:1,
  // 🟡 2积分（进阶）
  qwen3:2, kimi2:2, minimax1:2, doubao:2, doubao15:2, gpt4omini:2, gemini15flash:2,
  ali_qwen37_max:2, ali_deepseek_v4_pro:2, ali_kimi_k26:2,
  sf_glm5:2, bc_baichuan4:2,
  // 🟠 3积分（高级）
  nx_gpt5mini:3, nx_gpt54nano:3, llama4:3,
  // 🔴 5积分（旗舰）
  deepseekr1:5, gpt4o:5, hunyuan:5, gemini15pro:5, gemini25flash:5,
  grok3:5, ali_glm51:5, 'mistral-large2':5,
  or_llama3_70b:5, or_mistral_large:5, or_perplexity:5,
  nx_gpt5chat:5, nx_gpt54mini:5,
  // 🔵 8积分（高端）
  nx_gpt5:8, nx_gpt5all:8, nx_gpt51codex:8, nx_gpt52chat:8, nx_gpt52pro:8,
  nx_claude_haiku:8, nx_flux:8, ali_qwen37_max:8,
  // 💎 10积分（尊享）
  nx_gpt51codexmax:10, nx_o3mini:10,
  gpt4turbo:10, claude35:10, claude3opus:10, claude4:10,
  gemini25pro:10,
  or_gpt4o:10, or_claude_sonnet:10, or_gemini25pro:10,
  qiniu_claude37:10, qiniu_claudeopus4:10, qiniu_gpt4o:10, qiniu_o3:10,
  qiniu_gemini25pro:10,
  // 💎💎 12-15积分（顶级旗舰）
  nx_gpt54pro:12, nx_gemini_pro:12,
  nx_gpt55pro:15, nx_gpt55:15, nx_claude_sonnet:15, nx_dalle3:15, nx_suno:15, nx_grok3:15,
  claude4opus:15,
  // 👑 18-25积分（至尊）
  nx_gpt53chat:18,
  nx_gpt53codex:25, nx_claude_opus:25,
  // 3D（特殊高价）
  meshy_text:12, meshy_image:12,
};
function getModelCost(id){const m=models.find(x=>x.id===id);if(m&&m.cost!==undefined)return m.cost;return MODEL_COST[id]??2}
function getModelCostLabel(id){const c=getModelCost(id);return c===0?'<span style="font-size:0.65rem;padding:1px 5px;border-radius:3px;background:#10b981;color:#fff;margin-left:4px">免费</span>':'<span style="font-size:0.65rem;padding:1px 5px;border-radius:3px;background:var(--accent-light);color:var(--accent);margin-left:4px">⚡'+c+'</span>'}

function closeCreditLow(){document.getElementById('creditLow').style.display='none'}

// === 社交证明：动态人数 ===
(function(){const h=new Date().getHours();const ou=document.getElementById('onlineUsers');const tp=document.getElementById('todayPurchases');
  if(ou){const base=h>20||h<6?40:h>12?120:80;ou.textContent=base+Math.floor(Math.random()*60)}
  if(tp){tp.textContent=Math.floor(Math.random()*40+20)}
  // 每60秒随机微调
  setInterval(()=>{if(ou){const v=parseInt(ou.textContent)||100;ou.textContent=Math.max(20,v+Math.floor(Math.random()*11-5))}},60000);
})();

// === 促销组件初始化 ===
// 限时倒计时（每天重置）
function initPromoTimer(){
  const el=document.getElementById('promoCountdown');if(!el)return;
  const now=new Date();const end=new Date(now);end.setHours(23,59,59,999);
  const secs=Math.floor((end-now)/1000);
  const m=Math.floor(secs/60),s=secs%60;
  el.textContent=`${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`;
  document.getElementById('promoBanner').style.display='block';
  // 40% 概率显示限时活动
  if(Math.random()>0.4) document.getElementById('promoBanner').style.display='none';
}
setInterval(initPromoTimer,30000);

// 首次购买优惠
function initFirstPurchase(){
  const badge=document.getElementById('firstPurchaseBadge');
  const trial=document.getElementById('trialBanner');
  const hasPurchased=localStorage.getItem('has_purchased');
  if(!hasPurchased&&badge){badge.style.display='block'}
  if(!hasPurchased&&trial){trial.style.display='block'}
}

// 免费试用
function startFreeTrial(){
  if(localStorage.getItem('trial_used')){showToast('您已领取过优惠券');return}
  localStorage.setItem('trial_used','1');
  userCredits+=30;localStorage.setItem('cr',userCredits);updateCreditDisplay();
  showToast('🎉 已赠送 30 积分！首次充值享受 5 折优惠');
  document.getElementById('trialBanner').style.display='none';
}

// 成就奖励通知
function checkAchievement(){
  const streak=JSON.parse(localStorage.getItem('checkin_streak')||'{"count":0}');
  if(streak.count===7&&!localStorage.getItem('ach_7day')){
    localStorage.setItem('ach_7day','1');userCredits+=20;localStorage.setItem('cr',userCredits);
    setTimeout(()=>showToast('🏆 连续签到 7 天成就达成！+20 积分'),3000);
  }
  // 累计使用50次
  const total=parseInt(localStorage.getItem('utk')||'0');
  if(total>100000&&!localStorage.getItem('ach_usage')){
    localStorage.setItem('ach_usage','1');userCredits+=50;localStorage.setItem('cr',userCredits);
    setTimeout(()=>showToast('🏆 活跃用户成就达成！+50 积分 · 继续加油'),5000);
  }
}
function purchaseCredits(a,p){ 
  const productMap = { '150':'credits_starter', '700':'credits_standard', '1500':'credits_premium', '2500':'credits_pro', '6000':'credits_ultimate' };
  const productId = productMap[a.toString()];
  if(!productId) return;
  const isFirst=!localStorage.getItem('has_purchased');const disc=a>99&&isFirst?'\n\n🎉 首次充值特惠！':'';
  if(!confirm(`${disc?disc+'\n':''}购买 ${a} 积分 (¥${p})
─────────────────
💡 温馨提示：
• 积分为虚拟商品，充值后立即到账
• 已消耗积分无法退还
• 积分永久有效，无过期时间
─────────────────
确认支付表示同意用户协议及免责声明`)) return;
  // 调用支付 API
  createPaymentOrder(productId);
}
async function createPaymentOrder(productId) {
  if(!currentUser){ showToast('请先登录'); openAuth(); return; }
  try {
    const r = await fetch(API_BASE+'/api/payments/create-order', {
      method:'POST', 
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+(authToken||'')},
      body:JSON.stringify({productId})
    });
    const d = await r.json();
    if(!d.ok) { showToast(d.error || '下单失败'); return; }
    // 直接确认支付（模拟支付模式）
    const confirmR = await fetch(API_BASE+'/api/payments/confirm', {
      method:'POST',
      headers:{'Content-Type':'application/json','Authorization':'Bearer '+(authToken||'')},
      body:JSON.stringify({orderId: d.orderId})
    });
    const confirmD = await confirmR.json();
    if(confirmD.ok) {
      const isMembership = productId.startsWith('membership_');
      if(isMembership) {
        // 会员订阅成功后刷新
        const tier = productId.replace('membership_','');
        localStorage.setItem('membership',tier);
        renderMembershipBadge();
        document.getElementById('membershipModal')?.classList.remove('show');
        showToast('🎉 欢迎成为'+d.product.name+'！');
        setTimeout(()=>{window.location.reload()},1000);
      } else {
        showToast('🎉 '+d.product.name+' 购买成功！积分已到账');
        localStorage.setItem('has_purchased','1');
      }
      refreshUserCredits();
    } else {
      showToast(confirmD.error || '支付失败');
    }
  } catch(e) {
    showToast('网络错误，请重试');
  }
}
function subscribe(type){
  const productMap = { 'monthly':'membership_silver', 'quarterly':'membership_gold', 'yearly':'membership_platinum' };
  const productId = productMap[type];
  if(!productId) return;
  const plans={monthly:{n:'月度会员',p:49,c:1000},quarterly:{n:'季度会员',p:119,c:3500},yearly:{n:'年度会员',p:369,c:15000}};const plan=plans[type];if(!plan)return;
  if(!confirm(`订阅 ${plan.n}
¥${plan.p} · ${plan.c} 积分/周期
─────────────────
💡 温馨提示：
• 会员权益即时生效，不支持退款
• 积分按月发放，未用完不清零
• 可随时取消，权益保留至周期结束
─────────────────
确认支付表示同意用户协议及免责声明`)){
    return;
  }
  createPaymentOrder(productId);
}

// === 每日签到 ===
function DAILY_CHECKIN(){
  if(!currentUser){showToast('请先登录');return}
  // 先通过服务端验证（防止跨设备/跨浏览器重复签到）
  fetch(API_BASE+'/api/user/checkin',{method:'POST',headers:getAuthHeader()})
    .then(r=>r.json())
    .then(d=>{
      if(d.ok){
        userCredits=d.credits;
        localStorage.setItem('cr',userCredits);
        updateCreditDisplay();
        const msg=d.streak%7===0?'🎉 连续7天!':d.streak%30===0?'🔥 连续30天!':`+${d.bonus}`;
        showToast(`✅ 签到成功! ${msg}积分 · 连续${d.streak}天 · 余额${d.credits}`);
        updateCheckinBtn();
      }else if(d.already){
        showToast('今天已经签到过了，明天再来吧~');
      }else{
        showToast(d.error||'签到失败');
      }
    })
    .catch(()=>{showToast('网络错误，签到失败')});
}
function updateCheckinBtn(){
  const btn=document.getElementById('checkinBtn');
  if(!currentUser){btn.style.display='none';return}
  btn.style.display='inline-flex';
  // 从服务端查询签到状态
  fetch(API_BASE+'/api/user/checkin-status',{headers:getAuthHeader()})
    .then(r=>r.json())
    .then(d=>{
      if(d.ok && d.checkedIn){
        btn.textContent='✅ 已签到';
        btn.style.background='var(--bg-card)';
        btn.style.opacity='0.6';
      }else{
        btn.textContent='📅 签到 +5';
        btn.style.background='linear-gradient(135deg,#f59e0b,#d97706)';
        btn.style.opacity='1';
      }
    })
    .catch(()=>{
      btn.textContent='📅 签到 +5';
      btn.style.background='linear-gradient(135deg,#f59e0b,#d97706)';
      btn.style.opacity='1';
    });
}

// === User Auth ===
let currentUser=JSON.parse(localStorage.getItem('cuser')||'null');
// === 设备指纹（防多账号核心，使用统一指纹） ===
function getDeviceFingerprint(){return deviceFp||getDeviceFingerprint2()}
function getDeviceFingerprint2(){
  if(localStorage.getItem('device_fp'))return localStorage.getItem('device_fp');
  const comps=[
    screen.width+'x'+screen.height,screen.colorDepth,new Date().getTimezoneOffset(),
    navigator.language,navigator.hardwareConcurrency||'?',navigator.platform||'?',
    !!navigator.webdriver
  ];
  const hash=btoa(comps.join('|')+'|'+Math.random().toString(36).substring(2,8)).substring(0,12);
  localStorage.setItem('device_fp',hash);
  return hash;
}
// 检查本设备是否已有绑定账号
function getDeviceBoundUser(){
  const fp=getDeviceFingerprint();
  const users=getUsers();
  return users.find(u=>u.deviceFp===fp)||null;
}
function getUsers(){try{return JSON.parse(localStorage.getItem('users')||'[]')}catch(e){return[]}}
function saveUsers(u){localStorage.setItem('users',JSON.stringify(u))}
function renderUserNav(){
  const el=document.getElementById('userNav');
  if(currentUser){
    const ref=currentUser.refCode||genRefCode(currentUser.username);
    el.innerHTML=`<span style="font-size:0.75rem;cursor:pointer;display:flex;align-items:center;gap:4px" onclick="showRefCode()">👤 ${escapeHtml(currentUser.username)}</span><button class="btn-sm" onclick="doLogout()">退出</button>`;
  }else{
    el.innerHTML=`<button class="btn-sm primary" onclick="openAuth()">登录</button>`;
  }
  const su=document.getElementById('sidebarUserName');if(su)su.textContent=currentUser?currentUser.username:'未登录';
  renderMembershipBadge();
}
function showRefCode(){
  if(!currentUser)return;
  const users=getUsers();const u=users.find(x=>x.username===currentUser.username);
  const code=u?u.refCode:genRefCode(currentUser.username);
  prompt('你的推荐码（复制发给朋友）：\n\n'+(u?u.refCode:code)+'\n\n推荐链接：https://j3trisheng.com\n双方各得5积分！');}
function openAuth(){document.getElementById('authModal').classList.add('show');showLogin()}
// === 新认证系统 ===
function switchAuthTab(tab){
  document.querySelectorAll('.auth-tab').forEach(t=>t.classList.toggle('active',t.textContent===(tab==='login'?'登录':tab==='register'?'注册':'')));
  document.getElementById('authFormLogin').classList.toggle('active',tab==='login');
  document.getElementById('authFormRegister').classList.toggle('active',tab==='register');
  document.getElementById('authFormForgot').classList.toggle('active',tab==='forgot');
}
function clearFieldError(el){el.classList.remove('error');const hint=el.parentElement.querySelector('.field-hint');if(hint)hint.style.display='none'}
function showFieldError(el,msg){el.classList.add('error');const hint=el.parentElement.querySelector('.field-hint');if(hint){hint.textContent=msg;hint.style.display='block'}}
function checkUsername(){
  const v=document.getElementById('regUser').value.trim();
  const el=document.getElementById('regUser');
  const status=document.getElementById('regUserStatus');
  if(!v){clearFieldError(el);status.textContent='';status.style.color='';return false}
  if(!/^[a-zA-Z0-9]{2,20}$/.test(v)){
    showFieldError(el,'仅限2-20位字母或数字，不能使用中文或符号');
    status.textContent='❌ 格式错误：仅允许字母和数字';
    status.style.color='#ef4444';
    return false
  }
  clearFieldError(el);
  status.textContent='✅ 格式正确';
  status.style.color='#10b981';
  return true;
}
function checkEmail(){
  const v=document.getElementById('regEmail').value.trim();
  const el=document.getElementById('regEmail');
  if(!v){clearFieldError(el);return true} // 邮箱选填，清除可能残留的错误状态
  if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)){showFieldError(el,'⚠️ 邮箱格式错误（如 name@qq.com）');return false}
  clearFieldError(el);return true;
}
function checkPhone(){
  const v=document.getElementById('regPhone').value.trim();
  const el=document.getElementById('regPhone');
  if(!v){clearFieldError(el);return false} // 初始为空时清除错误，不显示报错
  if(!/^1[3-9]\d{9}$/.test(v)){showFieldError(el,'⚠️ 手机号格式不正确（11位数字，如13800138000）');return false}
  clearFieldError(el);return true;
}
function checkPwdStrength(){
  const v=document.getElementById('regPwd').value,bar=document.getElementById('pwdBar'),txt=document.getElementById('pwdStrengthText');
  if(!v){bar.className='pwd-strength';if(txt){txt.textContent='';txt.style.color='var(--text-secondary)'};return}
  let score=0;if(v.length>=6)score++;if(v.length>=10)score++;if(/[A-Z]/.test(v))score++;if(/[0-9]/.test(v))score++;if(/[^A-Za-z0-9]/.test(v))score++;
  const cls=score<=2?'weak':score<=3?'medium':'strong';
  bar.className='pwd-strength '+cls;
  if(txt){
    const labels={weak:{text:'弱 - 建议增加长度和特殊字符',color:'var(--red)'},medium:{text:'中 - 继续加强',color:'var(--orange)'},strong:{text:'强 - 密码很安全',color:'var(--green)'}};
    txt.textContent=labels[cls].text;txt.style.color=labels[cls].color;
  }
}
function doLoginNew(){
  const u=document.getElementById('loginUser').value.trim(),p=document.getElementById('loginPwd').value;
  let valid=true;
  if(!u){showFieldError(document.getElementById('loginUser'),'请输入用户名或邮箱');valid=false}
  if(!p){showFieldError(document.getElementById('loginPwd'),'请输入密码');valid=false}
  if(!valid)return;
  const btn=document.querySelector('.auth-btn');btn.textContent='登录中...';btn.disabled=true;
  apiFetch('/api/auth/login',{method:'POST',body:JSON.stringify({username:u,password:p})}).then(d=>{
    btn.textContent='登 录';btn.disabled=false;
    if(d.ok&&d.token){
      setAuthToken(d.token);currentUser=d.user||{username:u};
      localStorage.setItem('cuser',JSON.stringify(currentUser));
      if(d.user&&d.user.credits!==undefined){userCredits=d.user.credits;localStorage.setItem('cr',userCredits)}
      closeAuth();renderUserNav();updateCreditDisplay();updateCheckinBtn();updateCheckinBtn();showToast('👋 欢迎回来，'+(d.user?.name||u));
      syncUserData();
    }else{
      // 后端不可用时降级到本地登录
      const users=getUsers();const found=users.find(x=>(x.username===u||x.email===u)&&x.password===btoa(p));
      if(!found){showToast(d.error||'用户名或密码错误');return}
      currentUser={username:found.username,email:found.email};localStorage.setItem('cuser',JSON.stringify(currentUser));
      userCredits=parseInt(localStorage.getItem('cr_'+found.username)||'30');localStorage.setItem('cr',userCredits);
      closeAuth();renderUserNav();updateCreditDisplay();updateCheckinBtn();showToast('👋 欢迎回来，'+found.username);
    }
  });
}
function doRegisterNew(){
  try {
  const u=document.getElementById('regUser').value.trim(),e=document.getElementById('regEmail').value.trim(),p=document.getElementById('regPwd').value,ref=document.getElementById('regRefCode').value.trim();
  let valid=true;
  if(!checkUsername())valid=false;
  if(!checkEmail())valid=false;
  const phone=document.getElementById('regPhone').value.trim();
  if(!phone){showFieldError(document.getElementById('regPhone'),'⚠️ 手机号必填，是您账号的唯一身份凭证');valid=false}
  else if(!/^1[3-9]\d{9}$/.test(phone)){showFieldError(document.getElementById('regPhone'),'⚠️ 手机号格式不正确（11位数字）');valid=false}
  else{clearFieldError(document.getElementById('regPhone'))}
  if(p.length<6){showFieldError(document.getElementById('regPwd'),'密码至少6位');valid=false}
  const secQ=document.getElementById('regSecQ').value;
  const customQ=document.getElementById('regCustomQ').value.trim();
  const secA=document.getElementById('regSecA').value.trim();
  const securityQuestion=secQ==='自定义'?customQ:secQ;
  if(!securityQuestion||securityQuestion==='自定义'){showToast('请选择密保问题');valid=false}
  if(!secA){showFieldError(document.getElementById('regSecA'),'请输入密保答案');valid=false}
  if(!document.getElementById('regAgree').checked){showToast('请同意服务条款');valid=false}
  if(!valid)return;

  // === 强防薅：设备指纹绑定 ===
  const deviceFp=getDeviceFingerprint();
  const existingDeviceUser=getDeviceBoundUser();
  if(existingDeviceUser){showToast(`⚠️ 本设备已绑定账号「${existingDeviceUser.username}」，无法重复注册。请使用该账号登录。`);return}
  // 邮箱唯一性检查
  if(e){const users=getUsers();if(users.find(x=>x.email===e)){showFieldError(document.getElementById('regEmail'),'该邮箱已被注册');return}}

  const btn=document.getElementById('registerBtn');btn.textContent='注册中...';btn.disabled=true;
  apiFetch('/api/auth/register',{method:'POST',body:JSON.stringify({username:u,email:e||undefined,password:p,phone:phone||undefined,deviceFp,refCode:ref||undefined,securityQuestion:securityQuestion||undefined,securityA:secA||undefined})}).then(d=>{
    btn.textContent='注 册';btn.disabled=false;
    if(d.ok&&d.token){
      setAuthToken(d.token);currentUser=d.user||{username:u};
      localStorage.setItem('cuser',JSON.stringify(currentUser));
      if(d.user&&d.user.credits!==undefined){userCredits=d.user.credits;localStorage.setItem('cr',userCredits)}
      closeAuth();renderUserNav();updateCreditDisplay();updateCheckinBtn();
      switchPage('chat');setTimeout(()=>{document.getElementById('chatInput').focus();showToast('🎉 注册成功！欢迎来到 TriGen')},500);
      syncUserData();
    }else{
      // 显示后端错误消息
      if(d && d.error) { showToast('❌ ' + d.error); return; }
      // 后端不可用时降级到本地注册
      const users=getUsers();
      if(users.find(x=>x.username===u)){showFieldError(document.getElementById('regUser'),'用户名已存在');return}
      if(users.find(x=>x.email===e)){showFieldError(document.getElementById('regEmail'),'邮箱已被注册');return}
      const newUser={username:u,email:e,phone:phone||'',password:btoa(p),refCode:genRefCode(u),created:new Date().toISOString(),securityQ:securityQuestion,securityA:btoa(secA),deviceFp};
      users.push(newUser);saveUsers(users);
      let bonus=30;
      if(ref){const refUser=users.find(x=>x.refCode===ref||x.username===ref);if(refUser&&refUser.username!==u){bonus+=30;const rc=parseInt(localStorage.getItem('cr_'+refUser.username)||'30');localStorage.setItem('cr_'+refUser.username,rc+30);showToast('推荐码有效！你和推荐人各得30积分')}}
      localStorage.setItem('cr_'+u,bonus);userCredits=bonus;localStorage.setItem('cr',bonus);
      currentUser={username:u,email:e,phone:phone||''};localStorage.setItem('cuser',JSON.stringify(currentUser));
      closeAuth();renderUserNav();updateCreditDisplay();updateCheckinBtn();
      switchPage('chat');setTimeout(()=>{document.getElementById('chatInput').focus();showToast(`🎉 注册成功！赠送${bonus}积分。试试第一次AI对话吧~`)},500);
    }
  });
  } catch(e) { console.error('Register error:', e); showToast('注册出错: '+e.message); }
}
function showForgotPwd(){switchAuthTab('forgot')}
function doForgotPwd(){
  const input=document.getElementById('forgotEmail').value.trim();
  if(!input){showToast('请输入注册邮箱或用户名');return}
  
  // 先尝试通过服务器 API 查询
  fetch('/api/auth/forgot-password-query', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({input})
  }).then(r=>r.json()).then(d=>{
    if(!d.ok){
      // 服务器查询失败，降级到 localStorage
      const users=getUsers();
      const user=users.find(x=>x.email===input||x.username===input);
      if(!user){showToast(d.error||'未找到该邮箱或用户名对应的账号');return}
      if(!user.securityQ){showToast('该账号未设置密保，无法找回。请联系管理员');return}
      const answer=prompt('密保问题：'+atobFix(user.securityQ)+'\n\n请输入你的答案：');
      if(!answer)return;
      if(atobFix(user.securityA).toLowerCase()!==answer.toLowerCase()){showToast('❌ 密保答案错误！');return}
      const np=prompt('密保验证通过！请输入新密码（至少6位）：');
      if(!np||np.length<6){showToast('密码至少6位');return}
      user.password=btoa(np);saveUsers(users);
      showToast('✅ 密码已重置，请用新密码登录');
      switchAuthTab('login');
      return;
    }
    // 服务器查询成功，通过服务器 API 重置密码
    const answer=prompt('密保问题：'+d.securityQ+'\n\n请输入你的答案：');
    if(!answer)return;
    const np=prompt('密保验证通过！请输入新密码（至少6位）：');
    if(!np||np.length<6){showToast('密码至少6位');return}
    fetch('/api/auth/forgot-password', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({input, securityAnswer:answer, newPassword:np})
    }).then(r=>r.json()).then(d2=>{
      if(d2.ok) { showToast('✅ 密码已重置，请用新密码登录'); switchAuthTab('login'); }
      else { showToast('❌ '+d2.error); }
    }).catch(()=>{showToast('❌ 网络错误，请稍后重试')});
  }).catch(()=>{
    // 网络错误，降级到 localStorage
    const users=getUsers();
    const user=users.find(x=>x.email===input||x.username===input);
    if(!user){showToast('网络异常，请稍后重试');return}
    if(!user.securityQ){showToast('该账号未设置密保，无法找回。请联系管理员');return}
    const answer=prompt('密保问题：'+atobFix(user.securityQ)+'\n\n请输入你的答案：');
    if(!answer)return;
    if(atobFix(user.securityA).toLowerCase()!==answer.toLowerCase()){showToast('❌ 密保答案错误！');return}
    const np=prompt('密保验证通过！请输入新密码（至少6位）：');
    if(!np||np.length<6){showToast('密码至少6位');return}
    user.password=btoa(np);saveUsers(users);
    showToast('✅ 密码已重置，请用新密码登录');
    switchAuthTab('login');
  });
}
// 密保问题切换
document.getElementById('regSecQ').addEventListener('change',function(){
  document.getElementById('regCustomQField').style.display=this.value==='自定义'?'block':'none';
});
function closeAuth(){document.getElementById('authModal').classList.remove('show')}
function showLogin(){document.getElementById('authModal').classList.add('show');switchAuthTab('login');document.getElementById('loginUser').focus()}
function togglePwd(inputId,btn){
  const input=document.getElementById(inputId);
  if(input.type==='password'){input.type='text';btn.textContent='🙈'}
  else{input.type='password';btn.textContent='👁️'}
}

// 保留旧函数兼容性
function doLogin(){doLoginNew()}
function doRegister(){doRegisterNew()}
function showRegister(){document.getElementById('authModal').classList.add('show');switchAuthTab('register')}
function genRefCode(u){return 'J3'+u.substring(0,3).toUpperCase()+String(Math.floor(Math.random()*9000+1000))}
function atobFix(s){try{return decodeURIComponent(escape(atob(s)))}catch(e){try{return atob(s)}catch(e2){return s}}}
function doLogout(){currentUser=null;setAuthToken(null);localStorage.removeItem('cuser');localStorage.removeItem('cr');localStorage.removeItem('membership');localStorage.removeItem('membership_expires');location.reload()}

// === 会员体系 ===
const MEMBERSHIP_PLANS={
  free:{name:'免费用户',price:0,monthlyCredits:0,benefits:['30积分体验','基础模型免费使用（有限制）','对话功能'],color:'#64748b'},
  silver:{name:'月度会员',price:49,monthlyCredits:1000,benefits:['👑 高端模型8折','📚 知识库100条','📊 使用统计面板','🚫 无广告','🆓 免费模型无限用'],color:'#3b82f6',popular:false},
  gold:{name:'季度会员',price:119,monthlyCredits:3500,benefits:['🔥 高端模型7折','💰 5%积分返利','📖 小说导出无水印','📚 知识库200条','💎 专属模型优先','🆓 免费模型无限用'],color:'#f59e0b',popular:true},
  platinum:{name:'年度会员',price:369,monthlyCredits:15000,benefits:['💎 高端模型5折','💰 10%积分返利','🧊 3D生成5折','📚 知识库无限','🎯 专属模型优先','🆓 免费模型无限用','🏆 客服优先响应'],color:'#7c3aed'},
};
function renderMembershipBadge(){
  const badge=document.getElementById('sidebarMembershipBadge');
  if(!badge)return;
  if(!currentUser){badge.textContent='';badge.style.display='none';return}
  // 从 localStorage 读取会员信息
  const m=localStorage.getItem('membership')||'free';
  const expires=localStorage.getItem('membership_expires')||'';
  if(m==='free'){badge.textContent='';badge.style.display='none';return}
  const plan=MEMBERSHIP_PLANS[m];
  badge.textContent=plan?plan.name:'会员';
  badge.style.display='inline';
  badge.style.background=plan?plan.color+'22':'var(--accent-light)';
  badge.style.color=plan?plan.color:'var(--accent)';
}
function openMembershipModal(){
  const m=document.getElementById('membershipModal');
  if(m){m.classList.add('show');return}
  const modal=document.createElement('div');modal.id='membershipModal';
  modal.className='modal';
  let html='<div class="modal-content" style="max-width:700px">';
  html+='<div class="modal-header"><h2>🔥 开通会员</h2><button class="modal-close" onclick="this.closest(\'.modal\').classList.remove(\'show\')">✕</button></div>';
  html+='<div class="modal-body">';
  html+='<p style="text-align:center;color:var(--text-secondary);margin-bottom:20px">比单买划算 3-5 倍 · 免费模型无限用 · 高端模型最低 5 折</p>';
  html+='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:14px">';
  Object.entries(MEMBERSHIP_PLANS).filter(([k])=>k!=='free').forEach(([k,v])=>{
    const currentMembership=localStorage.getItem('membership')||'free';
    const isCurrent=k===currentMembership;
    html+='<div class="feature-card" style="text-align:center;padding:24px 16px;position:relative;'+(v.popular?'border:2px solid var(--accent)':'')+';'+(isCurrent?'opacity:0.7':'')+'">';
    if(v.popular) html+='<div style="position:absolute;top:-12px;left:50%;transform:translateX(-50%);background:var(--accent);color:#fff;padding:3px 12px;border-radius:10px;font-size:0.72rem;font-weight:700">🔥 最受欢迎</div>';
    if(isCurrent) html+='<div style="position:absolute;top:-12px;right:10px;background:var(--green);color:#fff;padding:3px 10px;border-radius:10px;font-size:0.68rem">当前</div>';
    html+='<div style="font-size:2rem;margin-bottom:6px">'+(k==='silver'?'🥈':k==='gold'?'🥇':'💎')+'</div>';
    html+='<h3>'+v.name+'</h3>';
    const priceStr=k==='gold'?v.price+'<span style="font-size:0.7rem;font-weight:400">/季</span>':k==='platinum'?v.price+'<span style="font-size:0.7rem;font-weight:400">/年</span>':v.price+'<span style="font-size:0.7rem;font-weight:400">/月</span>';
    html+='<div style="font-size:1.8rem;font-weight:800;color:'+v.color+';margin:8px 0">¥'+priceStr+'</div>';
    html+='<p style="font-size:0.78rem;color:var(--text-secondary);margin-bottom:8px">赠送 '+v.monthlyCredits+' 积分/月</p>';
    html+='<div style="text-align:left;font-size:0.72rem;color:var(--text-secondary);line-height:1.6;margin-bottom:12px;padding-left:8px">';
    v.benefits.forEach(b=>{html+='✅ '+b+'<br>'});
    html+='</div>';
    const btnStyle=v.popular?'background:linear-gradient(135deg,#f59e0b,#d97706)':'';
    html+='<button class="btn-send" style="'+btnStyle+';'+((isCurrent?'opacity:0.5;cursor:default':''))+'" '+(isCurrent?'disabled':'')+' onclick="subscribeMembership(\''+k+'\')">'+(isCurrent?'已订阅':'立即开通')+'</button>';
    html+='</div>';
  });
  html+='</div>';
  html+='<p style="text-align:center;font-size:0.7rem;color:var(--text-secondary);margin-top:14px">⚡ 会员积分每月自动到账 · 积分永不过期 · 可随时取消</p>';
  html+='</div></div>';
  modal.innerHTML=html;
  document.body.appendChild(modal);
  setTimeout(()=>modal.classList.add('show'),10);
}
async function subscribeMembership(tier){
  if(!currentUser){showToast('请先登录');openAuth();return}
  const months=tier==='platinum'?12:tier==='gold'?3:1;
  const plan=MEMBERSHIP_PLANS[tier];
  if(!confirm(`确认订阅${plan.name} ¥${plan.price}？`))return;
  // 改用统一支付流程
  const productMap = { 'silver':'membership_silver', 'gold':'membership_gold', 'platinum':'membership_platinum' };
  createPaymentOrder(productMap[tier]);
}

function openUserSettings(){
  if(!currentUser){showToast('请先���录');return}
  const oldPwd=prompt('当前密码（验证身份）：');
  if(!oldPwd)return;
  const users=getUsers();
  const user=users.find(x=>x.username===currentUser.username||x.email===currentUser.email);
  if(!user||user.password!==btoa(oldPwd)){showToast('❌ 当前密码错误');return}
  const act=prompt('选择操作：\n1. 修改密码\n2. 查看会员信息');
  if(act==='1'){
    const np=prompt('请输入新密码（至少6位）：');
    if(!np||np.length<6){showToast('密码至少6位');return}
    user.password=btoa(np);saveUsers(users);
    showToast('✅ 密码修改成功');
  }else if(act==='2'){
    // 获取服务器会员信息
    fetch(API_BASE+'/api/membership/status',{headers:{'Authorization':'Bearer '+(authToken||'')}})
      .then(r=>r.json()).then(d=>{
        if(d.ok){
          const plan=MEMBERSHIP_PLANS[d.membership]||MEMBERSHIP_PLANS.free;
          alert(`📊 会员信息\n━━━━━━━━━━━━━━━\n等级：${plan.name}\n到期：${d.expires||'永久'}\n每日免费调用：${d.dailyFreeUsed||0}/${d.dailyFreeCalls}\n积分：${d.credits||0}\n折扣：${(d.discount*100).toFixed(0)}%`);
        }else{alert('获取失败')}
      }).catch(()=>alert('网络错误'));
  }
}

