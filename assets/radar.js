/* MTA News Radar — multi-topic frontend logic (no framework, no build). */
(function () {
  "use strict";

  var state = { index: null, topicCache: new Map(), activeId: null };
  function $(id) { return document.getElementById(id); }

  /* ---- data loader ---- */
  async function loadIndex() {
    var resp = await fetch("data/index.json", { cache: "no-store" });
    if (!resp.ok) throw new Error("index.json " + resp.status);
    return resp.json();
  }
  async function loadTopic(dataUrl) {
    var resp = await fetch(dataUrl, { cache: "no-store" });
    if (!resp.ok) throw new Error(dataUrl + " " + resp.status);
    return resp.json();
  }

  /* ---- helpers ---- */
  function formatTime(iso) {
    if (!iso) return "—";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return "—";
    return d.toLocaleString("zh-CN", { dateStyle: "medium", timeStyle: "short" });
  }
  function healthCounts(sourceHealth) {
    var c = { ok: 0, failed: 0, skipped: 0 };
    (sourceHealth || []).forEach(function (h) {
      if (c[h.status] !== undefined) c[h.status] += 1;
    });
    return c;
  }
  function pill(kind, label, n) {
    var span = document.createElement("span");
    span.className = "pill pill-" + kind + (n === 0 ? " pill-zero" : "");
    span.textContent = label + " " + n;
    return span;
  }

  /* ---- tab bar ---- */
  function renderTabs(topics) {
    var bar = $("tabBar");
    bar.textContent = "";
    topics.forEach(function (t) {
      var btn = document.createElement("button");
      btn.className = "tab" + (t.id === state.activeId ? " active" : "");
      btn.type = "button";
      btn.setAttribute("role", "tab");
      btn.dataset.id = t.id;
      var name = document.createElement("span");
      name.textContent = t.name;
      var count = document.createElement("span");
      count.className = "tab-count";
      count.textContent = t.count;
      btn.append(name, count);
      btn.addEventListener("click", function () { selectTopic(t.id); });
      bar.appendChild(btn);
    });
  }
  function setActiveTab(id) {
    document.querySelectorAll(".tab").forEach(function (el) {
      el.classList.toggle("active", el.dataset.id === id);
    });
  }

  /* ---- topic view ---- */
  function renderTopicHeader(data) {
    var header = $("topicHeader");
    header.textContent = "";
    var h2 = document.createElement("h2");
    h2.textContent = data.name;

    var meta = document.createElement("div");
    meta.className = "topic-meta";
    var parts = [
      "模式 " + data.mode,
      "窗口 " + data.window_hours + "h",
      (data.items ? data.items.length : 0) + " 条",
      "更新 " + formatTime(data.generated_at),
    ];
    parts.forEach(function (text) {
      var s = document.createElement("span");
      s.textContent = text;
      meta.appendChild(s);
    });

    var c = healthCounts(data.source_health);
    var health = document.createElement("span");
    health.className = "health-summary";
    health.append(pill("ok", "ok", c.ok), pill("failed", "失败", c.failed), pill("skip", "跳过", c.skipped));
    meta.appendChild(health);

    header.append(h2, meta);
  }

  function renderHealthDetail(data) {
    var detail = $("healthDetail");
    var body = $("healthDetailBody");
    body.textContent = "";
    var list = data.source_health || [];
    if (!list.length) { detail.hidden = true; return; }
    detail.hidden = false;
    list.forEach(function (h) {
      var row = document.createElement("div");
      row.className = "health-row";
      var st = document.createElement("span");
      st.className = "hstatus " + h.status;
      st.textContent = h.status;
      var nm = document.createElement("span");
      nm.className = "hname";
      nm.textContent = h.source_name;
      row.append(st, nm);
      if (h.error) {
        var er = document.createElement("span");
        er.className = "herror";
        er.textContent = h.error;
        row.appendChild(er);
      }
      body.appendChild(row);
    });
  }

  /* ---- item renderer ---- */
  function renderItem(item, mode) {
    var node = $("itemTpl").content.cloneNode(true);
    var a = node.querySelector(".card-title");
    a.textContent = item.title;
    a.href = item.url;
    node.querySelector(".card-source").textContent = item.source_name;

    var sub = node.querySelector(".card-sublabel");
    if (item.sub_label) { sub.textContent = item.sub_label; sub.hidden = false; }

    node.querySelector(".card-time").textContent =
      item.published ? formatTime(item.published) : "时间未知";

    var score = node.querySelector(".card-score");
    if (mode === "topic" && item.score != null) {
      score.textContent = Number(item.score).toFixed(2);
      score.hidden = false;
    }

    var summary = node.querySelector(".card-summary");
    if (item.summary) { summary.textContent = item.summary; summary.hidden = false; }
    return node;
  }

  /* ---- empty / error states ---- */
  function renderEmpty(data) {
    var list = $("newsList");
    list.textContent = "";
    var msg = document.createElement("div");
    msg.className = "message";
    msg.textContent = data.topic_error
      ? "该主题抓取出错:" + data.topic_error
      : "该主题当前窗口内没有条目。";
    list.appendChild(msg);
  }
  function renderError(text) {
    var m = $("message");
    m.className = "message error";
    m.textContent = text;
    m.hidden = false;
    $("newsList").textContent = "";
    $("topicHeader").textContent = "";
    $("healthDetail").hidden = true;
  }
  function clearError() {
    var m = $("message");
    m.hidden = true;
    m.className = "message";
  }

  function renderTopic(data) {
    clearError();
    renderTopicHeader(data);
    renderHealthDetail(data);
    var list = $("newsList");
    list.textContent = "";
    if (data.topic_error || !data.items || !data.items.length) {
      renderEmpty(data);
      return;
    }
    var frag = document.createDocumentFragment();
    data.items.forEach(function (it) { frag.appendChild(renderItem(it, data.mode)); });
    list.appendChild(frag);
  }

  /* ---- controller ---- */
  async function selectTopic(id) {
    state.activeId = id;
    setActiveTab(id);
    if (state.topicCache.has(id)) { renderTopic(state.topicCache.get(id)); return; }
    var topic = state.index.topics.find(function (t) { return t.id === id; });
    if (!topic) { renderError("未找到主题 " + id); return; }
    try {
      var data = await loadTopic(topic.data_url);
      state.topicCache.set(id, data);
      if (state.activeId === id) renderTopic(data);
    } catch (e) {
      if (state.activeId === id) renderError("加载主题数据失败:" + e.message);
    }
  }

  async function init() {
    try {
      var index = await loadIndex();
      state.index = index;
      var topics = index.topics || [];
      if (!topics.length) { renderError("index.json 没有主题。"); return; }
      $("updatedAt").textContent = "更新 " + formatTime(topics[0].generated_at);
      state.activeId = topics[0].id;
      renderTabs(topics);
      selectTopic(topics[0].id);
    } catch (e) {
      renderError("加载 index.json 失败:" + e.message);
    }
  }

  init();
})();
