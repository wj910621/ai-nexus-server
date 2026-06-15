/* Web Worker - 后台 API 调用，不阻塞 UI */
self.onmessage = function(e) {
  var m = e.data;
  if (m.type === 'chat') {
    var ctrl = new AbortController();
    self._controllers = self._controllers || {};
    self._controllers[m.id] = ctrl;
    var body = JSON.stringify({
      model: m.model,
      messages: m.messages,
      temperature: (m.opts && m.opts.temperature) || 0.7,
      max_tokens: (m.opts && m.opts.max_tokens) || 4096,
      stream: true
    });
    fetch('https://j3trisheng.com/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body,
      signal: ctrl.signal
    }).then(function(r) {
      if (!r.ok) throw new Error('HTTP ' + r.status);
      var reader = r.body.getReader();
      var dec = new TextDecoder();
      var buf = '';
      function rd() {
        reader.read().then(function(res) {
          if (res.done) {
            self.postMessage({ type: 'done', id: m.id });
            delete self._controllers[m.id];
            return;
          }
          buf += dec.decode(res.value, { stream: true });
          var lines = buf.split('\n');
          buf = lines.pop() || '';
          for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim();
            if (line.indexOf('data: ') === 0) {
              var d = line.slice(6);
              if (d === '[DONE]') {
                self.postMessage({ type: 'done', id: m.id });
                delete self._controllers[m.id];
                return;
              }
              try {
                var p = JSON.parse(d);
                var c = '';
                if (p.message && p.message.content) {
                  c = p.message.content;
                  if (p.done) { self.postMessage({ type: 'done', id: m.id }); delete self._controllers[m.id]; return; }
                } else if (p.choices && p.choices[0] && p.choices[0].delta) {
                  c = p.choices[0].delta.content;
                }
                if (c) {
                  self.postMessage({ type: 'chunk', text: c, id: m.id });
                }
              } catch(e) {}
            }
          }
          rd();
        }).catch(function(err) {
          if (err.name !== 'AbortError') {
            self.postMessage({ type: 'error', text: err.message, id: m.id });
          }
        });
      }
      rd();
    }).catch(function(err) {
      self.postMessage({ type: 'error', text: err.message, id: m.id });
    });
  } else if (m.type === 'abort') {
    if (self._controllers && self._controllers[m.id]) {
      self._controllers[m.id].abort();
      delete self._controllers[m.id];
    }
  }
};
