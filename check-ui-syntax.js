// 下载 ui.js 并检查语法
const http = require('http');
const fs = require('fs');
const path = require('path');

const url = 'http://120.79.17.184:3001/studio/js/ui.js';
const dest = 'd:/temp_ui_check.js';

http.get(url, (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    fs.writeFileSync(dest, data);
    console.log('下载完成，大小:', data.length, '字节');
    console.log('行数:', data.split('\n').length);
    
    // 检查关键语法结构
    const lines = data.split('\n');
    console.log('\n=== 检查关键行 ===');
    console.log('第1行:', lines[0]?.trim());
    console.log('第3行:', lines[2]?.trim());
    
    // 找 init 函数定义
    for (let i = 0; i < Math.min(lines.length, 520); i++) {
      if (lines[i].includes('function init')) {
        console.log('function init 在第', i+1, '行:', lines[i].trim());
      }
    }
    
    // 检查 IIFE 括号平衡
    let open = 0, close = 0;
    for (let i = 0; i < data.length; i++) {
      if (data[i] === '(') open++;
      if (data[i] === ')') close++;
      if (data[i] === '{') openP++;
      if (data[i] === '}') closeP++;
    }
    
    console.log('\n=== IIFE 平衡检查 ===');
    console.log('( 共', data.split('(').length - 1, '个');
    console.log(') 共', data.split(')').length - 1, '个');
    console.log('{ 共', data.split('{').length - 1, '个');
    console.log('} 共', data.split('}').length - 1, '个');
    
    console.log('\n=== 第 1645-1657 行 ===');
    for (let i = 1644; i < Math.min(lines.length, 1658); i++) {
      if (lines[i]) console.log(`L${i+1}: ${lines[i]}`);
    }
    
    fs.unlinkSync(dest);
  });
}).on('error', (e) => {
  console.error('下载失败:', e.message);
});
