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

  // 为每个机器人分配颜色
  const robotColors = {};
  const colorPalette = [
    { bg: "#fef3c7", border: "#f59e0b", text: "#92400e" }, // amber
    { bg: "#dbeafe", border: "#0284c7", text: "#0c2340" }, // sky blue
    { bg: "#fecaca", border: "#dc2626", text: "#7f1d1d" }, // red
    { bg: "#d1fae5", border: "#059669", text: "#065f46" }, // emerald
    { bg: "#e9d5ff", border: "#a855f7", text: "#6b21a8" }  // purple
  ];

  function getRobotColor(robotId) {
    if (!robotColors[robotId]) {
      const idx = Object.keys(robotColors).length % colorPalette.length;
      robotColors[robotId] = colorPalette[idx];
    }
    return robotColors[robotId];
  }

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

  function createAdaptiveChip(label, state = "pending") {
    const palette = {
      pending: { bg: "#f3f4f6", border: "#d1d5db", text: "#374151" },
      done: { bg: "#ecfdf5", border: "#34d399", text: "#065f46" }
    };
    const colors = palette[state] || palette.pending;
    const chip = createEl("span", "", {
      style: {
        display: "inline-flex",
        alignItems: "center",
        padding: "2px 10px",
        borderRadius: "999px",
        fontSize: "11px",
        fontWeight: "600",
        border: `1px solid ${colors.border}`,
        background: colors.bg,
        color: colors.text
      }
    });
    chip.textContent = label;
    return chip;
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

  // Removed: generatePlanFromLLM function
  // Now using real backend LLM planner via /api/generate_plan

  class MVPApp {
    constructor(robots, demoData) {
      this.robots = robots;
      this.planData = demoData;
      this.selectedSite = null;
      this.selectedRobotId = null;
      this.selectedTaskOrder = null;
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
        // 不再自动选择第一个任务，用户需要手动点击查看详情
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

    // 获取指定机器人和order的task
    getTaskByRobotAndOrder(robotId, taskOrder) {
      const planning = this.planData.llm_global_planning || [];
      return planning.find(t => t.robot_id === robotId && t.task_order === taskOrder);
    }

    selectTask(robotId, taskOrder) {
      this.selectedRobotId = robotId;
      this.selectedTaskOrder = taskOrder;
      this.selectedTaskKey = `${robotId}:${taskOrder}`;
    }

    async startExecution() {
      if (!this.planData || this.isRunning) return;

      this.isRunning = true;
      const planning = this.planData.llm_global_planning || [];
      
      // 按 task_order 分组任务
      const tasksByOrder = {};
      planning.forEach(task => {
        const order = task.task_order || 0;
        if (!tasksByOrder[order]) {
          tasksByOrder[order] = [];
        }
        tasksByOrder[order].push(task);
      });

      // 按顺序执行每个 order
      const orders = Object.keys(tasksByOrder).map(Number).sort((a, b) => a - b);
      
      for (const order of orders) {
        const tasksInOrder = tasksByOrder[order];
        
        // 同一 order 内的所有任务并行执行
        const orderPromises = tasksInOrder.map(task => 
          this.executeTask(task)
        );
        
        // 等待该 order 的所有任务完成
        await Promise.all(orderPromises);
      }

      this.planData.status = "COMPLETED";
      this.isRunning = false;
      this.updateUI();
    }

    async executeTask(task) {
      // 执行单个任务
      task.status = "running";
      this.updateUI();
      
      // 模拟任务执行时间：10-15秒
      await this.sleep(10000 + Math.random() * 5000);

      // 执行该任务对应机器人的 tool calls（在任务完成前执行）
      const toolCalls = this.getRobotToolCalls(task.robot_id);
      if (toolCalls && toolCalls.length > 0) {
        // tool calls 还没完成，保持任务状态为 running
        for (const toolCall of toolCalls) {
          if (toolCall.status !== "done") {
            await this.executeToolCall(toolCall);
          }
        }
      }

      // 所有 tool calls 完成后，任务才标记为完成
      task.status = "done";
      
      this.updateUI();
    }

    async executeToolCall(toolCall) {
      // 执行单个 tool call
      toolCall.status = "running";
      this.updateUI();
      
      // 模拟 tool call 执行时间：3-5秒
      await this.sleep(3000 + Math.random() * 2000);

      // tool call 完成
      toolCall.status = "done";
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
      title.textContent = "多机器人 LLM 规划器";
      left.appendChild(title);

      if (this.planData) {
        const info = createEl("div", "", { style: { display: "flex", gap: "16px" } });
        const runId = createEl("div", "", { style: { fontSize: "13px", color: "#475569" } });
        runId.innerHTML = `<strong>执行ID:</strong> ${esc(this.planData.run_id || "N/A")}`;
        info.appendChild(runId);

        const status = createEl("div", "", { style: { fontSize: "13px", color: "#475569" } });
        const statusColor = getStatusColor(this.planData.status?.toLowerCase() || "pending");
        status.innerHTML = `<strong>状态:</strong> <span style="color:${statusColor.text}; font-weight:600">${esc(this.planData.status || "N/A")}</span>`;
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
            background: "#0b66ff", // 保持原来的蓝色样式
            color: "#fff",
            border: "none",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: "600"
          }
        });
        
        // 修改按钮文字，提示这是测试
        executeBtn.textContent = "执行规划";
        
        // [核心修改] 绑定点击事件到
        executeBtn.addEventListener("click", async () => {
          if (!this.planData) return;

          // 1. UI 反馈：防止重复点击
          const originalText = executeBtn.textContent;
          executeBtn.textContent = "⏳ 指令下发中...";
          executeBtn.disabled = true;
          executeBtn.style.opacity = "0.7";

          try {
            // 2. 发起请求：将当前的 planData 包装后发给后端
            const response = await fetch("/api/execute_plan", {
              method: "POST",
              headers: {
                "Content-Type": "application/json"
              },
              // 注意：后端 Pydantic 模型要求结构是 { plan: { ... } }
              body: JSON.stringify({ plan: this.planData })
            });

            const result = await response.json();

            if (response.ok) {
              alert(`✅ 执行成功！\n消息: ${result.message}\n(请查看机器人是否播报)`);
              console.log("后端返回的过滤后计划:", result.filtered_plan_preview);
            } else {
              alert(`❌ 执行失败: ${result.detail || "后端未知错误"}`);
            }

          } catch (error) {
            console.error("执行请求出错:", error);
            alert("网络请求失败，请检查后端服务");
          } finally {
            // 3. 恢复按钮状态
            executeBtn.textContent = originalText;
            executeBtn.disabled = false;
            executeBtn.style.opacity = "1";
          }
        });

        right.appendChild(executeBtn);
      }



      const pauseBtn = createEl("button", "", {
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
      pauseBtn.textContent = "暂停";
      right.appendChild(pauseBtn);

      const exportBtn = createEl("button", "", {
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
      exportBtn.textContent = "导出";
      right.appendChild(exportBtn);

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
      siteLabel.textContent = "选择站点";
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
      robotsLabel.textContent = "可用机器人";
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
        empty.textContent = "无可用的机器人";
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
      taskLabel.textContent = "任务描述";
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
      planBtn.textContent = "生成规划";
      planBtn.addEventListener("click", async () => {
        const instruction = taskInput.value.trim();
        if (!instruction) {
          alert("请输入任务描述");
          return;
        }

        const availableRobots = this.getAvailableRobots();
        if (availableRobots.length === 0) {
          alert("该站点没有可用的机器人");
          return;
        }

        planBtn.disabled = true;
        planBtn.textContent = "规划中...";

        try {
          // 调用后端 /api/generate_plan 接口，使用真实的 llm_planner_baidu
          const response = await fetch("/api/generate_plan", {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              instruction: instruction,
              site: this.selectedSite || ""
            })
          });

          if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            const errorMsg = errorData.detail || `服务器错误: ${response.status}`;
            alert(`生成规划失败: ${errorMsg}`);
            planBtn.disabled = false;
            planBtn.textContent = "生成规划";
            return;
          }

          const planData = await response.json();
          this.planData = planData;
          taskInput.value = "";
          this.render();
        } catch (err) {
          console.error("Error generating plan:", err);
          alert(`错误: ${err.message}`);
        } finally {
          planBtn.disabled = false;
          planBtn.textContent = "生成规划";
        }
      });
      inputContainer.appendChild(planBtn);
      taskSection.appendChild(inputContainer);
      container.appendChild(taskSection);

      panel.appendChild(container);
    }

    renderLLMThinkingPanel(root) {
      const panel = createEl("div", "", {
        style: {
          flex: "0 0 auto",
          width: "100%",
          background: "#ffffff",
          border: "1px solid #e6eef7",
          borderRadius: "8px",
          overflow: "hidden",
          display: "flex",
          flexDirection: "column"
        }
      });
      root.appendChild(panel);

      // Collapsible header similar to Inspector
      let isExpanded = true;
      const header = createEl("div", "", {
        style: {
          padding: "12px",
          borderBottom: "1px solid #e6eef7",
          background: "#f6f8fa",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
          userSelect: "none",
          flexShrink: "0"
        }
      });
      const titleContainer = createEl("div", "", { style: { display: "flex", alignItems: "center", gap: "8px" } });
      const toggleIcon = createEl("span", "", { style: { fontSize: "12px", color: "#666", fontWeight: "bold", minWidth: "12px" } });
      toggleIcon.textContent = "▼";

      // 判断响应类型：查询（information）还是规划（planning/task）
      const isInformation = this.planData.type === "information";
      const isQuery = this.planData.answer && this.planData.status === "ANSWERED";
      const headerTitle = createEl("div", "", { style: { fontSize: "13px", fontWeight: "700", color: "#0b1720" } });
      headerTitle.textContent = (isInformation || isQuery) ? "查询结果" : "LLM任务规划";
      titleContainer.appendChild(toggleIcon);
      titleContainer.appendChild(headerTitle);
      header.appendChild(titleContainer);
      panel.appendChild(header);

      const contentWrap = createEl("div", "", { style: { display: "flex", gap: "16px", padding: "12px" } });
      panel.appendChild(contentWrap);
      header.addEventListener("click", () => {
        isExpanded = !isExpanded;
        if (isExpanded) {
          contentWrap.style.display = "flex";
          toggleIcon.textContent = "▼";
        } else {
          contentWrap.style.display = "none";
          toggleIcon.textContent = "▶";
        }
      });

      const leftSection = createEl("div", "", { style: { flex: "1" } });
      const leftTitle = createEl("div", "", {
        style: { fontSize: "12px", fontWeight: "700", color: "#0b1720", marginBottom: "8px" }
      });
      
      if (isInformation || isQuery) {
        // === 查询响应类型 ===
        leftTitle.textContent = "📋 Query Response (Information)";
        leftSection.appendChild(leftTitle);

        const queryContent = createEl("div", "", {
          style: {
            background: "#ffffff",
            border: "1px solid #e6eef7",
            borderRadius: "6px",
            padding: "10px",
            fontSize: "11px",
            color: "#475569",
            lineHeight: "1.6",
            fontFamily: "'Monaco', 'Courier New', monospace"
          }
        });

        const queryDisplay = `问题 (Question):\n${this.planData.question || this.planData.instruction || "N/A"}\n\n` +
          `状态 (Status):\n${this.planData.status || "ANSWERED"}\n\n` +
          `答案 (Answer):\n${this.planData.answer || "No answer provided"}\n\n` +
          `模型 (Model):\n${this.planData.model || "unknown"}\n\n` +
          `来源 (Sources):\n${JSON.stringify(this.planData.sources || [], null, 2)}`;

        queryContent.textContent = queryDisplay;
        leftSection.appendChild(queryContent);
        contentWrap.appendChild(leftSection);

      } else {
        // === 任务规划类型 ===
        leftTitle.textContent = "🧠 规划与思考过程";
        leftSection.appendChild(leftTitle);

        const thinkingContent = createEl("div", "", {
          style: {
            background: "#ffffff",
            border: "1px solid #e6eef7",
            borderRadius: "6px",
            padding: "10px",
            fontSize: "11px",
            color: "#475569",
            lineHeight: "1.5",
            fontFamily: "'Monaco', 'Courier New', monospace",
            whiteSpace: "pre-wrap",
            wordBreak: "break-word"
          }
        });
        
        // 包含 thinking process 和 constraints
        let thinkingDisplay = this.planData.llm_thinking || "思考过程...";
        if (this.planData.constraints && this.planData.constraints.length > 0) {
          thinkingDisplay += "\n\n📋 约束条件 (Constraints):\n" + 
            JSON.stringify(this.planData.constraints, null, 2);
        }
        
        thinkingContent.textContent = thinkingDisplay;
        leftSection.appendChild(thinkingContent);
        contentWrap.appendChild(leftSection);
      }

      const rightSection = createEl("div", "", { style: { flex: "1" } });
      const rightTitle = createEl("div", "", {
        style: { fontSize: "12px", fontWeight: "700", color: "#0b1720", marginBottom: "8px" }
      });

      if (isInformation || isQuery) {
        rightTitle.textContent = "📊 问题答复 (JSON)";
      } else {
        rightTitle.textContent = "📊 任务拆解";
      }
      rightSection.appendChild(rightTitle);

      if (!isInformation && !isQuery) {
        // 任务规划：显示 robot_tool_calls 的列表形式（按机器人分组）
        const planList = createEl("div", "", {
          style: {
            background: "#ffffff",
            border: "1px solid #e6eef7",
            borderRadius: "6px",
            padding: "8px",
            fontSize: "11px",
            color: "#475569"
          }
        });

        const robotToolCallsData = this.planData.robot_tool_calls || {};
        
        // 检查是对象还是数组
        let robotCallsMap = {};
        if (Array.isArray(robotToolCallsData)) {
          // 如果是数组，按 robot_id 分组
          robotToolCallsData.forEach(call => {
            const robotId = call.robot_id || "Unknown";
            if (!robotCallsMap[robotId]) {
              robotCallsMap[robotId] = [];
            }
            robotCallsMap[robotId].push(call);
          });
        } else if (typeof robotToolCallsData === 'object') {
          // 如果是对象，直接使用
          robotCallsMap = robotToolCallsData;
        }

        const robotIds = Object.keys(robotCallsMap);
        if (robotIds.length === 0) {
          const empty = createEl("div", "", {
            style: { color: "#9ca3af", padding: "8px" }
          });
          empty.textContent = "No tool calls";
          planList.appendChild(empty);
        } else {
          robotIds.forEach((robotId, robotIdx) => {
            const calls = robotCallsMap[robotId];
            
            // 机器人标题（只显示一次）
            const robotHeader = createEl("div", "", {
              style: {
                fontWeight: "700",
                color: "#0b1720",
                marginBottom: "6px",
                paddingBottom: "4px",
                borderBottom: "1px solid #e6eef7"
              }
            });
            robotHeader.textContent = `🤖 ${robotId}`;
            planList.appendChild(robotHeader);

            // 该机器人的 actions 列表
            calls.forEach((call, callIdx) => {
              const callItem = createEl("div", "", {
                style: {
                  padding: "4px 6px",
                  marginLeft: "8px",
                  marginBottom: callIdx < calls.length - 1 ? "4px" : "0",
                  background: "#f9fafc",
                  borderLeft: "2px solid #3b82f6",
                  borderRadius: "3px",
                  fontSize: "10px"
                }
              });

              const action = createEl("div", "", {
                style: { color: "#475569", marginBottom: "2px", fontFamily: "'Monaco', 'Courier New', monospace", fontWeight: "600" }
              });
              action.textContent = `${call.action}`;
              callItem.appendChild(action);

              const args = createEl("div", "", {
                style: { color: "#6b7280", fontFamily: "'Monaco', 'Courier New', monospace", fontSize: "9px", wordBreak: "break-word" }
              });
              const argsStr = typeof call.arguments === 'object' 
                ? JSON.stringify(call.arguments) 
                : String(call.arguments);
              args.textContent = argsStr;
              callItem.appendChild(args);

              planList.appendChild(callItem);
            });

            // 机器人之间添加间隔
            if (robotIdx < robotIds.length - 1) {
              const divider = createEl("div", "", {
                style: { height: "6px" }
              });
              planList.appendChild(divider);
            }
          });
        }
        rightSection.appendChild(planList);
      } else {
        // 查询响应：显示 JSON
        const planJson = createEl("div", "", {
          style: {
            background: "#0b1220",
            border: "1px solid #1e293b",
            borderRadius: "6px",
            padding: "10px",
            fontSize: "10px",
            color: "#e6eef8",
            fontFamily: "'Monaco', 'Courier New', monospace",
            whiteSpace: "pre-wrap"
          }
        });

        const displayObj = {
          status: this.planData.status,
          question: this.planData.question || this.planData.instruction,
          model: this.planData.model
        };

        planJson.textContent = JSON.stringify(displayObj, null, 2);
        rightSection.appendChild(planJson);
      }

      contentWrap.appendChild(rightSection);
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
        empty.textContent = "请在上方描述任务或加载示例数据";
        root.appendChild(empty);
        return;
      }

      const body = createEl("div", "", {
        style: {
          flex: "1",
          display: "flex",
          flexDirection: "column",
          gap: "12px",
          padding: "12px",
          overflow: "auto"
        }
      });
      root.appendChild(body);

      // First section: LLM 任务规划（与其它同级）
      if (this.planData) {
        this.renderLLMThinkingPanel(body);
      }

      // 第二：时间线视图
      const timelineSection = createEl("div", "", {
        style: {
          display: "flex",
          flex: "0 0 auto"
        }
      });
      body.appendChild(timelineSection);

      this.renderTimelinePanel(timelineSection);

      // 第三：详情执行过程（默认固定高度，折叠时释放空间）
      const inspectorContainer = createEl("div", "", {
        style: {
          flex: "0 0 300px",
          
        }
      });
      body.appendChild(inspectorContainer);
      this.renderInspectorPanel(inspectorContainer);
    }

    renderTimelinePanel(body) {
      const panel = createEl("div", "", {
        style: {
          flex: "0 0 auto",
          width: "100%",
          background: "#ffffff",
          border: "1px solid #e6eef7",
          borderRadius: "8px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden"
        }
      });
      body.appendChild(panel);

      let isExpanded = true;
      const header = createEl("div", "", {
        style: {
          padding: "12px",
          borderBottom: "1px solid #e6eef7",
          background: "#f6f8fa",
          cursor: "pointer",
          userSelect: "none",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start"
        }
      });
      
      const headerLeft = createEl("div", "", {});
      const title = createEl("div", "", {
        style: { fontSize: "13px", fontWeight: "700", color: "#0b1720" }
      });
      title.textContent = "时间线视图";
      headerLeft.appendChild(title);
      
      const stats = createEl("div", "", {
        style: { fontSize: "11px", color: "#6b7280", marginTop: "4px" }
      });
      const planning = this.planData.llm_global_planning || [];
      const uniqueRobots = new Set(planning.map(t => t.robot_id)).size;
      const maxOrder = Math.max(0, ...planning.map(t => t.task_order || 0));
      stats.textContent = `${uniqueRobots} 个机器人 · ${maxOrder + 1} 个阶段`;
      headerLeft.appendChild(stats);
      header.appendChild(headerLeft);

      const toggleIcon = createEl("span", "", {
        style: { fontSize: "12px", color: "#666", fontWeight: "bold", minWidth: "12px", marginTop: "2px" }
      });
      toggleIcon.textContent = "▼";
      header.appendChild(toggleIcon);

      header.addEventListener("click", () => {
        isExpanded = !isExpanded;
        if (isExpanded) {
          legend.style.display = "flex";
          content.style.display = "flex";
          toggleIcon.textContent = "▼";
        } else {
          legend.style.display = "none";
          content.style.display = "none";
          toggleIcon.textContent = "▶";
        }
      });

      panel.appendChild(header);

      // 添加图例
      const legend = createEl("div", "", {
        style: {
          padding: "8px 12px",
          background: "#f9fafc",
          borderBottom: "1px solid #e6eef7",
          display: "flex",
          gap: "16px",
          fontSize: "11px"
        }
      });
      const legendItems = [
        { status: "pending", label: "待执行", color: "#f3f4f6" },
        { status: "running", label: "执行中", color: "#eff6ff" },
        { status: "done", label: "已完成", color: "#ecfdf5" }
      ];
      legendItems.forEach(item => {
        const legendItem = createEl("div", "", {
          style: { display: "flex", alignItems: "center", gap: "6px" }
        });
        const box = createEl("div", "", {
          style: {
            width: "16px",
            height: "16px",
            borderRadius: "3px",
            background: item.color,
            border: "1px solid #d1d5db"
          }
        });
        legendItem.appendChild(box);
        const text = createEl("span", "", { style: { color: "#6b7280" } });
        text.textContent = item.label;
        legendItem.appendChild(text);
        legend.appendChild(legendItem);
      });
      panel.appendChild(legend);

      const content = createEl("div", "", {
        style: { flex: "1", padding: "12px", display: "flex", flexDirection: "column" }
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
            minHeight: "48px",
            overflowX: "auto",
            paddingBottom: "4px"
          }
        });

        orders.forEach(order => {
          const phase = createEl("div", "", {
            style: {
              flex: "0 0 200px",
              maxWidth: "220px",
              minWidth: "150px",
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
            const robotColor = getRobotColor(robotId);
            
            // 根据状态选择背景色
            let bgColor;
            if (taskInOrder.status === "done") {
              bgColor = "#ecfdf5"; // 完成：绿色
            } else if (taskInOrder.status === "running") {
              bgColor = "#eff6ff"; // 运行中：蓝色
            } else {
              bgColor = "#f3f4f6"; // pending：灰色
            }
            
            const block = createEl("div", "", {
              style: {
                width: "95%",
                padding: "8px",
                background: bgColor,
                border: `2px solid ${robotColor.border}`,
                borderRadius: "6px",
                cursor: "pointer",
                textAlign: "center",
                transition: "all 150ms ease"
              }
            });

            const isSelected = this.selectedTaskKey === `${robotId}:${order}`;
            if (isSelected) {
              block.style.boxShadow = `0 4px 12px ${robotColor.border}80`;
              block.style.transform = "scale(1.08)";
            }

            block.addEventListener("mouseenter", () => {
              if (!isSelected) block.style.transform = "scale(1.05)";
            });
            block.addEventListener("mouseleave", () => {
              if (!isSelected) block.style.transform = "";
            });

            block.addEventListener("click", () => {
              this.selectTask(robotId, order);
              this.render();
            });

            const blockText = createEl("div", "", {
              style: { fontSize: "11px", fontWeight: "600", color: robotColor.text }
            });
            blockText.textContent = `O${order}`;
            block.appendChild(blockText);

            const summary = createEl("div", "", {
              style: { fontSize: "10px", color: robotColor.text, marginTop: "2px" }
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

      const supervision = this.planData.execution_supervision;
      if (supervision && Array.isArray(supervision.steps) && supervision.steps.length > 0) {
        const supHeader = createEl("div", "", {
          style: { marginTop: "16px", fontSize: "12px", fontWeight: "700", color: "#0b1720" }
        });
        supHeader.textContent = "指令监督与回退";
        content.appendChild(supHeader);

        const supList = createEl("div", "", {
          style: {
            marginTop: "8px",
            display: "flex",
            flexDirection: "column",
            gap: "6px"
          }
        });

        supervision.steps.forEach(step => {
          const row = createEl("div", "", {
            style: {
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              padding: "8px",
              background: "#f9fafc",
              border: "1px solid #e2e8f0",
              borderRadius: "6px",
              fontSize: "11px"
            }
          });

          const left = createEl("div", "", {
            style: { display: "flex", flexDirection: "column", gap: "4px" }
          });

          const statusWrap = createEl("div", "", { style: { display: "flex", gap: "6px", alignItems: "center" } });
          statusWrap.appendChild(statusBadge(step.status || "pending"));
          const title = createEl("span", "", { style: { fontWeight: "600", color: "#0b1720" } });
          title.textContent = `${step.robot_id} · ${step.action}`;
          statusWrap.appendChild(title);
          left.appendChild(statusWrap);

          const meta = createEl("div", "", { style: { color: "#6b7280" } });
          meta.textContent = `timeout ${step.timeout_sec}s · retriable: ${step.retriable ? "是" : "否"}`;
          left.appendChild(meta);

          if (step.metadata?.reason) {
            const hint = createEl("div", "", { style: { color: "#9ca3af" } });
            hint.textContent = step.metadata.reason;
            left.appendChild(hint);
          }

          row.appendChild(left);

          const right = createEl("div", "", { style: { textAlign: "right", color: "#94a3b8" } });
          right.textContent = step.step_id;
          row.appendChild(right);

          supList.appendChild(row);
        });

        const ruleHint = createEl("div", "", {
          style: {
            fontSize: "11px",
            color: "#475569",
            marginTop: "4px"
          }
        });
        ruleHint.textContent = supervision.supervision_rules?.description || "顺序执行并在失败时重规划";
        supList.appendChild(ruleHint);
        content.appendChild(supList);
      }

      panel.appendChild(content);
    }

    renderInspectorPanel(body) {
      const panel = createEl("div", "", {
        style: {
          width: "100%",
          height: "100%",
          background: "#ffffff",
          border: "1px solid #e6eef7",
          borderRadius: "8px",
          display: "flex",
          flexDirection: "column",
          overflow: "hidden"
        }
      });
      body.appendChild(panel);

      // 可折叠的标签头
      let isExpanded = true;
      const header = createEl("div", "", {
        style: {
          padding: "12px",
          borderBottom: "1px solid #e6eef7",
          background: "#f6f8fa",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          cursor: "pointer",
          userSelect: "none",
          flexShrink: "0"
        }
      });
      
      const titleContainer = createEl("div", "", {
        style: { display: "flex", alignItems: "center", gap: "8px" }
      });

      const toggleIcon = createEl("span", "", {
        style: { fontSize: "12px", color: "#666", fontWeight: "bold", minWidth: "12px" }
      });
      toggleIcon.textContent = "▼";

      const title = createEl("div", "", {
        style: { fontSize: "13px", fontWeight: "700", color: "#0b1720" }
      });
      if (this.selectedRobotId && this.selectedTaskOrder !== null) {
        title.textContent = `详情执行过程 · ${this.selectedRobotId} · Order ${this.selectedTaskOrder}`;
      } else {
        title.textContent = "详情执行过程";
      }
      
      titleContainer.appendChild(toggleIcon);
      titleContainer.appendChild(title);
      header.appendChild(titleContainer);
      panel.appendChild(header);

      const content = createEl("div", "", {
        style: { flex: "1", padding: "12px", display: "flex", flexDirection: "column" }
      });

      header.addEventListener("click", () => {
        isExpanded = !isExpanded;
        if (isExpanded) {
          content.style.display = "flex";
          toggleIcon.textContent = "▼";
          // Expand: restore reserved height
          body.style.flex = "0 0 300px";
        } else {
          content.style.display = "none";
          toggleIcon.textContent = "▶";
          // Collapse: free space for other controls
          body.style.flex = "0 0 auto";
        }
      });

      if (!this.selectedRobotId || this.selectedTaskOrder === null) {
        const empty = createEl("div", "", {
          style: { color: "#9ca3af", fontSize: "13px", textAlign: "center", marginTop: "24px" }
        });
        empty.textContent = "选择任务查看详情";
        content.appendChild(empty);
      } else {
        const robotId = this.selectedRobotId;
        const taskOrder = this.selectedTaskOrder;
        const task = this.getTaskByRobotAndOrder(robotId, taskOrder);

        if (task) {
          const info = createEl("div", "", {
            style: { marginBottom: "12px", padding: "10px", background: "#f0f4f8", borderRadius: "6px" }
          });

          const robotLabel = createEl("div", "", {
            style: { fontSize: "12px", fontWeight: "700", color: "#0b1720" }
          });
          robotLabel.textContent = `🤖 机器人: ${robotId}`;
          info.appendChild(robotLabel);

          const taskText = createEl("div", "", {
            style: { fontSize: "12px", color: "#475569", marginTop: "6px" }
          });
          taskText.textContent = `📋 任务: ${task.task}`;
          info.appendChild(taskText);

          if (task.from || task.to) {
            const location = createEl("div", "", {
              style: { fontSize: "11px", color: "#6b7280", marginTop: "4px" }
            });
            location.textContent = `📍 ${task.from ? "来源: " + task.from : ""}${task.from && task.to ? " → " : ""}${task.to ? "目标: " + task.to : ""}`;
            info.appendChild(location);
          }

          if (task.object) {
            const object = createEl("div", "", {
              style: { fontSize: "11px", color: "#6b7280", marginTop: "4px" }
            });
            object.textContent = `🎯 物体: ${task.object}${task.count ? ` ×${task.count}` : ""}`;
            info.appendChild(object);
          }

          const status = createEl("div", "", {
            style: { marginTop: "8px", display: "flex", alignItems: "center", gap: "8px" }
          });
          status.appendChild(statusBadge(task.status || "pending"));
          
          // 如果任务正在运行，显示进度提示
          if (task.status === "running") {
            const hint = createEl("span", "", {
              style: { fontSize: "11px", color: "#6b7280" }
            });
            hint.textContent = "(执行工具调用中...)";
            status.appendChild(hint);
          }
          
          info.appendChild(status);

          content.appendChild(info);
        }

        const toolsTitle = createEl("div", "", {
          style: { fontSize: "12px", fontWeight: "700", color: "#0b1720", marginBottom: "8px", marginTop: "4px", flexShrink: "0" }
        });
        toolsTitle.textContent = "工具调用";
        content.appendChild(toolsTitle);

        const toolCalls = this.getRobotToolCalls(robotId);
        if (toolCalls.length === 0) {
          const empty = createEl("div", "", {
            style: { color: "#9ca3af", fontSize: "12px" }
          });
          empty.textContent = "No tool calls";
          content.appendChild(empty);
        } else {
          // 创建水平滚动容器
          const toolsContainer = createEl("div", "", {
            style: {
              display: "flex",
              gap: "8px",
              overflow: "auto",
              paddingRight: "8px",
              flexShrink: "0",
              minHeight: "100px"
            }
          });

          toolCalls.forEach((call, idx) => {
            const callItem = createEl("div", "", {
              style: {
                flex: "0 0 auto",
                minWidth: "180px",
                padding: "10px",
                background: "#f9fafc",
                border: "1px solid #d1d5db",
                borderRadius: "6px",
                display: "flex",
                flexDirection: "column"
              }
            });

            if (call.status === "running") {
              callItem.style.background = "#eff6ff";
              callItem.style.border = "2px solid #3b82f6";
              callItem.style.boxShadow = "0 2px 8px rgba(59, 130, 246, 0.2)";
            }

            const action = createEl("div", "", {
              style: { fontSize: "11px", fontWeight: "600", color: "#0b1720", marginBottom: "4px", wordBreak: "break-word" }
            });
            const argsStr = typeof call.arguments === 'object' 
              ? JSON.stringify(call.arguments).slice(0, 20)
              : String(call.arguments || "").slice(0, 20);
            action.innerHTML = `${esc(call.action)}<span style="color:#9ca3af; font-weight:400; fontSize:10px"> (${esc(argsStr)})</span>`;
            callItem.appendChild(action);

            const statusBadgeEl = createEl("div", "", {
              style: { marginTop: "4px", marginBottom: "4px" }
            });
            statusBadgeEl.appendChild(statusBadge(call.status || "pending"));
            callItem.appendChild(statusBadgeEl);

            const stepId = call.step_id || call.metadata?.step_id;
            const adaptiveInfo = this.planData.execution_supervision?.adaptive_search?.find?.(
              search => search.step_id === stepId
            );
            if (adaptiveInfo) {
              const adaptiveBox = createEl("div", "", {
                style: {
                  marginTop: "6px",
                  padding: "6px",
                  background: "#ecfdf5",
                  border: "1px dashed #34d399",
                  borderRadius: "6px"
                }
              });
              const adaptiveTitle = createEl("div", "", {
                style: { fontSize: "10px", fontWeight: "700", color: "#065f46", marginBottom: "4px" }
              });
              adaptiveTitle.textContent = "多目标感知";
              adaptiveBox.appendChild(adaptiveTitle);

              const chipWrap = createEl("div", "", {
                style: { display: "flex", flexWrap: "wrap", gap: "4px" }
              });
              (adaptiveInfo.targets || []).forEach(target => {
                const done = (adaptiveInfo.found_targets || []).includes(target);
                chipWrap.appendChild(createAdaptiveChip(target, done ? "done" : "pending"));
              });
              adaptiveBox.appendChild(chipWrap);

              if (Array.isArray(adaptiveInfo.waypoints) && adaptiveInfo.waypoints.length > 0) {
                const route = createEl("div", "", {
                  style: { marginTop: "4px", fontSize: "10px", color: "#0f5132" }
                });
                route.textContent = `路线: ${adaptiveInfo.waypoints.join(" → ")}`;
                adaptiveBox.appendChild(route);
              }

              callItem.appendChild(adaptiveBox);
            }

            if (call.result) {
              const resultBtn = createEl("div", "", {
                style: {
                  fontSize: "10px",
                  color: "#0b66ff",
                  cursor: "pointer",
                  marginTop: "auto"
                }
              });
              resultBtn.textContent = "View Result";
              resultBtn.addEventListener("click", () => {
                const detail = createEl("pre", "", {
                  style: {
                    fontSize: "9px",
                    background: "#0b1220",
                    color: "#e6eef8",
                    padding: "4px",
                    borderRadius: "4px",
                    marginTop: "4px",
                    overflow: "auto",
                    maxHeight: "80px"
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

            toolsContainer.appendChild(callItem);
          });

          content.appendChild(toolsContainer);
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