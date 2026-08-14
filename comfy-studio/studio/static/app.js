const state = {
  mode: "t2v",
  models: [],
  presets: null,
  imageFile: null,
  poll: null,
  jobId: null,
  downloadPoll: null,
  recorder: null,
};

function setBusy(busy) {
  $("generate").disabled = busy;
  $("cancel").hidden = !busy;
  $("cancel").disabled = false;
  document.querySelector(".actions").classList.toggle("has-cancel", busy);
}

const $ = (id) => document.getElementById(id);

async function api(path, options) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const message = Array.isArray(detail) ? detail.map((item) => item.msg || item).join("; ") : (detail || data.message || res.statusText);
    throw new Error(message);
  }
  return data;
}

function isVideoFile(name, kind) {
  if (/\.webp$/i.test(name || "")) return false;
  return kind === "video" || /\.(webm|mp4)$/i.test(name || "");
}

function mediaUrl(output) {
  const params = new URLSearchParams({
    filename: output.filename,
    subfolder: output.subfolder || "",
    type: output.type || "output",
  });
  return `/api/media?${params}`;
}

function currentModels() {
  return state.models.filter((item) => item.mode === state.mode);
}

function renderModels() {
  const select = $("model");
  const models = currentModels();
  select.innerHTML = models.map((item) => {
    const mark = item.ready ? "" : " — download required";
    return `<option value="${item.id}" ${item.ready ? "" : "data-blocked=1"}>${item.label} (${item.tier})${mark}</option>`;
  }).join("");
  const ready = models.find((item) => item.ready);
  if (ready) select.value = ready.id;
  updateModelNote();
}

function selectedModel() {
  return state.models.find((item) => item.id === $("model").value);
}

function updateModelNote() {
  const model = selectedModel();
  const note = $("model-note");
  const hint = $("camera-hint");
  if (!model) {
    note.textContent = "No models in this mode.";
    return;
  }
  if (!model.ready) {
    note.textContent = `Not ready. Missing: ${(model.missing || []).join(", ")}`;
  } else {
    note.textContent = `${model.label} is ready on this machine.`;
  }
  if (state.mode === "still") {
    hint.textContent = model.lemonade_image
      ? "Stills render on Lemonade (Flux 2 Klein 9B). Keep Lemonade running."
      : "Stills ignore camera duration. Use Send to I2V from the gallery.";
  } else if (model.camera_native && model.ready) {
    hint.textContent = "This model has native camera control.";
  } else {
    hint.textContent = "Camera is applied as cinematic language until Wan Fun Camera is downloaded.";
  }
  $("drop").classList.toggle("disabled", state.mode === "t2v");
}

function renderPresets() {
  const { cameras, formats, durations, qualities } = state.presets;
  $("camera").innerHTML = cameras.map((item) => `<option value="${item.id}">${item.label}</option>`).join("");
  $("format").innerHTML = formats.map((item) => `<option value="${item.id}">${item.label}</option>`).join("");
  $("duration").innerHTML = durations.map((item) => `<option value="${item.id}">${item.label}</option>`).join("");
  $("quality").innerHTML = (qualities || []).map((item) => `<option value="${item.id}">${item.label}</option>`).join("");
  $("format").value = state.presets.defaults.format;
  $("duration").value = state.presets.defaults.duration;
  $("quality").value = state.presets.defaults.quality || "quality";
  $("refine").checked = state.presets.defaults.refine !== false;
  const hint = $("refine-hint");
  if (state.presets.defaults.refine_ready) {
    hint.textContent = "After the model finishes, frames are upscaled 2x and sharpened.";
  } else {
    hint.textContent = "Download the upscale model from Pinokio → Download Models → Final Render Upscale.";
    $("refine").checked = false;
  }
}

function setHealth(data) {
  const el = $("health");
  const lemonade = data.lemonade && data.lemonade.ok;
  const whisper = data.whisper && data.whisper.ok;
  if (data.comfy && data.comfy.ok && lemonade) {
    const extra = whisper ? ` · ${data.whisper.model}` : "";
    el.textContent = `ComfyUI + Lemonade · ${data.lemonade.model || "LLM"}${extra}`;
    el.className = "status ok";
  } else if (data.comfy && data.comfy.ok) {
    el.textContent = "ComfyUI connected · Lemonade offline";
    el.className = "status ok";
  } else {
    el.textContent = "Studio up · ComfyUI offline";
    el.className = "status bad";
  }
  const note = $("transcribe-note");
  if (note) {
    note.textContent = whisper
      ? `Uses Lemonade ${data.whisper.model}.`
      : "Whisper is not ready on Lemonade.";
  }
}

function stopMedia(root) {
  if (!root) return;
  root.querySelectorAll("video").forEach((video) => {
    video.pause();
    video.removeAttribute("autoplay");
    video.loop = false;
    video.removeAttribute("src");
    video.load();
  });
  root.querySelectorAll("img").forEach((image) => {
    image.removeAttribute("src");
  });
}

function freezeElement(media) {
  if (!media || !media.parentNode) return;
  const width = media.naturalWidth || media.videoWidth || media.clientWidth;
  const height = media.naturalHeight || media.videoHeight || media.clientHeight;
  if (!width || !height) {
    if (media.tagName === "VIDEO") {
      media.pause();
      media.loop = false;
    }
    return;
  }
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  try {
    canvas.getContext("2d").drawImage(media, 0, 0, width, height);
  } catch (err) {
    if (media.tagName === "VIDEO") {
      media.pause();
      media.loop = false;
    }
    return;
  }
  if (media.tagName === "VIDEO") {
    media.pause();
    media.removeAttribute("src");
    media.load();
  } else {
    media.removeAttribute("src");
  }
  media.replaceWith(canvas);
}

function durationSeconds(job) {
  const raw = (job && job.request && job.request.duration) || "5s";
  const value = parseInt(String(raw), 10);
  return Number.isFinite(value) && value > 0 ? value : 5;
}

function stopStage() {
  const stage = $("stage");
  stopMedia(stage);
  stage.innerHTML = `<div class="empty" id="empty-stage"><p>Cancelled.</p><span>The render was stopped. Generate again when you want a new clip.</span></div>`;
}

function renderStage(output, playSeconds = 0) {
  const stage = $("stage");
  stopMedia(stage);
  $("empty-stage")?.remove();
  const url = mediaUrl(output);
  if (isVideoFile(output.filename, output.kind)) {
    const video = document.createElement("video");
    video.src = url;
    video.controls = true;
    video.muted = true;
    video.loop = false;
    video.autoplay = playSeconds > 0;
    video.addEventListener("ended", () => freezeElement(video), { once: true });
    stage.replaceChildren(video);
    return;
  }
  const image = document.createElement("img");
  image.src = url;
  image.alt = "generation";
  stage.replaceChildren(image);
  if (/\.webp$/i.test(output.filename || "")) {
    image.addEventListener("load", () => {
      if (playSeconds > 0) {
        window.setTimeout(() => freezeElement(image), playSeconds * 1000);
      } else {
        freezeElement(image);
      }
    }, { once: true });
  }
}

function renderJob(job) {
  const el = $("job");
  const text = $("job-text");
  const bar = $("job-bar");
  el.hidden = false;
  const pct = job.progress_max ? Math.round((job.progress / job.progress_max) * 100) : 0;
  if (job.status === "cancelled") {
    text.textContent = "Cancelled.";
    bar.hidden = true;
    stopStage();
  } else if (job.status === "error") {
    text.textContent = `Error: ${job.error}`;
    bar.hidden = true;
  } else if (job.status === "running" && !job.progress_max) {
    text.textContent = "Loading model on the R9700… first clip after load takes about 10 minutes.";
    bar.hidden = false;
    bar.firstElementChild.style.width = "8%";
  } else {
    text.textContent = `${job.status}${job.progress_max ? ` · ${pct}%` : ""}`;
    bar.hidden = !job.progress_max;
    bar.firstElementChild.style.width = `${pct}%`;
  }
  if (job.status === "done" && job.outputs && job.outputs[0]) {
    renderStage(job.outputs[0], durationSeconds(job));
    loadGallery();
  }
}

function renderGallery(items) {
  const root = $("gallery");
  stopMedia(root);
  root.replaceChildren();
  if (!items.length) {
    root.innerHTML = `<div class="meta">Nothing generated yet.</div>`;
    return;
  }
  items.forEach((item) => {
    const article = document.createElement("article");
    article.className = "card";
    article.dataset.job = item.job_id;
    const url = mediaUrl(item.output);
    if (isVideoFile(item.output.filename, item.output.kind)) {
      const video = document.createElement("video");
      video.src = url;
      video.muted = true;
      video.preload = "metadata";
      video.loop = false;
      article.appendChild(video);
    } else {
      const image = document.createElement("img");
      image.src = url;
      image.alt = "";
      article.appendChild(image);
      if (/\.webp$/i.test(item.output.filename || "")) {
        image.addEventListener("load", () => freezeElement(image), { once: true });
      }
    }
    const meta = document.createElement("div");
    meta.className = "meta";
    meta.innerHTML = `${item.model || ""} · ${item.camera || ""}<br>${escapeHtml((item.prompt || "").slice(0, 80))}`;
    article.appendChild(meta);
    root.appendChild(article);
  });
}

function escapeHtml(text) {
  return String(text)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function loadGallery() {
  const data = await api("/api/gallery");
  renderGallery(data.items || []);
}

async function pollJob(id) {
  state.jobId = id;
  setBusy(true);
  clearInterval(state.poll);
  state.poll = setInterval(async () => {
    try {
      const job = await api(`/api/jobs/${id}`);
      renderJob(job);
      if (["done", "error", "cancelled"].includes(job.status)) {
        clearInterval(state.poll);
        state.poll = null;
        setBusy(false);
      }
    } catch (err) {
      clearInterval(state.poll);
      state.poll = null;
      $("job").hidden = false;
      $("job-text").textContent = err.message;
      setBusy(false);
    }
  }, 1500);
}

async function cancelJob() {
  if (!state.jobId) return;
  $("cancel").disabled = true;
  stopStage();
  try {
    const data = await api(`/api/jobs/${state.jobId}/cancel`, { method: "POST" });
    renderJob(data.job);
    clearInterval(state.poll);
    state.poll = null;
    setBusy(false);
  } catch (err) {
    $("job").hidden = false;
    $("job-text").textContent = err.message;
    $("cancel").disabled = false;
  }
}

function renderDownloads(data) {
  const select = $("download-pack");
  const current = select.value;
  select.innerHTML = (data.packs || []).map((item) => {
    const mark = item.installed ? " — installed" : "";
    return `<option value="${item.id}">${item.label}${mark}</option>`;
  }).join("");
  if (current && [...select.options].some((item) => item.value === current)) {
    select.value = current;
  }
  updateDownloadNote(data);
  const live = data.current;
  if (live && live.status === "running") {
    const pct = live.total ? Math.round((live.bytes / live.total) * 100) : 0;
    $("download-note").textContent = `Downloading ${live.file || live.label}… ${pct}%`;
    $("download-go").disabled = true;
  } else if (live && live.status === "error") {
    $("download-note").textContent = `Download failed: ${live.error}`;
    $("download-go").disabled = false;
  } else if (live && live.status === "done") {
    $("download-go").disabled = false;
  } else {
    $("download-go").disabled = false;
  }
}

function updateDownloadNote(data) {
  const packs = (data && data.packs) || state.downloadPacks || [];
  const pack = packs.find((item) => item.id === $("download-pack").value);
  if (!pack) return;
  if (pack.installed) {
    $("download-note").textContent = `${pack.label} is already on disk. ${pack.note}`;
  } else {
    $("download-note").textContent = pack.note || "Saves into this ComfyUI models folder.";
  }
}

async function loadDownloads() {
  const data = await api("/api/downloads");
  state.downloadPacks = data.packs || [];
  renderDownloads(data);
  if (data.current && data.current.status === "running") {
    pollDownload();
  }
}

async function startDownload() {
  const packId = $("download-pack").value;
  if (!packId) return;
  $("download-go").disabled = true;
  try {
    await api(`/api/downloads/${packId}`, { method: "POST" });
    pollDownload();
  } catch (err) {
    $("download-note").textContent = err.message;
    $("download-go").disabled = false;
  }
}

function pollDownload() {
  clearInterval(state.downloadPoll);
  state.downloadPoll = setInterval(async () => {
    try {
      const data = await api("/api/downloads");
      state.downloadPacks = data.packs || [];
      renderDownloads(data);
      if (!data.current || data.current.status !== "running") {
        clearInterval(state.downloadPoll);
        const models = await api("/api/models");
        state.models = models.models || [];
        renderModels();
      }
    } catch (err) {
      clearInterval(state.downloadPoll);
      $("download-note").textContent = err.message;
      $("download-go").disabled = false;
    }
  }, 1500);
}

async function transcribeBlob(blob, filename) {
  const note = $("transcribe-note");
  note.textContent = "Transcribing with Whisper-Large-v3-Turbo…";
  const body = new FormData();
  body.set("audio", blob, filename);
  const data = await api("/api/transcribe", { method: "POST", body });
  $("prompt").value = data.text || "";
  $("health").textContent = `Prompt from ${data.model || "Whisper"}`;
  $("health").className = "status ok";
  note.textContent = `Transcribed with ${data.model}.`;
  return data;
}

async function uploadAudio() {
  $("audio").click();
}

async function onAudioPicked() {
  const file = $("audio").files[0];
  $("audio").value = "";
  if (!file) return;
  $("audio-go").disabled = true;
  $("record-go").disabled = true;
  try {
    await transcribeBlob(file, file.name || "audio.wav");
  } catch (err) {
    $("transcribe-note").textContent = err.message;
  } finally {
    $("audio-go").disabled = false;
    $("record-go").disabled = false;
  }
}

async function toggleRecord() {
  if (state.recorder) {
    state.recorder.stop();
    return;
  }
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    $("transcribe-note").textContent = "This browser cannot record audio. Upload a WAV instead.";
    return;
  }
  let stream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    $("transcribe-note").textContent = "Microphone permission was denied.";
    return;
  }
  const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
    ? "audio/webm;codecs=opus"
    : (MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "");
  const chunks = [];
  const recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
  recorder.ondataavailable = (event) => {
    if (event.data && event.data.size) chunks.push(event.data);
  };
  recorder.onstop = async () => {
    stream.getTracks().forEach((track) => track.stop());
    state.recorder = null;
    $("record-go").textContent = "Record voice";
    $("audio-go").disabled = false;
    const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
    const name = (recorder.mimeType || "").includes("ogg") ? "voice.ogg" : "voice.webm";
    $("record-go").disabled = true;
    try {
      await transcribeBlob(blob, name);
    } catch (err) {
      $("transcribe-note").textContent = err.message;
    } finally {
      $("record-go").disabled = false;
    }
  };
  recorder.start();
  state.recorder = recorder;
  $("record-go").textContent = "Stop & transcribe";
  $("audio-go").disabled = true;
  $("transcribe-note").textContent = "Listening… click Stop & transcribe when you finish.";
}

async function generatePrompt() {
  const button = $("prompt-go");
  button.disabled = true;
  button.textContent = "Writing…";
  try {
    const data = await api("/api/prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        idea: $("prompt").value,
        mode: state.mode,
        camera: $("camera").value,
        format: $("format").value,
      }),
    });
    $("prompt").value = data.prompt || "";
    if (data.source === "lemonade") {
      $("health").textContent = `Prompt from Lemonade · ${data.model || "local LLM"}`;
      $("health").className = "status ok";
    }
  } catch (err) {
    $("job").hidden = false;
    $("job-text").textContent = err.message;
  } finally {
    button.disabled = false;
    button.textContent = "Generate prompt";
  }
}

async function generate() {
  const model = selectedModel();
  if (!model) return;
  if (!model.ready) {
    $("job").hidden = false;
    $("job").textContent = `Download ${model.label} from the Pinokio Download Mix menu first.`;
    return;
  }
  if (state.mode === "i2v" && !state.imageFile) {
    $("job").hidden = false;
    $("job").textContent = "Add a start frame for image-to-video.";
    return;
  }
  const body = new FormData();
  body.set("prompt", $("prompt").value);
  body.set("negative", $("negative").value);
  body.set("model", model.id);
  body.set("mode", state.mode);
  body.set("camera", $("camera").value);
  body.set("format", $("format").value);
  body.set("duration", $("duration").value);
  body.set("quality", $("quality").value);
  body.set("seed", $("seed").value);
  body.set("cinematic", $("cinematic").checked ? "true" : "false");
  body.set("refine", $("refine").checked ? "true" : "false");
  if (state.imageFile) body.set("image", state.imageFile);
  clearInterval(state.poll);
  state.poll = null;
  if (state.jobId) {
    try {
      await api(`/api/jobs/${state.jobId}/cancel`, { method: "POST" });
    } catch (err) {
    }
  }
  stopMedia($("stage"));
  $("stage").innerHTML = `<div class="empty" id="empty-stage"><p>Rendering…</p><span>Previous clip stopped. New frames will appear here when this job finishes.</span></div>`;
  setBusy(true);
  try {
    const data = await api("/api/generate", { method: "POST", body });
    renderJob(data.job);
    pollJob(data.job_id);
  } catch (err) {
    $("job").hidden = false;
    $("job-text").textContent = err.message;
    setBusy(false);
  }
}

function bind() {
  $("modes").addEventListener("click", (event) => {
    const button = event.target.closest("button");
    if (!button) return;
    state.mode = button.dataset.mode;
    [...$("modes").children].forEach((item) => item.classList.toggle("active", item === button));
    renderModels();
  });
  $("model").addEventListener("change", updateModelNote);
  $("image").addEventListener("change", () => {
    state.imageFile = $("image").files[0] || null;
    const img = $("preview-image");
    if (state.imageFile) {
      img.src = URL.createObjectURL(state.imageFile);
      img.hidden = false;
    } else {
      img.hidden = true;
    }
  });
  $("generate").addEventListener("click", generate);
  $("cancel").addEventListener("click", cancelJob);
  $("download-go").addEventListener("click", startDownload);
  $("prompt-go").addEventListener("click", generatePrompt);
  $("record-go").addEventListener("click", toggleRecord);
  $("audio-go").addEventListener("click", uploadAudio);
  $("audio").addEventListener("change", onAudioPicked);
  $("download-pack").addEventListener("change", updateDownloadNote);
  $("refresh").addEventListener("click", loadGallery);
  $("gallery").addEventListener("click", async (event) => {
    const card = event.target.closest(".card");
    if (!card) return;
    const job = await api(`/api/jobs/${card.dataset.job}`);
    if (job.outputs && job.outputs[0]) renderStage(job.outputs[0], durationSeconds(job));
  });
}

async function boot() {
  bind();
  try {
    const [health, models, presetData] = await Promise.all([
      api("/api/health"),
      api("/api/models"),
      api("/api/presets"),
    ]);
    setHealth(health);
    state.models = models.models || [];
    state.presets = presetData;
    renderModels();
    renderPresets();
    await loadDownloads();
    $("prompt").value = $("prompt").value || "a fox moving quickly in a beautiful winter scenery";
    const gallery = await api("/api/gallery");
    renderGallery(gallery.items || []);
    if (gallery.items && gallery.items[0]) {
      renderStage(gallery.items[0].output, 0);
    }
    const now = Date.now() / 1000;
    const live = (await api("/api/jobs")).jobs.find((item) => (
      ["queued", "running"].includes(item.status) && (now - (item.updated_at || 0) < 180)
    ));
    if (live) {
      renderJob(live);
      pollJob(live.id);
    }
  } catch (err) {
    $("health").textContent = err.message;
    $("health").className = "status bad";
  }
}

boot();
