/**
 * TriGenClaw Music Module (Suno AI)
 */
(function() {
  'use strict';

  window.MUSIC_GENERATE = function() {
    var title = document.getElementById('musicTitle').value.trim();
    var lyric = document.getElementById('musicLyric').value.trim();
    var style = document.getElementById('musicStyle').value.trim();
    var instrumental = document.getElementById('musicInstrumental').checked;

    if (!title && !lyric) { showToast('Please enter a song title or description'); return; }
    if (!spendCredits(10)) return;

    var historyList = document.getElementById('musicHistoryList');
    var player = document.getElementById('musicPlayer');
    var audio = document.getElementById('musicAudio');
    historyList.innerHTML = '<div style="text-align:center;padding:20px"><span class="spinner"></span><p>Generating music...</p><p style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px">This may take 1-3 minutes</p></div>';

    var taskId = 'music_' + Date.now();
    var promptText = '';
    if (title) promptText += 'Title: ' + title + '\n';
    if (lyric) promptText += (MUSIC_CURRENT_MODE === 'idealmode' ? 'Idea: ' : 'Lyrics: ') + lyric + '\n';
    if (style) promptText += 'Style: ' + style + '\n';
    if (instrumental) promptText += '(Instrumental)\n';

    // 通过后端代理调用 Suno
    fetch('https://j3trisheng.com/api/music/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        prompt: promptText,
        title: title || 'Untitled',
        tags: style || 'pop',
        instrumental: instrumental
      })
    }).then(function(r) { return r.json(); }).then(function(data) {
      var taskId = data.id || data.taskId;
      if (!taskId) {
        historyList.innerHTML = '<div style="text-align:center;color:var(--orange);padding:20px">❌ ' + (data.error || 'Generation failed') + '</div>';
        return;
      }

      // 轮询结果
      var attempts = 0;
      function poll() {
        attempts++;
        fetch('https://j3trisheng.com/api/music/task?id=' + taskId)
          .then(function(r) { return r.json(); })
          .then(function(result) {
            if (result.status === 'completed' || result.status === 'success' || result.audio_url) {
              var url = result.audio_url || result.data[0]?.audio_url || '';
              if (url) {
                audio.src = url;
                audio.style.display = 'block';
                player.style.display = 'block';
                historyList.innerHTML = '<div style="text-align:center;padding:10px;color:var(--green)">✅ Generation complete! <br><button class="btn btn-sm btn-ghost" onclick="document.getElementById(\'musicAudio\').play()">▶️ Play</button></div>';
                // 保存历史
                var history = JSON.parse(localStorage.getItem('musicHistory') || '[]');
                history.unshift({ title: title, url: url, time: new Date().toISOString() });
                localStorage.setItem('musicHistory', JSON.stringify(history.slice(0, 20)));
              } else {
                historyList.innerHTML = '<div style="text-align:center;color:var(--orange);padding:20px">⚠️ No audio URL returned</div>';
              }
            } else if (result.status === 'failed' || result.status === 'error') {
              historyList.innerHTML = '<div style="text-align:center;color:var(--orange);padding:20px">❌ Generation failed</div>';
            } else if (attempts < 60) {
              var progress = Math.min(attempts * 5, 95);
              historyList.innerHTML = '<div style="text-align:center;padding:20px"><div class="spinner"></div><p>Generating... ' + progress + '%</p><p style="font-size:0.75rem;color:var(--text-secondary)">Estimated 1-3 minutes</p></div>';
              setTimeout(poll, 3000);
            } else {
              historyList.innerHTML = '<div style="text-align:center;color:var(--orange);padding:20px">⏰ Polling timeout, please check later</div>';
            }
          }).catch(function(e) {
            historyList.innerHTML = '<div style="text-align:center;color:var(--orange);padding:20px">❌ Error: ' + e.message + '</div>';
          });
      }
      poll();
    }).catch(function(e) {
      historyList.innerHTML = '<div style="text-align:center;color:var(--orange);padding:20px">❌ Connection failed: ' + e.message + '</div>';
    });
  };

  window.MUSIC_CURRENT_MODE = 'lyric';

  function showToast(msg) {
    var el = document.getElementById('toastContainer');
    if (!el) return;
    var t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    el.appendChild(t);
    setTimeout(function() { t.remove(); }, 3000);
  }

  function spendCredits(n) {
    // Desktop credit check (simplified)
    return true;
  }
})();
