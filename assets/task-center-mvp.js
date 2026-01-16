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
          if (typeof window.renderMVP === "function") window.renderMVP();
        } else {
          hostEl.style.display = "none";
          mainSections.forEach(el => el.style.display = "");
        }
      } catch (e) { console.error("showTab error", e); }
    };
  }

  const statusColors = {
    done: { bg: "#ecfdf5", border: "#10b981", text: "#065f46", dot: "#10b981" },
    running: { bg: "#eff6ff", border: "#3b82f6", text: "#1e40af", dot: "#3b82f6" },
    pending: { bg: "#f9fafb", border: "#9ca3af", text: "#374151", dot: "#9ca3af" },
    failed: { bg: "#fef2f2", border: "#ef4444", text: "#7f1d1d", dot: "#ef4444" },
    ONLINE: { bg: "#ecfdf5", border: "#10b981", text: "#065f46", dot: "#10b981" },
    OFFLINE: { bg: "#fef2f2", border: "#ef4444", text: "#7f1d1d", dot: "#ef4444" },
    ALARM: { bg: "#fef3c7", border: "#f59e0b", text: "#92400e", dot: "#f59e0b" },
    CHARGING: { bg: "#f0fdf4", border: "#84cc16", text: "#3f6212", dot: "#84cc16" }
  };

  function getStatusColor(status) {
    return statusColors[status] || statusColors.pending;
  }

  function truncate(s, len = 40) {
    return String(s || "").length > len ? String(s).slice(0, len) + "…" : s;
  }

  function esc(s = "") {
    return String(s ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
  }

  function createEl(tag = "div", cls = "", attrs = {}) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "style" && typeof v === "object") Object.assign(el.style, v);
      else el.setAttribute(k, String(v));
    }
    return el;
  }

  function statusBadge(status) {
    const color = getStatusColor(status);
    const badge = createEl("span", "", {
      style: {
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        padding: "2px 8px",
        borderRadius: "999px",
        fontSize: "11px",
        fontWeight: "600",
        background: color.bg,
        border: `1px solid ${color.border}`,
        color: color.text
      }
    });
    const dot = createEl("span", "", {
      style: {
        width: "6px",
        height: "6px",
        borderRadius: "50%",
        background: color.dot
      }
    });
    badge.appendChild(dot);
    badge.appendChild(document.createTextNode(status.toUpperCase()));
    return badge;
  }

  async function loadRobots() {
    try {
      const resp = await fetch("/data/robots.json");
      if (!resp.ok) throw new Error("Failed to load robots");
      return await resp.json();
    } catch (e) {
      console.error("Error loading robots:", e);
      return [];
    }
  }

  async function loadDemoData() {
    try {
      const resp = await fetch("/data/demo_run.json");
      if (!resp.ok) throw new Error("Failed to load demo data");
      return await resp.json();
    } catch (e) {
      console.error("Error loading demo data:", e);
      return null;
    }
  }

  function generatePlanFromLLM(instruction, robots) {
    const timestamp = new Date().toISOString();
    const runId = `run_${Date.now()}`;

    const robotIds = robots.map(r => r.id);
    const capabilities = robots.flatMap(r => r.capabilities || []);

    const tasks = [];
    const toolCalls = {};

    robotIds.forEach(rid => {
      toolCalls[rid] = [];
    });

    if (instruction.includes("观察") || instruction.includes("监控") || instruction.includes("巡检")) {
      tasks.push({
        task_order: 0,
        robot_id: robotIds[0],
        task: "扫描并观察周围环境",
        status: "pending"
      });
      if (robotIds[0]) {
        toolCalls[robotIds[0]].push(
          { action: "move_to", arguments: "target_area", status: "pending" },
          { action: "observe", arguments: "environment", status: "pending" }
        );
      }
    }

    if (instruction.includes("搬运") || instruction.includes("移动")) {
      if (robotIds[1]) {
        tasks.push({
          task_order: 0,
          robot_id: robotIds[1],
          task: "前往指定位置",
          status: "pending"
        });
        toolCalls[robotIds[1]].push(
          { action: "move_to", arguments: "destination", status: "pending" },
          { action: "locate_object", arguments: "target", status: "pending" }
        );
      }
    }

    tasks.push({
      task_order: 1,
      robot_id: robotIds[0],
      task: "完成协作任务",
      status: "pending"
    });

    if (robotIds[0]) {
      toolCalls[robotIds[0]].push(
        { action: "return_to_base", arguments: "charging_station", status: "pending" }
      );
    }

    return {
      run_id: runId,
      status: "PLANNING",
      timestamp,
      instruction,
      llm_global_planning: tasks,
      robot_tool_calls: toolCalls,
      llm_thinking: `Analyzing task: "${instruction}"\n\n` +
        `Available robots: ${robotIds.join(", ")}\n` +
        `Capabilities: ${capabilities.join(", ")}\n\n` +
        `Planning strategy:\n` +
        `1. Allocate robots based on task requirements\n` +
        `2. Create sequential task orders for multi-robot coordination\n` +
        `3. Generate tool call sequences for each robot\n\n` +
        `Execution plan generated successfully.`
    };
  }

  class MVPApp {
    constructor(robots, demoData) {
      this.robots = robots;
      this.planData = demoData;
      this.selectedSite = null;
      this.selectedRobotId = null;
      this.selectedTaskKey = null;
      this.executionState = {};
      this.isRunning = false;

      this.sites = [...new Set(robots.map(r => r.site))];
      if (this.sites.length > 0) {
        this.selectedSite = this.sites[0];
      }

      this.planning = {};
      if (this.planData) {
        this.parseData();
        if (this.planData.llm_global_planning && this.planData.llm_global_planning.length > 0) {
          const firstRobot = this.planData.llm_global_planning[0].robot_id;
          this.selectedRobotId = firstRobot;
        }
      }
    }

    getAvailableRobots() {
      if (!this.selectedSite) return [];
      return this.robots.filter(r => r.site === this.selectedSite);
    }

    parseData() {
      if (!this.planData || !this.planData.llm_global_planning) return;
      const planning = this.planData.llm_global_planning;
      for (const task of planning) {
        const rid = task.robot_id;
        if (!this.planning[rid]) this.planning[rid] = [];
        this.planning[rid].push(task);
      }
    }

    getTasksGroupedByOrder() {
      if (!this.planData) return {};
      const groups = {};
      const planning = this.planData.llm_global_planning || [];
      for (const task of planning) {
        const ord = task.task_order || 0;
        if (!groups[ord]) groups[ord] = [];
        groups[ord].push(task);
      }
      return groups;
    }

    getRobotToolCalls(robotId) {
      return this.planData && this.planData.robot_tool_calls && this.planData.robot_tool_calls[robotId] 
        ? this.planData.robot_tool_calls[robotId] 
        : [];
    }

    selectTask(robotId, taskIdx) {
      this.selectedRobotId = robotId;
      this.selectedTaskKey = `${robotId}:${taskIdx}`;
    }

    async startExecution() {
      if (!this.planData || this.isRunning) return;

      this.isRunning = true;
      const planning = this.planData.llm_global_planning || [];

      for (let i = 0; i < planning.length; i++) {
        const task = planning[i];
        task.status = "running";
        this.updateUI();
        await this.sleep(10000 + Math.random() * 5000);

        task.status = "done";
        const toolCalls = this.getRobotToolCalls(task.robot_id);
        for (let j = 0; j < toolCalls.length; j++) {
          if (toolCalls[j].status !== "done") {
            toolCalls[j].status = "running";
            this.updateUI();
            await this.sleep(3000 + Math.random() * 2000);
            toolCalls[j].status = "done";
            this.updateUI();
          }
        }
      }

      this.planData.status = "COMPLETED";
      this.isRunning = false;
      this.updateUI();
    }

    sleep(ms) {
      return new Promise(resolve => setTimeout(resolve, ms));
    }

    updateUI() {
      this.render();
    }

    render() {
      host.innerHTML = "";
      const root = createEl("div", "", {
        style: {
          display: "flex",
          flexDirection: "column",
          height: "100vh",
          background: "#f6f8fa",
          fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif"
        }
      });
      host.appendChild(root);

      this.renderTopBar(root);
      this.renderInteractionPanel(root);
      if (this.planData) {
        this.renderLLMThinkingPanel(root);
      }
      this.renderMainBody(root);
    }

    renderTopBar(root) {
      const topBar = createEl("div", "", {
        style: {
          height: "64px",
          background: "#ffffff",
          borderBottom: "1px solid #e6eef7",
          padding: "0 20px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          boxShadow: "0 2px 8px rgba(0,0,0,0.06)"
        }
      });
      root.appendChild(topBar);

      const left = createEl("div", "", { style: { display: "flex", gap: "24px", alignItems: "center" } });
      const title = createEl("h1", "", {
        style: { margin: "0", fontSize: "20px", fontWeight: "700", color: "#0b1720" }
      });
      title.textContent = "Multi-Robot LLM Planner";
      left.appendChild(title);

      if (this.planData) {
        const info = createEl("div", "", { style: { display: "flex", gap: "16px" } });
        const runId = createEl("div", "", { style: { fontSize: "13px", color: "#475569" } });
        runId.innerHTML = `<strong>Run:</strong> ${esc(this.planData.run_id || "N/A")}`;
        info.appendChild(runId);

        const status = createEl("div", "", { style: { fontSize: "13px", color: "#475569" } });
        const statusColor = getStatusColor(this.planData.status?.toLowerCase() || "pending");
        status.innerHTML = `<strong>Status:</strong> <span style="color:${statusColor.text}; font-weight:600">${esc(this.planData.status || "N/A")}</span>`;
        info.appendChild(status);
        left.appendChild(info);
      }

      topBar.appendChild(left);

      const right = createEl("div", "", { style: { display: "flex", gap: "8px" } });
      if (this.planData && !this.isRunning) {
        const executeBtn = createEl("button", "", {
          style: {
            padding: "8px 16px",
            fontSize: "12px",
            background: "#0b66ff",
            color: "#fff",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: "600"
          }
        });
        executeBtn.textContent = "Execute Plan";
        executeBtn.addEventListener("click", () => this.startExecution());
        right.appendChild(executeBtn);
      }

      ["Pause", "Export"].forEach(label => {
        const btn = createEl("button", "", {
          style: {
            padding: "6px 14px",
            fontSize: "12px",
            background: "#f1f5f9",
            border: "1px solid #d1d5db",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: "500"
          }
        });
        btn.textContent = label;
        right.appendChild(btn);
      });
      topBar.appendChild(right);
    }

    renderInteractionPanel(root) {
      const panel = createEl("div", "", {
        style: {
          background: "#ffffff",
          borderBottom: "1px solid #e6eef7",
          padding: "16px 20px",
          boxShadow: "0 2px 8px rgba(0,0,0,0.06)"
        }
      });
      root.appendChild(panel);

      const container = createEl("div", "", {
        style: {
          display: "flex",
          gap: "16px",
          alignItems: "flex-start"
        }
      });

      const siteSection = createEl("div", "", { style: { flex: "0 0 auto", minWidth: "240px" } });
      const siteLabel = createEl("div", "", {
        style: { fontSize: "12px", fontWeight: "700", color: "#0b1720", marginBottom: "6px" }
      });
      siteLabel.textContent = "Select Site";
      siteSection.appendChild(siteLabel);

      const siteSelect = createEl("select", "", {
        style: {
          width: "100%",
          padding: "8px 12px",
          borderRadius: "6px",
          border: "1px solid #d1d5db",
          fontSize: "12px",
          color: "#0b1720",
          cursor: "pointer"
        }
      });
      this.sites.forEach(site => {
        const opt = document.createElement("option");
        opt.value = site;
        opt.textContent = site;
        if (site === this.selectedSite) opt.selected = true;
        siteSelect.appendChild(opt);
      });
      siteSelect.addEventListener("change", (e) => {
        this.selectedSite = e.target.value;
        this.planData = null;
        this.render();
      });
      siteSection.appendChild(siteSelect);
      container.appendChild(siteSection);

      const robotsInfo = createEl("div", "", { style: { flex: "0 0 auto" } });
      const robotsLabel = createEl("div", "", {
        style: { fontSize: "12px", fontWeight: "700", color: "#0b1720", marginBottom: "6px" }
      });
      robotsLabel.textContent = "Available Robots";
      robotsInfo.appendChild(robotsLabel);

      const robotsList = createEl("div", "", {
        style: {
          display: "flex",
          gap: "8px",
          flexWrap: "wrap"
        }
      });
      const available = this.getAvailableRobots();
      if (available.length === 0) {
        const empty = createEl("div", "", {
          style: { fontSize: "12px", color: "#9ca3af" }
        });
        empty.textContent = "No robots available";
        robotsList.appendChild(empty);
      } else {
        available.forEach(robot => {
          const tag = createEl("div", "", {
            style: {
              padding: "4px 8px",
              background: "#f0f4f8",
              border: "1px solid #d1d5db",
              borderRadius: "4px",
              fontSize: "11px",
              fontWeight: "600",
              color: "#0b1720"
            }
          });
          tag.appendChild(statusBadge(robot.status));
          const name = createEl("span", "", { style: { marginLeft: "6px" } });
          name.textContent = robot.name;
          tag.appendChild(name);
          robotsList.appendChild(tag);
        });
      }
      robotsInfo.appendChild(robotsList);
      container.appendChild(robotsInfo);

      const taskSection = createEl("div", "", { style: { flex: "1" } });
      const taskLabel = createEl("div", "", {
        style: { fontSize: "12px", fontWeight: "700", color: "#0b1720", marginBottom: "6px" }
      });
      taskLabel.textContent = "Task Description";
      taskSection.appendChild(taskLabel);

      const inputContainer = createEl("div", "", {
        style: { display: "flex", gap: "8px" }
      });

      const taskInput = createEl("textarea", "", {
        style: {
          flex: "1",
          padding: "8px 12px",
          borderRadius: "6px",
          border: "1px solid #d1d5db",
          fontSize: "12px",
          fontFamily: "inherit",
          resize: "vertical",
          minHeight: "44px"
        }
      });
      taskInput.placeholder = "描述任务，例如：协调多个机器人观察仓库，然后搬运物品到指定位置";
      inputContainer.appendChild(taskInput);

      const planBtn = createEl("button", "", {
        style: {
          padding: "8px 16px",
          background: "#0b66ff",
          color: "#fff",
          border: "none",
          borderRadius: "6px",
          cursor: "pointer",
          fontWeight: "600",
          fontSize: "12px",
          minWidth: "100px",
          height: "44px"
        }
      });
      planBtn.textContent = "Generate Plan";
      planBtn.addEventListener("click", async () => {
        const instruction = taskInput.value.trim();
        if (!instruction) {
          alert("Please enter a task description");
          return;
        }

        const availableRobots = this.getAvailableRobots();
        if (availableRobots.length === 0) {
          alert("No robots available in this site");
          return;
        }

        planBtn.disabled = true;
        planBtn.textContent = "Planning...";

        await new Promise(resolve => setTimeout(resolve, 1500));

        this.planData = generatePlanFromLLM(instruction, availableRobots);
        planBtn.disabled = false;
        planBtn.textContent = "Generate Plan";
        taskInput.value = "";
        this.render();
      });
      inputContainer.appendChild(planBtn);
      taskSection.appendChild(inputContainer);
      container.appendChild(taskSection);

      const loadDemoBtn = createEl("button", "", {
        style: {
          padding: "8px 16px",
          background: "#059669",
          color: "#fff",
          border: "none",
          borderRadius: "6px",
          cursor: "pointer",
          fontWeight: "600",
          fontSize: "12px",
          height: "44px",
          alignSelf: "flex-end"
        }
      });
      loadDemoBtn.textContent = "Load Demo";
      loadDemoBtn.addEventListener("click", async () => {
        loadDemoBtn.disabled = true;
        loadDemoBtn.textContent = "Loading...";
        const demoData = await loadDemoData();
        if (demoData) {
          this.planData = demoData;
          this.render();
        } else {
          alert("Failed to load demo data");
        }
        loadDemoBtn.disabled = false;
        loadDemoBtn.textContent = "Load Demo";
      });

      const btnContainer = createEl("div", "", {
        style: { display: "flex", gap: "8px", alignSelf: "flex-end" }
      });
      btnContainer.appendChild(loadDemoBtn);
      container.appendChild(btnContainer);

      panel.appendChild(container);
    }

    renderLLMThinkingPanel(root) {
      const panel = createEl("div", "", {
        style: {
          background: "#f6f8fa",
          borderBottom: "1px solid #e6eef7",
          padding: "12px 20px",
          maxHeight: "220px",
          overflow: "hidden",
          display: "flex",
          gap: "16px"
        }
      });
      root.appendChild(panel);

      const thinkingSection = createEl("div", "", { style: { flex: "1" } });
      const thinkingTitle = createEl("div", "", {
        style: { fontSize: "12px", fontWeight: "700", color: "#0b1720", marginBottom: "8px" }
      });
      thinkingTitle.textContent = "LLM Thinking Process";
      thinkingSection.appendChild(thinkingTitle);

      const thinkingContent = createEl("div", "", {
        style: {
          background: "#ffffff",
          border: "1px solid #e6eef7",
          borderRadius: "6px",
          padding: "10px",
          fontSize: "11px",
          color: "#475569",
          lineHeight: "1.5",
          maxHeight: "180px",
          overflow: "auto",
          fontFamily: "'Monaco', 'Courier New', monospace",
          whiteSpace: "pre-wrap",
          wordBreak: "break-word"
        }
      });
      thinkingContent.textContent = this.planData.llm_thinking || "思考过程...";
      thinkingSection.appendChild(thinkingContent);
      panel.appendChild(thinkingSection);

      const planJsonSection = createEl("div", "", { style: { flex: "1" } });
      const planTitle = createEl("div", "", {
        style: { fontSize: "12px", fontWeight: "700", color: "#0b1720", marginBottom: "8px" }
      });
      planTitle.textContent = "Generated Plan (JSON)";
      planJsonSection.appendChild(planTitle);

      const planJson = createEl("div", "", {
        style: {
          background: "#0b1220",
          border: "1px solid #1e293b",
          borderRadius: "6px",
          padding: "10px",
          fontSize: "10px",
          color: "#e6eef8",
          maxHeight: "180px",
          overflow: "auto",
          fontFamily: "'Monaco', 'Courier New', monospace"
        }
      });
      const planObj = {
        run_id: this.planData.run_id,
        status: this.planData.status,
        instruction: this.planData.instruction,
        llm_global_planning: this.planData.llm_global_planning,
        robot_tool_calls: this.planData.robot_tool_calls
      };
      planJson.textContent = JSON.stringify(planObj, null, 2);
      planJsonSection.appendChild(planJson);
      panel.appendChild(planJsonSection);
    }

    renderMainBody(root) {
      if (!this.planData) {
        const empty = createEl("div", "", {
          style: {
            flex: "1",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            color: "#9ca3af",
            fontSize: "14px"
          }
        });
        empty.textContent = "Generate a plan from the task description above or load demo data";
        root.appendChild(empty);
        return;
      }

      const body = createEl("div", "", {
        style: {
          flex: "1",
          display: "flex",
          gap: "12px",
          padding: "12px",
          overflow: "hidden"
        }
      });
      root.appendChild(body);

      this.renderPlanningPanel(body);
      this.renderTimelinePanel(body);
      this.renderInspectorPanel(body);
    }

    renderPlanningPanel(body) {
      const panel = createEl("div", "", {
        style: {
          width: "280px",
          background: "#ffffff",
          border: "1px solid #e6eef7",
          borderRadius: "8px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden"
        }
      });
      body.appendChild(panel);

      const header = createEl("div", "", {
        style: {
          padding: "12px",
          borderBottom: "1px solid #e6eef7",
          background: "#f6f8fa"
        }
      });
      const title = createEl("div", "", {
        style: { fontSize: "13px", fontWeight: "700", color: "#0b1720" }
      });
      title.textContent = "Planning DAG";
      header.appendChild(title);
      const stats = createEl("div", "", {
        style: { fontSize: "11px", color: "#6b7280", marginTop: "4px" }
      });
      const planning = this.planData.llm_global_planning || [];
      const uniqueRobots = new Set(planning.map(t => t.robot_id)).size;
      stats.textContent = `${planning.length} tasks · ${uniqueRobots} robots`;
      header.appendChild(stats);
      panel.appendChild(header);

      const content = createEl("div", "", {
        style: { flex: "1", overflow: "auto", padding: "12px" }
      });
      const groups = this.getTasksGroupedByOrder();
      const orders = Object.keys(groups).map(Number).sort((a, b) => a - b);

      orders.forEach((order, idx) => {
        const group = groups[order];
        const orderGroup = createEl("div", "", { style: { marginBottom: "16px" } });

        const orderLabel = createEl("div", "", {
          style: {
            fontSize: "12px",
            fontWeight: "700",
            color: "#0b1720",
            marginBottom: "8px",
            padding: "6px 8px",
            background: "#eff8ff",
            borderRadius: "6px"
          }
        });
        orderLabel.textContent = `Order ${order}`;
        orderGroup.appendChild(orderLabel);

        group.forEach((task, taskIdx) => {
          const card = createEl("div", "", {
            style: {
              padding: "8px",
              marginBottom: "6px",
              background: "#f9fafc",
              border: "1px solid #d1d5db",
              borderRadius: "6px",
              cursor: "pointer",
              transition: "all 150ms ease"
            }
          });

          const isSelected = this.selectedTaskKey === `${task.robot_id}:${taskIdx}`;
          if (isSelected) {
            card.style.background = "#dfeeff";
            card.style.border = "2px solid #0b66ff";
          }

          card.addEventListener("mouseenter", () => {
            if (!isSelected) card.style.background = "#f0f4f8";
          });
          card.addEventListener("mouseleave", () => {
            if (!isSelected) card.style.background = "#f9fafc";
          });

          card.addEventListener("click", () => {
            this.selectTask(task.robot_id, taskIdx);
            this.render();
          });

          const robotLabel = createEl("div", "", {
            style: { fontSize: "11px", fontWeight: "700", color: "#0b1720" }
          });
          robotLabel.textContent = task.robot_id;
          card.appendChild(robotLabel);

          const taskText = createEl("div", "", {
            style: { fontSize: "12px", color: "#475569", marginTop: "4px", lineHeight: "1.3" }
          });
          taskText.textContent = truncate(task.task, 35);
          card.appendChild(taskText);

          const statusRow = createEl("div", "", {
            style: { marginTop: "6px", display: "flex", justifyContent: "space-between", alignItems: "center" }
          });
          statusRow.appendChild(statusBadge(task.status || "pending"));
          card.appendChild(statusRow);

          orderGroup.appendChild(card);
        });

        content.appendChild(orderGroup);

        if (idx < orders.length - 1) {
          const arrow = createEl("div", "", {
            style: {
              textAlign: "center",
              color: "#cbd5e1",
              marginBottom: "12px",
              fontSize: "16px"
            }
          });
          arrow.textContent = "↓";
          content.appendChild(arrow);
        }
      });

      panel.appendChild(content);
    }

    renderTimelinePanel(body) {
      const panel = createEl("div", "", {
        style: {
          flex: "1",
          background: "#ffffff",
          border: "1px solid #e6eef7",
          borderRadius: "8px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden"
        }
      });
      body.appendChild(panel);

      const header = createEl("div", "", {
        style: {
          padding: "12px",
          borderBottom: "1px solid #e6eef7",
          background: "#f6f8fa"
        }
      });
      const title = createEl("div", "", {
        style: { fontSize: "13px", fontWeight: "700", color: "#0b1720" }
      });
      title.textContent = "Timeline";
      header.appendChild(title);
      const stats = createEl("div", "", {
        style: { fontSize: "11px", color: "#6b7280", marginTop: "4px" }
      });
      const planning = this.planData.llm_global_planning || [];
      const uniqueRobots = new Set(planning.map(t => t.robot_id)).size;
      const maxOrder = Math.max(0, ...planning.map(t => t.task_order || 0));
      stats.textContent = `${uniqueRobots} robots · ${maxOrder + 1} phases`;
      header.appendChild(stats);
      panel.appendChild(header);

      const content = createEl("div", "", {
        style: { flex: "1", overflow: "auto", padding: "12px" }
      });
      const timeline = createEl("div", "", { style: { display: "flex", flexDirection: "column", gap: "12px" } });

      const robots = [...new Set(planning.map(t => t.robot_id))];
      const groups = this.getTasksGroupedByOrder();
      const orders = Object.keys(groups).map(Number).sort((a, b) => a - b);

      robots.forEach(robotId => {
        const row = createEl("div", "", {
          style: {
            display: "flex",
            gap: "12px",
            alignItems: "center"
          }
        });

        const label = createEl("div", "", {
          style: {
            width: "100px",
            fontSize: "12px",
            fontWeight: "700",
            color: "#0b1720"
          }
        });
        label.textContent = robotId;
        row.appendChild(label);

        const track = createEl("div", "", {
          style: {
            flex: "1",
            display: "flex",
            gap: "8px",
            alignItems: "center",
            minHeight: "48px"
          }
        });

        orders.forEach((order, orderIdx) => {
          const phase = createEl("div", "", {
            style: {
              flex: `${1 + order * 0.5}`,
              position: "relative",
              minHeight: "48px",
              background: "#f9fafc",
              border: "1px dashed #d1d5db",
              borderRadius: "6px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center"
            }
          });

          const taskInOrder = groups[order].find(t => t.robot_id === robotId);
          if (taskInOrder) {
            const block = createEl("div", "", {
              style: {
                width: "95%",
                padding: "8px",
                background: "#eff6ff",
                border: "2px solid #3b82f6",
                borderRadius: "6px",
                cursor: "pointer",
                textAlign: "center",
                transition: "all 150ms ease"
              }
            });

            const color = getStatusColor(taskInOrder.status);
            block.style.background = color.bg;
            block.style.borderColor = color.border;

            const isSelected = this.selectedTaskKey === `${robotId}:${groups[order].indexOf(taskInOrder)}`;
            if (isSelected) {
              block.style.boxShadow = "0 4px 12px rgba(59, 130, 246, 0.3)";
            }

            block.addEventListener("mouseenter", () => {
              if (!isSelected) block.style.transform = "scale(1.05)";
            });
            block.addEventListener("mouseleave", () => {
              block.style.transform = "";
            });

            block.addEventListener("click", () => {
              this.selectTask(robotId, groups[order].indexOf(taskInOrder));
              this.render();
            });

            const blockText = createEl("div", "", {
              style: { fontSize: "11px", fontWeight: "600", color: color.text }
            });
            blockText.textContent = `O${order}`;
            block.appendChild(blockText);

            const summary = createEl("div", "", {
              style: { fontSize: "10px", color: color.text, marginTop: "2px" }
            });
            summary.textContent = truncate(taskInOrder.task, 20);
            block.appendChild(summary);

            phase.appendChild(block);
          }

          track.appendChild(phase);
        });

        row.appendChild(track);
        timeline.appendChild(row);
      });

      content.appendChild(timeline);
      panel.appendChild(content);
    }

    renderInspectorPanel(body) {
      const panel = createEl("div", "", {
        style: {
          width: "320px",
          background: "#ffffff",
          border: "1px solid #e6eef7",
          borderRadius: "8px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden"
        }
      });
      body.appendChild(panel);

      const header = createEl("div", "", {
        style: {
          padding: "12px",
          borderBottom: "1px solid #e6eef7",
          background: "#f6f8fa"
        }
      });
      const title = createEl("div", "", {
        style: { fontSize: "13px", fontWeight: "700", color: "#0b1720" }
      });
      title.textContent = "Inspector";
      header.appendChild(title);
      panel.appendChild(header);

      const content = createEl("div", "", {
        style: { flex: "1", overflow: "auto", padding: "12px" }
      });

      if (!this.selectedRobotId) {
        const empty = createEl("div", "", {
          style: { color: "#9ca3af", fontSize: "13px", textAlign: "center", marginTop: "24px" }
        });
        empty.textContent = "Select a task to inspect";
        content.appendChild(empty);
      } else {
        const robotId = this.selectedRobotId;
        const info = createEl("div", "", {
          style: { marginBottom: "16px", padding: "10px", background: "#f0f4f8", borderRadius: "6px" }
        });

        const robotLabel = createEl("div", "", {
          style: { fontSize: "12px", fontWeight: "700", color: "#0b1720" }
        });
        robotLabel.textContent = `Robot: ${robotId}`;
        info.appendChild(robotLabel);

        const planning = this.planData.llm_global_planning || [];
        const robotTasks = planning.filter(t => t.robot_id === robotId);
        if (robotTasks.length > 0) {
          const current = robotTasks[0];
          const taskText = createEl("div", "", {
            style: { fontSize: "12px", color: "#475569", marginTop: "6px" }
          });
          taskText.textContent = truncate(current.task, 40);
          info.appendChild(taskText);

          const status = createEl("div", "", {
            style: { marginTop: "6px" }
          });
          status.appendChild(statusBadge(current.status || "pending"));
          info.appendChild(status);
        }

        content.appendChild(info);

        const toolsTitle = createEl("div", "", {
          style: { fontSize: "12px", fontWeight: "700", color: "#0b1720", marginBottom: "8px" }
        });
        toolsTitle.textContent = "Tool Calls";
        content.appendChild(toolsTitle);

        const toolCalls = this.getRobotToolCalls(robotId);
        if (toolCalls.length === 0) {
          const empty = createEl("div", "", {
            style: { color: "#9ca3af", fontSize: "12px" }
          });
          empty.textContent = "No tool calls";
          content.appendChild(empty);
        } else {
          toolCalls.forEach((call, idx) => {
            const callItem = createEl("div", "", {
              style: {
                padding: "8px",
                marginBottom: "6px",
                background: "#f9fafc",
                border: "1px solid #d1d5db",
                borderRadius: "6px"
              }
            });

            if (call.status === "running") {
              callItem.style.background = "#eff6ff";
              callItem.style.border = "2px solid #3b82f6";
            }

            const action = createEl("div", "", {
              style: { fontSize: "12px", fontWeight: "600", color: "#0b1720" }
            });
            action.innerHTML = `${esc(call.action)}<span style="color:#9ca3af; font-weight:400"> (${esc(call.arguments || "")})</span>`;
            callItem.appendChild(action);

            const statusBadgeEl = createEl("div", "", {
              style: { marginTop: "4px" }
            });
            statusBadgeEl.appendChild(statusBadge(call.status || "pending"));
            callItem.appendChild(statusBadgeEl);

            if (call.result) {
              const resultBtn = createEl("div", "", {
                style: {
                  fontSize: "11px",
                  color: "#0b66ff",
                  marginTop: "4px",
                  cursor: "pointer"
                }
              });
              resultBtn.textContent = "View Result";
              resultBtn.addEventListener("click", () => {
                const detail = createEl("pre", "", {
                  style: {
                    fontSize: "10px",
                    background: "#0b1220",
                    color: "#e6eef8",
                    padding: "6px",
                    borderRadius: "4px",
                    marginTop: "4px",
                    overflow: "auto"
                  }
                });
                detail.textContent = JSON.stringify(call.result, null, 2);
                if (!callItem.querySelector("pre")) {
                  callItem.appendChild(detail);
                  resultBtn.textContent = "Hide Result";
                } else {
                  callItem.querySelector("pre").remove();
                  resultBtn.textContent = "View Result";
                }
              });
              callItem.appendChild(resultBtn);
            }

            content.appendChild(callItem);
          });
        }
      }

      panel.appendChild(content);
    }
  }

  async function renderMVP() {
    const robots = await loadRobots();
    if (robots.length === 0) {
      host.innerHTML = '<div style="padding:20px;color:#ef4444">Failed to load robots</div>';
      return;
    }

    const demoData = await loadDemoData();
    const app = new MVPApp(robots, demoData);
    app.render();
  }

  window.renderMVP = renderMVP;

  let rendered = false;
  const mo = new MutationObserver(() => {
    try {
      const st = window.getComputedStyle(host);
      const visible = st && st.display !== "none" && st.visibility !== "hidden" && host.offsetParent !== null;
      if (visible && !rendered) { rendered = true; renderMVP(); }
    } catch (e) {}
  });
  mo.observe(host, { attributes: true, attributeFilter: ["style", "class"] });

  setTimeout(() => {
    try {
      const st = window.getComputedStyle(host);
      if (st && st.display !== "none" && !rendered) { rendered = true; renderMVP(); }
    } catch (e) {}
  }, 100);
})();