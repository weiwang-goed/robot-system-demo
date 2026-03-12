// 数据来源：/api/robots?t=${Date.now()}

let robots = [];
let selectedId = null;
let twinLeftCollapsed = false;
let twinRightCollapsed = false;
let twinDividerPos = 50; // 默认50%

// Add: ensure showTab exists so index.html onclick won't throw
window.showTab = function (tabId) {
  const taskEl = document.getElementById("task-center");
  // const statsEl = document.getElementById("stats");
  // const filtersEl = document.querySelector(".filters");
  // const contentEl = document.querySelector(".content");

  const dbEl = document.getElementById("main-dashbord");
  const roboCtrEl = document.getElementById("robo-control");
  const twinEl = document.getElementById("digital-twin");

  if (tabId === "task-center") {
    if (taskEl) taskEl.style.display = "block";
    if (dbEl) dbEl.style.display = "none";
    if (roboCtrEl) roboCtrEl.style.display = "none";
    if (twinEl) twinEl.style.display = "none";
    // if (filtersEl) filtersEl.style.display = "none";
    // if (contentEl) contentEl.style.display = "none";
    // If task-center renderer is available, call it
    if (typeof window.renderTaskCenter === "function") {
      try { window.renderTaskCenter(); } catch (e) { console.error("renderTaskCenter error:", e); }
    }
  } else if (tabId === "robo-control") {
    if (roboCtrEl) roboCtrEl.style.display = "";

    if (taskEl) taskEl.style.display = "none";
    if (dbEl) dbEl.style.display = "none";
    if (twinEl) twinEl.style.display = "none";
    // if (statsEl) statsEl.style.display = "none";
    // if (filtersEl) filtersEl.style.display = "none";
    // if (contentEl) contentEl.style.display = "none";
  } else if (tabId === "digital-twin") {
    if (twinEl) twinEl.style.display = "";
    if (taskEl) taskEl.style.display = "none";
    if (dbEl) dbEl.style.display = "none";
    if (roboCtrEl) roboCtrEl.style.display = "none";

    // 设置数字孪生页面的iframe src
    const leftIframe = document.getElementById("twin-left-iframe");
    const rightIframe = document.getElementById("twin-right-iframe");
    if (leftIframe) leftIframe.src = "http://192.168.8.61:38080/#/acts";
    if (rightIframe) rightIframe.src = "http://192.168.8.61:8188/";
  }
  else {
    // show main dashboard
    if (taskEl) taskEl.style.display = "none";
    // if (statsEl) statsEl.style.display = "";
    // if (filtersEl) filtersEl.style.display = "";
    // if (contentEl) contentEl.style.display = "";
    if (dbEl) dbEl.style.display = "";
    if (roboCtrEl) roboCtrEl.style.display = "none";
    if (twinEl) twinEl.style.display = "none";
  }
}

function statusMeta(s) {
  if (s === "ONLINE") return { cls: "s-online", text: "在线" };
  if (s === "OFFLINE") return { cls: "s-offline", text: "离线" };
  if (s === "CHARGING") return { cls: "s-charging", text: "充电中" };
  if (s === "ALARM") return { cls: "s-alarm", text: "告警" };
  return { cls: "s-offline", text: s };
}

function pill(s) {
  const m = statusMeta(s);
  return `<span class="pill ${m.cls}"><span class="dot"></span>${m.text}</span>`;
}

function uniqueSorted(arr) {
  return [...new Set(arr)].sort((a, b) => String(a).localeCompare(String(b), "zh-CN"));
}

function initFilters() {
  const catEl = document.getElementById("cat");
  const modelEl = document.getElementById("model");

  const cats = uniqueSorted(robots.map((r) => r.category).filter(Boolean));
  const models = uniqueSorted(robots.map((r) => r.model).filter(Boolean));

  catEl.innerHTML =
    `<option value="">全部类别</option>` +
    cats.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");

  modelEl.innerHTML =
    `<option value="">全部型号</option>` +
    models.map((m) => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join("");
}

function initTwinSites() {
  const siteEl = document.getElementById("twin-site");
  if (!siteEl) return;

  const sites = uniqueSorted(robots.map((r) => r.site).filter(Boolean));
  siteEl.innerHTML =
    `<option value="">全部站点</option>` +
    sites.map((s) => `<option value="${escapeHtml(s)}">${escapeHtml(s)}</option>`).join("");
}

function computeStats(list) {
  const total = list.length;
  const online = list.filter((r) => r.status === "ONLINE").length;
  const offline = list.filter((r) => r.status === "OFFLINE").length;
  const charging = list.filter((r) => r.status === "CHARGING").length;
  const alarm = list.filter((r) => r.status === "ALARM").length;
  const running = list.filter((r) => r.task && r.task !== "—" && r.task !== "待命").length;

  return [
    { label: "接入总数", value: total },
    { label: "在线", value: online },
    { label: "离线", value: offline },
    { label: "充电中", value: charging },
    { label: "告警", value: alarm },
    { label: "任务执行中", value: running },
  ];
}

function renderStats(list) {
  const s = computeStats(list);
  document.getElementById("stats").innerHTML = s
    .map(
      (x) => `
      <div class="card">
        <div class="label">${escapeHtml(x.label)}</div>
        <div class="value">${x.value}</div>
      </div>
    `
    )
    .join("");

  const navCount = document.getElementById("navCount");
  if (navCount) navCount.textContent = `${list.length} 台`;
}

function filterList() {
  const q = document.getElementById("q").value.trim().toLowerCase();
  const cat = document.getElementById("cat").value;
  const st = document.getElementById("st").value;
  const model = document.getElementById("model").value;

  return robots.filter((r) => {
    if (cat && r.category !== cat) return false;
    if (st && r.status !== st) return false;
    if (model && r.model !== model) return false;

    if (!q) return true;
    const hay = `${r.name || ""} ${r.ip || ""} ${r.model || ""} ${r.site || ""} ${r.sn || ""}`.toLowerCase();
    return hay.includes(q);
  });
}


function buildControlUrl(r) {
  if (!r) return null;
  if (!r.ip) return null;

  // 可选扩展：以后你也可以在 robots.json 配 controlUrl/controlPath（不影响现在）
  if (r.controlUrl) 
    return `http://${r.ip}${r.controlUrl}`;
  else
    return `http://${r.ip}`;
}

function openControl(id) {
  const r = robots.find((x) => x.id === id);
  const url = buildControlUrl(r);

  console.log("open url: ", url);
  if (!url) {
    alert("该机器人未配置 IP（或 controlUrl）");
    return;
  }
  // window.open(url, "_blank", "noopener,noreferrer"); // 新标签打开（推荐）
  // 若你想在当前页跳转：window.location.href = url;
  showTab('robo-control'); 
  roboControl.switchTo(id);
}


function renderRows(list) {
  const tbody = document.getElementById("rows");
  tbody.innerHTML = list
    .map(
      (r) => `
      <tr onclick="selectRobot('${escapeAttr(r.id)}')">
        <td>${pill(r.status)}</td>
        <td>
          <div style="font-weight:700">${escapeHtml(r.name || "—")}</div>
          <div class="hint mono">${escapeHtml(r.id || "—")}</div>
        </td>
        <td>${escapeHtml(r.category || "—")}</td>
        <td><span class="mono">${escapeHtml(r.model || "—")}</span></td>
        <td class="mono">${escapeHtml(r.ip || "—")}</td>
        <td>${escapeHtml(r.site || "—")}</td>
        <td>${Number.isFinite(r.battery) ? batteryRing(r.battery) : "—"}</td>
        <td>${escapeHtml(r.task || "—")}</td>
        <td>${escapeHtml(r.lastSeen || "—")}</td>
        <td style="text-align:right;">
          <div class="actions">
            <span class="chip" onclick="event.stopPropagation(); alert('打开：/robots/${escapeJs(r.id)}/stream')">视频</span>
            <span class="chip" onclick="event.stopPropagation(); alert('控制：/teleop/${escapeJs(r.id)}')">驾驶</span>
            <span class="chip" onclick="event.stopPropagation(); openControl('${escapeJs(r.id)}')">更多</span>
          </div>
        </td>
      </tr>
    `
    )
    .join("");

  document.getElementById("countHint").textContent = `当前显示：${list.length} / ${robots.length} 台`;
}

function renderDetail(r) {
  document.getElementById("d_name").textContent = r?.name || "—";
  document.getElementById("d_id").textContent = `${r?.id || "—"}  ·  SN: ${r?.sn || "—"}`;
  document.getElementById("d_status").innerHTML = pill(r?.status || "OFFLINE");

  const kv = [
    ["类别", r?.category],
    ["型号", r?.model],
    ["IP", r?.ip],
    ["站点/区域", r?.site],
    ["电量", Number.isFinite(r?.battery) ? `${r.battery}%` : "—"],
    ["当前任务", r?.task || "—"],
    ["心跳", r?.lastSeen || "—"],
    ["固件", r?.firmware || "—"],
    ["备注", r?.notes || "—"],
  ];

  document.getElementById("d_kv").innerHTML = kv
    .map(
      ([k, v]) => `
      <div class="k">${escapeHtml(k)}</div><div class="v">${escapeHtml(v ?? "—")}</div>
    `
    )
    .join("");

  document.getElementById("d_caps").innerHTML = (r?.capabilities || [])
    .map((c) => `<span class="tag">${escapeHtml(c)}</span>`)
    .join("");
}

function selectRobot(id) {
  selectedId = id;
  const r = robots.find((x) => x.id === id);
  if (r) renderDetail(r);
}

function render() {
  const list = filterList();
  renderStats(list);
  renderRows(list);

  // 保持右侧详情：如果当前选中不在过滤列表里，就展示第一条（或空）
  const selected = robots.find((x) => x.id === selectedId) || list[0] || robots[0];
  if (selected) renderDetail(selected);
}

async function loadRobots() {
  // cache busting：方便你改 robots.json 后点“刷新”立刻生效
  const url = `/api/robots?t=${Date.now()}`;
  const res = await fetch(url, { cache: "no-store" });
  if (!res.ok) throw new Error(`加载 /api/robots 失败：${res.status}`);
  const data = await res.json();
  if (!Array.isArray(data)) throw new Error("robots.json 必须是数组（Array）");
  initState_A2D(data.filter((i)=>{return i.model== "AGIBOT-A2D"}));
  initState_A2(data.filter((i)=>{return i.model== "A2_T3D1_FLAGSHIP"}));
  initState_Go2(data.filter((i)=>{return i.model== "Go2-EDU"}));
  robots = data;
  window.robots = robots;

  // 默认选中第一条（如果之前选中的 id 仍存在则保留）
  if (!selectedId || !robots.some((r) => r.id === selectedId)) {
    selectedId = robots[0]?.id ?? null;
  }
}

function initState_A2D([a2d]) {
  //更新电量相关的参数
  a2d.status = "OFFLINE";
  a2d.battery = null;
  if (a2d && a2d.statusRes && a2d.statusRes.message=="OK") {
    a2d.status = "ONLINE";
    const { energy, isCharging } = a2d.statusRes.data.state.Content.batteryStateList[0];
    a2d.battery = energy;
    if (isCharging) {
      a2d.status = "CHARGING";
    }
  }
}

function initState_A2([a2]) {
  //更新电量相关的参数
  a2.status = "OFFLINE";
  a2.battery = null;
  if (a2 && a2.data) {
    const { charge, charger_state } = a2.data;
    a2.status = "ONLINE";
    a2.battery = charge;
    if (charger_state	== "ChargerConnected") {
      a2.status = "CHARGING";
    }
  }
}

function initState_Go2(robots) {
  for (const rbt of robots) {
    //更新电量相关的参数
    rbt.status = "OFFLINE";
    rbt.battery = null;
    if (rbt && rbt.statusMqtt) {
      const { battery, charge } = rbt.statusMqtt;
      rbt.status = "ONLINE";
      rbt.battery = battery;
      if (charge) {
        rbt.status = "CHARGING";
      }
    }
  }
}

async function refresh() {
  try {
    await loadRobots();
    initFilters();
    initTwinSites();
    render();
  } catch (e) {
    console.error(e);
    alert(
      "刷新失败： 读取数据有误"
    );
  }
}

function batteryRing(percentage) {
  // 确定颜色
  let color = "#10b981"; // 绿色
  if (percentage < 20) color = "#ef4444"; // 红色
  else if (percentage < 40) color = "#f59e0b"; // 黄色
  
  // 计算圆环参数
  const size = 36; // SVG大小
  const strokeWidth = 3;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (percentage / 100) * circumference;
  
  return `
    <div class="battery-ring-container" title="${percentage}%">
      <svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
        <!-- 背景圆环 -->
        <circle
          cx="${size/2}"
          cy="${size/2}"
          r="${radius}"
          fill="none"
          stroke="#e5e7eb"
          stroke-width="${strokeWidth}"
        />
        <!-- 进度圆环 -->
        <circle
          cx="${size/2}"
          cy="${size/2}"
          r="${radius}"
          fill="none"
          stroke="${color}"
          stroke-width="${strokeWidth}"
          stroke-dasharray="${circumference}"
          stroke-dashoffset="${strokeDashoffset}"
          stroke-linecap="round"
          transform="rotate(-90 ${size/2} ${size/2})"
        />
        <!-- 百分比文字 -->
        <text
          x="50%"
          y="50%"
          text-anchor="middle"
          dy="0.3em"
          font-size="10"
          font-weight="600"
          fill="${color}"
        >
          ${Math.round(percentage)}%
        </text>
      </svg>
    </div>
  `;
}


// ---- 数字孪生面板控制 ----
window.toggleTwinPanel = function (side) {
  const leftPanel = document.querySelector('.left-panel');
  const rightPanel = document.querySelector('.right-panel');
  const divider = document.getElementById('twin-divider');

  if (side === 'left') {
    twinLeftCollapsed = !twinLeftCollapsed;
    leftPanel.classList.toggle('collapsed', twinLeftCollapsed);
  } else {
    twinRightCollapsed = !twinRightCollapsed;
    rightPanel.classList.toggle('collapsed', twinRightCollapsed);
  }

  updateTwinLayout();
};

function updateTwinLayout() {
  const leftPanel = document.querySelector('.left-panel');
  const rightPanel = document.querySelector('.right-panel');
  const divider = document.getElementById('twin-divider');
  const leftBtn = leftPanel?.querySelector('.collapse-btn');
  const rightBtn = rightPanel?.querySelector('.collapse-btn');

  if (leftBtn) leftBtn.textContent = twinLeftCollapsed ? '→' : '←';
  if (rightBtn) rightBtn.textContent = twinRightCollapsed ? '←' : '→';

  if (twinLeftCollapsed && twinRightCollapsed) {
    divider.style.display = 'none';
    leftPanel.style.flex = '0 0 44px';
    rightPanel.style.flex = '0 0 44px';
    return;
  }

  if (twinLeftCollapsed) {
    divider.style.display = 'none';
    leftPanel.style.flex = '0 0 44px';
    rightPanel.style.flex = '1';
    return;
  }

  if (twinRightCollapsed) {
    divider.style.display = 'none';
    rightPanel.style.flex = '0 0 44px';
    leftPanel.style.flex = '1';
    return;
  }

  divider.style.display = '';
  updateTwinPanelSizes();
}

function updateTwinPanelSizes() {
  const leftPanel = document.querySelector('.left-panel');
  const rightPanel = document.querySelector('.right-panel');

  leftPanel.style.flex = `${twinDividerPos}`;
  rightPanel.style.flex = `${100 - twinDividerPos}`;
}

window.startResizing = function (e) {
  e.preventDefault();
  const container = document.querySelector('.twin-container');
  const divider = document.getElementById('twin-divider');
  
  function handleMouseMove(moveEvent) {
    const rect = container.getBoundingClientRect();
    const newPos = ((moveEvent.clientX - rect.left) / rect.width) * 100;
    
    // 限制最小宽度，防止panel过小
    if (newPos > 20 && newPos < 80) {
      twinDividerPos = newPos;
      updateTwinPanelSizes();
    }
  }
  
  function handleMouseUp() {
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  }
  
  document.addEventListener('mousemove', handleMouseMove);
  document.addEventListener('mouseup', handleMouseUp);
};

// ---- 小工具：避免 XSS/属性注入（原型也建议保留） ----
function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
function escapeAttr(s) {
  // 用于 onclick 参数（单引号包裹）
  return escapeHtml(String(s ?? "")).replaceAll("\\", "\\\\").replaceAll("'", "\\'");
}
function escapeJs(s) {
  // 用于 alert 模板拼接（尽量简单）
  return String(s ?? "").replaceAll("\\", "\\\\").replaceAll("'", "\\'");
}

// ---- 启动 ----
window.addEventListener("DOMContentLoaded", async () => {
  // 绑定全局函数（供 HTML inline onclick 调用）
  window.refresh = refresh;
  window.render = render;
  window.selectRobot = selectRobot;

  // 首次加载, 并每2s轮询
  await refresh();

  setInterval(async () => {
    try {
      await loadRobots();
      render();
    } catch (e) {
      console.warn("auto refresh failed:", e);
    }
  }, 2000);
});

