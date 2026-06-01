(function () {
  // Inject CSRF token into every HTMX request.
  function csrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute("content") : "";
  }

  document.body && document.body.addEventListener("htmx:configRequest", function (e) {
    e.detail.headers["X-CSRF-Token"] = csrfToken();
  });

  // Toast notifications.
  function toast(n) {
    var box = document.getElementById("toasts");
    if (!box) return;
    var el = document.createElement("div");
    el.className = "toast" + (n.severity === "critical" ? " crit" : "");
    var title = document.createElement("div");
    title.className = "t-title";
    title.textContent = n.title || "Уведомление";
    var body = document.createElement("div");
    body.className = "t-body";
    body.textContent = n.body || "";
    el.appendChild(title);
    el.appendChild(body);
    box.appendChild(el);
    setTimeout(function () {
      el.style.opacity = "0";
      setTimeout(function () { el.remove(); }, 300);
    }, 6000);
  }

  function bumpBadge() {
    var b = document.getElementById("nav-notif-badge");
    if (!b) return;
    var n = parseInt(b.textContent || "0", 10) || 0;
    b.textContent = String(n + 1);
    b.style.display = "inline-flex";
  }

  function showBrowserNotification(data) {
    if (!window.Notification || Notification.permission !== "granted") return;
    try {
      var n = new Notification(data.title || "oopsys", {
        body: data.body || "",
        tag: data.id || "oopsys-notification",
      });
      n.onclick = function () {
        window.focus();
        n.close();
      };
    } catch (_) {}
  }

  function updateBrowserNotifyUi() {
    var status = document.getElementById("browser-notify-status");
    var btn = document.getElementById("browser-notify-enable");
    if (!status || !btn) return;
    if (!window.Notification) {
      status.textContent = "Этот браузер не поддерживает уведомления.";
      btn.disabled = true;
      return;
    }
    if (Notification.permission === "granted") {
      status.textContent = "Разрешено. Алерты будут приходить в ОС дополнительно к тостам на сайте.";
      btn.textContent = "Разрешение выдано";
      btn.disabled = true;
      btn.classList.remove("primary");
      return;
    }
    if (Notification.permission === "denied") {
      status.textContent = "Заблокировано. Разрешите уведомления для этого сайта в настройках браузера и обновите страницу.";
      btn.textContent = "Заблокировано в браузере";
      btn.disabled = true;
      btn.classList.remove("primary");
      return;
    }
    status.textContent = "Разрешение ещё не запрошено. Нажмите кнопку — браузер покажет запрос.";
    btn.textContent = "Разрешить уведомления в браузере";
    btn.disabled = false;
    btn.classList.add("primary");
  }

  function initBrowserNotifySettings() {
    var btn = document.getElementById("browser-notify-enable");
    if (!btn || btn.__wired) return;
    btn.__wired = true;
    updateBrowserNotifyUi();
    btn.addEventListener("click", function () {
      if (!window.Notification) return;
      Notification.requestPermission().finally(updateBrowserNotifyUi);
    });
  }

  // Throttled live refresh: re-fetch the current page and swap only #content.
  var REFRESH_MIN_MS = 1500;
  var refreshTimer = null;
  var lastRefresh = 0;

  function isEditing() {
    var el = document.activeElement;
    var content = document.getElementById("content");
    if (!el || !content || !content.contains(el)) return false;
    var tag = (el.tagName || "").toLowerCase();
    return tag === "input" || tag === "select" || tag === "textarea";
  }

  function refreshContent() {
    if (!window.htmx || !document.getElementById("content")) return;
    if (document.hidden) return;
    if (isEditing()) { scheduleRefresh(); return; }
    lastRefresh = Date.now();
    htmx.ajax("GET", window.location.pathname + window.location.search, {
      target: "#content",
      select: "#content",
      swap: "outerHTML"
    });
  }

  function scheduleRefresh() {
    if (refreshTimer) return;
    var wait = Math.max(0, REFRESH_MIN_MS - (Date.now() - lastRefresh));
    refreshTimer = setTimeout(function () {
      refreshTimer = null;
      refreshContent();
    }, wait);
  }

  // Realtime SSE stream (account-scoped).
  function connectStream() {
    if (!window.EventSource) return;
    var src = new EventSource("/web/stream");
    src.addEventListener("notification", function (ev) {
      try {
        var data = JSON.parse(ev.data);
        toast(data);
        showBrowserNotification(data);
        bumpBadge();
      } catch (_) {}
      scheduleRefresh();
    });
    ["error", "metric", "container", "agent_status"].forEach(function (name) {
      src.addEventListener(name, function () { scheduleRefresh(); });
    });
    src.onerror = function () { /* browser auto-reconnects */ };
    // Refresh immediately when the tab regains focus (events are skipped while hidden).
    document.addEventListener("visibilitychange", function () {
      if (!document.hidden) scheduleRefresh();
    });
  }

  function tryParse(s) { try { return JSON.parse(s); } catch (_) { return {}; } }

  // Render charts declared as <script type="application/json" data-chart="...">.
  function renderCharts() {
    if (typeof Chart === "undefined") return;
    document.querySelectorAll("[data-chart-config]").forEach(function (holder) {
      if (holder.__rendered) return;
      holder.__rendered = true;
      var canvas = holder.querySelector("canvas");
      var cfgEl = holder.querySelector('script[type="application/json"]');
      if (!canvas || !cfgEl) return;
      var cfg = tryParse(cfgEl.textContent);
      new Chart(canvas.getContext("2d"), cfg);
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (document.getElementById("toasts")) connectStream();
    initBrowserNotifySettings();
    renderCharts();
  });
  document.body && document.body.addEventListener("htmx:afterSwap", function () {
    renderCharts();
    initBrowserNotifySettings();
  });
})();
