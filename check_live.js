const https = require('https');
https.get('https://j3trisheng.com', (res) => {
  let data = '';
  res.on('data', chunk => data += chunk);
  res.on('end', () => {
    const m = data.match(/<script>([\s\S]*?)<\/script>/);
    if (!m) { console.log('No script tag'); return; }
    const js = m[1];
    let inStr = false, inTmpl = false, inSingle = false, inCmnt = false, esc = false;
    let problems = [];
    for (let i = 0; i < js.length; i++) {
      const c = js[i], n = js[i + 1] || '';
      if (inCmnt) { if (c === '\n') inCmnt = false; continue; }
      if (esc) { esc = false; continue; }
      if (c === '\\') { esc = true; continue; }
      if (!inTmpl && !inSingle && c === '"') { inStr = !inStr; continue; }
      if (!inStr && !inTmpl && c === "'") { inSingle = !inSingle; continue; }
      if (!inStr && !inSingle && c === '`') { inTmpl = !inTmpl; continue; }
      if (!inStr && !inTmpl && !inSingle) {
        if (c === '/' && n === '/') { inCmnt = true; continue; }
        if (c === '<') {
          const ctx = js.substring(Math.max(0, i-15), Math.min(js.length, i+30));
          problems.push('stray < at js pos ' + i + ': ...' + ctx.replace(/\n/g, '\\n') + '...');
          if (problems.length > 5) break;
        }
      }
    }
    if (problems.length) console.log('FOUND STRAY < :\n' + problems.join('\n'));
    else console.log('JS CLEAN - no stray < characters');
  });
}).on('error', e => console.log('Error:', e.message));
