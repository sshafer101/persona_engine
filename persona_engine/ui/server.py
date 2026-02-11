from __future__ import annotations

import asyncio
import json
import logging
import re
import traceback
import uuid
from typing import Any, Dict

from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse

from ..env import load_dotenv_if_present


# Support launching UI via either `persona-engine ui` or direct `uvicorn ...`.
load_dotenv_if_present(".env")

logger = logging.getLogger(__name__)


def _looks_like_url(s: str) -> bool:
    v = (s or "").strip().lower()
    return v.startswith("http://") or v.startswith("https://")


def _looks_like_env_name(s: str) -> bool:
    return bool(re.fullmatch(r"[A-Z_][A-Z0-9_]*", (s or "").strip()))


INDEX_HTML = r"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>Persona Engine Blob Sim</title>
    <style>
      :root {
        --bg0: #0b0f14;
        --bg1: #101925;
        --panel: rgba(255, 255, 255, 0.06);
        --panel2: rgba(255, 255, 255, 0.09);
        --text: rgba(255, 255, 255, 0.92);
        --muted: rgba(255, 255, 255, 0.65);
        --accent: #35c1ff;
        --bad: #ff5a7a;
        --ok: #7cff7c;
        --mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
        --sans: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial;
      }
      html, body { height: 100%; margin: 0; background: radial-gradient(1200px 800px at 20% 0%, #13243a, var(--bg0)); color: var(--text); font-family: var(--sans); }
      .wrap { display: grid; grid-template-columns: 360px 1fr; gap: 14px; height: 100%; padding: 14px; box-sizing: border-box; }
      .panel { background: var(--panel); border: 1px solid rgba(255,255,255,0.10); border-radius: 14px; backdrop-filter: blur(10px); overflow: hidden; }
      .panel h2 { margin: 0; padding: 12px 14px; font-size: 14px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); border-bottom: 1px solid rgba(255,255,255,0.10); }
      .controls { padding: 12px 14px; display: grid; gap: 10px; }
      .row { display: grid; gap: 6px; }
      label { font-size: 12px; color: var(--muted); }
      input, select { width: 100%; box-sizing: border-box; background: rgba(0,0,0,0.25); border: 1px solid rgba(255,255,255,0.14); color: var(--text); border-radius: 10px; padding: 9px 10px; font-family: var(--mono); }
      .btns { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; }
      button { border: 1px solid rgba(255,255,255,0.16); background: linear-gradient(180deg, rgba(53,193,255,0.18), rgba(0,0,0,0.12)); color: var(--text); padding: 10px 12px; border-radius: 12px; font-weight: 650; cursor: pointer; }
      button.secondary { background: rgba(255,255,255,0.06); }
      button:disabled { opacity: 0.55; cursor: not-allowed; }
      .statline { padding: 10px 14px; font-family: var(--mono); font-size: 12px; color: var(--muted); border-top: 1px solid rgba(255,255,255,0.10); display: flex; justify-content: space-between; gap: 12px; }
      .stage { position: relative; }
      .right { display: grid; grid-template-rows: minmax(280px, 1fr) minmax(260px, 1fr); min-height: 0; }
      canvas { width: 100%; height: 100%; display: block; background: radial-gradient(800px 520px at 50% 35%, var(--bg1), rgba(0,0,0,0.0)); }
      .log { display: grid; grid-template-rows: auto auto 1fr; min-height: 0; }
      .tabs { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 8px 10px; border-bottom: 1px solid rgba(255,255,255,0.10); }
      .tab { border: 1px solid rgba(255,255,255,0.14); background: rgba(255,255,255,0.04); color: var(--muted); padding: 8px 10px; border-radius: 10px; font-family: var(--mono); font-size: 12px; }
      .tab.active { color: var(--text); border-color: rgba(53,193,255,0.55); background: rgba(53,193,255,0.12); }
      .feed { padding: 10px 14px; overflow: auto; font-family: var(--mono); font-size: 12px; line-height: 1.35; }
      .feed .evt { padding: 8px 10px; border-radius: 12px; background: rgba(0,0,0,0.18); border: 1px solid rgba(255,255,255,0.10); margin-bottom: 10px; }
      .hidden { display: none; }
      .stats { padding: 10px 14px; overflow: auto; font-family: var(--mono); font-size: 12px; line-height: 1.45; }
      .inspector { padding: 8px 12px; border-bottom: 1px solid rgba(255,255,255,0.10); font-family: var(--mono); font-size: 12px; color: var(--muted); background: rgba(0,0,0,0.14); }
      .stats-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-bottom: 10px; }
      .stat-card { border: 1px solid rgba(255,255,255,0.12); background: rgba(0,0,0,0.18); border-radius: 10px; padding: 8px; }
      .leader { border-top: 1px solid rgba(255,255,255,0.10); padding-top: 8px; margin-top: 8px; }
      .tag { display: inline-block; padding: 2px 8px; border-radius: 999px; border: 1px solid rgba(255,255,255,0.14); margin-right: 8px; font-size: 11px; color: var(--muted); }
      .tag.bad { border-color: rgba(255,90,122,0.5); color: rgba(255,90,122,0.95); }
      .tag.ok { border-color: rgba(124,255,124,0.45); color: rgba(124,255,124,0.95); }
      .muted { color: var(--muted); }
      .mono { font-family: var(--mono); }
      @media (max-width: 980px) {
        .wrap { grid-template-columns: 1fr; grid-template-rows: auto 1fr; }
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="panel">
        <h2>Controls</h2>
        <div class="controls">
          <div class="row">
            <label>Seed</label>
            <input id="seed" type="number" value="123" />
          </div>
          <div class="row">
            <label>Agents (blobs)</label>
            <input id="agents" type="number" min="2" max="200" value="30" />
          </div>
          <div class="row">
            <label>Steps</label>
            <input id="steps" type="number" min="1" max="50000" value="2000" />
          </div>
          <div class="row">
            <label>Tick (ms, controls playback speed)</label>
            <input id="tickMs" type="number" min="0" max="2000" value="16" />
          </div>
          <div class="row">
            <label>Interaction radius</label>
            <input id="radius" type="number" step="0.01" min="0.01" max="0.30" value="0.06" />
          </div>
          <div class="row">
            <label>Speed</label>
            <input id="speed" type="number" step="0.005" min="0.005" max="0.20" value="0.02" />
          </div>
          <div class="row">
            <label>Decider</label>
            <select id="decider">
              <option value="heuristic">heuristic</option>
              <option value="openai">openai</option>
            </select>
          </div>
          <div class="row">
            <label>Model (decider=openai)</label>
            <select id="model">
              <option value="gpt-4o-mini" selected>gpt-4o-mini</option>
              <option value="gpt-4.1-mini">gpt-4.1-mini</option>
              <option value="gpt-4.1">gpt-4.1</option>
              <option value="gpt-5-mini">gpt-5-mini</option>
              <option value="gpt-5">gpt-5</option>
              <option value="grok-3-mini">grok-3-mini (xAI)</option>
              <option value="grok-3">grok-3 (xAI)</option>
              <option value="custom">custom...</option>
            </select>
            <input id="modelCustom" type="text" placeholder="enter custom model id" style="display:none; margin-top:6px;" />
          </div>
          <div class="row">
            <label>Temperature (decider=openai)</label>
            <input id="temp" type="number" step="0.05" min="0" max="2" value="0.30" />
          </div>
          <div class="row">
            <label>Max conversation lines (<= 20 recommended)</label>
            <input id="maxMsgs" type="number" min="1" max="20" value="20" />
          </div>
          <div class="row">
            <label>Max interactions per tick</label>
            <input id="maxPerTick" type="number" min="1" max="200" value="4" />
          </div>
          <div class="row">
            <label>LLM concurrency (decider=openai)</label>
            <input id="llmConc" type="number" min="1" max="64" value="4" />
          </div>
          <div class="row">
            <label>Max pending LLM requests</label>
            <input id="maxPending" type="number" min="1" max="256" value="8" />
          </div>
          <div class="row">
            <label>Pair cache size</label>
            <input id="pairCache" type="number" min="0" max="200000" value="2000" />
          </div>
          <div class="row">
            <label>Memory size (recent interactions)</label>
            <input id="memorySize" type="number" min="1" max="64" value="8" />
          </div>
          <div class="row">
            <label>API base URL (optional)</label>
            <input id="baseUrl" type="text" placeholder="https://api.x.ai/v1" />
          </div>
          <div class="row">
            <label>API key env var (server-side)</label>
            <input id="keyEnv" type="text" value="OPENAI_API_KEY" />
          </div>
          <div class="btns">
            <button id="startBtn">Start</button>
            <button id="pauseBtn" class="secondary" disabled>Pause</button>
            <button id="resetBtn" class="secondary">Reset</button>
          </div>
          <div id="status" class="muted mono" style="font-size:12px;">status: idle</div>
          <div class="muted" style="font-size:12px;">
            Tip: for model comparisons, use the CLI benchmarks. This UI is for watching the chaos.
          </div>
        </div>
        <div class="statline">
          <div><span class="mono">t=</span><span id="tVal" class="mono">-</span></div>
          <div><span class="mono">alive=</span><span id="aliveVal" class="mono">-</span></div>
        </div>
      </div>

      <div class="panel right">
        <div class="stage">
          <canvas id="cv"></canvas>
        </div>
        <div class="log panel" style="border:none; border-radius:0; background:transparent;">
          <h2>Interactions</h2>
          <div class="tabs">
            <button id="tabInteractions" class="tab active">Interactions</button>
            <button id="tabStats" class="tab">Stats</button>
          </div>
          <div id="inspector" class="inspector">paused inspector: click Pause, then hover/click a blob</div>
          <div id="feed" class="feed"></div>
          <div id="statsPane" class="stats hidden"></div>
        </div>
      </div>
    </div>

    <script>
      const cv = document.getElementById("cv");
      const ctx = cv.getContext("2d");
      const feed = document.getElementById("feed");
      const statsPane = document.getElementById("statsPane");
      const tVal = document.getElementById("tVal");
      const aliveVal = document.getElementById("aliveVal");
      const tabInteractions = document.getElementById("tabInteractions");
      const tabStats = document.getElementById("tabStats");
      const inspector = document.getElementById("inspector");
      const modelSelect = document.getElementById("model");
      const modelCustom = document.getElementById("modelCustom");
      const baseUrlInput = document.getElementById("baseUrl");
      const keyEnvInput = document.getElementById("keyEnv");
      const startBtn = document.getElementById("startBtn");
      const pauseBtn = document.getElementById("pauseBtn");
      const resetBtn = document.getElementById("resetBtn");

      function resize() {
        const r = cv.getBoundingClientRect();
        cv.width = Math.max(2, Math.floor(r.width * devicePixelRatio));
        cv.height = Math.max(2, Math.floor(r.height * devicePixelRatio));
      }
      window.addEventListener("resize", resize);
      resize();

      let ws = null;
      let latest = null;
      let highlight = null;
      let pausedMode = false;
      let hoveredBlobId = null;
      let lockedBlobId = null;
      const statusEl = document.getElementById("status");
      let runStats = null;

      function initRunStats() {
        return {
          ticks: 0,
          interactions: 0,
          pair: 0,
          fling: 0,
          avoid: 0,
          removed: 0,
          pairedExit: 0,
          alive: 0,
          mostConnected: [],
          mostViolent: [],
          mostPromiscuous: []
        };
      }

      function switchTab(tab) {
        const showStats = tab === "stats";
        feed.classList.toggle("hidden", showStats);
        statsPane.classList.toggle("hidden", !showStats);
        tabInteractions.classList.toggle("active", !showStats);
        tabStats.classList.toggle("active", showStats);
      }
      tabInteractions.addEventListener("click", () => switchTab("interactions"));
      tabStats.addEventListener("click", () => switchTab("stats"));

      function renderStats() {
        if (!runStats) return;
        const safe = (s) => String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
        const interactions = runStats.interactions || 1;
        const killRate = runStats.removed / interactions;
        const pairRate = runStats.pair / interactions;
        const flingRate = runStats.fling / interactions;
        let html = `<div class="stats-grid">
          <div class="stat-card"><div class="muted">ticks</div><div>${runStats.ticks}</div></div>
          <div class="stat-card"><div class="muted">alive</div><div>${runStats.alive}</div></div>
          <div class="stat-card"><div class="muted">interactions</div><div>${runStats.interactions}</div></div>
          <div class="stat-card"><div class="muted">kill count</div><div>${runStats.removed}</div></div>
          <div class="stat-card"><div class="muted">pair exits</div><div>${runStats.pairedExit}</div></div>
          <div class="stat-card"><div class="muted">kill rate</div><div>${killRate.toFixed(3)}</div></div>
          <div class="stat-card"><div class="muted">pair rate</div><div>${pairRate.toFixed(3)}</div></div>
          <div class="stat-card"><div class="muted">fling rate</div><div>${flingRate.toFixed(3)}</div></div>
        </div>`;
        html += `<div class="leader"><div class="muted">most connected</div>`;
        if (!runStats.mostConnected.length) {
          html += `<div class="muted">no data yet</div>`;
        } else {
          for (const x of runStats.mostConnected.slice(0, 8)) {
            html += `<div><span class="mono">${safe(x.name)}</span> <span class="muted">known=${x.known_count}</span> ${x.alive ? "" : "<span class='muted'>(out)</span>"}</div>`;
          }
        }
        html += `</div>`;
        html += `<div class="leader"><div class="muted">most violent (reputation)</div>`;
        if (!runStats.mostViolent.length) {
          html += `<div class="muted">no data yet</div>`;
        } else {
          for (const x of runStats.mostViolent.slice(0, 6)) {
            html += `<div><span class="mono">${safe(x.name)}</span> <span class="muted">violence_rep=${x.violence_rep}</span></div>`;
          }
        }
        html += `</div>`;
        html += `<div class="leader"><div class="muted">most promiscuous (reputation)</div>`;
        if (!runStats.mostPromiscuous.length) {
          html += `<div class="muted">no data yet</div>`;
        } else {
          for (const x of runStats.mostPromiscuous.slice(0, 6)) {
            html += `<div><span class="mono">${safe(x.name)}</span> <span class="muted">promiscuity_rep=${x.promiscuity_rep}</span></div>`;
          }
        }
        html += `</div>`;
        statsPane.innerHTML = html;
      }

      function updateRunStats(frameMsg) {
        if (!runStats) runStats = initRunStats();
        runStats.ticks = frameMsg.t;
        runStats.alive = frameMsg.blobs.filter(b => b.alive).length;
        const evs = (frameMsg.events && frameMsg.events.length) ? frameMsg.events : (frameMsg.event ? [frameMsg.event] : []);
        for (const ev of evs) {
          runStats.interactions += 1;
          if (ev.outcome === "pair") runStats.pair += 1;
          else if (ev.outcome === "fling") runStats.fling += 1;
          else if (ev.outcome === "avoid") runStats.avoid += 1;
          if (ev.detail && ev.detail.reason === "avoid_elimination") runStats.removed += 1;
          if (ev.detail && ev.detail.reason === "pair_exit") runStats.pairedExit += 2;
        }
        const connected = frameMsg.blobs.map(b => ({name: b.name, known_count: Number(b.known_count || 0), alive: !!b.alive}));
        connected.sort((a, b) => (b.known_count - a.known_count) || (a.name < b.name ? -1 : 1));
        runStats.mostConnected = connected.slice(0, 12);
        const violent = frameMsg.blobs.map(b => ({name: b.name, violence_rep: Number(b.violence_rep || 0)}));
        violent.sort((a, b) => (b.violence_rep - a.violence_rep) || (a.name < b.name ? -1 : 1));
        runStats.mostViolent = violent.filter(x => x.violence_rep > 0).slice(0, 12);
        const prom = frameMsg.blobs.map(b => ({name: b.name, promiscuity_rep: Number(b.promiscuity_rep || 0)}));
        prom.sort((a, b) => (b.promiscuity_rep - a.promiscuity_rep) || (a.name < b.name ? -1 : 1));
        runStats.mostPromiscuous = prom.filter(x => x.promiscuity_rep > 0).slice(0, 12);
        renderStats();
      }

      function setStatus(s) {
        statusEl.textContent = "status: " + s;
      }

      function pushSystemError(msg) {
        const div = document.createElement("div");
        div.className = "evt";
        const safe = (s) => String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
        div.innerHTML = `<div><span class="tag bad">error</span> <span class="muted">${safe(msg)}</span></div>`;
        feed.prepend(div);
      }

      function colorFor(id) {
        // Stable-ish HSL.
        const h = (id * 47) % 360;
        return `hsl(${h} 85% 60%)`;
      }

      function draw() {
        if (!latest) {
          requestAnimationFrame(draw);
          return;
        }
        const W = cv.width, H = cv.height;
        ctx.clearRect(0, 0, W, H);

        // faint grid
        ctx.save();
        ctx.globalAlpha = 0.08;
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1 * devicePixelRatio;
        const step = Math.max(24, Math.floor(60 * devicePixelRatio));
        for (let x = 0; x < W; x += step) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke(); }
        for (let y = 0; y < H; y += step) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke(); }
        ctx.restore();

        // blobs
        for (const b of latest.blobs) {
          const x = b.x * W;
          const y = b.y * H;
          const alive = !!b.alive;
          const r = (alive ? 6 : 3) * devicePixelRatio;
          const c = colorFor(b.id);

          ctx.beginPath();
          ctx.arc(x, y, r, 0, Math.PI * 2);
          ctx.fillStyle = alive ? c : "rgba(255,255,255,0.22)";
          ctx.fill();

          if (highlight && (highlight.a === b.id || highlight.b === b.id)) {
            ctx.beginPath();
            ctx.arc(x, y, (r + 7 * devicePixelRatio), 0, Math.PI * 2);
            ctx.strokeStyle = "rgba(53,193,255,0.85)";
            ctx.lineWidth = 2.2 * devicePixelRatio;
            ctx.stroke();
          }

          const focused = (lockedBlobId === b.id) || (lockedBlobId == null && hoveredBlobId === b.id);
          if (focused) {
            ctx.beginPath();
            ctx.arc(x, y, (r + 11 * devicePixelRatio), 0, Math.PI * 2);
            ctx.strokeStyle = "rgba(255,255,255,0.90)";
            ctx.lineWidth = 1.8 * devicePixelRatio;
            ctx.stroke();
          }
        }

        requestAnimationFrame(draw);
      }
      requestAnimationFrame(draw);

      function blobById(id) {
        if (!latest || id == null) return null;
        for (const b of latest.blobs) if (b.id === id) return b;
        return null;
      }

      function updateInspectorFromBlob(blob, pinned=false) {
        if (!blob) {
          inspector.textContent = pausedMode
            ? "paused inspector: hover/click a blob"
            : "paused inspector: click Pause, then hover/click a blob";
          return;
        }
        const state = blob.alive ? "alive" : ("out (" + (blob.exit_reason || "unknown") + ")");
        inspector.textContent =
          (pinned ? "[pinned] " : "") +
          blob.name +
          " | id=" + blob.id +
          " | seed=" + blob.seed +
          " | violence_rep=" + (blob.violence_rep || 0) +
          " | promiscuity_rep=" + (blob.promiscuity_rep || 0) +
          " | known=" + (blob.known_count || 0) +
          " | memories=" + (blob.memory_count || 0) +
          " | " + state;
      }

      function pickBlobAtEvent(evt) {
        if (!latest) return null;
        const rect = cv.getBoundingClientRect();
        const px = (evt.clientX - rect.left) * devicePixelRatio;
        const py = (evt.clientY - rect.top) * devicePixelRatio;
        const W = cv.width, H = cv.height;
        const maxDist2 = Math.pow(12 * devicePixelRatio, 2);
        let best = null;
        let bestD2 = maxDist2;
        for (const b of latest.blobs) {
          const bx = b.x * W;
          const by = b.y * H;
          const dx = bx - px;
          const dy = by - py;
          const d2 = dx * dx + dy * dy;
          if (d2 <= bestD2) {
            bestD2 = d2;
            best = b;
          }
        }
        return best;
      }

      cv.addEventListener("mousemove", (evt) => {
        if (!pausedMode) return;
        if (lockedBlobId != null) return;
        const b = pickBlobAtEvent(evt);
        hoveredBlobId = b ? b.id : null;
        updateInspectorFromBlob(b, false);
      });

      cv.addEventListener("click", (evt) => {
        if (!pausedMode) return;
        const b = pickBlobAtEvent(evt);
        if (!b) {
          lockedBlobId = null;
          hoveredBlobId = null;
          updateInspectorFromBlob(null, false);
          return;
        }
        if (lockedBlobId === b.id) {
          lockedBlobId = null;
          hoveredBlobId = b.id;
          updateInspectorFromBlob(b, false);
          return;
        }
        lockedBlobId = b.id;
        hoveredBlobId = b.id;
        updateInspectorFromBlob(b, true);
      });

      function pushEvent(evt) {
        const isKill = evt.outcome === "avoid" && evt.detail && evt.detail.reason === "avoid_elimination";
        const tagClass = isKill ? "bad" : (evt.outcome === "pair" ? "ok" : "");
        const div = document.createElement("div");
        div.className = "evt";
        const safe = (s) => String(s).replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;");
        const label = isKill ? "kill" : evt.outcome;
        let html = `<div><span class="tag ${tagClass}">${safe(label)}</span><span class="muted">t=${evt.t}</span> <span class="mono">${safe(evt.a.name)}</span> vs <span class="mono">${safe(evt.b.name)}</span></div>`;
        if (isKill && evt.detail) {
          const loserId = evt.detail.eliminated_id;
          const loserName = (evt.a.id === loserId) ? evt.a.name : evt.b.name;
          const winnerName = (evt.a.id === loserId) ? evt.b.name : evt.a.name;
          html += `<div class="muted" style="margin-top:4px;"><span class="mono">${safe(winnerName)}</span> avoided out <span class="mono">${safe(loserName)}</span></div>`;
        }
        if (evt.chat && evt.chat.length) {
          html += `<div style="margin-top:6px;">`;
          for (const m of evt.chat) {
            html += `<div><span class="muted">${safe(m.speaker)}:</span> ${safe(m.text)}</div>`;
          }
          html += `</div>`;
        }
        div.innerHTML = html;
        feed.prepend(div);
      }

      function getCfg() {
        const selectedModel = modelSelect.value === "custom"
          ? (modelCustom.value || "").trim()
          : modelSelect.value;
        const cfg = {
          seed: parseInt(document.getElementById("seed").value || "123", 10),
          agents: parseInt(document.getElementById("agents").value || "30", 10),
          steps: parseInt(document.getElementById("steps").value || "2000", 10),
          tick_ms: parseInt(document.getElementById("tickMs").value || "16", 10),
          interaction_radius: parseFloat(document.getElementById("radius").value || "0.06"),
          speed: parseFloat(document.getElementById("speed").value || "0.02"),
          decider: document.getElementById("decider").value,
          openai_model: selectedModel || "gpt-4o-mini",
          openai_temperature: parseFloat(document.getElementById("temp").value || "0.3"),
          max_messages: parseInt(document.getElementById("maxMsgs").value || "20", 10),
          max_interactions_per_tick: parseInt(document.getElementById("maxPerTick").value || "4", 10),
          llm_concurrency: parseInt(document.getElementById("llmConc").value || "4", 10),
          max_pending_requests: parseInt(document.getElementById("maxPending").value || "8", 10),
          pair_cache_size: parseInt(document.getElementById("pairCache").value || "2000", 10),
          memory_size: parseInt(document.getElementById("memorySize").value || "8", 10),
          api_base_url: (document.getElementById("baseUrl").value || "").trim() || null,
          api_key_env: (document.getElementById("keyEnv").value || "").trim() || "OPENAI_API_KEY"
        };
        if (cfg.decider === "openai") {
          const base = cfg.api_base_url || "";
          const env = cfg.api_key_env || "";
          const looksUrl = /^https?:\/\//i.test(base);
          const looksEnv = /^[A-Z_][A-Z0-9_]*$/.test(base);
          const envLooksUrl = /^https?:\/\//i.test(env);
          const keyLooksEnv = /^[A-Z_][A-Z0-9_]*$/.test(env);

          // Auto-fix accidental swap.
          if (!looksUrl && looksEnv && envLooksUrl) {
            cfg.api_base_url = env;
            cfg.api_key_env = base;
          }
          // Hard fail with clear message.
          if (cfg.api_base_url && !/^https?:\/\//i.test(cfg.api_base_url)) {
            throw new Error("API base URL must be a URL (e.g. https://api.x.ai/v1) or blank.");
          }
          if (!keyLooksEnv) {
            throw new Error("API key env must look like OPENAI_API_KEY or XAI_API_KEY.");
          }
        }
        return cfg;
      }

      function syncModelInput() {
        const isCustom = modelSelect.value === "custom";
        modelCustom.style.display = isCustom ? "block" : "none";

        // Convenience provider presets.
        if (modelSelect.value.startsWith("grok-")) {
          if (!(baseUrlInput.value || "").trim()) baseUrlInput.value = "https://api.x.ai/v1";
          if (!(keyEnvInput.value || "").trim() || keyEnvInput.value === "OPENAI_API_KEY") keyEnvInput.value = "XAI_API_KEY";
        } else if (modelSelect.value.startsWith("gpt-")) {
          // Flip back to OpenAI defaults when selecting GPT models.
          if ((baseUrlInput.value || "").trim() === "https://api.x.ai/v1") baseUrlInput.value = "";
          if (!(keyEnvInput.value || "").trim() || keyEnvInput.value === "XAI_API_KEY") keyEnvInput.value = "OPENAI_API_KEY";
        }
      }
      modelSelect.addEventListener("change", syncModelInput);
      syncModelInput();

      function setButtons(running) {
        startBtn.disabled = running;
        pauseBtn.disabled = !running;
        resetBtn.disabled = false;
      }

      function stop({setIdle=true} = {}) {
        if (ws) {
          try { ws.close(); } catch {}
          ws = null;
        }
        setButtons(false);
        if (setIdle) setStatus("idle");
      }

      function resetView() {
        feed.innerHTML = "";
        statsPane.innerHTML = "";
        latest = null;
        highlight = null;
        pausedMode = false;
        hoveredBlobId = null;
        lockedBlobId = null;
        runStats = initRunStats();
        renderStats();
        updateInspectorFromBlob(null, false);
        tVal.textContent = "-";
        aliveVal.textContent = "-";
      }

      startBtn.addEventListener("click", () => {
        stop({setIdle:true});
        resetView();
        setStatus("connecting...");

        ws = new WebSocket((location.protocol === "https:" ? "wss://" : "ws://") + location.host + "/ws");
        ws.onopen = () => {
          setButtons(true);
          pausedMode = false;
          setStatus("running (waiting on model if openai)");
          try {
            ws.send(JSON.stringify(getCfg()));
          } catch (e) {
            const msg = (e && e.message) ? e.message : String(e);
            setStatus("error: " + msg);
            pushSystemError(msg);
            stop({setIdle:false});
          }
        };
        ws.onmessage = (ev) => {
          const msg = JSON.parse(ev.data);
          if (msg.type === "frame") {
            latest = msg;
            tVal.textContent = String(msg.t);
            const alive = msg.blobs.filter(b => b.alive).length;
            aliveVal.textContent = String(alive);
            if (msg.inflight_requests && msg.inflight_requests > 0) {
              setStatus("running (inflight LLM: " + msg.inflight_requests + ")");
            } else if ((statusEl.textContent || "").includes("inflight LLM")) {
              setStatus("running");
            }
            updateRunStats(msg);
            const evs = (msg.events && msg.events.length) ? msg.events : (msg.event ? [msg.event] : []);
            if (evs.length) {
              const last = evs[evs.length - 1];
              highlight = {a: last.a.id, b: last.b.id};
              for (const ev of evs) pushEvent(ev);
              // clear highlight after a moment
              setTimeout(() => { highlight = null; }, 600);
            }
          } else if (msg.type === "error") {
            const trace = msg.trace_id ? (" trace_id=" + msg.trace_id) : "";
            const errType = msg.error_type ? (msg.error_type + ": ") : "";
            const full = errType + (msg.message || "server error") + trace;
            setStatus("error: " + full);
            pushSystemError(full);
            stop({setIdle:false});
          } else if (msg.type === "done") {
            setStatus("done");
            stop({setIdle:false});
          }
        };
        ws.onclose = (ev) => {
          // If it closes immediately, this is usually a server-side websocket rejection.
          setButtons(false);
          if (ev && typeof ev.code === "number") {
            if (ev.code !== 1000) setStatus("closed (" + ev.code + ")");
          } else {
            setStatus("closed");
          }
        };
        ws.onerror = () => {
          setStatus("websocket error (check server output)");
          stop({setIdle:false});
        };
      });

      pauseBtn.addEventListener("click", () => {
        if (!ws) return;
        stop({setIdle:false});
        pausedMode = true;
        lockedBlobId = null;
        hoveredBlobId = null;
        updateInspectorFromBlob(null, false);
        setStatus("paused");
      });

      resetBtn.addEventListener("click", () => {
        stop({setIdle:false});
        resetView();
        setStatus("reset");
      });
    </script>
  </body>
</html>
"""


def create_app():
    from ..sim.blob_sim import iter_blob_sim

    app = FastAPI()

    @app.get("/")
    async def index():
        return HTMLResponse(INDEX_HTML)

    @app.websocket("/ws")
    async def ws_endpoint(websocket: WebSocket):
        # FastAPI expects the parameter name `websocket` here; other names may
        # be treated as dependency injection and cause the connection to be rejected.
        await websocket.accept()
        trace_id = uuid.uuid4().hex[:12]
        try:
            raw = await websocket.receive_text()
            cfg: Dict[str, Any] = json.loads(raw)

            # Defensive normalization for common UI/user mixups.
            decider = str(cfg.get("decider", "heuristic"))
            if decider == "openai":
                base = str(cfg.get("api_base_url", "") or "").strip()
                key_env = str(cfg.get("api_key_env", "OPENAI_API_KEY") or "").strip()

                # If swapped (base has env name, key has URL), auto-fix.
                if base and _looks_like_env_name(base) and _looks_like_url(key_env):
                    logger.warning("Swapped api_base_url/api_key_env detected; auto-correcting trace_id=%s", trace_id)
                    base, key_env = key_env, base
                    cfg["api_base_url"] = base
                    cfg["api_key_env"] = key_env

                if base and not _looks_like_url(base):
                    raise ValueError(
                        f"Invalid API base URL '{base}'. Expected URL like https://api.x.ai/v1 "
                        f"or leave empty for default provider."
                    )
                if not _looks_like_env_name(key_env):
                    raise ValueError(
                        f"Invalid API key env name '{key_env}'. Expected something like OPENAI_API_KEY or XAI_API_KEY."
                    )
            logger.info(
                "WS run start trace_id=%s decider=%s model=%s base_url=%s key_env=%s",
                trace_id,
                decider,
                str(cfg.get("openai_model", "gpt-4o-mini")),
                str(cfg.get("api_base_url", "")),
                str(cfg.get("api_key_env", "OPENAI_API_KEY")),
            )

            tick_ms = int(cfg.get("tick_ms", 16))
            tick_s = max(0.0, tick_ms / 1000.0)

            for frame in iter_blob_sim(
                seed=int(cfg.get("seed", 123)),
                agents=int(cfg.get("agents", 30)),
                steps=int(cfg.get("steps", 2000)),
                interaction_radius=float(cfg.get("interaction_radius", 0.06)),
                speed=float(cfg.get("speed", 0.02)),
                decider=str(cfg.get("decider", "heuristic")),
                openai_model=str(cfg.get("openai_model", "gpt-4o-mini")),
                openai_temperature=float(cfg.get("openai_temperature", 0.3)),
                api_base_url=cfg.get("api_base_url", None),
                api_key_env=str(cfg.get("api_key_env", "OPENAI_API_KEY")),
                max_messages=int(cfg.get("max_messages", 20)),
                llm_concurrency=int(cfg.get("llm_concurrency", 4)),
                max_pending_requests=int(cfg.get("max_pending_requests", 8)),
                pair_cache_size=int(cfg.get("pair_cache_size", 2000)),
                max_interactions_per_tick=int(cfg.get("max_interactions_per_tick", 4)),
                memory_size=int(cfg.get("memory_size", 8)),
            ):
                await websocket.send_text(json.dumps({"type": "frame", **frame}, ensure_ascii=False))
                if tick_s:
                    await asyncio.sleep(tick_s)

            await websocket.send_text(json.dumps({"type": "done"}))
        except Exception as e:
            tb = traceback.format_exc(limit=20)
            logger.error("WS run failed trace_id=%s error=%s\n%s", trace_id, str(e), tb)
            payload = {
                "type": "error",
                "trace_id": trace_id,
                "error_type": type(e).__name__,
                "message": str(e),
                "details": {
                    "hint": "Check API key env, model name, and API base URL for provider compatibility.",
                },
            }
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))
        finally:
            try:
                await websocket.close()
            except Exception:
                pass

    return app


app = create_app()
