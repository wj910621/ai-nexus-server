const http = require('http');
const fs = require('fs');

const url = 'http://120.79.17.184:3001/studio/js/ui.js';
const dest = 'd:/temp_ui_syntax.js';

http.get(url, (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    fs.writeFileSync(dest, data);
    console.log('下载完成:', data.length, '字节');
    
    // 用 Node.js 语法检查
    try {
      new Function(data);
      console.log('✅ 语法检查通过！无语法错误');
    } catch(e) {
      console.log('❌ 语法错误:', e.message);
      console.log('行号:', e.lineNumber || '未知');
      console.log('列号:', e.columnNumber || '未知');
    }
    
    // 检查括号平衡
    const opens = ['(', '{', '['];
    const closes = [')', '}', ']'];
    const counts = [0, 0, 0];
    const lines = data.split('\n');
    
    for (let i = 0; i < data.length; i++) {
      for (let j = 0; j < 3; j++) {
        if (data[i] === opens[j]) counts[j]++;
        if (data[i] === closes[j]) counts[j]--;
      }
    }
    
    console.log('\n=== 括号平衡 ===');
    console.log('():', counts[0] === 0 ? '✅' : '❌ (' + counts[0] + ')');
    console.log('{}:', counts[1] === 0 ? '✅' : '❌ (' + counts[1] + ')');
    console.log('[]:', counts[2] === 0 ? '✅' : '❌ (' + counts[2] + ')');
    
    // 在第1648-1655行检查 return 语句
    console.log('\n=== 第1648-1655行 ===');
    for (let i = 1647; i < Math.min(lines.length, 1655); i++) {
      if (lines[i] !== undefined) console.log(`L${i+1}: ${lines[i]}`);
    }
    
    // 最后5行
    console.log('\n=== 最后5行 ===');
    for (let i = Math.max(0, lines.length - 5); i < lines.length; i++) {
      console.log(`L${i+1}: ${lines[i]}`);
    }
    
    fs.unlinkSync(dest);
  });
});
