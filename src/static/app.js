const SPEAKER_COLORS = ['#42a5f5', '#ef5350', '#66bb6a', '#ffa726', '#ab47bc', '#26c6da'];

let ws = null;
let audioContext = null;
let stream = null;
let processor = null;
let isRecording = false;
let mode = 'dialogue';
let speakerMap = {};
let recordingStartTime = 0;
let timerInterval = null;

const btnToggle = document.getElementById('btnToggle');
const selMode = document.getElementById('selMode');
const btnSummarize = document.getElementById('btnSummarize');
const statusEl = document.getElementById('status');
const transcriptEl = document.getElementById('transcript');
const speakersEl = document.getElementById('speakers');
const audioPlayer = document.getElementById('audioPlayer');
const recordingTimer = document.getElementById('recordingTimer');

function fmtOffset(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return m + ':' + String(s).padStart(2, '0');
}

function fmtClock(ms) {
  const d = new Date(ms);
  return d.toLocaleTimeString('zh-CN', { hour12: false });
}

function startTimer() {
  recordingStartTime = Date.now();
  recordingTimer.classList.remove('hidden');
  ensureRuler();
  const ruler = document.getElementById('timelineRuler');
  if (ruler) ruler.classList.add('visible');
  updateTimer();
  timerInterval = setInterval(updateTimer, 1000);
}

function updateTimer() {
  const elapsed = (Date.now() - recordingStartTime) / 1000;
  recordingTimer.textContent = fmtOffset(elapsed);
  updateRuler(Math.floor(elapsed));
}

function stopTimer() {
  clearInterval(timerInterval);
  timerInterval = null;
  recordingTimer.classList.add('hidden');
}

function updateRuler(totalSec) {
  const ruler = document.getElementById('timelineRuler');
  if (!ruler) return;
  const fill = ruler.querySelector('.ruler-fill');
  if (!fill) return;
  const existingMarks = ruler.querySelectorAll('.ruler-mark, .ruler-label');
  existingMarks.forEach(el => el.remove());
  const span = Math.max(totalSec, 30);
  [10, 20, 30].forEach(sec => {
    if (sec > totalSec + 5) return;
    const pct = (sec / span) * 100;
    const mark = document.createElement('div');
    mark.className = 'ruler-mark';
    mark.style.left = pct + '%';
    ruler.querySelector('.ruler-track').appendChild(mark);
    const label = document.createElement('div');
    label.className = 'ruler-label';
    label.style.left = pct + '%';
    label.textContent = fmtOffset(sec);
    ruler.querySelector('.ruler-track').appendChild(label);
  });
}

function connectWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws';
  const url = `${protocol}://${location.host}/ws`;
  ws = new WebSocket(url);
  ws.onopen = () => {
    statusEl.textContent = 'Connected';
    statusEl.className = 'status connected';
    btnToggle.disabled = false;
    btnSummarize.disabled = false;
    ws.send(JSON.stringify({ type: 'mode', mode }));
  };
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    handleMessage(msg);
  };
  ws.onclose = () => {
    stopRecording();
    statusEl.textContent = 'Disconnected';
    statusEl.className = 'status idle';
    btnToggle.disabled = true;
    btnSummarize.disabled = true;
    btnToggle.textContent = 'Start Recording';
    btnToggle.classList.remove('recording');
    setTimeout(connectWebSocket, 2000);
  };
  ws.onerror = () => {
    ws.close();
  };
}

function handleMessage(msg) {
  if (msg.type === 'transcript') {
    addTranscript(msg.speaker, msg.text, msg.start, msg.end);
  } else if (msg.type === 'response') {
    addResponse('assistant', msg.text);
    if (msg.audio) {
      playAudio(msg.audio);
    }
  } else if (msg.type === 'tool_start') {
    addToolCall(msg.name, msg.arguments, msg.call_id);
  } else if (msg.type === 'tool_result') {
    updateToolCall(msg.call_id, msg.success, msg.output);
  } else if (msg.type === 'interrupt') {
    audioPlayer.pause();
    audioPlayer.src = '';
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'tts_end' }));
    }
    if (isRecording) {
      statusEl.textContent = 'Listening...';
      statusEl.className = 'status recording';
    }
  } else if (msg.type === 'error') {
    btnSummarize.textContent = 'Summarize';
    btnSummarize.classList.remove('summarizing');
    btnSummarize.disabled = false;
    addSystemMessage('Error: ' + msg.message);
  } else if (msg.type === 'mode_set') {
    mode = msg.mode;
    selMode.value = mode;
  } else if (msg.type === 'busy') {
    if (msg.status) {
      statusEl.textContent = 'AI Speaking';
      statusEl.className = 'status busy';
    } else if (isRecording) {
      statusEl.textContent = 'Recording';
      statusEl.className = 'status recording';
    } else {
      statusEl.textContent = 'Connected';
      statusEl.className = 'status connected';
    }
  } else if (msg.type === 'summarizing') {
    btnSummarize.textContent = 'Summarizing...';
    btnSummarize.classList.add('summarizing');
    btnSummarize.disabled = true;
  } else if (msg.type === 'summary') {
    btnSummarize.textContent = 'Summarize';
    btnSummarize.classList.remove('summarizing');
    btnSummarize.disabled = false;
    addSummary(msg.text);
  }
}

function ensureRuler() {
  if (!document.getElementById('timelineRuler')) {
    const ruler = document.createElement('div');
    ruler.id = 'timelineRuler';
    ruler.className = 'timeline-ruler visible';
    ruler.innerHTML = '<div class="ruler-track"><div class="ruler-fill"></div></div>';
    transcriptEl.parentNode.insertBefore(ruler, transcriptEl);
  }
}

function addTranscript(speaker, text, start, end) {
  if (transcriptEl.querySelector('.placeholder')) {
    transcriptEl.innerHTML = '';
  }
  ensureRuler();

  const gotSpeaker = ensureSpeaker(speaker);
  const clockTime = recordingStartTime ? fmtClock(recordingStartTime + start * 1000) : '';
  const duration = (end - start).toFixed(1);
  const color = getSpeakerColor(speaker);

  const totalSec = recordingStartTime ? (Date.now() - recordingStartTime) / 1000 : 30;
  const span = Math.max(totalSec, 30);
  const barLeft = (start / span) * 100;
  const barWidth = Math.max(((end - start) / span) * 100, 1);

  const isAI = gotSpeaker === 'assistant' || gotSpeaker.startsWith('AI');
  const div = document.createElement('div');
  div.className = 'message ' + (isAI ? 'assistant' : 'user');
  div.innerHTML =
    '<div class="msg-header">' +
      '<span class="speaker-label" style="color:' + color + '">' + gotSpeaker + '</span>' +
      '<span class="msg-time">' +
        (clockTime ? clockTime + '  ' : '') +
        '[' + fmtOffset(start) + ' → ' + fmtOffset(end) + ']' +
        '  <span style="opacity:0.5">' + duration + 's</span>' +
      '</span>' +
    '</div>' +
    '<div class="text">' + escapeHtml(text) + '</div>' +
    '<div class="time-bar"><div class="bar-inner" style="left:' + barLeft + '%;width:' + barWidth + '%;background:' + color + '"></div></div>';

  transcriptEl.appendChild(div);
  updateRuler(Math.floor(span));
  requestAnimationFrame(() => {
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
  });
}

function addResponse(role, text) {
  if (transcriptEl.querySelector('.placeholder')) {
    transcriptEl.innerHTML = '';
  }
  const now = recordingStartTime ? fmtClock(Date.now()) : '';
  const div = document.createElement('div');
  div.className = 'message assistant';
  div.innerHTML =
    '<div class="msg-header">' +
      '<span class="speaker-label" style="color:#66bb6a">AI Assistant</span>' +
      '<span class="msg-time">' + now + '</span>' +
    '</div>' +
    '<div class="text">' + escapeHtml(text) + '</div>';
  transcriptEl.appendChild(div);
  requestAnimationFrame(() => {
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
  });
}

function addSystemMessage(text) {
  const div = document.createElement('div');
  div.className = 'message';
  div.style.background = '#3a1a1a';
  div.innerHTML = '<div class="text" style="color:#ef5350">' + escapeHtml(text) + '</div>';
  transcriptEl.appendChild(div);
}

function ensureSpeaker(speaker) {
  if (speakerMap[speaker]) return speakerMap[speaker];
  if (speaker.startsWith('SPEAKER_')) {
    const num = parseInt(speaker.split('_')[1]);
    const name = 'Person ' + (num + 1);
    speakerMap[speaker] = name;
    updateSpeakerList();
    return name;
  }
  speakerMap[speaker] = speaker;
  updateSpeakerList();
  return speaker;
}

function getSpeakerColor(speaker) {
  if (speaker.startsWith('SPEAKER_')) {
    const num = parseInt(speaker.split('_')[1]);
    return SPEAKER_COLORS[num % SPEAKER_COLORS.length];
  }
  const keys = Object.keys(speakerMap);
  const idx = keys.indexOf(speaker);
  return SPEAKER_COLORS[idx >= 0 ? idx % SPEAKER_COLORS.length : 0];
}

function updateSpeakerList() {
  speakersEl.innerHTML = '';
  for (const [id, name] of Object.entries(speakerMap)) {
    const chip = document.createElement('span');
    chip.className = 'speaker-chip';
    chip.style.color = getSpeakerColor(id);
    chip.style.borderColor = getSpeakerColor(id);
    chip.textContent = name;
    speakersEl.appendChild(chip);
  }
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function addToolCall(name, args, callId) {
  if (transcriptEl.querySelector('.placeholder')) {
    transcriptEl.innerHTML = '';
  }
  const div = document.createElement('div');
  div.className = 'message tool-call';
  div.id = 'tool-' + callId;
  const label = name === 'run_command' ? 'Command' : name === 'read_file' ? 'Read File' : name === 'list_directory' ? 'List Dir' : name;
  const argsStr = args && Object.keys(args).length ? escapeHtml(JSON.stringify(args)) : '';
  div.innerHTML =
    '<div class="msg-header">' +
      '<span class="tool-icon">&#9881;</span>' +
      '<span class="speaker-label" style="color:#ffa726">Tool: ' + label + '</span>' +
      '<span class="tool-args">' + argsStr + '</span>' +
    '</div>' +
    '<div class="tool-status">Running...</div>';
  transcriptEl.appendChild(div);
  requestAnimationFrame(() => {
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
  });
}

function updateToolCall(callId, success, output) {
  const div = document.getElementById('tool-' + callId);
  if (!div) return;
  const statusDiv = div.querySelector('.tool-status');
  if (statusDiv) {
    statusDiv.textContent = success ? 'Done' : 'Failed';
    statusDiv.style.color = success ? '#66bb6a' : '#ef5350';
  }
  const pre = document.createElement('pre');
  pre.className = 'tool-output';
  pre.textContent = typeof output === 'string' ? output : JSON.stringify(output, null, 2);
  div.appendChild(pre);
  requestAnimationFrame(() => {
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
  });
}

function playAudio(base64Audio) {
  const blob = base64ToBlob(base64Audio, 'audio/mp3');
  const url = URL.createObjectURL(blob);
  audioPlayer.src = url;
  audioPlayer.play().catch(() => {});
  audioPlayer.onended = () => {
    URL.revokeObjectURL(url);
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'tts_end' }));
    }
  };
}

function base64ToBlob(base64, mimeType) {
  const byteChars = atob(base64);
  const byteArrays = [];
  for (let offset = 0; offset < byteChars.length; offset += 512) {
    const slice = byteChars.slice(offset, offset + 512);
    const byteNumbers = new Array(slice.length);
    for (let i = 0; i < slice.length; i++) {
      byteNumbers[i] = slice.charCodeAt(i);
    }
    byteArrays.push(new Uint8Array(byteNumbers));
  }
  return new Blob(byteArrays, { type: mimeType });
}

async function startRecording() {
  if (isRecording) return;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { sampleRate: 16000, channelCount: 1, echoCancellation: true, noiseSuppression: true }
    });
    audioContext = new AudioContext({ sampleRate: 16000 });
    const source = audioContext.createMediaStreamSource(stream);
    processor = audioContext.createScriptProcessor(4096, 1, 1);
    source.connect(processor);
    processor.connect(audioContext.destination);
    processor.onaudioprocess = (event) => {
      if (!isRecording || !ws || ws.readyState !== WebSocket.OPEN) return;
      const input = event.inputBuffer.getChannelData(0);
      const int16 = new Int16Array(input.length);
      for (let i = 0; i < input.length; i++) {
        int16[i] = Math.max(-32768, Math.min(32767, Math.round(input[i] * 32767)));
      }
      const base64 = btoa(String.fromCharCode(...new Uint8Array(int16.buffer)));
      ws.send(JSON.stringify({ type: 'audio', data: base64 }));
    };
    isRecording = true;
    startTimer();
    btnToggle.textContent = 'Stop Recording';
    btnToggle.classList.add('recording');
    statusEl.textContent = 'Recording';
    statusEl.className = 'status recording';
  } catch (err) {
    console.error('Microphone error:', err);
    alert('Cannot access microphone: ' + err.message);
  }
}

function stopRecording() {
  isRecording = false;
  stopTimer();
  if (processor) { processor.disconnect(); processor = null; }
  if (stream) { stream.getTracks().forEach(t => t.stop()); stream = null; }
  if (audioContext) { audioContext.close(); audioContext = null; }
  btnToggle.textContent = 'Start Recording';
  btnToggle.classList.remove('recording');
  if (ws && ws.readyState === WebSocket.OPEN) {
    statusEl.textContent = 'Connected';
    statusEl.className = 'status connected';
  }
}

btnToggle.addEventListener('click', () => {
  if (isRecording) {
    stopRecording();
  } else {
    startRecording();
  }
});

selMode.addEventListener('change', () => {
  mode = selMode.value;
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'mode', mode }));
  }
});

function addSummary(text) {
  if (transcriptEl.querySelector('.placeholder')) {
    transcriptEl.innerHTML = '';
  }
  const now = recordingStartTime ? fmtClock(Date.now()) : '';
  const div = document.createElement('div');
  div.className = 'message';
  div.style.cssText = 'background:#1a1030;border:1px solid #7c4dff;';
  div.innerHTML =
    '<div class="msg-header">' +
      '<span class="speaker-label" style="color:#b388ff">Summary</span>' +
      '<span class="msg-time">' + now + '</span>' +
    '</div>' +
    '<div class="text">' + escapeHtml(text) + '</div>';
  transcriptEl.appendChild(div);
  requestAnimationFrame(() => {
    div.scrollIntoView({ behavior: 'smooth', block: 'end' });
  });
}

function collectAllTranscripts() {
  const messages = transcriptEl.querySelectorAll('.message.user .text');
  const lines = [];
  for (const el of messages) {
    lines.push(el.textContent.trim());
  }
  return lines.join('\n');
}

btnSummarize.addEventListener('click', () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const text = collectAllTranscripts();
  if (!text.trim()) {
    alert('No transcripts to summarize.');
    return;
  }
  ws.send(JSON.stringify({ type: 'summarize', text }));
});

connectWebSocket();
