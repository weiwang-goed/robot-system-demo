# 机器人统一入口驾驶舱（模块化前端原型）

## 目录结构
- index.html：页面骨架（保持原设计不变）
- assets/styles.css：样式（从原 HTML 拆出）
- assets/app.js：渲染逻辑（从原 HTML 拆出）
- server.js : 后端服务
- data/robots.json：机器人配置文件



### 启动服务：Python 一行启动，默认端口8000
在该目录执行：
```bash
npm i express mqtt
node server.js 
```

## 如何修改表项内容（数据）
编辑 `data/robots.json`（是一个数组，每个元素是一台机器人）：

必填字段建议：
- id（唯一）
- name（名称）
- category（类别）
- model（型号）
- ip
- status：ONLINE / OFFLINE / CHARGING / ALARM

可选字段：
- battery（0-100）
- site（站点/区域）
- task（当前任务）
- lastSeen（心跳，例如 “12秒前”）
- firmware
- sn
- capabilities（数组）
- notes（备注）

改完后在页面右上角点【刷新】即可重新加载 robots.json 并更新 UI。
