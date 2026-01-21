// robo-control.js - iframe 切换控制器
// 功能：在 id="robo-control" 的元素内，生成下拉框切换显示多个 iframe

(function () {
  const HOST_ID = "robo-control";
  const host = document.getElementById(HOST_ID);
  if (!host) {
    console.warn(`Element with id "${HOST_ID}" not found.`);
    return;
  }

  // 工具函数：创建 DOM 元素
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

  // 预定义 iframe 配置
  let iframeConfigs = [
    // { id: "dashboard", name: "仪表盘", url: "/dashboard.html" },
    // { id: "monitor", name: "监控面板", url: "/monitor.html" },
    // { id: "logs", name: "日志查看", url: "/logs.html" },
    // { id: "config", name: "配置页面", url: "/config.html" }
  ];
  console.log(window.robots)


  // 渲染主界面
  function render() {
    host.innerHTML = "";
    
    // 创建容器
    const container = createEl("div", {
      class: "robo-control-container flex-col",
      style: {
        padding: "20px",
        background: "#f5f7fa",
        borderRadius: "8px",
        fontFamily: "Arial, sans-serif",
        height: "100%"
      }
    });

    // 标题
    const title = createEl("h2", {
      style: {
        margin: "0 0 20px 0",
        color: "#333",
        fontSize: "20px"
      }
    }, ["机器人控制面板"]);
    container.appendChild(title);

    // 下拉选择区域
    const selectorArea = createEl("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: "10px",
        marginBottom: "20px"
      }
    });

    const label = createEl("label", {
      style: {
        fontWeight: "bold",
        color: "#555"
      }
    }, ["选择机器:"]);

    const select = createEl("select", {
      id: "iframe-selector",
      style: {
        padding: "8px 12px",
        border: "1px solid #ddd",
        borderRadius: "4px",
        minWidth: "200px",
        fontSize: "14px"
      }
    });

    // 添加选项
    iframeConfigs.forEach(config => {
      const option = createEl("option", { value: config.id }, [config.name]);
      select.appendChild(option);
    });

    selectorArea.appendChild(label);
    selectorArea.appendChild(select);
    container.appendChild(selectorArea);

    // iframe 容器
    const iframeContainer = createEl("div", {
      id: "iframe-display-area",
      class: "flex flex1",
      style: {
        border: "1px solid #ddd",
        borderRadius: "4px",
        overflow: "hidden",
        height: "500px",
        background: "#fff"
      }
    });

    // 初始加载第一个 iframe
    const initialConfig = iframeConfigs[0];
    const initialIframe = createEl("iframe", {
      id: `iframe-${initialConfig.id}`,
      src: initialConfig.url,
      style: {
        width: "100%",
        height: "100%",
        border: "none"
      },
      loading: "lazy"
    });
    iframeContainer.appendChild(initialIframe);
    container.appendChild(iframeContainer);

    // 状态显示
    const status = createEl("div", {
      id: "iframe-status",
      style: {
        marginTop: "10px",
        fontSize: "12px",
        color: "#666"
      }
    }, [`当前显示: ${initialConfig.name}`]);
    container.appendChild(status);

    host.appendChild(container);

    // 下拉框切换事件
    select.addEventListener("change", function() {
      const selectedId = this.value;
      const config = iframeConfigs.find(c => c.id === selectedId);
      if (!config) return;

      // 更新状态
      document.getElementById("iframe-status").textContent = `当前显示: ${config.name}`;

      // 隐藏所有 iframe
      const allIframes = iframeContainer.querySelectorAll("iframe");
      allIframes.forEach(iframe => {
        iframe.style.display = "none";
      });

      // 显示或创建选中的 iframe
      let targetIframe = document.getElementById(`iframe-${selectedId}`);
      if (!targetIframe) {
        targetIframe = createEl("iframe", {
          id: `iframe-${selectedId}`,
          src: config.url,
          style: {
            width: "100%",
            height: "100%",
            border: "none",
            display: "block"
          },
          loading: "lazy"
        });
        iframeContainer.appendChild(targetIframe);
      } else {
        targetIframe.style.display = "block";
      }
    });
  }

  let timer = setInterval(() => {
      if (window.robots) {
          clearInterval(timer);
          iframeConfigs = window.robots.map((item)=>{
            return {
              ...item,
              url: buildControlUrl(item)
            }
          })

          // 初始化
          if (document.readyState === "loading") {
            document.addEventListener("DOMContentLoaded", render);
          } else {
            render();
          }
      }
  }, 800);


  // 暴露 API
  window.roboControl = {
    switchTo: function(id) {
      const select = document.getElementById("iframe-selector");
      if (select) {
        select.value = id;
        select.dispatchEvent(new Event("change"));
      }
    },
    addView: function(id, name, url) {
      iframeConfigs.push({ id, name, url });
      const select = document.getElementById("iframe-selector");
      if (select) {
        const option = createEl("option", { value: id }, [name]);
        select.appendChild(option);
      }
    },
    getCurrentView: function() {
      const select = document.getElementById("iframe-selector");
      return select ? select.value : null;
    }
  };
})();
