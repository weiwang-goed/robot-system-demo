// server.js (adapted: MQTT + HTTP polling -> /api/robots)
// npm i express mqtt
//
// ✅ 支持两类来源融合：
// 1) MQTT: 订阅 robots/+/state（或你自定义 topic），消息 JSON 直接 merge 到缓存
// 2) HTTP: 从 robots roster(robots.json) 中读取每台机器的 statusUrl，按固定频率拉取并 merge 到缓存
//
// 说明：前端继续请求 GET /api/robots，即可看到实时状态

const express = require("express");
const mqtt = require("mqtt");
const path = require("path");

// ===== [新增] 读取 roster + HTTP 拉取用到的依赖 =====
const fs = require("fs");
const http = require("http");
const https = require("https");

// === 需要你按环境改的 2 行（最关键） ===
const MQTT_URL = process.env.MQTT_URL || "mqtt://robot-gw:1883";      // MQTT broker
const MQTT_TOPIC = process.env.MQTT_TOPIC || "robots/+/state";       // 订阅的 topic
const CONNECT_TIMEOUT_MS = Number(process.env.CONNECT_TIMEOUT_MS || 10000);

const PORT = process.env.PORT || 8000;
const OFFLINE_MS = Number(process.env.OFFLINE_MS || 30_000); // 30 秒没心跳就判离线（可调）

// ===== [新增] roster 路径 + HTTP 轮询参数 =====
const ROBOT_ROSTER_PATH =
  process.env.ROBOT_ROSTER_PATH ||
  path.join(__dirname, "data", "robots.json");

const HTTP_POLL_MS = Number(process.env.HTTP_POLL_MS || 2000);        // 多久拉一次
const HTTP_TIMEOUT_MS = Number(process.env.HTTP_TIMEOUT_MS || 1500);  // 单次请求超时

// 缓存：id -> { ...robotFields, _ts: lastUpdateTs }
const robotMap = new Map();

// ===== [新增] 只注册不更新时间戳：让“只靠HTTP的机器人”也能在列表里出现 =====
function registerRobot(id, base = {}) {
  if (!id) return;

  const { statusUrl, ...rest } = base; // statusUrl 不对外透出
  if (!robotMap.has(id)) {
    robotMap.set(id, {
      id,
      status: "OFFLINE",
      lastSeen: "—",
      ...rest,
    });
  } else {
    const prev = robotMap.get(id);
    // 静态字段补齐，但不覆盖动态字段（prev 放后面）
    robotMap.set(id, { ...rest, ...prev });
  }
}

function mergeRobot(id, patch) {
  if (!id || !patch) return;

  // 避免把 statusUrl 融进缓存（以免误返回给前端）
  if (Object.prototype.hasOwnProperty.call(patch, "statusUrl")) {
    const { statusUrl, ...rest } = patch;
    patch = rest;
  }

  const prev = robotMap.get(id) || { id };
  const now = Date.now();
  robotMap.set(id, {
    ...prev,
    ...patch,
    id,
    _ts: now,
    // 前端目前展示 lastSeen 是字符串，后端顺手生成最省改动
    lastSeen: "1秒前",
  });
}

// ===== [新增] 从 roster 读 HTTP 拉取目标，并提前注册所有机器人 =====
let httpTargets = [];
try {
  const rosterRaw = fs.readFileSync(ROBOT_ROSTER_PATH, "utf-8");
  const roster = JSON.parse(rosterRaw);
  if (Array.isArray(roster)) {
    for (const r of roster) {
      if (!r?.id) continue;
      registerRobot(r.id, r);
      if (r.statusUrl) {
        console.log("statusUrl: " + `id : ${r.id}` +`http://${r.ip}${r.statusUrl}`);
        httpTargets.push({ id: r.id, url:`http://${r.ip}${r.statusUrl}`, static: r });
      }
    }
  } else {
    console.warn("[roster] robots.json 必须是数组(Array)：", ROBOT_ROSTER_PATH);
  }
} catch (e) {
  console.warn("[roster] load failed:", ROBOT_ROSTER_PATH, e.message);
}

// ===================== MQTT =====================
const client = mqtt.connect(MQTT_URL, {
  connectTimeout: CONNECT_TIMEOUT_MS,           // 连接超时
  reconnectPeriod: CONNECT_TIMEOUT_MS * 10,     // 自动重连间隔（0=不重连）
});

client.on("connect", () => {
  console.log("[mqtt] connected:", MQTT_URL);
  client.subscribe(MQTT_TOPIC, (err) => {
    if (err) console.error("[mqtt] subscribe error:", err);
    else console.log("[mqtt] subscribed:", MQTT_TOPIC);
  });
});

client.on("message", (topic, payload) => {
  try {
    const msg = JSON.parse(payload.toString());
    // 推荐 payload 里带 id；如果没有，就从 topic robots/<id>/state 里取
    const id = msg.id || topic.split("/")[1];
    if (!id) return;

    // 你们上报什么就合并什么：status/battery/task/site/ip/model/category/name...
    mergeRobot(id, msg);
  } catch (e) {
    console.error("[mqtt] bad payload:", e);
  }
});

// ===================== HTTP polling（新增） =====================
function normalizeStatus(s) {
  if (s == null) return undefined;

  // 兼容中文/英文/简写
  const raw = String(s).trim();
  const zh = { "在线": "ONLINE", "离线": "OFFLINE", "充电中": "CHARGING", "告警": "ALARM", "故障": "ALARM" };
  if (zh[raw]) return zh[raw];

  const v = raw.toUpperCase();
  if (["ONLINE", "ON", "OK", "RUNNING", "NORMAL"].includes(v)) return "ONLINE";
  if (["OFFLINE", "OFF", "DOWN"].includes(v)) return "OFFLINE";
  if (["CHARGING", "CHARGE"].includes(v)) return "CHARGING";
  if (["ALARM", "ERROR", "FAULT", "WARN", "WARNING"].includes(v)) return "ALARM";
  return v; // 其他状态也允许透传
}

function parseBattery(v) {
  if (v == null) return undefined;
  const n = Number(v);
  if (!Number.isFinite(n)) return undefined;
  if (n >= 0 && n <= 1) return Math.round(n * 100); // 兼容 0~1
  return Math.max(0, Math.min(100, Math.round(n))); // 0~100
}

function hostFromUrl(u) {
  try { return new URL(u).hostname; } catch { return undefined; }
}

function fetchJsonWithTimeout(url, timeoutMs) {
  return new Promise((resolve, reject) => {
    let u;
    try { u = new URL(url); } catch { return reject(new Error("bad url")); }

    const lib = u.protocol === "https:" ? https : http;
    const req = lib.request(
      {
        method: "GET",
        hostname: u.hostname,
        port: u.port || (u.protocol === "https:" ? 443 : 80),
        path: u.pathname + u.search,
        headers: { Accept: "application/json" },
        timeout: timeoutMs,
      },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => (body += chunk));
        res.on("end", () => {
          if (res.statusCode < 200 || res.statusCode >= 300) {
            return reject(new Error(`HTTP ${res.statusCode}`));
          }
          try {
            resolve(JSON.parse(body));
          } catch {
            reject(new Error("invalid json"));
          }
        });
      }
    );

    req.on("timeout", () => req.destroy(new Error("timeout")));
    req.on("error", reject);
    req.end();
  });
}

// 允许各家机器人 HTTP 返回字段不完全一致：做一个“尽量兼容”的归一化
function normalizeHttpPayload(target, raw) {
  const msg = raw?.data ?? raw; // 兼容 {data:{...}} 包装
  const s = target.static || {};

  return {
    // 静态信息优先从 roster 来（这样 UI 字段齐）
    name: msg?.name ?? s.name,
    category: msg?.category ?? s.category,
    model: msg?.model ?? s.model,
    ip: msg?.ip ?? s.ip ?? hostFromUrl(target.url),

    // 动态信息
    status: normalizeStatus(msg?.status ?? msg?.state ?? msg?.robot_state),
    battery: parseBattery(
      msg?.battery ??
      msg?.batteryPct ??
      msg?.battery_percent ??
      msg?.power_percent
    ),

    task: msg?.task ?? msg?.current_task ?? msg?.mission ?? s.task,
    site: msg?.site ?? msg?.location ?? s.site,
    firmware: msg?.firmware ?? msg?.version ?? s.firmware,
    sn: msg?.sn ?? msg?.serial ?? s.sn,
    capabilities: msg?.capabilities ?? s.capabilities,
    notes: msg?.notes ?? s.notes,
  };
}

async function pollHttpTargetsOnce() {
  if (!httpTargets?.length) return;

  await Promise.all(
    httpTargets.map(async (t) => {
      try {
        const raw = await fetchJsonWithTimeout(t.url, HTTP_TIMEOUT_MS);
        const patch = normalizeHttpPayload(t, raw);

        // 如果对方没给 status，就别覆盖（让 MQTT/离线判定决定）
        if (patch.status == null) delete patch.status;

        mergeRobot(t.id, patch);
      } catch (e) {
        // 不更新 _ts：让离线判定自然生效
        const r = robotMap.get(t.id);
        if (r) r.notes = `HTTP 拉取失败：${e.message}`;
      }
    })
  );
}

// 启动 HTTP 轮询
if (httpTargets.length) {
  console.log(`[http-poll] targets: ${httpTargets.length} (every ${HTTP_POLL_MS}ms)`);
  pollHttpTargetsOnce().catch(() => {});
  setInterval(() => pollHttpTargetsOnce().catch(() => {}), HTTP_POLL_MS);
}

// 每 1 秒刷新 lastSeen + 离线判定（兼容“从未更新过”的机器人）
setInterval(() => {
  const now = Date.now();
  for (const [id, r] of robotMap.entries()) {
    const ts = r._ts;
    if (typeof ts !== "number") {
      r.lastSeen = "—";
      continue;
    }

    const age = now - ts;
    const sec = Math.max(1, Math.round(age / 1000));
    r.lastSeen = `${sec}秒前`;

    if (age > OFFLINE_MS) {
      r.status = "OFFLINE";
    }
  }
}, 1000);

// ===================== HTTP server =====================
const app = express();

// 静态托管前端（保持你原来方式不变）
app.use(express.static(path.join(__dirname, ""))); //robot_console_dashboard_modular

app.get("/api/robots", (req, res) => {
  // 不返回 _ts / statusUrl
  res.json([...robotMap.values()].map(({ _ts, statusUrl, ...rest }) => rest));
});

app.listen(PORT, () => {
  console.log(`[http] listening http://localhost:${PORT}`);
  console.log(`[ui] open     http://localhost:${PORT}/index.html`);
  console.log(`[roster]      ${ROBOT_ROSTER_PATH}`);
});
