/* MTA News Radar — multi-topic frontend logic (no framework, no build). */
(function () {
  "use strict";

  var PAGE_SIZE = 25;
  var state = {
    index: null,
    topicCache: new Map(),
    activeId: null,
    current: null, // current topicData being shown
    shown: 0, // how many items rendered for current topic
  };
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
  // Strip HTML markup from feed text -> plain text. DOMParser('text/html') is
  // inert: it does not run scripts or load resources, so this is XSS-safe.
  function htmlToText(s) {
    if (!s) return s;
    if (s.indexOf("<") === -1 && s.indexOf("&") === -1) return s;
    try {
      var doc = new DOMParser().parseFromString(s, "text/html");
      return (doc.body.textContent || "").replace(/\s+/g, " ").trim();
    } catch (e) {
      return s;
    }
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

  /* ---- sidebar nav ---- */
  function renderNav(topics) {
    var nav = $("topicNav");
    nav.textContent = "";
    topics.forEach(function (t) {
      var btn = document.createElement("button");
      btn.className = "nav-item" + (t.id === state.activeId ? " active" : "");
      btn.type = "button";
      btn.dataset.id = t.id;
      var name = document.createElement("span");
      name.className = "nav-name";
      name.textContent = t.name;
      var count = document.createElement("span");
      count.className = "nav-count";
      count.textContent = t.count;
      btn.append(name, count);
      var failed = (t.stats && t.stats.failed) || 0;
      // health dot if any source failed (best-effort from index stats if present)
      if (t.topic_error) {
        var dot = document.createElement("span");
        dot.className = "nav-dot";
        btn.appendChild(dot);
      }
      btn.addEventListener("click", function () { selectTopic(t.id); closeNav(); });
      nav.appendChild(btn);
    });
  }
  function setActiveNav(id) {
    document.querySelectorAll(".nav-item").forEach(function (el) {
      el.classList.toggle("active", el.dataset.id === id);
    });
  }

  /* ---- topic header + health ---- */
  function renderTopicHeader(data) {
    var header = $("topicHeader");
    header.textContent = "";
    var h2 = document.createElement("h2");
    h2.textContent = data.name;

    var meta = document.createElement("div");
    meta.className = "topic-meta";
    [
      "模式 " + data.mode,
      "窗口 " + data.window_hours + "h",
      (data.items ? data.items.length : 0) + " 条",
      "更新 " + formatTime(data.generated_at),
    ].forEach(function (text) {
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
    a.textContent = htmlToText(item.title);
    a.href = item.url;
    node.querySelector(".card-source").textContent = item.source_name;
    var sub = node.querySelector(".card-sublabel");
    if (item.sub_label) { sub.textContent = item.sub_label; sub.hidden = false; }
    node.querySelector(".card-time").textContent = item.published ? formatTime(item.published) : "时间未知";
    var score = node.querySelector(".card-score");
    if (mode === "topic" && item.score != null) {
      score.textContent = Number(item.score).toFixed(2);
      score.hidden = false;
    }
    var summary = node.querySelector(".card-summary");
    var text = htmlToText(item.summary);
    if (text) { summary.textContent = text; summary.hidden = false; }
    return node;
  }

  /* ---- pagination ---- */
  function renderMore() {
    var data = state.current;
    if (!data) return;
    var items = data.items || [];
    var frag = document.createDocumentFragment();
    var end = Math.min(state.shown + PAGE_SIZE, items.length);
    for (var i = state.shown; i < end; i += 1) {
      frag.appendChild(renderItem(items[i], data.mode));
    }
    $("newsList").appendChild(frag);
    state.shown = end;
    var remaining = items.length - state.shown;
    var wrap = $("loadMoreWrap");
    if (remaining > 0) {
      wrap.hidden = false;
      $("loadMoreBtn").textContent = "加载更多(还有 " + remaining + " 条)";
    } else {
      wrap.hidden = true;
    }
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
    $("loadMoreWrap").hidden = true;
  }
  function clearError() { var m = $("message"); m.hidden = true; m.className = "message"; }

  function renderTopic(data) {
    clearError();
    state.current = data;
    state.shown = 0;
    renderTopicHeader(data);
    renderHealthDetail(data);
    $("newsList").textContent = "";
    if (data.topic_error || !data.items || !data.items.length) {
      $("loadMoreWrap").hidden = true;
      renderEmpty(data);
      return;
    }
    renderMore();
    window.scrollTo(0, 0);
  }

  /* ---- controller ---- */
  async function selectTopic(id) {
    state.activeId = id;
    setActiveNav(id);
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

  /* ---- mobile drawer ---- */
  function openNav() { $("layout").classList.add("nav-open"); $("scrim").hidden = false; }
  function closeNav() { $("layout").classList.remove("nav-open"); $("scrim").hidden = true; }

  async function init() {
    $("loadMoreBtn").addEventListener("click", renderMore);
    $("navToggle").addEventListener("click", openNav);
    $("scrim").addEventListener("click", closeNav);
    try {
      var index = await loadIndex();
      state.index = index;
      var topics = index.topics || [];
      if (!topics.length) { renderError("index.json 没有主题。"); return; }
      $("updatedAt").textContent = "更新于 " + formatTime(topics[0].generated_at);
      state.activeId = topics[0].id;
      renderNav(topics);
      selectTopic(topics[0].id);
    } catch (e) {
      renderError("加载 index.json 失败:" + e.message);
    }
  }

  init();
})();
