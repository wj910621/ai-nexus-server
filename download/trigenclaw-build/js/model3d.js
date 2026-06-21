/**
 * TriGenClaw 3D Model Module (Meshy)
 */
(function() {
  'use strict';

  var API_BASE = 'https://j3trisheng.com';

  // Text to 3D
  window.D3_TEXT_TO_3D = function() {
    var prompt = document.getElementById('d3TextPrompt').value.trim();
    var style = document.getElementById('d3TextStyle').value;
    var r = document.getElementById('d3TextResult');
    var viewer = document.getElementById('d3ModelViewer');

    if (!prompt) { showToast('Please enter a 3D description'); return; }
    
    r.style.display = 'block';
    r.innerHTML = '<span class="spinner"></span> Submitting 3D model...<p style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px">Generation takes 5-15 minutes, auto-polling...</p>';

    fetch(API_BASE + '/api/meshy/txt2d', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: prompt, style: style })
    }).then(function(resp) { return resp.json(); }).then(function(data) {
      if (data.id || data.result) {
        var taskId = data.id || data.result;
        r.innerHTML = '<div style="text-align:center"><div style="font-size:2rem">⏳</div><p>Generating...</p><p id="d3Progress" style="font-size:0.75rem;color:var(--text-secondary)">Initializing</p></div>';
        pollViewer(taskId, r, viewer);
      } else {
        r.innerHTML = '<p style="color:var(--orange)">⚠️ ' + (data.message || data.error || 'Submission failed') + '</p>';
      }
    }).catch(function(e) {
      r.innerHTML = '<p style="color:var(--orange)">❌ Connection failed: ' + e.message + '</p>';
    });
  };

  // Image to 3D
  window.D3_IMAGE_TO_3D = function() {
    var file = document.getElementById('d3ImageInput').files[0];
    var r = document.getElementById('d3ImageResult');
    var viewer = document.getElementById('d3ModelViewer');

    if (!file) { showToast('Please select a reference image'); return; }

    r.style.display = 'block';
    r.innerHTML = '<span class="spinner"></span> Uploading image and submitting...<p style="font-size:0.75rem;color:var(--text-secondary);margin-top:4px">Generation takes 5-15 minutes</p>';

    var reader = new FileReader();
    reader.onload = function(e) {
      var imgData = e.target.result;
      fetch(API_BASE + '/api/meshy/img2d', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_data: imgData, prompt: document.getElementById('d3TextPrompt').value.trim() })
      }).then(function(resp) { return resp.json(); }).then(function(data) {
        if (data.id || data.result) {
          var taskId = data.id || data.result;
          r.innerHTML = '<div style="text-align:center"><div style="font-size:2rem">⏳</div><p>Image to 3D generating...</p><p id="d3ProgressImg" style="font-size:0.75rem;color:var(--text-secondary)">Initializing</p></div>';
          pollViewer(taskId, r, viewer);
        } else {
          r.innerHTML = '<p style="color:var(--orange)">⚠️ ' + (data.message || data.error || 'Submission failed') + '</p>';
        }
      }).catch(function(err) {
        r.innerHTML = '<p style="color:var(--orange)">❌ Connection failed: ' + err.message + '</p>';
      });
    };
    reader.readAsDataURL(file);
  };

  // Polling helper
  function pollViewer(taskId, r, viewer) {
    var done = false;
    var attempts = 0;

    function poll() {
      if (done || attempts >= 80) {
        if (!done) r.innerHTML = '<p style="color:var(--orange)">⏰ Polling timeout, please refresh later</p>';
        return;
      }
      attempts++;
      setTimeout(function() {
        fetch(API_BASE + '/api/meshy/result/' + taskId)
          .then(function(resp) { return resp.json(); })
          .then(function(d) {
            var progressEl = document.getElementById('d3Progress') || document.getElementById('d3ProgressImg');
            if (progressEl) progressEl.textContent = 'Progress ' + Math.round(d.progress || 0) + '%';

            if (d.status === 'SUCCEEDED' || (d.progress && d.progress >= 100)) {
              var url = d.model_urls && d.model_urls.glb;
              if (url) {
                r.style.display = 'none';
                viewer.style.display = 'block';
                document.getElementById('d3Viewer').src = url;
                viewer.scrollIntoView({ behavior: 'smooth' });
                showToast('✅ 3D model generated!');
              } else {
                r.innerHTML = '<p style="color:var(--green)">✅ Generated, loading model...</p>';
              }
              done = true;
            } else if (d.status === 'FAILED') {
              r.innerHTML = '<p style="color:var(--orange)">❌ Generation failed, please retry</p>';
              done = true;
            } else {
              poll();
            }
          }).catch(function() { poll(); });
      }, 15000);
    }
    poll();
  }

  function showToast(msg) {
    var el = document.getElementById('toastContainer');
    if (!el) return;
    var t = document.createElement('div');
    t.className = 'toast';
    t.textContent = msg;
    el.appendChild(t);
    setTimeout(function() { t.remove(); }, 3000);
  }
})();
