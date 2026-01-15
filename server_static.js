// server.js
// npm i express mqtt
const express = require("express");
const mqtt = require("mqtt");
const path = require("path");

// === 需要你按环境改的 2 行（最关键） ===
const MQTT_URL = process.env.MQTT_URL || "mqtt://robot-gw:1883";      // [改这里1] MQTT broker
const MQTT_TOPIC = process.env.MQTT_TOPIC || "robots/+/state";       // [改这里2] 订阅的 topic
const CONNECT_TIMEOUT_MS = 10000;

const PORT = process.env.PORT || 8000;
const OFFLINE_MS = 30_000; // 30 秒没心跳就判离线（可调）

// 缓存：id -> { ...robotFields, _ts: lastUpdateTs }
const robotMap = new Map();

function mergeRobot(id, patch) {
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

// MQTT
const client = mqtt.connect(MQTT_URL, { // non-block
  connectTimeout: CONNECT_TIMEOUT_MS, // 连接超时
  reconnectPeriod: CONNECT_TIMEOUT_MS * 10, // 自动重连间隔（0=不重连）
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

// 每 1 秒刷新 lastSeen + 离线判定
setInterval(() => {
  const now = Date.now();
  for (const [id, r] of robotMap.entries()) {
    const age = now - (r._ts || now);
    const sec = Math.max(1, Math.round(age / 1000));
    r.lastSeen = `${sec}秒前`;

    if (age > OFFLINE_MS) {
      r.status = "OFFLINE";
    }
  }
}, 1000);

// HTTP
const app = express();

// === 把你解压的 robot_console_dashboard_modular 目录放到同级，然后静态托管 ===
// 例如：./robot_console_dashboard_modular/index.html
app.use(express.static(path.join(__dirname, "robot_console_dashboard_modular")));

app.get("/api/robots", (req, res) => {
  res.json([...robotMap.values()].map(({ _ts, ...rest }) => rest));
});

app.listen(PORT, () => {
  console.log(`[http] listening http://localhost:${PORT}`);
  console.log(`[ui] open     http://localhost:${PORT}/index.html`);
});
