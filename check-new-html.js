const fs = require('fs');
const content = fs.readFileSync('G:/大模型聚合网站/new-nexus/index.html', 'utf8');

// Extract JS code between <script> and </script>
const match = content.match(/<script>([\s\S]*?)<\/script>/);
if (match) {
  const js = match[1];
  try {
    new Function(js);
    console.log('✅ JavaScript syntax check passed');
    console.log('File size:', content.length, 'bytes');
    console.log('JS size:', js.length, 'bytes');
  } catch(e) {
    console.log('❌ Syntax error:', e.message);
    console.log('Line:', e.lineNumber);
  }
} else {
  console.log('❌ No script tag found');
}
