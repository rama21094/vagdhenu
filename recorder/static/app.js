const $ = (id) => document.getElementById(id);
const state = {
  projects: [], project: null, items: [], index: 0, stream: null, recorder: null,
  chunks: [], startedAt: 0, timerHandle: null, audioContext: null, analyser: null,
  animation: null, pending: null, microphone: localStorage.getItem("vagdhenu-mic") || "",
};

async function api(path, options = {}) {
  const response = await fetch(path, {headers: {"Content-Type": "application/json"}, ...options});
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function toast(message) {
  $("toast").textContent = message; $("toast").classList.add("show");
  clearTimeout(toast.timer); toast.timer = setTimeout(() => $("toast").classList.remove("show"), 2600);
}

async function load(project) {
  const payload = await api(`/api/bootstrap${project ? `?project=${encodeURIComponent(project)}` : ""}`);
  state.projects = payload.projects; state.project = payload.project; state.items = payload.project.items;
  const firstPending = state.items.findIndex(item => item.recording?.status !== "accepted");
  state.index = Math.max(0, firstPending);
  renderProjectOptions(); render();
}

function renderProjectOptions() {
  $("projectSelect").innerHTML = state.projects.map(project => `<option value="${escapeHtml(project.id)}" ${project.id === state.project.id ? "selected" : ""}>${escapeHtml(project.name)}</option>`).join("");
}

function escapeHtml(value = "") { const node = document.createElement("span"); node.textContent = value; return node.innerHTML; }
function current() { return state.items[state.index]; }

function render() {
  if (!state.items.length) return;
  const item = current(); const accepted = state.items.filter(value => value.recording?.status === "accepted").length;
  $("collectionLabel").textContent = item.collection || state.project.name;
  const parts = [];
  if (item.dasakam) parts.push(`Dasakam ${item.dasakam}`); if (item.verse) parts.push(`Verse ${item.verse}`); parts.push(`Quarter ${item.quarter || state.index + 1}`);
  $("locationLabel").textContent = parts.join(" · "); $("verseText").textContent = item.text;
  $("meterPill").textContent = item.meter || "Unlabelled metre"; $("syllableLabel").textContent = item.syllables ? `${item.syllables} syllables` : "Syllables not labelled";
  $("takeLabel").textContent = item.recording ? `Take ${item.recording.take} · ${item.recording.status}` : "No takes yet";
  $("existingPlayback").classList.toggle("hidden", !item.recording?.audio_url); $("existingPlayback").src = item.recording?.audio_url || "";
  $("progressText").textContent = `${accepted.toLocaleString()} / ${state.items.length.toLocaleString()}`;
  $("progressBar").style.width = `${100 * accepted / state.items.length}%`;
  $("previousButton").disabled = state.index === 0; $("nextButton").disabled = state.index === state.items.length - 1;
  $("reviewPanel").classList.add("hidden"); state.pending = null; renderQueue();
}

function renderQueue() {
  const search = $("queueSearch").value.toLowerCase(); const filter = $("queueFilter").value;
  const visible = state.items.map((item, index) => ({item, index})).filter(({item}) => {
    const status = item.recording?.status || "pending";
    const matchesFilter = filter === "all" || (filter === "pending" ? status === "pending" : filter === "review" ? status === "recorded" : status === filter);
    return matchesFilter && (!search || item.text.toLowerCase().includes(search) || `${item.dasakam || ""}.${item.verse || ""}.${item.quarter || ""}`.includes(search));
  });
  $("queueList").innerHTML = visible.map(({item, index}) => {
    const status = item.recording?.status || "pending"; const label = item.dasakam ? `${item.dasakam}.${item.verse}.${item.quarter}` : `Verse ${item.verse} · Q${item.quarter}`;
    return `<button class="queue-item ${index === state.index ? "active" : ""}" data-index="${index}" role="listitem"><span class="queue-number">${index + 1}</span><span class="queue-copy"><strong>${escapeHtml(label)}</strong><span>${escapeHtml(item.text)}</span></span><span class="status-dot ${status}"></span></button>`;
  }).join("") || `<p class="recording-hint">No matching quarters.</p>`;
  $("queueList").querySelectorAll(".queue-item").forEach(button => button.addEventListener("click", () => { state.index = Number(button.dataset.index); render(); }));
  requestAnimationFrame(() => $("queueList").querySelector(".active")?.scrollIntoView({block: "nearest"}));
}

async function ensureMicrophone() {
  if (state.stream?.active) return state.stream;
  const constraints = {audio: {channelCount: 1, echoCancellation: false, noiseSuppression: false, autoGainControl: false, ...(state.microphone ? {deviceId: {exact: state.microphone}} : {})}};
  state.stream = await navigator.mediaDevices.getUserMedia(constraints);
  state.audioContext = new AudioContext(); const source = state.audioContext.createMediaStreamSource(state.stream);
  state.analyser = state.audioContext.createAnalyser(); state.analyser.fftSize = 2048; source.connect(state.analyser); drawMeter(); await populateMicrophones();
  return state.stream;
}

async function populateMicrophones() {
  const devices = (await navigator.mediaDevices.enumerateDevices()).filter(device => device.kind === "audioinput");
  $("microphoneSelect").innerHTML = devices.map((device, index) => `<option value="${escapeHtml(device.deviceId)}" ${device.deviceId === state.microphone ? "selected" : ""}>${escapeHtml(device.label || `Microphone ${index + 1}`)}</option>`).join("");
  if (!state.microphone && devices[0]) state.microphone = devices[0].deviceId;
}

function drawMeter() {
  const canvas = $("levelCanvas"), context = canvas.getContext("2d"), data = new Float32Array(state.analyser.fftSize);
  const loop = () => {
    state.analyser.getFloatTimeDomainData(data); let sum = 0, peak = 0;
    for (const sample of data) { sum += sample * sample; peak = Math.max(peak, Math.abs(sample)); }
    const rms = Math.sqrt(sum / data.length); const db = 20 * Math.log10(rms + 1e-8); const width = canvas.width, height = canvas.height;
    context.clearRect(0, 0, width, height); context.fillStyle = "#e8e1d5"; context.fillRect(0, 0, width, height);
    const level = Math.max(0, Math.min(1, (db + 60) / 60)); const gradient = context.createLinearGradient(0, 0, width, 0); gradient.addColorStop(0, "#8bad94"); gradient.addColorStop(.72, "#2f8064"); gradient.addColorStop(.9, "#d59a42"); gradient.addColorStop(1, "#b84836"); context.fillStyle = gradient; context.fillRect(0, 0, width * level, height);
    context.fillStyle = "rgba(255,255,255,.75)"; context.fillRect(width * Math.max(0, Math.min(1, (20 * Math.log10(peak + 1e-8) + 60) / 60)) - 2, 0, 3, height);
    state.animation = requestAnimationFrame(loop);
  }; loop();
}

async function toggleRecording() { state.recorder?.state === "recording" ? stopRecording() : startRecording(); }
async function startRecording() {
  try {
    const stream = await ensureMicrophone(); state.chunks = [];
    const mime = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(value => MediaRecorder.isTypeSupported(value));
    state.recorder = new MediaRecorder(stream, mime ? {mimeType: mime} : undefined);
    state.recorder.ondataavailable = event => { if (event.data.size) state.chunks.push(event.data); };
    state.recorder.onstop = reviewRecording; state.recorder.start(250); state.startedAt = performance.now();
    $("recordButton").classList.add("recording"); $("recordLabel").textContent = "Stop"; $("reviewPanel").classList.add("hidden");
    state.timerHandle = setInterval(updateTimer, 50); updateTimer();
  } catch (error) { toast(`Microphone unavailable: ${error.message}`); }
}
function stopRecording() { if (state.recorder?.state !== "recording") return; state.recorder.stop(); clearInterval(state.timerHandle); $("recordButton").classList.remove("recording"); $("recordLabel").textContent = "Record"; }
function updateTimer() { const seconds = (performance.now() - state.startedAt) / 1000; $("timer").textContent = `${String(Math.floor(seconds / 60)).padStart(2,"0")}:${(seconds % 60).toFixed(1).padStart(4,"0")}`; }

async function reviewRecording() {
  try {
    const blob = new Blob(state.chunks, {type: state.recorder.mimeType}); const decoded = await state.audioContext.decodeAudioData(await blob.arrayBuffer());
    const rendered = await resampleMono(decoded, 24000); const samples = rendered.getChannelData(0); const wav = encodeWav(samples, 24000); const metrics = measure(samples, 24000);
    state.pending = {wav, metrics, url: URL.createObjectURL(wav)}; $("playback").src = state.pending.url; renderQuality(metrics); $("reviewPanel").classList.remove("hidden"); $("playback").play().catch(() => {});
  } catch (error) { toast(`Could not prepare recording: ${error.message}`); }
}

async function resampleMono(buffer, sampleRate) {
  const length = Math.ceil(buffer.duration * sampleRate); const offline = new OfflineAudioContext(1, length, sampleRate); const mono = offline.createBuffer(1, buffer.length, buffer.sampleRate); const output = mono.getChannelData(0);
  for (let channel = 0; channel < buffer.numberOfChannels; channel++) { const input = buffer.getChannelData(channel); for (let i = 0; i < input.length; i++) output[i] += input[i] / buffer.numberOfChannels; }
  const source = offline.createBufferSource(); source.buffer = mono; source.connect(offline.destination); source.start(); return offline.startRendering();
}

function encodeWav(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2), view = new DataView(buffer); const write = (offset, text) => [...text].forEach((character, i) => view.setUint8(offset + i, character.charCodeAt(0)));
  write(0,"RIFF"); view.setUint32(4,36 + samples.length * 2,true); write(8,"WAVE"); write(12,"fmt "); view.setUint32(16,16,true); view.setUint16(20,1,true); view.setUint16(22,1,true); view.setUint32(24,sampleRate,true); view.setUint32(28,sampleRate*2,true); view.setUint16(32,2,true); view.setUint16(34,16,true); write(36,"data"); view.setUint32(40,samples.length*2,true);
  for (let i=0; i<samples.length; i++) { const value=Math.max(-1,Math.min(1,samples[i])); view.setInt16(44+i*2, value<0 ? value*0x8000 : value*0x7fff, true); } return new Blob([view],{type:"audio/wav"});
}

function measure(samples, sampleRate) {
  let sum=0, peak=0, clipped=0, silent=0; for (const sample of samples) { const absolute=Math.abs(sample); sum+=sample*sample; peak=Math.max(peak,absolute); if(absolute>=.995) clipped++; if(absolute<.008) silent++; }
  const rms=Math.sqrt(sum/samples.length); return {duration_s:+(samples.length/sampleRate).toFixed(3), sample_rate:sampleRate, peak_dbfs:+(20*Math.log10(peak+1e-12)).toFixed(2), rms_dbfs:+(20*Math.log10(rms+1e-12)).toFixed(2), clipped_fraction:+(clipped/samples.length).toFixed(7), silence_fraction:+(silent/samples.length).toFixed(4)};
}

function renderQuality(metrics) {
  const values=[
    ["Duration",`${metrics.duration_s.toFixed(1)} s`,metrics.duration_s>=2&&metrics.duration_s<=15],
    ["Peak",`${metrics.peak_dbfs.toFixed(1)} dB`,metrics.peak_dbfs<=-1&&metrics.peak_dbfs>=-12],
    ["Loudness",`${metrics.rms_dbfs.toFixed(1)} dB`,metrics.rms_dbfs>=-32&&metrics.rms_dbfs<=-14],
    ["Clipping",`${(metrics.clipped_fraction*100).toFixed(3)}%`,metrics.clipped_fraction===0],
    ["Silence",`${(metrics.silence_fraction*100).toFixed(0)}%`,metrics.silence_fraction<.7],
  ]; $("qualityGrid").innerHTML=values.map(([label,value,good])=>`<div class="quality-chip ${good?"good":"warn"}"><strong>${value}</strong><span>${label}</span></div>`).join("");
}

function blobBase64(blob) { return new Promise((resolve,reject)=>{ const reader=new FileReader(); reader.onload=()=>resolve(reader.result.split(",")[1]); reader.onerror=reject; reader.readAsDataURL(blob); }); }
async function savePending(accepted) {
  if (!state.pending) return; try { const item=current(); const result=await api("/api/recordings",{method:"POST",body:JSON.stringify({project:state.project.id,item_id:item.id,audio_base64:await blobBase64(state.pending.wav),accepted,microphone:$("microphoneSelect").selectedOptions[0]?.textContent||"",notes:$("notes").value,metrics:state.pending.metrics})}); item.recording=result; toast(accepted?"Take accepted":"Saved for review"); if(accepted) move(1); else render(); } catch(error){ toast(error.message); }
}
function discard() { if(state.pending?.url) URL.revokeObjectURL(state.pending.url); state.pending=null; $("reviewPanel").classList.add("hidden"); $("notes").value=""; $("timer").textContent="00:00.0"; }
function move(delta) { if(state.recorder?.state==="recording") return; state.index=Math.max(0,Math.min(state.items.length-1,state.index+delta)); render(); }

$("recordButton").addEventListener("click",toggleRecording); $("previousButton").addEventListener("click",()=>move(-1)); $("nextButton").addEventListener("click",()=>move(1));
$("discardButton").addEventListener("click",discard); $("acceptButton").addEventListener("click",()=>savePending(true)); $("saveReviewButton").addEventListener("click",()=>savePending(false));
$("queueSearch").addEventListener("input",renderQueue); $("queueFilter").addEventListener("change",renderQueue); $("projectSelect").addEventListener("change",event=>load(event.target.value));
$("settingsButton").addEventListener("click",async()=>{ try{await ensureMicrophone(); $("settingsDialog").showModal();}catch(error){toast(error.message);} });
$("microphoneSelect").addEventListener("change",event=>{ state.microphone=event.target.value; localStorage.setItem("vagdhenu-mic",state.microphone); state.stream?.getTracks().forEach(track=>track.stop()); state.stream=null; cancelAnimationFrame(state.animation); toast("Microphone changed"); });
$("importButton").addEventListener("click",()=>$("importDialog").showModal());
$("importForm").addEventListener("submit",async event=>{ if(event.submitter?.value==="cancel") return; event.preventDefault(); try{const project=await api("/api/import",{method:"POST",body:JSON.stringify({name:$("importName").value,text:$("importText").value})}); $("importDialog").close(); await load(project.id); toast(`Imported ${project.items.length} quarters`);}catch(error){toast(error.message);} });
document.addEventListener("keydown",event=>{ if(["INPUT","TEXTAREA","SELECT"].includes(document.activeElement.tagName))return; if(event.key.toLowerCase()==="r"){event.preventDefault();toggleRecording();} if(event.code==="Space"&&state.pending){event.preventDefault();$("playback").paused?$("playback").play():$("playback").pause();} if(event.key==="Enter"&&state.pending){event.preventDefault();savePending(true);} });
load().catch(error=>toast(error.message));
