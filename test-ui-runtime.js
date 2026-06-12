const http = require('http');
const url = 'http://120.79.17.184:3001/studio/js/ui.js';

http.get(url, (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    console.log('下载完成:', data.length, '字节');
    
    try {
      // 在原生 JS 环境中执行这个 IIFE
      const result = eval(data);
      console.log('✅ IIFE 执行成功');
      console.log('返回对象类型:', typeof result);
      console.log('是否有 init:', typeof result.init);
      console.log('init 是否为函数:', typeof result.init === 'function');
      
      if (typeof result.init === 'function') {
        console.log('✅ init 可正常访问');
      } else {
        console.log('❌ init 不可访问!');
      }
      
      // 列出 return 中的所有键
      console.log('\n=== 返回对象的键 ===');
      for (const key in result) {
        if (result.hasOwnProperty(key)) {
          console.log(`  ${key}: ${typeof result[key]}`);
        }
      }
    } catch (e) {
      console.log('❌ 执行错误:', e.message);
      console.log('堆栈:', e.stack);
    }
  });
});
