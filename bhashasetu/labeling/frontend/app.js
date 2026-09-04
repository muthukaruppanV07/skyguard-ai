"use strict";

/* BhashaSetu labeling workbench — vanilla JS SPA. */

const $ = (id) => document.getElementById(id);

const POSE_BONES = [
  [0,1],[1,2],[2,3],[3,7],[0,4],[4,5],[5,6],[6,8],[9,10],
  [11,12],[11,13],[13,15],[15,17],[15,19],[15,21],[17,19],
  [12,14],[14,16],[16,18],[16,20],[16,22],[18,20],[11,23],[12,24],[23,24],
  [23,25],[25,27],[27,29],[29,31],[26,28],[28,30],[30,32],[27,28],[25,26],
];
const HAND_BONES = [
  [0,1],[1,2],[2,3],[3,4],[0,5],[5,6],[6,7],[7,8],[5,9],[9,10],[10,11],[11,12],
  [9,13],[13,14],[14,15],[15,16],[13,17],[17,18],[18,19],[19,20],[0,17],
];
const FACE_SUBSET = [10,152,234,454,33,133,362,263,61,291,81,178,311,402,14];

const state = {
  config: null,
  glossaries: {},
  samples: { total: 0, samples: [] },
  current: null,
  keypoints: null,
  frame: 0,
  playing: false,
  playTimer: null,
};

// ---------------------------------------------------------------- api helper
async function api(path, opts = {}) {
  const init = { headers: { "Content-Type": "application/json" }, ...opts };
  if (opts.body) init.body = JSON.stringify(opts.body);
  const res = await fetch("/api" + path, init);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
  return data;
}

// ---------------------------------------------------------------- boot
async function boot() {
  try {
    state.config = await api("/config");
    $("serverBadge").textContent = `v${state.config.dataset_version} · thresh ${state.config.consensus_threshold}`;
    $("serverBadge").classList.add("ok");
    populateSelect("labelDomain", Object.keys(state.config.domains).map(d => [d, d.toUpperCase()]));
    populateSelect("rDomain", Object.keys(state.config.domains).map(d => [d, d.toUpperCase()]));
    populateSelect("recDomain", Object.keys(state.config.domains).map(d => [d, d.toUpperCase()]));
    populateSelect("queueDomain", ["", ...Object.keys(state.config.domains)].map(d => [d, d ? d.toUpperCase() : "all domains"]));
    populateSelect("labelRegion", [["", ""], ...state.config.regions.map(r => [r.code, r.label])]);
    populateSelect("rRegion", state.config.regions.map(r => [r.code, r.label]));
    await loadGlossary(localSelectValue("labelDomain"));
    await refreshQueue();
    await refreshStats();
  } catch (err) {
    $("serverBadge").textContent = "server offline";
    toast("Cannot reach labeling server: " + err.message, true);
  }
}

function populateSelect(id, pairs) {
  const sel = $(id);
  sel.innerHTML = "";
  for (const [val, label] of pairs) {
    const o = document.createElement("option");
    o.value = val; o.textContent = label;
    sel.appendChild(o);
  }
}
function localSelectValue(id) { const s = $(id); return s.options[s.selectedIndex]?.value; }

async function loadGlossary(domain) {
  if (!domain || state.glossaries[domain]) return;
  const g = await api(`/glossaries/${domain}`);
  state.glossaries[domain] = g;
  refreshSuggestions(domain);
}
async function refreshSuggestions(domain) {
  const dl = $("glossSuggest");
  dl.innerHTML = "";
  const g = state.glossaries[domain];
  if (!g) return;
  for (const e of g.glosses) {
    const o = document.createElement("option");
    o.value = e.gloss + (e.fingerspelled ? " (FS)" : "");
    o.label = `${e.gloss} — ${e.english}`;
    dl.appendChild(o);
  }
}

// ---------------------------------------------------------------- queue
async function refreshQueue() {
  const domain = localSelectValue("queueDomain");
  const status = localSelectValue("queueStatus");
  const params = new URLSearchParams();
  if (domain) params.set("domain", domain);
  if (status) params.set("status", status);
  const data = await api(`/samples?${params}`);
  state.samples = data;
  $("queueCount").textContent = `${data.total} sample(s)`;
  const ul = $("queueList");
  ul.innerHTML = "";
  if (!data.samples.length) {
    const li = document.createElement("li");
    li.textContent = "No samples.";
    ul.appendChild(li);
    return;
  }
  for (const s of data.samples) {
    const li = document.createElement("li");
    li.dataset.id = s.sample_id;
    const gloss = s.consensus?.gloss || s.gloss_seq.join(" ") || "—";
    li.innerHTML = `<span class="qid">${s.sample_id}</span>
      <div class="sgloss">${escapeHtml(gloss)}</div>
      <div class="qmeta"><span>${s.domain}</span><span>${s.status}</span>
      <span>${s.signer?.anon_id || "no signer"}</span></div>`;
    li.addEventListener("click", () => selectSample(s.sample_id, li));
    ul.appendChild(li);
  }
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

// ---------------------------------------------------------------- sample view
async function selectSample(id, liEl) {
  document.querySelectorAll(".queue li").forEach(el => el.classList.remove("active"));
  if (liEl) liEl.classList.add("active");
  const s = await api(`/samples/${id}`);
  state.current = s;
  $("sampleId").textContent = s.sample_id;

  const meta = [
    ["domain", s.domain], ["status", s.status], ["consent", s.consent?.status],
    ["qa", s.qa?.status], ["signer", s.signer?.anon_id || "—"],
    ["region", s.signer?.region], ["created", s.created_at],
    ["eligible", s.eligible_for_manifest ? "YES" : "no"],
  ];
  $("metaList").innerHTML = meta.map(([k, v]) => `<dt>${k}</dt><dd>${escapeHtml(v)}</dd>`).join("");

  $("labelDomain").value = s.domain;
  loadGlossary(s.domain);
  renderConsent(s);
  renderVotes(s);
  renderProvenance(s);
  await loadMedia(s);
}

function renderConsent(s) {
  $("consentBox").textContent = s.consent
    ? `status: ${s.consent.status}\nform: ${s.consent.form_id || "—"}\nusage: ${(s.consent.usage || []).join(",") || "—"}`
    : "unknown";
}

function renderVotes(s) {
  const box = $("consensusBox");
  const c = s.consensus || {};
  const verdictClass = c.status || "needs_voting";
  const verdictText = {
    agreed: `AGREED — ${c.gloss} (agreement ${c.agreement})`,
    ambiguous: `AMBIGUOUS (${c.agreement}) — needs more annotators`,
    needs_voting: `needs ${s.configMin || 2} annotators`,
  }[verdictClass] || c.status;
  box.innerHTML = `<div class="verdict ${verdictClass}">${escapeHtml(verdictText)}</div>` +
    (c.votes || []).map(v => `<div class="vote">${escapeHtml(v.gloss)} × ${v.votes}</div>`).join("") +
    (c.english_sentence ? `<div class="vote-item">→ ${escapeHtml(c.english_sentence)}</div>` : "") +
    (s.labels || []).map(l => `<div class="vote-item"><b>${escapeHtml(l.annotator)}</b> ${escapeHtml(l.gloss)}`
      + (l.english_sentence ? `: "${escapeHtml(l.english_sentence)}"` : "")
      + ` <span class="qmeta">conf ${l.confidence?.toFixed?.(2)} ${l.region || ""}</span></div>`).join("");
}

function renderProvenance(s) {
  $("provenanceBox").textContent = JSON.stringify({
    source: s.source, video: s.video, keypoints: s.keypoints, dialect: s.dialect,
  }, null, 2);
}

// ---------------------------------------------------------------- media
async function loadMedia(s) {
  stopPlay();
  state.keypoints = null;
  state.frame = 0;
  const video = $("video"), overlay = $("overlay");
  $("noVideo").classList.add("hidden");
  video.pause();
  video.removeAttribute("src");
  video.load();

  let hasVideo = false;
  if (s.video?.path) {
    video.src = "/media/" + s.video.path;
    video.style.display = "block";
    hasVideo = true;
  }
  overlay.style.display = "none";

  if (s.keypoints?.path) {
    try {
      const res = await fetch("/media/" + s.keypoints.path);
      if (res.ok) state.keypoints = await res.json();
    } catch (_) { /* keypoints optional */ }
  }

  if (state.keypoints?.frames?.length) {
    overlay.style.display = "block";
    const n = state.keypoints.frames.length - 1;
    $("frameScrub").max = n;
    if (!hasVideo) $("noVideo").classList.remove("hidden");
  }
  updateFrameLabel();
  drawOverlay();
}

function currentFrameIndex() {
  if (state.keypoints) {
    const fps = state.keypoints.fps || 30;
    if (state.current?.video?.path && !$("video").paused) {
      return Math.min(state.keypoints.frames.length - 1,
        Math.floor($("video").currentTime * fps));
    }
    return state.frame;
  }
  return 0;
}

function updateFrameLabel() {
  const n = state.keypoints?.frames?.length || 0;
  $("frameLabel").textContent = `${currentFrameIndex()} / ${n ? n - 1 : 0}`;
}

function drawOverlay() {
  const overlay = $("overlay");
  const kp = state.keypoints;
  if (!kp || !kp.frames?.length) { overlay.style.display = "none"; return; }
  overlay.style.display = "block";
  const video = $("video");
  const w = video.videoWidth > 0 ? video.clientWidth : overlay.clientWidth;
  const h = video.videoHeight > 0 ? video.clientHeight : overlay.clientHeight;
  if (overlay.width !== w || overlay.height !== h) {
    overlay.width = w; overlay.height = h;
  }
  const ctx = overlay.getContext("2d");
  const idx = currentFrameIndex();
  const frame = kp.frames[Math.min(idx, kp.frames.length - 1)];
  ctx.clearRect(0, 0, w, h);
  if (!frame) return;
  drawPart(ctx, frame.pose, POSE_BONES, "#38bdf8", w, h);
  drawPart(ctx, frame.left_hand, HAND_BONES, "#34d399", w, h);
  drawPart(ctx, frame.right_hand, HAND_BONES, "#fbbf24", w, h);
  drawFace(ctx, frame.face, "#f58be0", w, h);

  const fps = kp.fps || 30;
  ctx.fillStyle = "rgba(7,12,20,.66)";
  ctx.fillRect(0, h - 26, 210, 26);
  ctx.fillStyle = "#e7ecf3";
  ctx.font = "12px Consolas, monospace";
  ctx.fillText(`frame ${idx}/${kp.frames.length - 1} · ${fps} fps`, 10, h - 9);
}

function drawPart(ctx, pts, bones, color, w, h) {
  if (!pts || !pts.length) return;
  const P = (i) => pts[i] && pts[i][2] !== -1
    ? [pts[i][0] * w, pts[i][1] * h] : null;
  ctx.strokeStyle = color;
  ctx.lineWidth = 2;
  ctx.lineJoin = "round";
  ctx.beginPath();
  for (const [a, b] of bones) {
    const pa = P(a), pb = P(b);
    if (pa && pb) { ctx.moveTo(pa[0], pa[1]); ctx.lineTo(pb[0], pb[1]); }
  }
  ctx.stroke();
  ctx.fillStyle = color;
  for (let i = 0; i < pts.length; i++) {
    const p = P(i);
    if (p) { ctx.beginPath(); ctx.arc(p[0], p[1], 1.8, 0, 2 * Math.PI); ctx.fill(); }
  }
}

function drawFace(ctx, face, color, w, h) {
  if (!face) return;
  ctx.fillStyle = color;
  for (const i of FACE_SUBSET) {
    const f = face[i];
    if (f && f[2] !== -1) {
      ctx.beginPath();
      ctx.arc(f[0] * w, f[1] * h, 1.4, 0, 2 * Math.PI);
      ctx.fill();
    }
  }
}

function startPlay() {
  if (!state.keypoints || !$("video").paused) return;
  stopPlay();
  state.playing = true;
  const fps = state.keypoints.fps || 30;
  state.playTimer = setInterval(() => {
    if (state.frame >= state.keypoints.frames.length - 1) { stopPlay(); return; }
    state.frame++;
    $("frameScrub").value = state.frame;
    drawOverlay(); updateFrameLabel();
  }, 1000 / fps);
}
function stopPlay() {
  state.playing = false;
  if (state.playTimer) { clearInterval(state.playTimer); state.playTimer = null; }
  $("btnPlay").textContent = "▶";
}

// ---------------------------------------------------------------- actions
$("video").addEventListener("timeupdate", () => { drawOverlay(); updateFrameLabel(); });
$("video").addEventListener("play", () => { if (state.keypoints) { } drawOverlay(); });
$("frameScrub").addEventListener("input", () => {
  state.frame = parseInt($("frameScrub").value, 10);
  const video = $("video");
  if (state.current?.video?.path && video.src) {
    if (state.keypoints?.fps) video.currentTime = state.frame / state.keypoints.fps;
  }
  drawOverlay(); updateFrameLabel();
});
$("btnPlay").addEventListener("click", () => {
  if (state.playing) { stopPlay(); } else { startPlay(); }
});

$("labelDomain").addEventListener("change", async () => {
  await loadGlossary(localSelectValue("labelDomain")); refreshSuggestions(localSelectValue("labelDomain"));
});
$("labelConfidence").addEventListener("input", () => {
  $("confValue").textContent = (parseInt($("labelConfidence").value, 10) / 100).toFixed(2);
});

$("btnSubmitLabel").addEventListener("click", async () => {
  if (!state.current) return toast("select a sample first", true);
  const body = {
    annotator: $("labelAnnotator").value.trim() || "anon",
    gloss: $("labelGloss").value.trim(),
    english_sentence: $("labelEnglish").value.trim(),
    region: localSelectValue("labelRegion"),
    dialect_notes: $("labelDialectNotes").value.trim(),
    confidence: parseInt($("labelConfidence").value, 10) / 100,
    flags: [...document.querySelectorAll(".flag:checked")].map(f => f.value),
    _actor: "web",
  };
  if (!body.gloss) return toast("gloss is required", true);
  try {
    const s = await api(`/samples/${state.current.sample_id}/labels`, { method: "POST", body });
    state.current = s; renderVotes(s);
    toast("vote recorded — " + s.consensus.status);
    refreshQueue();
  } catch (err) { toast(err.message, true); }
});

async function qa(status) {
  if (!state.current) return toast("select a sample first", true);
  try {
    const s = await api(`/samples/${state.current.sample_id}/qa`, {
      method: "POST",
      body: { status, reviewer: $("qaReviewer").value.trim() || "web", notes: $("qaNotes").value.trim() },
    });
    state.current = s; renderVotes(s);
    toast("QA: " + status); refreshQueue();
  } catch (err) { toast(err.message, true); }
}
$("btnQaPass").addEventListener("click", () => qa("passed"));
$("btnQaReject").addEventListener("click", () => qa("rejected"));

$("btnConsentGrant").addEventListener("click", async () => {
  const s = state.current; if (!s) return toast("select a sample first", true);
  const formId = $("consFormId").value.trim();
  if (!formId) return toast("form id required", true);
  try {
    await api("/consent", { method: "POST", body: {
      signer_id: s.signer?.anon_id, form_id: formId,
      region: s.signer?.region, usage: ["training"], status: "granted" } });
    toast("consent granted for " + s.signer?.anon_id);
  } catch (err) { toast(err.message, true); }
});
$("btnConsentWithdraw").addEventListener("click", async () => {
  const s = state.current; if (!s) return toast("select a sample first", true);
  if (!confirm(`Withdraw signer ${s.signer?.anon_id}? Their samples are removed from manifests.`)) return;
  const r = await api("/consent/withdraw", { method: "POST", body: { signer_id: s.signer?.anon_id } });
  toast(`withdrawn: ${r.withdrawn_samples.length} sample(s)`);
  refreshQueue(); refreshStats();
});

// ---------------------------------------------------------------- register
$("btnAddConsent").addEventListener("click", async () => {
  const formId = $("rFormId").value.trim();
  if (!formId) return toast("consent form id required", true);
  try {
    await api("/consent", { method: "POST", body: {
      signer_id: $("rSignerId").value.trim(),
      form_id: formId,
      region: localSelectValue("rRegion"),
      age_group: localSelectValue("rAgeGroup"),
      gender: localSelectValue("rGender"),
      handedness: localSelectValue("rHandedness"),
      native_sign_language: $("rNative").checked,
      usage: [...document.querySelectorAll(".usageBox:checked")].map(f => f.value),
    }});
    toast("consent registered");
  } catch (err) { toast(err.message, true); }
});

function refreshSignerSelect() {
  api("/stats").then(st => {
    populateSelect("rSignerSelect", st.signers.map(s => [s.anon_id, `${s.anon_id} (${s.region})`]));
  }).catch(() => {});
}

$("btnAddSample").addEventListener("click", async () => {
  const signerId = localSelectValue("rSignerSelect");
  if (!signerId) return toast("register a signer first (consent record)", true);
  const gp = $("rGlossSeq").value.split(",").map(s => s.trim()).filter(Boolean);
  try {
    const s = await api("/samples", { method: "POST", body: {
      domain: localSelectValue("rDomain"),
      signer: { anon_id: signerId, region: localSelectValue("rRegion") },
      gloss_seq: gp,
      source: { kind: localSelectValue("rSourceKind"), url: $("rSourceUrl").value.trim() },
      video: $("rVideoPath").value.trim() ? { path: $("rVideoPath").value.trim() } : null,
      keypoints: $("rKeypointsPath").value.trim() ? { path: $("rKeypointsPath").value.trim() } : null,
      _consent_status: localSelectValue("rConsentStatus"),
      _consent_form_id: $("rFormId").value.trim(),
    }});
    toast("registered " + s.sample_id);
    refreshQueue(); refreshStats();
  } catch (err) { toast(err.message, true); }
});

$("btnExport").addEventListener("click", async () => {
  try {
    const m = await api("/export", { method: "POST", body: { version: $("exportVersion").value.trim() || undefined } });
    $("exportResult").textContent =
      `manifest ${m.manifest_file}\n${m.sample_count} samples (${m.by_domain.pds} pds / ${m.by_domain.health} health / ${m.by_domain.legal} legal)`;
    toast("manifest exported");
  } catch (err) { toast(err.message, true); }
});

// ---------------------------------------------------------------- stats
async function refreshStats() {
  try {
    const st = await api("/stats");
    $("statChips").textContent =
      `${st.samples_total} samples · ${st.by_domain.pds?.total || 0} pds · ` +
      `${st.by_domain.health?.total || 0} hth · ${st.by_domain.legal?.total || 0} leg · ` +
      `${st.signer_diversity.signers} signers · ${st.labels_total} votes`;
    const el = $("view-stats");
    const rows = st.by_domain;
    const signerRows = st.signers.map(s =>
      `<tr><td>${s.anon_id}</td><td>${s.region || "—"}</td><td>${s.age_group || "—"}</td>` +
      `<td>${s.gender || "—"}</td><td>${s.samples}</td></tr>`).join("");
    el.innerHTML = `<div class="cards">
      <div class="card"><h3>Corpus by domain</h3>
        <table class="stat-table">
          <tr><th>domain</th><th>total</th><th>statuses</th></tr>
          ${Object.entries(rows).map(([d, v]) =>
            `<tr><td>${d}</td><td>${v.total}</td><td>${JSON.stringify(v.by_status)}</td></tr>`).join("")}
        </table>
      </div>
      <div class="card"><h3>Signer diversity (anti-bias)</h3>
        <p>regions: ${st.signer_diversity.regions.join(", ") || "—"}<br>
        age groups: ${st.signer_diversity.age_groups.join(", ") || "—"}<br>
        genders: ${st.signer_diversity.genders.join(", ") || "—"}</p>
      </div>
    </div>
    <div class="cards"><div class="card"><h3>Signers</h3>
      <table class="stat-table">
        <tr><th>id</th><th>region</th><th>age</th><th>gender</th><th>samples</th></tr>
        ${signerRows}
      </table>
    </div></div>`;
  } catch (_) { /* stats best-effort */ }
}

// ---------------------------------------------------------------- recorder
const rec = {
  stream: null,
  mediaRec: null,
  chunks: [],
  blob: null,
  consent: {},   // signer_id -> consent record (form_id, region, status)
};

async function refreshSignerConsents() {
  try {
    const st = await api("/stats");
    const ids = st.signers.map(s => s.anon_id);
    rec.consent = {};
    for (const id of ids) {
      const c = await api(`/consent/${id}`);
      if (c && c.status === "granted") rec.consent[id] = c;
    }
    populateSelect("recSigner",
      Object.values(rec.consent).map(c => [c.signer_id, `${c.signer_id} (${c.region}, form ${c.form_id})`]));
  } catch (_) {}
}

$("btnCamStart").addEventListener("click", async () => {
  try {
    rec.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
    $("camPreview").srcObject = rec.stream;
    $("btnRec").disabled = false;
    toast("camera on — press ● Record");
  } catch (err) {
    toast("camera blocked: " + err.message, true);
  }
});

$("btnRec").addEventListener("click", () => {
  if (!rec.stream) return;
  rec.chunks = [];
  const mime = ["video/webm;codecs=vp9", "video/webm;codecs=vp8", "video/webm", "video/mp4"].find(t => MediaRecorder.isTypeSupported(t)) || "";
  rec.mediaRec = new MediaRecorder(rec.stream, mime ? { mimeType: mime } : undefined);
  rec.mediaRec.ondataavailable = (e) => { if (e.data.size) rec.chunks.push(e.data); };
  rec.mediaRec.onstop = () => {
    rec.blob = new Blob(rec.chunks, { type: rec.mediaRec.mimeType || "video/webm" });
    $("recPlayback").src = URL.createObjectURL(rec.blob);
    $("btnStop").disabled = true; $("btnRec").disabled = false;
    $("recStatus").textContent = `Recorded ${(rec.blob.size / 1024).toFixed(0)} KB — review, then tick consent and Save.`;
  };
  rec.mediaRec.start();
  $("btnRec").disabled = true; $("btnStop").disabled = false;
  toast("recording… press ■ Stop when done");
});

$("btnStop").addEventListener("click", () => { rec.mediaRec && rec.mediaRec.stop(); });

document.getElementById("recConsent").addEventListener("change", () => {
  $("btnSaveRec").disabled = !(document.getElementById("recConsent").checked && rec.blob);
});

$("btnSaveRec").addEventListener("click", async () => {
  const signerId = localSelectValue("recSigner");
  if (!signerId) return toast("choose a signer first", true);
  const c = rec.consent[signerId];
  if (!c) return toast("this signer has no granted consent — register one in the Register tab first", true);
  if (!rec.blob) return toast("record something first", true);
  if (!document.getElementById("recConsent").checked) return toast("tick the consent box to save", true);

  try {
    const name = "rec-" + Date.now() + ".webm";
    const up = await fetch("/api/upload/video?name=" + encodeURIComponent(name), {
      method: "POST", headers: { "Content-Type": rec.blob.type || "video/webm" }, body: rec.blob,
    });
    const upJson = await up.json();
    if (!up.ok) throw new Error(upJson.error || "upload failed");

    const s = await api("/samples", { method: "POST", body: {
      domain: localSelectValue("recDomain"),
      signer: { anon_id: signerId, region: c.region },
      gloss_seq: $("recGloss").value.trim().split(/[-,]+/).filter(Boolean),
      source: { kind: "self-recorded", provenance_notes: "recorded in-labeling-tool (webcam)" },
      video: { path: upJson.path, source_kind: "recorded" },
      _consent_status: "granted",
      _consent_form_id: c.form_id,
    }});
    toast("saved " + s.sample_id + " — now add votes in the Queue tab");
    $("recPlayback").src = ""; rec.blob = null; $("btnSaveRec").disabled = true;
    document.getElementById("recConsent").checked = false;
    refreshQueue(); refreshStats();
  } catch (err) { toast(err.message, true); }
});
function switchView(name) {
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  $("view-" + name).classList.add("active");
  document.querySelectorAll("nav button").forEach(b => b.classList.toggle("active", b.dataset.view === name));
  if (name === "stats") refreshStats();
  if (name === "register") refreshSignerSelect();
  if (name === "record") refreshSignerConsents();
}
document.querySelectorAll("nav button").forEach(b => b.addEventListener("click", () => switchView(b.dataset.view)));
$("queueDomain").addEventListener("change", refreshQueue);
$("queueStatus").addEventListener("change", refreshQueue);

function toast(msg, isError = false) {
  const t = $("toast");
  t.textContent = msg;
  t.classList.remove("hidden", "err");
  if (isError) t.classList.add("err");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), 2600);
}

boot();