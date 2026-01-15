// Task Center (browser-only). Renders into <section id="task-center"> when it becomes visible.
// - No Node APIs, no redeclare of globals like showTab/spawnSync.
// - Uses /api/robots and /api/tasks (POST {instruction, site, dryRun})
(function () {
  const HOST_ID = "task-center";
  const host = document.getElementById(HOST_ID);
  if (!host) return;

  if (typeof window.showTab !== "function") {
    window.showTab = function (id) {
      try {
        const hostEl = document.getElementById(HOST_ID);
        const mainSections = Array.from(document.querySelectorAll(".main section, .main .card, .main .grid, .main .filters, .main .content"));
        if (id === HOST_ID || id === "task-center") {
          mainSections.forEach(el => { if (el !== hostEl) el.style.display = "none"; });
          hostEl.style.display = "block";
          if (typeof window.renderTaskCenter === "function") window.renderTaskCenter();
        } else {
          hostEl.style.display = "none";
          mainSections.forEach(el => el.style.display = "");
        }
      } catch (e) { console.error("showTab error", e); }
    };
  }

  const esc = (s = "") => String(s ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");

  function safeParseJSON(maybe) {
    if (!maybe && maybe !== "") return null;
    if (typeof maybe === "object") return maybe;
    if (typeof maybe !== "string") return null;
    maybe = maybe.trim();
    if (!maybe) return null;
    try {
      return JSON.parse(maybe);
    } catch (e) {
      const arrStart = maybe.indexOf("[");
      const objStart = maybe.indexOf("{");
      const start = (arrStart >= 0 ? arrStart : (objStart >= 0 ? objStart : -1));
      if (start >= 0) {
        const substr = maybe.slice(start);
        try { return JSON.parse(substr); } catch (_) {}
      }
      return null;
    }
  }

  function normalizeGlobalPlan(raw) {
    const parsed = safeParseJSON(raw) ?? raw;
    if (!parsed) return [];
    if (Array.isArray(parsed)) return parsed.map(normalizeGlobalItem);
    if (typeof parsed === "object") {
      if (Array.isArray(parsed.plan)) return parsed.plan.map(normalizeGlobalItem);
      if (Array.isArray(parsed.global)) return parsed.global.map(normalizeGlobalItem);
      if (parsed.robots) {
        const out = [];
        for (const [rid, tasks] of Object.entries(parsed.robots)) {
          (Array.isArray(tasks) ? tasks : [tasks]).forEach((t, i) => out.push({ robot_id: rid, task: t.task || String(t), task_order: t.task_order ?? i }));
        }
        return out;
      }
    }
    return [];
  }

  function normalizeGlobalItem(item) {
    if (!item) return { robot_id: "unknown", task: "", task_order: 0 };
    if (typeof item === "string") return { robot_id: "unknown", task: item, task_order: 0 };
    return {
      robot_id: item.robot_id || item.robot || item.agent || "unknown",
      task: item.task || item.action || item.name || JSON.stringify(item),
      task_order: Number(item.task_order ?? item.order ?? 0)
    };
  }

  function normalizeRobotCalls(raw) {
    const parsed = safeParseJSON(raw) ?? raw;
    if (!parsed) return {};
    if (Array.isArray(parsed)) {
      const map = {};
      for (const it of parsed) {
        if (it.robot_id && Array.isArray(it.actions)) {
          map[it.robot_id] = it.actions.slice();
        } else if (it.robot_id && it.action) {
          map[it.robot_id] = map[it.robot_id] || [];
          map[it.robot_id].push({ action: it.action, arguments: it.arguments ?? "" });
        }
      }
      return map;
    }
    if (typeof parsed === "object") {
      const out = {};
      for (const [k, v] of Object.entries(parsed)) {
        if (Array.isArray(v)) {
          out[k] = v.map(s => typeof s === "string" ? { action: s, arguments: "" } : { action: s.action || String(s), arguments: s.arguments ?? s.args ?? "" });
        } else if (typeof v === "string") {
          out[k] = [{ action: v, arguments: "" }];
        }
      }
      return out;
    }
    return {};
  }

  function createEl(tag = "div", props = {}, children = []) {
    const el = document.createElement(tag);
    for (const [k, v] of Object.entries(props || {})) {
      if (k === "class") el.className = v;
      else if (k === "style" && typeof v === "object") Object.assign(el.style, v);
      else if (k.startsWith("on") && typeof v === "function") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, String(v));
    }
    for (const c of children) {
      if (typeof c === "string") el.appendChild(document.createTextNode(c));
      else if (c instanceof Node) el.appendChild(c);
    }
    return el;
  }

  function renderGantt(container, plan) {
    container.innerHTML = "";
    if (!plan || !Array.isArray(plan.steps) || plan.steps.length === 0) {
      container.appendChild(createEl("div", { style: { color: "#b0b6bd" } }, ["无计划数据"]));
      return;
    }
    const rows = {};
    plan.steps.forEach(s => {
      const rid = s.assignedRobotId || s.robot_id || "未分配";
      rows[rid] = rows[rid] || [];
      rows[rid].push(s);
    });

    const palette = ['#0b66ff','#d92323','#15a347','#ff8c00','#6a3d9a','#b15928','#238b45','#005f73'];
    function darken(hex, amt) {
      if (!hex) return hex;
      let c = hex.replace('#','');
      if (c.length === 3) c = c.split('').map(ch => ch + ch).join('');
      const num = parseInt(c, 16);
      let r = (num >> 16) + amt;
      let g = ((num >> 8) & 0xFF) + amt;
      let b = (num & 0xFF) + amt;
      r = Math.max(0, Math.min(255, r));
      g = Math.max(0, Math.min(255, g));
      b = Math.max(0, Math.min(255, b));
      return '#' + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
    }

    const wrap = createEl("div", { style: { display: "flex", flexDirection: "column", gap: "8px" } });
    let ridIndex = 0;
    for (const [rid, steps] of Object.entries(rows)) {
      const row = createEl("div", { style: { display: "flex", alignItems: "center", gap: "12px" } });
      const label = createEl("div", { style: { width: "160px", fontSize: "13px", fontWeight: 700, color: "#0f1720" } }, [rid]);
      const barWrap = createEl("div", { style: { flex: "1", height: "48px", position: "relative", background: "#0f172014", border: "1px solid #e0e6eb", borderRadius: "8px", overflow: "hidden", padding: "6px" } });

      const total = steps.reduce((acc, s) => acc + (Number(s.estimatedDurationSec) || 60), 0) || 1;
      let offset = 0;
      const baseColor = palette[ridIndex % palette.length];
      const accent = darken(baseColor, -40);

      steps.forEach(s => {
        const dur = Number(s.estimatedDurationSec) || 60;
        const widthPct = (dur / total) * 100;
        const block = createEl("div", {
          style: {
            position: "absolute",
            left: offset + "%",
            top: "6px",
            height: "36px",
            width: widthPct + "%",
            background: `linear-gradient(90deg, ${baseColor}, ${accent})`,
            color: "#ffffff",
            padding: "6px 10px",
            boxSizing: "border-box",
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
            borderRadius: "6px",
            boxShadow: "0 6px 18px rgba(11,22,33,0.12)",
            border: `1px solid ${darken(baseColor, -80)}`,
            fontWeight: 700,
            fontSize: "12px"
          }
        }, [`${s.action || s.task || ""} (${dur}s)`]);
        block.title = `${s.action || s.task || ""} · ${dur}s · ${rid}`;
        block.addEventListener("mouseenter", () => {
          block.style.transform = "translateY(-3px)";
          block.style.transition = "transform 150ms ease";
        });
        block.addEventListener("mouseleave", () => {
          block.style.transform = "";
        });
        barWrap.appendChild(block);
        offset += widthPct;
      });

      row.appendChild(label);
      row.appendChild(barWrap);
      wrap.appendChild(row);
      ridIndex++;
    }
    container.appendChild(wrap);
  }

  async function renderTaskCenter() {
    host.innerHTML = "";
    const card = createEl("div", { class: "card", style: { padding: "12px", background: "#f6f8fa", borderRadius: "8px", border: "1px solid #e6eef7" } });
    host.appendChild(card);

    const header = createEl("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, [
      createEl("div", { style: { fontWeight: 700, color: "#0b1720" } }, ["任务中心 · 智能体工作流（Demo）"]),
      createEl("div", { style: { fontSize: "12px", color: "#475569" } }, ["兼容 LLM 输出的演示"])
    ]);
    card.appendChild(header);

    const body = createEl("div", { style: { display: "flex", gap: "12px", marginTop: "12px" } });
    card.appendChild(body);

    const left = createEl("div", { style: { width: "260px", borderRight: "1px solid #e6eef7", paddingRight: "12px" } });
    const ops = createEl("div", { style: { display: "flex", flexDirection: "column", gap: "8px" } });
    const btnLoad = createEl("button", { class: "btn" }, ["加载示例计划"]);
    const btnFetch = createEl("button", { class: "btn" }, ["请求后端 Plan（若可用）"]);
    const btnPlay = createEl("button", { class: "btn" }, ["播放"]);
    const btnStop = createEl("button", { class: "btn" }, ["停止"]);
    const btnReset = createEl("button", { class: "btn" }, ["重置"]);
    ops.appendChild(btnLoad); ops.appendChild(btnFetch); ops.appendChild(btnPlay); ops.appendChild(btnStop); ops.appendChild(btnReset);
    left.appendChild(createEl("div", { style: { fontWeight: 600, marginBottom: "8px", color: "#0b1720" } }, ["操作"]));
    left.appendChild(ops);
    left.appendChild(createEl("div", { style: { marginTop: "12px", fontWeight: 600, color: "#0b1720" } }, ["全局计划（摘要）"]));
    const summary = createEl("div", { id: "tc_summary", style: { marginTop: "8px", fontSize: "13px", color: "#0b1720" } }, ["尚未加载"]);
    left.appendChild(summary);

    const right = createEl("div", { style: { flex: "1" } });
    const instr = createEl("textarea", { id: "tc_instruction", rows: 3, style: { width: "100%", padding: "8px", background: "#ffffff", border: "1px solid #e6eef7", color: "#0b1720" }, placeholder: "示例：协调多个机器人搬运苹果等（此处为 demo）" });
    right.appendChild(instr);
    right.appendChild(createEl("div", { style: { display: "flex", gap: "8px", marginTop: "8px" } }, []));
    const planArea = createEl("div", { id: "tc_plan_area", style: { marginTop: "12px" } });
    right.appendChild(planArea);

    body.appendChild(left);
    body.appendChild(right);

    const state = { globalPlan: [], robotCalls: {}, playbackTimer: null };

    function renderPlanArea() {
      planArea.innerHTML = "";
      if (!state.globalPlan.length && Object.keys(state.robotCalls).length === 0) {
        planArea.appendChild(createEl("div", { style: { color: "#6b7280" } }, ["点击“加载示例计划”或请求后端生成 plan。"]));
        summary.textContent = "尚未加载";
        return;
      }

      const groups = {};
      state.globalPlan.forEach(it => {
        const ord = String(it.task_order ?? 0);
        groups[ord] = groups[ord] || [];
        groups[ord].push(it);
      });
      const ordered = Object.keys(groups).sort((a,b) => Number(a) - Number(b));
      summary.innerHTML = ordered.map(o => {
        const items = groups[o].map(x => `<span style="display:inline-block;background:#dfeeff;color:#042a6b;padding:6px 8px;border-radius:8px;margin:2px;font-weight:600;">${esc(x.robot_id)}</span>`).join("");
        return `<div style="margin-bottom:6px"><strong style="color:#0b1720">阶段 ${esc(o)}</strong>: ${items}</div>`;
      }).join("") || "（无）";

      const robotSet = new Set(state.globalPlan.map(x => x.robot_id).concat(Object.keys(state.robotCalls)));
      const lanes = createEl("div", { style: { display: "flex", flexDirection: "column", gap: "12px" } });
      for (const rid of Array.from(robotSet)) {
        const lane = createEl("div", { style: { border: "1px solid #e6eef7", padding: "10px", borderRadius: "8px", background: "#ffffff" } });
        const header = createEl("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, [
          createEl("div", { style: { fontWeight: 700, color: "#0b1720" } }, [rid]),
          createEl("div", { style: { fontSize: "12px", color: "#6b7280" } }, [String((state.robotCalls[rid] || []).length) + " 步"])
        ]);
        lane.appendChild(header);

        const row = createEl("div", { style: { display: "flex", gap: "8px", marginTop: "8px", flexWrap: "wrap" } });
        (state.robotCalls[rid] || []).forEach((s, idx) => {
          const stepEl = createEl("div", { class: "tc-step", "data-robot": rid, "data-index": idx, style: { minWidth: "180px", padding: "10px", border: "1px solid #d1e3f8", borderRadius: "8px", background: "#eff8ff", cursor: "pointer", display: "flex", flexDirection: "column", gap: "8px" } });
          stepEl.appendChild(createEl("div", { style: { fontWeight: 700, fontSize: "13px", color: "#042a6b" } }, [`${idx + 1}. ${s.action}`]));
          stepEl.appendChild(createEl("div", { style: { fontSize: "12px", color: "#344054" } }, [`args: ${s.arguments ?? s.args ?? ""}`]));
          const meta = createEl("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } });
          const badge = createEl("div", { class: "tc-badge", style: { fontSize: "12px", padding: "6px 8px", borderRadius: "999px", background: "#f1f5f9", color: "#0b1720", fontWeight: 700, border: "1px solid #e2e8f0" } }, ["PENDING"]);
          meta.appendChild(badge);
          const ctl = createEl("div", { style: { display: "flex", gap: "6px" } });
          const runBtn = createEl("button", { class: "btn", style: { fontSize: "12px" } }, ["RUN"]);
          const doneBtn = createEl("button", { class: "btn", style: { fontSize: "12px" } }, ["DONE"]);
          ctl.appendChild(runBtn); ctl.appendChild(doneBtn);
          meta.appendChild(ctl);
          stepEl.appendChild(meta);

          runBtn.addEventListener("click", ev => { ev.stopPropagation(); markStepStatus(stepEl, "RUNNING"); setTimeout(() => markStepStatus(stepEl, "DONE"), 700); });
          doneBtn.addEventListener("click", ev => { ev.stopPropagation(); markStepStatus(stepEl, "DONE"); });
          stepEl.addEventListener("click", () => openStepDetail(rid, idx, s, stepEl));
          row.appendChild(stepEl);
        });
        lane.appendChild(row);
        lanes.appendChild(lane);
      }

      const leftJson = createEl("div", { style: { flex: 1 } }, [
        createEl("div", { style: { fontWeight: 700, marginBottom: "6px", color: "#0b1720" } }, ["Plan JSON"]),
        createEl("pre", { style: { background: "#0b1220", color: "#e6eef8", border: "1px solid #122233", padding: "10px", maxHeight: "240px", overflow: "auto", fontSize: "12px", borderRadius: "6px" } }, [JSON.stringify({ globalPlan: state.globalPlan, robotCalls: state.robotCalls }, null, 2)])
      ]);
      const ganttContainer = createEl("div", { style: { width: "520px", minWidth: "240px" } }, [
        createEl("div", { style: { fontWeight: 700, marginBottom: "6px", color: "#0b1720" } }, ["甘特预览"]),
        createEl("div", { id: "tc_gantt_container", style: { border: "1px solid #e6eef7", padding: "10px", background: "#fbfdff", maxHeight: "300px", overflow: "auto", borderRadius: "8px" } }, [])
      ]);
      planArea.appendChild(createEl("div", { style: { display: "flex", gap: "12px" } }, [leftJson, ganttContainer]));
      planArea.appendChild(lanes);

      const ganttPlan = { steps: [] };
      const orderedByTaskOrder = state.globalPlan.slice().sort((a,b) => Number(a.task_order)-Number(b.task_order));
      orderedByTaskOrder.forEach(g => {
        const rid = g.robot_id || "unknown";
        const calls = state.robotCalls[rid] || [];
        for (const c of calls) {
          ganttPlan.steps.push({ assignedRobotId: rid, action: c.action, estimatedDurationSec: c.estimatedDurationSec || 60 });
        }
      });
      for (const [rid, calls] of Object.entries(state.robotCalls)) {
        calls.forEach(c => {
          if (!ganttPlan.steps.find(s => s.action === c.action && s.assignedRobotId === rid)) {
            ganttPlan.steps.push({ assignedRobotId: rid, action: c.action, estimatedDurationSec: c.estimatedDurationSec || 60 });
          }
        });
      }
      renderGantt(ganttContainer.querySelector("#tc_gantt_container"), ganttPlan);
    }

    function markStepStatus(stepEl, status) {
      stepEl.dataset.status = status;
      const badge = stepEl.querySelector(".tc-badge");
      if (badge) {
        badge.textContent = status;
        if (status === "DONE") {
          badge.style.background = "#0f5132";
          badge.style.color = "#e6fff2";
          badge.style.border = "1px solid #0b3626";
        } else if (status === "RUNNING") {
          badge.style.background = "#ffecb5";
          badge.style.color = "#663f00";
          badge.style.border = "1px solid #ffd27a";
        } else {
          badge.style.background = "#f1f5f9";
          badge.style.color = "#0b1720";
          badge.style.border = "1px solid #e2e8f0";
        }
      }
      if (status === "DONE") { stepEl.style.opacity = "0.6"; stepEl.style.textDecoration = "line-through"; }
      else if (status === "RUNNING") { stepEl.style.opacity = "1"; }
      else { stepEl.style.opacity = "1"; stepEl.style.textDecoration = "none"; }
    }

    function openStepDetail(robot, index, step, el) {
      const overlay = createEl("div", { style: { position: "fixed", left: 0, right: 0, top: 0, bottom: 0, background: "rgba(3,7,18,0.45)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 9999 } });
      const card = createEl("div", { style: { width: "560px", background: "#071022", color: "#e6eef8", borderRadius: "8px", padding: "16px", boxShadow: "0 12px 40px rgba(2,6,23,0.6)" } });
      card.appendChild(createEl("div", { style: { display: "flex", justifyContent: "space-between", alignItems: "center" } }, [
        createEl("div", { style: { fontWeight: 700 } }, [`步骤详情 — ${robot} #${index + 1}`]),
        createEl("div", { style: { fontSize: "12px", color: "#cbd5e1" } }, [step.action || ""])
      ]));
      card.appendChild(createEl("div", { style: { marginTop: "8px", color: "#e6eef8" } }, [
        createEl("div", {}, ["参数:"]),
        createEl("pre", { style: { background: "#071022", border: "1px solid #0f1720", padding: "8px", color: "#e6eef8" } }, [esc(JSON.stringify(step.arguments ?? step.args ?? "", null, 2))])
      ]));
      const foot = createEl("div", { style: { display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" } });
      const closeBtn = createEl("button", { class: "btn" }, ["关闭"]);
      const doneBtn = createEl("button", { class: "btn primary" }, ["标为完成"]);
      foot.appendChild(closeBtn); foot.appendChild(doneBtn);
      card.appendChild(foot);
      overlay.appendChild(card);
      document.body.appendChild(overlay);
      closeBtn.addEventListener("click", () => document.body.removeChild(overlay));
      doneBtn.addEventListener("click", () => {
        document.querySelectorAll(".tc-step").forEach(elm => {
          if (elm.dataset.robot === robot && elm.dataset.index === String(index)) markStepStatus(elm, "DONE");
        });
        document.body.removeChild(overlay);
      });
    }

    function loadDemo() {
      const demoGlobal = [
        { robot_id: "robot_1", task: "go to the table and bring an apple to the fridge.", task_order: 0 },
        { robot_id: "robot_2", task: "go to the table and bring an apple to the fridge.", task_order: 0 },
        { robot_id: "robot_3", task: "go to the fridge and bring two apples to the counter.", task_order: 1 },
        { robot_id: "robot_4", task: "monitor the fridge door and report if opened.", task_order: 1 }
      ];
      const demoCalls = {
        robot_1: [{ action: "move_to", arguments: "table" }, { action: "observe", arguments: "" }, { action: "grasp", arguments: "apple" }],
        robot_2: [{ action: "move_to", arguments: "table" }, { action: "grasp", arguments: "apple" }, { action: "move_to", arguments: "fridge" }],
        robot_3: [{ action: "move_to", arguments: "fridge" }, { action: "grasp", arguments: "apple" }, { action: "move_to", arguments: "counter" }],
        robot_4: [{ action: "monitor", arguments: "fridge_door" }]
      };
      state.globalPlan = normalizeGlobalPlan(demoGlobal);
      state.robotCalls = normalizeRobotCalls(demoCalls);
      renderPlanArea();
    }

    async function fetchBackendPlan() {
      planArea.innerHTML = createEl("div", {}, ["请求中..."]).outerHTML;
      try {
        const instruction = instr.value.trim() || "Demo instruction";
        const resp = await fetch("/api/tasks", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ instruction, site: "", dryRun: true })
        });
        if (!resp.ok) throw new Error("server " + resp.status);
        const obj = await resp.json();
        const plan = obj.plan || (obj.task && obj.task.plan);
        if (!plan || !Array.isArray(plan.steps)) {
          alert("后端未返回可用 plan，显示 demo");
          loadDemo();
          return;
        }
        const gp = plan.steps.map(s => ({ robot_id: s.assignedRobotId || s.robot_id || ("robot_" + Math.random().toString(36).slice(2,4)), task: s.action || s.task || "", task_order: s.startSec ?? 0 }));
        const calls = {};
        for (const s of plan.steps) {
          const rid = s.assignedRobotId || s.robot_id || ("robot_x");
          calls[rid] = calls[rid] || [];
          calls[rid].push({ action: s.action || s.task || "step", arguments: s.arguments ?? s.args ?? "" , estimatedDurationSec: s.estimatedDurationSec ?? 60});
        }
        state.globalPlan = normalizeGlobalPlan(gp);
        state.robotCalls = normalizeRobotCalls(calls);
        renderPlanArea();
      } catch (err) {
        console.error(err);
        alert("请求失败，使用 demo 数据");
        loadDemo();
      }
    }

    function startPlayback() {
      if (state.playbackTimer) return;
      const pending = Array.from(planArea.querySelectorAll(".tc-step")).filter(el => el.querySelector(".tc-badge")?.textContent === "PENDING");
      let idx = 0;
      state.playbackTimer = setInterval(() => {
        if (idx >= pending.length) { stopPlayback(); return; }
        const el = pending[idx++];
        if (!el) return;
        markStepStatus(el, "RUNNING");
        setTimeout(() => markStepStatus(el, "DONE"), 700);
      }, 800);
    }

    function stopPlayback() {
      if (state.playbackTimer) { clearInterval(state.playbackTimer); state.playbackTimer = null; }
    }

    function resetAll() {
      state.globalPlan = [];
      state.robotCalls = {};
      stopPlayback();
      renderPlanArea();
    }

    btnLoad.addEventListener("click", loadDemo);
    btnFetch.addEventListener("click", fetchBackendPlan);
    btnPlay.addEventListener("click", startPlayback);
    btnStop.addEventListener("click", stopPlayback);
    btnReset.addEventListener("click", resetAll);

    renderPlanArea();

    window.loadPlanFromLLM = (globalPlanRaw, robotCallsRaw) => {
      state.globalPlan = normalizeGlobalPlan(globalPlanRaw);
      state.robotCalls = normalizeRobotCalls(robotCallsRaw);
      renderPlanArea();
    };
    window.tcStartPlayback = startPlayback;
    window.tcStopPlayback = stopPlayback;
    window.tcReset = resetAll;
  }

  let renderedOnce = false;
  const mo = new MutationObserver(() => {
    try {
      const st = window.getComputedStyle(host);
      const visible = st && st.display !== "none" && st.visibility !== "hidden" && host.offsetParent !== null;
      if (visible && !renderedOnce) { renderedOnce = true; renderTaskCenter(); }
    } catch (e) {}
  });
  mo.observe(host, { attributes: true, attributeFilter: ["style", "class"] });

  setTimeout(() => {
    try {
      const st = window.getComputedStyle(host);
      if (st && st.display !== "none" && !renderedOnce) { renderedOnce = true; renderTaskCenter(); }
    } catch (e) {}
  }, 120);

  window.renderTaskCenter = window.renderTaskCenter || function () { try { renderTaskCenter(); } catch (e) { console.error(e); } };
})();