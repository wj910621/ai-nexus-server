const fs = require('fs'), path = require('path');
const V = process.argv.includes('--version') ? process.argv[process.argv.indexOf('--version') + 1] : '0';
const $ROOT = __dirname;

// 所有需要内联的 JS 文件（按依赖顺序�?const INL = ['storage.js','api.js','models.js','chat.js','code.js','agent.js','agent-v2.js','skills.js','plugin.js','particles.js','autonomous.js','knowledge.js','ui.js','app.js'];

function esc(h) {
  return h.replace(/<\/script>(?!\s*[\r\n])/g, '<\\/script>');
}

var idx = fs.readFileSync(path.join($ROOT, 'index.html'), 'utf-8');

// 插入 Service Worker 清理代码
var CL = '<script>\nif(\'serviceWorker\' in navigator){navigator.serviceWorker.getRegistrations().then(function(r){r.forEach(function(x){x.unregister()})})}\nif(\'caches\' in window){caches.keys().then(function(n){n.forEach(function(k){caches.delete(k)})})}\n</script>';
idx = idx.replace('<head>', '<head>\n' + CL);

// index_app.html（只�?SW 清理，保留模块化加载�?fs.writeFileSync(path.join($ROOT, 'index_app.html'), idx, 'utf-8');
console.log('index_app.html ' + (idx.length / 1024).toFixed(1) + 'KB');

// index_standalone.html：把所�?JS 合并到一�?script �?var stdHtml = idx;

// 1. 读取所�?JS 文件内容，按顺序拼接
var allJs = '';
INL.forEach(function(f) {
  var c = fs.readFileSync(path.join($ROOT, 'js', f), 'utf-8');
  allJs += '/*** ' + f + ' ***/\n' + c + '\n\n';
});

// 2. 去掉所有原�?script 引用（用正则匹配替换�?stdHtml = stdHtml.replace(/<script src="js\/[^"]+\.js(?:\?v=\d+)?"><\/script>/g, '');
stdHtml = stdHtml.replace(/<script src='js\/[^']+\.js(?:\?v=\d+)?'><\/script>/g, '');

// 3. �?</body> 前插入合并后�?script
stdHtml = stdHtml.replace('</body>', '<script>\n' + allJs + '\n</script>\n</body>');

// 4. 转义 </script>
stdHtml = esc(stdHtml);

fs.writeFileSync(path.join($ROOT, 'index_standalone.html'), stdHtml, 'utf-8');
console.log('index_standalone.html ' + (stdHtml.length / 1024).toFixed(1) + 'KB (all JS in one scope)');

// 生成 sw.js
var sw = 'var CN="trigenclaw-v"+' + JSON.stringify(V) + '\nvar CU=[".","index.html"';
var us = ['css/style.css?v=' + V];
INL.forEach(function(f) { us.push('js/' + f + '?v=' + V); });
us.push('js/app.js?v=' + V, 'js/worker.js?v=' + V, 'manifest.json', 'sw.js');
us.forEach(function(u) { sw += ',"' + u + '"'; });
sw += '];\n';
sw += 'self.addEventListener("install",function(e){e.waitUntil(caches.open(CN).then(function(c){return c.addAll(CU)}).then(function(){return self.skipWaiting()}))});';
sw += 'self.addEventListener("activate",function(e){e.waitUntil(caches.keys().then(function(n){return Promise.all(n.map(function(k){if(k!==CN)return caches.delete(k)}))}).then(function(){return self.clients.claim()}))});';
sw += 'self.addEventListener("fetch",function(e){var r=e.request;if(r.mode==="navigate"){e.respondWith(fetch(r).then(function(res){var c=res.clone();caches.open(CN).then(function(ca){ca.put(r,c)});return res}).catch(function(){return caches.match("index.html")}));return}e.respondWith(caches.match(r).then(function(m){return m||fetch(r).then(function(res){if(res&&res.ok){var c=res.clone();caches.open(CN).then(function(ca){ca.put(r,c)})}return res})}))});';
fs.writeFileSync(path.join($ROOT, 'sw.js'), sw, 'utf-8');
console.log('sw.js ' + (sw.length / 1024).toFixed(1) + 'KB');
console.log('Done');
