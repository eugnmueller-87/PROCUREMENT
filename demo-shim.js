// =============================================================================
// demo-shim.js — the frozen backend behind the SpendLens static demo.
//
// The FastAPI backend on Railway was paused on 03.11.2026. Before that, every read
// endpoint the screens use was exported once into demo/snapshot.json (the backend
// was serving its built-in demo dataset at the time). This script loads before the
// app and answers same-origin /api/* calls from that file:
//
//   GET   the recorded response; signals are filtered by category in the browser
//   POST  upload, contract scan, signal scan, strategy, Hades investigation:
//         these need the live backend and Claude, so they answer with a demo note
// =============================================================================
(function () {
  var SNAPSHOT_DATE = "03.11.2026";
  var DEMO_NOTE = "Static demo: this action needs the live backend (paused since November 2026).";
  var realFetch = window.fetch.bind(window);
  var snapshot = null;

  function load() {
    if (!snapshot) snapshot = realFetch("demo/snapshot.json").then(function (r) { return r.json(); });
    return snapshot;
  }

  function json(body, status) {
    return new Response(JSON.stringify(body), {
      status: status || 200,
      headers: { "Content-Type": "application/json" },
    });
  }

  async function answer(url, method) {
    if (method !== "GET") return json({ status: "demo", detail: DEMO_NOTE }, 503);
    var s = await load();
    var path = url.pathname.slice(url.pathname.indexOf("/api/"));

    if (path === "/api/signals") {
      var days = url.searchParams.get("days") || "30";
      var base = s["/api/signals?days=" + days + "&limit=100"] || s["/api/signals?days=30&limit=100"];
      var category = url.searchParams.get("category");
      if (!category) return json(base);
      var signals = base.signals.filter(function (x) { return x.category === category; });
      return json(Object.assign({}, base, { signals: signals, total: signals.length }));
    }
    if (path === "/api/hades/health") return json({ status: "offline", detail: DEMO_NOTE });

    var key = path + url.search;
    if (s[key]) return json(s[key]);
    if (s[path]) return json(s[path]);
    return json({ detail: "Not part of the static demo: " + path }, 404);
  }

  window.fetch = function (input, init) {
    var url = new URL(typeof input === "string" ? input : input.url, location.href);
    var method = ((init && init.method) || "GET").toUpperCase();
    if (url.origin === location.origin && url.pathname.indexOf("/api/") !== -1) return answer(url, method);
    return realFetch(input, init);
  };

  function banner() {
    var bar = document.createElement("div");
    bar.textContent = "Static demo: data frozen on " + SNAPSHOT_DATE + ". Uploads and AI actions need the live backend; nothing leaves this page.";
    Object.assign(bar.style, {
      position: "fixed", left: "0", right: "0", bottom: "0", zIndex: "9999", padding: "6px 12px",
      font: "12px/1.4 system-ui, sans-serif", textAlign: "center", color: "#fff", background: "#1B2A4A",
    });
    document.body.appendChild(bar);
  }
  if (document.body) banner();
  else window.addEventListener("DOMContentLoaded", banner);
})();
