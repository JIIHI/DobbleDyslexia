/* Word Spot online - runs in any modern browser (iPad, iPhone, Android, computer). */
"use strict";

const $ = (id) => document.getElementById(id);
const FONT_FAMILY = { opendyslexic: "OpenDyslexic", lexend: "Lexend", andika: "Andika" };
const BG = "#fdf6e3";   // used only if the server sends no card colour
const SVGNS = "http://www.w3.org/2000/svg";

let info = { decks: [], avatars: [], join_base: location.origin };
let me = { name: "", avatar: "" };
let mode = "together";        // "solo" or "together"
let roomCode = null;
let pid = null;
let ws = null;
let leaving = false;
let retries = 0;
let state = null;
let editing = false;          // showing the settings screen after a game
let drawnRound = -1;
let celebratedRound = -1;
let frozenUntil = 0;
let roundStartLocal = 0;
let wakeLock = null;
let speakOn = localStorage.getItem("ws_speak") !== "off";

/* ------------------------------------------------------------ helpers */
function show(screen) {
  for (const s of ["home", "lobby", "game", "results"]) $(s).classList.toggle("hidden", s !== screen);
}
function toast(text, ms = 2200) {
  const t = $("toast");
  t.textContent = text;
  t.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => t.classList.add("hidden"), ms);
}
function el(tag, attrs = {}, parent = null) {
  const node = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
  if (parent) parent.appendChild(node);
  return node;
}
function esc(text) {
  return String(text).replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
}
function isHost() { return state && state.host === pid; }
function player(id) { return state && state.players.find((p) => p.id === id); }

/* ------------------------------------------------------- sound + voice */
let audio = null;
function unlockAudio() {
  try {
    if (!audio) audio = new (window.AudioContext || window.webkitAudioContext)();
    if (audio.state === "suspended") audio.resume();
  } catch (e) { audio = null; }
  if (window.speechSynthesis && !unlockAudio.done) {
    const u = new SpeechSynthesisUtterance(" ");
    u.volume = 0;
    speechSynthesis.speak(u);
    unlockAudio.done = true;
  }
}
function tone(freqs, dur = 0.12, type = "sine", vol = 0.18) {
  if (!audio) return;
  let t = audio.currentTime;
  for (const f of freqs) {
    const o = audio.createOscillator(), g = audio.createGain();
    o.type = type; o.frequency.value = f;
    g.gain.setValueAtTime(vol, t);
    g.gain.exponentialRampToValueAtTime(0.001, t + dur);
    o.connect(g).connect(audio.destination);
    o.start(t); o.stop(t + dur);
    t += dur * 0.85;
  }
}
const chime = () => tone([660, 880, 1320], 0.14);
const softChime = () => tone([520, 700], 0.12, "sine", 0.1);
const bonk = () => tone([180, 140], 0.15, "triangle", 0.2);

function speak(word) {
  if (!speakOn || !window.speechSynthesis) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(word);
  u.lang = "en-GB";
  u.rate = 0.8;
  const voice = speechSynthesis.getVoices().find((v) => v.lang === "en-GB")
    || speechSynthesis.getVoices().find((v) => v.lang && v.lang.startsWith("en"));
  if (voice) u.voice = voice;
  speechSynthesis.speak(u);
}
function setSpeak(on) {
  speakOn = on;
  localStorage.setItem("ws_speak", on ? "on" : "off");
  $("speak-toggle").classList.toggle("off", !on);
  $("speak-toggle").textContent = on ? "🔊" : "🔈";
}

/* ---------------------------------------------------------------- home */
function buildHome() {
  me.name = localStorage.getItem("ws_name") || "";
  me.avatar = localStorage.getItem("ws_avatar") || info.avatars[Math.floor(Math.random() * info.avatars.length)];
  $("name").value = me.name;
  const box = $("avatars");
  box.innerHTML = "";
  for (const a of info.avatars) {
    const b = document.createElement("button");
    b.textContent = a;
    b.className = a === me.avatar ? "sel" : "";
    b.onclick = () => {
      me.avatar = a;
      localStorage.setItem("ws_avatar", a);
      for (const x of box.children) x.classList.toggle("sel", x === b);
    };
    box.appendChild(b);
  }
  const saved = localStorage.getItem("ws_family") || "";
  $("family").value = saved;
  $("family-box").classList.toggle("hidden", !info.needs_code || !!saved);
  const join = new URLSearchParams(location.search).get("join");
  if (join) $("code").value = join.toUpperCase();
}
function readName() {
  me.name = $("name").value.trim();
  if (!me.name) {
    $("home-error").textContent = "Type your name first 🙂";
    $("name").focus();
    return false;
  }
  localStorage.setItem("ws_name", me.name);
  localStorage.setItem("ws_avatar", me.avatar);
  $("home-error").textContent = "";
  return true;
}
async function newGame(m) {
  unlockAudio();
  if (!readName()) return;
  mode = m;
  const family = $("family").value.trim();
  if (info.needs_code && !family) {
    $("family-box").classList.remove("hidden");
    $("home-error").textContent = "Type the family code first.";
    $("family").focus();
    return;
  }
  let res;
  try {
    res = await fetch("/api/rooms", { method: "POST", headers: { "X-Family-Code": family } });
  } catch (e) {
    $("home-error").textContent = "Can't reach the Word Spot server.";
    return;
  }
  if (res.status === 403) {
    localStorage.removeItem("ws_family");
    $("family-box").classList.remove("hidden");
    $("home-error").textContent = "That family code isn't right.";
    return;
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    $("home-error").textContent = err.detail || "Something went wrong - try again.";
    return;
  }
  if (family) localStorage.setItem("ws_family", family);
  const data = await res.json();
  connect(data.code);
}
async function joinGame() {
  unlockAudio();
  if (!readName()) return;
  const code = $("code").value.trim().toUpperCase();
  if (code.length !== 4) { $("home-error").textContent = "Type the 4-letter game code."; return; }
  const res = await fetch(`/api/rooms/${code}`).catch(() => null);
  if (!res || !res.ok) { $("home-error").textContent = "No game with that code. Check the letters?"; return; }
  mode = "together";
  connect(code);
}

/* ----------------------------------------------------------- websocket */
function connect(code) {
  roomCode = code;
  leaving = false;
  pid = sessionStorage.getItem(`ws_pid_${code}`);
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const q = new URLSearchParams({ name: me.name, avatar: me.avatar });
  if (pid) q.set("pid", pid);
  ws = new WebSocket(`${proto}://${location.host}/ws/${code}?${q}`);
  ws.onopen = () => { retries = 0; };
  ws.onmessage = (ev) => onMessage(JSON.parse(ev.data));
  ws.onclose = () => {
    if (leaving || !roomCode) return;
    if (retries++ < 15) {
      toast("Reconnecting…", 1500);
      setTimeout(() => roomCode && !leaving && connect(roomCode), 1000);
    } else {
      toast("Lost connection to the game.");
      goHome();
    }
  };
}
function send(msg) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg));
}
function goHome() {
  leaving = true;
  if (ws) ws.close();
  ws = null; roomCode = null; state = null; editing = false; drawnRound = -1;
  releaseWakeLock();
  history.replaceState(null, "", "/");
  show("home");
}
function onMessage(msg) {
  if (msg.type === "error") {
    leaving = true;
    goHome();
    $("home-error").textContent = msg.message;
    return;
  }
  if (msg.type === "tap_result") {
    if (msg.result === "wrong" || msg.result === "frozen") wrongTap(msg.freeze || 1.5);
    return;
  }
  if (msg.type !== "state") return;
  pid = msg.you;
  sessionStorage.setItem(`ws_pid_${msg.room}`, pid);
  const prev = state;
  state = msg;
  if (state.players.length > 1) mode = "together";
  render(prev);
}

/* ---------------------------------------------------------------- lobby */
function buildDeckSelect() {
  const sel = $("s-deck");
  sel.innerHTML = "";
  for (const d of info.decks) sel.add(new Option(d.name, d.key));
  sel.add(new Option("✏️ My own words…", "custom"));
  $("s-custom").value = localStorage.getItem("ws_custom") || "";
}
function sendSettings(extra) {
  send({ type: "settings", settings: { ...state.settings, ...extra } });
}
function setSeg(id, value) {
  for (const b of $(id).children) b.classList.toggle("sel", String(b.dataset.v) === String(value));
}
function renderLobby() {
  show("lobby");
  const host = isHost();
  const s = state.settings;
  const solo = mode === "solo" && state.players.length === 1;
  $("invite").classList.toggle("hidden", solo);
  $("room-code").textContent = state.room;
  const link = `${info.join_base}/?join=${state.room}`;
  if ($("qr").dataset.link !== link) {
    $("qr").src = `/qr.svg?data=${encodeURIComponent(link)}`;
    $("qr").dataset.link = link;
  }
  $("join-link").textContent = link;
  $("print").href = `/print/${state.room}.pdf`;
  $("players").innerHTML = state.players.map((p) =>
    `<li class="${p.connected ? "" : "away"}"><span class="av">${p.avatar}</span>${esc(p.name)}${p.id === state.host ? " ⭐" : ""}</li>`).join("");

  const sel = $("s-deck");
  if (document.activeElement !== sel) sel.value = s.deck;
  $("custom-box").classList.toggle("hidden", sel.value !== "custom");
  if (s.deck === "custom") $("custom-msg").textContent = `${s.custom_count} words in use`;
  setSeg("s-rounds", s.rounds);
  setSeg("s-shape", s.shape);
  setSeg("s-per", s.words_per_card === 8 ? 0 : s.words_per_card);
  setSeg("s-font", s.font);
  setSeg("s-colours", s.colours);
  setSeg("s-circles", s.circles ? "on" : "off");
  setSeg("s-bg", s.background);
  const bgBtn = $("s-bg").querySelector(`[data-v="${s.background}"]`);
  if (bgBtn) $("s-colours").style.setProperty("--card-bg", bgBtn.dataset.hex);   // preview "abc" on that card colour
  for (const id of ["s-rounds", "s-shape", "s-per", "s-font", "s-colours", "s-bg", "s-circles"]) $(id).classList.toggle("readonly", !host);
  sel.disabled = !host;
  $("s-custom").disabled = !host;
  $("s-custom-use").classList.toggle("hidden", !host);
  $("start").classList.toggle("hidden", !host);
  $("wait-msg").classList.toggle("hidden", host);
  const deckName = s.deck === "custom" ? "Own words" : (info.decks.find((d) => d.key === s.deck) || {}).name;
  $("settings-readonly").textContent = host ? "" : deckName;
  $("start").textContent = solo ? "Start!" : (state.players.length < 2 ? "Start (waiting for others…)" : "Start!");
}
function bindLobby() {
  $("s-deck").onchange = () => {
    const v = $("s-deck").value;
    $("custom-box").classList.toggle("hidden", v !== "custom");
    if (v !== "custom") sendSettings({ deck: v });
  };
  $("s-custom-use").onclick = () => {
    const words = $("s-custom").value.split(/[\n,]+/).map((w) => w.trim()).filter(Boolean);
    localStorage.setItem("ws_custom", $("s-custom").value);
    if (new Set(words.map((w) => w.toLowerCase())).size < 7) {
      $("custom-msg").textContent = "Please type at least 7 different words.";
      return;
    }
    sendSettings({ deck: "custom", custom_words: words });
  };
  const seg = (id, key, num) => {
    for (const b of $(id).children) b.onclick = () => {
      if (!isHost()) return;
      sendSettings({ [key]: num ? Number(b.dataset.v) : b.dataset.v });
    };
  };
  seg("s-rounds", "rounds", true);
  seg("s-shape", "shape", false);
  seg("s-per", "words_per_card", true);
  seg("s-font", "font", false);
  seg("s-colours", "colours", false);
  seg("s-bg", "background", false);
  for (const b of $("s-circles").children) b.onclick = () => {
    if (isHost()) sendSettings({ circles: b.dataset.v === "on" });
  };
  $("start").onclick = () => { unlockAudio(); editing = false; send({ type: "start" }); };
  $("leave").onclick = goHome;
  $("print").onclick = () => toast("Making your cards - this takes a few seconds…", 6000);
}

/* ----------------------------------------------------------------- cards */
function drawCard(svg, card, font) {
  svg.innerHTML = "";
  const family = FONT_FAMILY[font] || "OpenDyslexic";
  const bg = card.bg || BG;
  // The bubble is always drawn - even when circles are off it is there (but
  // see-through) so taps between the letters count and the found/wrong ring
  // can still flash round the word.
  const bub = (w) => {
    const a = { class: "bub", fill: w.f || "transparent" };
    if (card.stroke) { a.stroke = card.stroke; a["stroke-width"] = 6; }
    return a;
  };
  if (card.shape === "rect") {
    svg.setAttribute("viewBox", "0 0 1000 1400");
    el("rect", { x: 6, y: 6, width: 988, height: 1388, rx: 60, fill: bg, stroke: "#2b2b2b", "stroke-width": 12 }, svg);
    const pad = 70, iw = 860, ih = 1260;
    for (const w of card.words) {
      const g = el("g", { class: "word", "data-word": w.w }, svg);
      const cx = pad + w.x * iw, cy = pad + w.y * ih, bw = w.bw * iw, bh = w.bh * ih;
      el("rect", { ...bub(w), x: cx - bw / 2, y: cy - bh / 2, width: bw, height: bh, rx: bh * 0.25 }, g);
      const t = el("text", { x: cx, y: cy, "text-anchor": "middle", "dominant-baseline": "central",
        "font-family": family, "font-size": w.fs * 1000, fill: w.c }, g);
      t.textContent = w.w;
    }
  } else {
    svg.setAttribute("viewBox", "-1010 -1010 2020 2020");
    el("circle", { cx: 0, cy: 0, r: 1000, fill: bg, stroke: "#2b2b2b", "stroke-width": 12 }, svg);
    const K = 985;
    for (const w of card.words) {
      const g = el("g", { class: "word", "data-word": w.w, transform: `translate(${w.x * K} ${w.y * K})` }, svg);
      el("circle", { ...bub(w), cx: 0, cy: 0, r: w.r * K }, g);
      const t = el("text", { x: 0, y: 0, "text-anchor": "middle", "dominant-baseline": "central",
        "font-family": family, "font-size": w.fs * K, fill: w.c, transform: `rotate(${-w.a})` }, g);
      t.textContent = w.w;
    }
  }
  for (const g of svg.querySelectorAll(".word")) {
    g.addEventListener("pointerdown", (ev) => { ev.preventDefault(); tapWord(g, svg); });
  }
}
function layoutCards() {
  if (!state || !state.cards.length) return;
  const ratio = state.cards[0].shape === "rect" ? 1.4 : 1;
  const barH = document.querySelector(".game-bar").offsetHeight;
  const W = window.innerWidth - 24, H = window.innerHeight - barH - 28, gap = 16;
  const rowW = Math.min((W - gap) / 2, H / ratio);
  const colW = Math.min(W, (H - gap) / 2 / ratio);
  const row = rowW >= colW;
  const cw = Math.floor(row ? rowW : colW);
  const box = $("cards");
  box.style.setProperty("--dir", row ? "row" : "column");
  box.style.setProperty("--cw", `${cw}px`);
  box.style.setProperty("--ch", `${Math.floor(cw * ratio)}px`);
}
function tapWord(g, svg) {
  if (!state || state.phase !== "playing") return;
  if (Date.now() < frozenUntil) return;
  unlockAudio();
  tapWord.last = { g, svg };
  send({ type: "tap", round: state.round, word: g.dataset.word });
}
function wrongTap(seconds) {
  bonk();
  frozenUntil = Date.now() + seconds * 1000;
  const last = tapWord.last;
  if (last) {
    last.g.classList.add("wrong");
    last.svg.classList.remove("shake");
    void last.svg.getBoundingClientRect();
    last.svg.classList.add("shake");
    setTimeout(() => last.g.classList.remove("wrong"), seconds * 1000);
  }
  $("freeze").classList.remove("hidden");
  setTimeout(() => $("freeze").classList.add("hidden"), seconds * 1000);
}
function mark(answer, cls, cardIdx = [0, 1]) {
  for (const i of cardIdx) {
    for (const g of $(`card${i}`).querySelectorAll(".word")) {
      if (g.dataset.word === answer) g.classList.add(cls);
    }
  }
}

/* ------------------------------------------------------------------ game */
function renderGame(prev) {
  show("game");
  requestWakeLock();
  const solo = state.players.length === 1;
  $("round").textContent = `${state.round} / ${state.total_rounds}`;
  $("scores").innerHTML = state.players.map((p) =>
    `<span class="score ${p.id === pid ? "me" : ""}" data-id="${p.id}"><span class="av">${p.avatar}</span>${solo ? "" : esc(p.name) + " "}${p.score}</span>`).join("");
  $("timer").classList.toggle("hidden", !solo);

  if (drawnRound !== state.round) {
    drawnRound = state.round;
    frozenUntil = 0;
    $("freeze").classList.add("hidden");
    $("banner").classList.add("hidden");
    drawCard($("card0"), state.cards[0], state.settings.font);
    drawCard($("card1"), state.cards[1], state.settings.font);
    layoutCards();
    roundStartLocal = Date.now() - (state.elapsed || 0) * 1000;
  }
  if (state.hint && state.answer) mark(state.answer, "hinted", [0]);

  if (state.phase === "answer" && celebratedRound !== state.round) {
    celebratedRound = state.round;
    mark(state.answer, "found");
    const w = player(state.winner);
    const banner = $("banner");
    if (state.winner === pid) {
      banner.textContent = solo ? `⭐ “${state.answer}”  ${state.win_time}s` : `⭐ You found “${state.answer}”!`;
      banner.className = "banner";
      chime();
    } else {
      banner.textContent = `${w ? w.avatar + " " + w.name : "Someone"} found “${state.answer}”`;
      banner.className = "banner other";
      softChime();
    }
    const chip = document.querySelector(`.score[data-id="${state.winner}"]`);
    if (chip) chip.classList.add("bump");
    speak(state.answer);
  }
}
setInterval(() => {
  if (!state || state.phase !== "playing" || $("game").classList.contains("hidden")) {
    $("hint-btn").classList.add("hidden");
    return;
  }
  const secs = (Date.now() - roundStartLocal) / 1000;
  $("timer").textContent = `${secs.toFixed(0)}s`;
  $("hint-btn").classList.toggle("hidden", state.hint || secs < state.hint_after);
}, 250);

/* --------------------------------------------------------------- results */
function renderResults() {
  show("results");
  releaseWakeLock();
  const res = state.results || [];
  const solo = res.length === 1;
  $("res-title").textContent = solo ? "Well done! 🎉" : `${res[0].avatar} ${res[0].name} wins! 🎉`;
  $("res-list").innerHTML = res.map((r) =>
    `<li><span class="av">${r.avatar}</span><span>${esc(r.name)}<span class="sub">${r.avg != null ? `about ${r.avg}s a word` : ""}</span></span><span class="pts">${r.score}</span></li>`).join("");
  $("res-best").textContent = "";
  if (solo && res[0].score) {
    const s = state.settings;
    const key = `ws_best_${s.deck}_${state.total_rounds}_${s.words_per_card}`;
    const best = parseFloat(localStorage.getItem(key) || "0");
    const total = res[0].total;
    if (!best || total < best) {
      if (best) $("res-best").textContent = `🏆 New personal best: ${total}s (was ${best}s)`;
      else $("res-best").textContent = `You found ${res[0].score} words in ${total}s`;
      localStorage.setItem(key, String(total));
    } else {
      $("res-best").textContent = `${total}s this time - your best is ${best}s`;
    }
  }
  const host = isHost();
  $("again").classList.toggle("hidden", !host);
  $("change").classList.toggle("hidden", !host);
  $("res-wait").classList.toggle("hidden", host);
}

/* ---------------------------------------------------------------- render */
function render(prev) {
  if (!state) return;
  if (state.phase === "lobby" || (state.phase === "finished" && editing)) {
    if (prev && prev.phase === "lobby" && state.players.length > prev.players.length && isHost()) softChime();
    renderLobby();
  } else if (state.phase === "playing" || state.phase === "answer") {
    editing = false;
    renderGame(prev);
  } else if (state.phase === "finished") {
    renderResults();
  }
  if (roomCode) history.replaceState(null, "", `/?join=${roomCode}`);
}

/* ------------------------------------------------------------ wake lock */
async function requestWakeLock() {
  if (wakeLock || !("wakeLock" in navigator)) return;
  try { wakeLock = await navigator.wakeLock.request("screen"); wakeLock.onrelease = () => { wakeLock = null; }; }
  catch (e) { wakeLock = null; }
}
function releaseWakeLock() { if (wakeLock) { wakeLock.release(); wakeLock = null; } }
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && state && state.phase !== "lobby" && state.phase !== "finished") requestWakeLock();
});

/* ------------------------------------------------------------------ init */
async function init() {
  try {
    info = await (await fetch("/api/info")).json();
  } catch (e) {
    $("home-error").textContent = "Can't reach the Word Spot server.";
  }
  buildHome();
  buildDeckSelect();
  bindLobby();
  setSpeak(speakOn);
  $("solo").onclick = () => newGame("solo");
  $("together").onclick = () => newGame("together");
  $("join").onclick = joinGame;
  $("code").addEventListener("keydown", (e) => { if (e.key === "Enter") joinGame(); });
  $("code").addEventListener("input", () => { $("code").value = $("code").value.toUpperCase().replace(/[^A-Z]/g, ""); });
  $("speak-toggle").onclick = () => { unlockAudio(); setSpeak(!speakOn); if (speakOn) speak("on"); };
  $("quit").onclick = () => { if (confirm("Leave this game?")) goHome(); };
  $("hint-btn").onclick = () => send({ type: "hint" });
  $("again").onclick = () => { unlockAudio(); send({ type: "start" }); };
  $("change").onclick = () => { editing = true; render(null); };
  $("home-btn").onclick = goHome;
  window.addEventListener("resize", layoutCards);
  window.addEventListener("orientationchange", () => setTimeout(layoutCards, 200));
  setInterval(() => send({ type: "ping" }), 20000);
  show("home");
}
init();
