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

// = [新增] SSH 客户端依赖 =
const { Client } = require('ssh2');

// === 需要你按环境改的 2 行（最关键） ===
const MQTT_URL = process.env.MQTT_URL || "183.24.158.245";      // MQTT broker
const MQTT_PORT = process.env.MQTT_PORT || "11883";      // MQTT broker
const MQTT_TOPIC = process.env.MQTT_TOPIC || "/Vehicle_11/vehicle_state";       // 订阅的 topic
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

// ===== [新增] 从 roster 读 HTTP SSH 拉取目标，并提前注册所有机器人 =====
let httpTargets = [], sshTargets = [];
try {
  const rosterRaw = fs.readFileSync(ROBOT_ROSTER_PATH, "utf-8");
  const roster = JSON.parse(rosterRaw);
  if (Array.isArray(roster)) {
    for (const r of roster) {
      if (!r.id) continue;
      registerRobot(r.id, r);
      if (r.statusUrl) {
        console.log("statusUrl: " + `id : ${r.id}` +`http://${r.ip}${r.statusUrl}`);
        httpTargets.push({ id: r.id, url:`http://${r.ip}${r.statusUrl}`, static: r });
      }
      if (r.sshConfig) {
        sshTargets.push({
        id: r.id,
        sshConfig: r.sshConfig,
        static: r // 保留静态信息用于合并
        });
        console.log('sshTargets: ' + sshTargets);
      }
    }
  } else {
    console.warn("[roster] robots.json 必须是数组(Array)：", ROBOT_ROSTER_PATH);
  }
} catch (e) {
  console.warn("[roster] load failed:", ROBOT_ROSTER_PATH, e.message);
}

// ===================== MQTT =====================
const client = mqtt.connect({
  host: MQTT_URL,
  port: MQTT_PORT,
  // clientId: getClientId(deviceId),
  // username: deviceId,
  // password:HmacSHA256(secret, timestamp).toString(),
  // ca: TRUSTED_CA,
  // protocol: 'mqtts',
  // rejectUnauthorized: false,
  // keepalive: 120,
  connectTimeout: CONNECT_TIMEOUT_MS,           // 连接超时
  reconnectPeriod: CONNECT_TIMEOUT_MS * 10,     // 自动重连间隔（0=不重连）
});

client.on("connect", () => {
  console.log(`[mqtt] connected: ${MQTT_URL}:${MQTT_PORT}`);
  client.subscribe(MQTT_TOPIC, (err) => {
    if (err) console.error("[mqtt] subscribe error:", err);
    else console.log("[mqtt] subscribed:", MQTT_TOPIC);
  });
});

client.on("reconnect", (...val) => {
  console.log("[mqtt] reconnect:", val);
});

client.on("message", (topic, payload) => {
  try {
    const msg = JSON.parse(payload.toString());
    // 推荐 payload 里带 id；如果没有，就从 topic robots/<id>/state 里取
    const id = msg.id || topic.split("/")[1];
    if (!id) return;

    // 你们上报什么就合并什么：status/battery/task/site/ip/model/category/name...
    mergeRobot(id, { statusMqtt : msg });
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
        patch.statusRes = raw;

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


// = SSH 轮询 =

// 执行 SSH 命令并返回结果
function execSshCommand(config) {
  return new Promise((resolve, reject) => {
    const conn = new Client();
    const { host, port = 22, username, password, command, timeout = 10000 } = config;

    conn.on('ready', () => {
      console.log(`[ssh] 连接就绪: ${host}`);
      conn.exec(command, (err, stream) => {
        if (err) {
          conn.end();
          return reject(new Error(`执行命令失败: ${err.message}`));
        }

        let stdout = '';
        let stderr = '';
        stream.on('data', (data) => { stdout += data.toString(); });
        stream.stderr.on('data', (data) => { stderr += data.toString(); });
        stream.on('close', (code, signal) => {
          conn.end();
          if (code !== 0) {
            return reject(new Error(`命令退出码 ${code}, stderr: ${stderr}`));
          }
          resolve(stdout.trim());
        });
      });
    }).on('error', (err) => {
      reject(new Error(`SSH 连接错误: ${err.message}`));
    }).connect({
      host,
      port,
      username,
      ...(password ? { password } : {}),
      readyTimeout: timeout
    });

  });
}

// SSH 数据归一化适配器（可根据实际返回结构调整）
function normalizeSshPayload(target, raw) {
  const s = target.static || {};
  // 假设 raw 已经是 { status, battery, ... } 格式
  return {
    name: raw?.name ?? s.name,
    status: normalizeStatus(raw?.status),
    battery: parseBattery(raw?.battery),
    ip: s.ip, // SSH 目标可能没有直接 IP，用静态配置的
    ...raw // 合并其他所有字段
  };
}

// 轮询所有 SSH 目标
async function pollSshTargetsOnce() {
  if (!sshTargets.length) return;

  await Promise.all(
    sshTargets.map(async (target) => {
      const { id, sshConfig, static: staticInfo } = target;
      try {
        // 1. 执行 SSH 命令获取原始输出
        const rawOutput = await execSshCommand(sshConfig);
        //console.log(`[rawOutput] `+ rawOutput);

        // 2. 解析 JSON（支持可选的预处理脚本）
        let jsonData;
        if (sshConfig.parseScript) {
          // 如果有预处理脚本，可以在此调用（示例略）
          // jsonData = await preprocessWithScript(rawOutput, sshConfig.parseScript);
          jsonData = JSON.parse(rawOutput); // 简化：直接解析
        } else {
          jsonData = JSON.parse(rawOutput.toString().split('\r\n').pop());
        }

        // 3. 数据归一化（复用 HTTP 的归一化函数，或创建适配器）
        const patch = normalizeSshPayload(target, jsonData); // 需要定义 normalizeSshPayload
        // 或直接使用现有的，如果字段结构兼容: const patch = normalizeHttpPayload(target, jsonData);

        // 4. 合并到缓存
        mergeRobot(id, patch);
        console.log(`[ssh] 成功更新机器人 ${id} 的状态`);
      } catch (e) {
        console.error(`[ssh] 轮询机器人 ${id} 失败:`, e.message);
        // 可选：在机器人信息中记录错误
        const r = robotMap.get(id);
        if (r) r.notes = `SSH 拉取失败: ${e.message}`;
      }
    })

  );
}

// 加载 SSH 目标
if (sshTargets.length) {
  const SSH_POLL_MS = Number(process.env.SSH_POLL_MS || 2000); // 轮询间隔，可配置
  pollSshTargetsOnce().catch(() => {});
  setInterval(() => pollSshTargetsOnce().catch(() => {}), SSH_POLL_MS);
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

// 配置中间件：解析 JSON 请求体
app.use(express.json({ limit: "50mb" }));
app.use(express.urlencoded({ limit: "50mb", extended: true }));

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

// ------------- 新增：基于 OpenAI + OR-Tools 的 Planner 接入（minimal prototype） -------------
const { spawnSync } = require("child_process");

// openai client (npm i openai)
let OpenAI;
try {
  OpenAI = require("openai");
} catch (e) {
  console.warn("openai npm client not found. install with: npm i openai");
  OpenAI = null;
}

const OPENAI_API_KEY = process.env.OPENAI_API_KEY || null;
const openaiClient = OPENAI_API_KEY && OpenAI ? new OpenAI.OpenAIApi(new OpenAI.Configuration({ apiKey: OPENAI_API_KEY })) : null;

// 将自然语言 instruction 转成简单的 steps（用 LLM）
async function llmExtractSteps(instruction, maxSteps = 8) {
  // fallback simple heuristic if no LLM configured
  if (!openaiClient) {
    const kws = instruction.split(/[,;，。]/).filter(Boolean).slice(0, maxSteps);
    return kws.map((k, i) => ({ id: `LLM-${i}`, action: k.trim(), estimatedDurationSec: 60 + (i * 30) }));
  }

  const prompt = [
    "你是一个任务分解助理。将用户自然语言的任务指令分解为最多 8 个有序步骤（step），每个 step 提供：短动作描述(action)、估计耗时（秒，estimatedDurationSec）以及可选的 requiredCapabilities 列表（能力关键词）。",
    "只返回 JSON 数组，不要额外解释。示例：[{\"action\":\"到A区拍照\",\"estimatedDurationSec\":60,\"requiredCapabilities\":[\"可见光\"]}, ...]",
    `用户指令：${instruction}`
  ].join("\n\n");

  try {
    const resp = await openaiClient.createChatCompletion({
      model: process.env.OPENAI_MODEL || "gpt-4o-mini",
      messages: [{ role: "user", content: prompt }],
      max_tokens: 800,
      temperature: 0.2,
    });
    const txt = resp.data.choices?.[0]?.message?.content || resp.data.choices?.[0]?.text || "";
    // 尝试解析 JSON
    const jsonStart = txt.indexOf("[");
    const jsonStr = jsonStart >= 0 ? txt.slice(jsonStart) : txt;
    const parsed = JSON.parse(jsonStr);
    // normalize
    return parsed.slice(0, maxSteps).map((s, i) => ({
      id: s.id || `LLM-${i}`,
      action: s.action || s.name || `step-${i}`,
      estimatedDurationSec: Number(s.estimatedDurationSec) || 60,
      requiredCapabilities: Array.isArray(s.requiredCapabilities) ? s.requiredCapabilities : (s.capabilities || []),
    }));
  } catch (e) {
    console.error("llmExtractSteps error:", e?.message || e);
    // fallback heuristic
    return [{ id: "LLM-FALLBACK-1", action: instruction.slice(0, 60), estimatedDurationSec: 90, requiredCapabilities: [] }];
  }
}

// 替换 OR-Tools 调用：使用 LLM 生成 steps，然后用简单启发式调度（capability match + round-robin + greedy start times）
function simpleSchedule(robots, steps) {
  // robots: [{id, capabilities[], status, site, battery}], steps: [{id, action, estimatedDurationSec, requiredCapabilities[]}]
  const avail = robots.filter(r => (r.status === "ONLINE" || r.status == null));
  const planSteps = [];
  if (steps.length === 0) return { steps: [] };

  // prepare robot cumulative timeline (seconds)
  const robotTime = {};
  for (const r of avail) robotTime[r.id] = 0;

  let rr = 0;
  for (const s of steps) {
    // find candidate robots that meet requiredCapabilities
    const reqs = (s.requiredCapabilities || []).map(x => String(x || "").toLowerCase()).filter(Boolean);
    let candidate = null;
    if (reqs.length > 0) {
      candidate = avail.find(r => {
        const caps = (r.capabilities || []).map(c => String(c || "").toLowerCase());
        return reqs.every(req => caps.some(c => c.includes(req)));
      });
    }
    if (!candidate) {
      // fallback: choose next robot by round-robin
      if (avail.length > 0) candidate = avail[rr % avail.length];
      rr++;
    }

    const assignedId = candidate ? candidate.id : null;
    const startSec = assignedId ? robotTime[assignedId] : 0;
    const dur = Number(s.estimatedDurationSec || 60);

    // advance robot timeline if assigned
    if (assignedId) robotTime[assignedId] = startSec + dur;

    planSteps.push({
      id: s.id || `STEP-${Math.random().toString(36).slice(2,8)}`,
      action: s.action || "",
      estimatedDurationSec: dur,
      requiredCapabilities: s.requiredCapabilities || [],
      assignedRobotId: assignedId,
      startSec: startSec
    });
  }

  return { steps: planSteps };
}

// POST /api/tasks: 使用 llmExtractSteps -> simpleSchedule -> 返回 plan（dryRun 支持）
app.post("/api/tasks", async (req, res) => {
  try {
    const { instruction, site, dryRun } = req.body || {};
    if (!instruction) return res.status(400).json({ error: "instruction required" });

    // 收集候选机器人（最小描述）
    const robots = [...robotMap.values()].map(r => ({
      id: r.id,
      capabilities: r.capabilities || [],
      status: r.status,
      site: r.site,
      battery: r.battery
    })).filter(Boolean);

    const candidateRobots = site ? robots.filter(r => (r.site || "").toLowerCase().includes(String(site).toLowerCase())) : robots;

    // 1) LLM -> steps（llmExtractSteps 应在文件中已定义）
    const steps = await llmExtractSteps(instruction, 8);

    // 2) 调度：简单启发式
    const scheduled = simpleSchedule(candidateRobots, steps);

    const plan = {
      id: genId("PLAN"),
      instruction,
      site,
      createdAt: Date.now(),
      steps: scheduled.steps.map(s => ({
        id: s.id,
        action: s.action,
        assignedRobotId: s.assignedRobotId || null,
        estimatedDurationSec: s.estimatedDurationSec,
        startSec: s.startSec || 0,
        status: "PENDING"
      }))
    };

    if (!dryRun) {
      const taskId = genId("TASK");
      const task = { id: taskId, instruction, site, createdAt: Date.now(), status: "PLANNED", plan };
      tasks.set(taskId, task);
      return res.json({ task, plan, dryRun: false });
    } else {
      return res.json({ task: null, plan, dryRun: true });
    }
  } catch (e) {
    console.error("POST /api/tasks error:", e);
    res.status(500).json({ error: e.message || String(e) });
  }
});

// ===== [新增] FastAPI 代理路由 =====
// 将 POST /api/generate_plan 转发到 FastAPI 后端（端口 8000）
const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000";

app.post("/api/generate_plan", async (req, res) => {
  try {
    const payload = req.body; // { instruction, site }
    
    console.log("[PROXY] /api/generate_plan 被调用");
    console.log("[PROXY] 请求体类型:", typeof payload, "值:", JSON.stringify(payload));
    
    // 验证请求体
    if (!payload) {
      console.error("[PROXY] 错误：payload 为 null/undefined");
      return res.status(400).json({ error: "Request body is empty" });
    }
    
    // 转发请求到 FastAPI
    const urlObj = new URL("/api/generate_plan", FASTAPI_URL);
    const payloadStr = JSON.stringify(payload);
    
    console.log("[PROXY] 转发到:", urlObj.toString());
    console.log("[PROXY] 负载长度:", payloadStr.length);
    
    const options = {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Content-Length": Buffer.byteLength(payloadStr)
      },
    };

    // 选择合适的模块（http 或 https），不要总是用 https.request
    const transport = urlObj.protocol === "https:" ? https : http;

    const proxyReq = transport.request(urlObj, options, (proxyRes) => {
      let data = "";
      proxyRes.on("data", (chunk) => {
        data += chunk;
      });
      proxyRes.on("end", () => {
        try {
          const result = JSON.parse(data);
          console.log("[PROXY] 收到响应，状态码:", proxyRes.statusCode);
          res.status(proxyRes.statusCode || 200).json(result);
        } catch (parseErr) {
          console.error("[PROXY] 解析响应失败:", parseErr.message);
          res.status(500).json({ error: "Failed to parse FastAPI response" });
        }
      });
    });

    proxyReq.on("error", (err) => {
      console.error("[PROXY] 请求错误:", err.message);
      res.status(503).json({ error: "FastAPI backend unavailable", detail: err.message });
    });

    proxyReq.write(payloadStr);
    proxyReq.end();
  } catch (e) {
    console.error("[PROXY] 异常:", e);
    res.status(500).json({ error: e.message || String(e) });
  }
});
