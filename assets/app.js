// 数据来源：/api/robots?t=${Date.now()}

let robots = [];
let selectedId = null;

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
    return `http://${r.ip}`
}

function openControl(id) {
  const r = robots.find((x) => x.id === id);
  const url = buildControlUrl(r);
  if (!url) {
    alert("该机器人未配置 IP（或 controlUrl）");
    return;
  }
  window.open(url, "_blank", "noopener,noreferrer"); // 新标签打开（推荐）
  // 若你想在当前页跳转：window.location.href = url;
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
        <td>${Number.isFinite(r.battery) ? `${r.battery}%` : "—"}</td>
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
  robots = data;

  // 默认选中第一条（如果之前选中的 id 仍存在则保留）
  if (!selectedId || !robots.some((r) => r.id === selectedId)) {
    selectedId = robots[0]?.id ?? null;
  }
}

async function refresh() {
  try {
    await loadRobots();
    initFilters();
    render();
  } catch (e) {
    console.error(e);
    alert(
      "刷新失败： 读取数据有误"
    );
  }
}

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

