(function () {
  var SDK = window.__HERMES_PLUGIN_SDK__;
  var React = SDK.React;
  var h = React.createElement;
  var useState = SDK.hooks.useState, useEffect = SDK.hooks.useEffect;
  var C = SDK.components;
  var fetchJSON = SDK.fetchJSON;
  var BASE = (typeof SDK.api === "string" ? SDK.api : "/api/plugins/hermes-evenhub-bridge").replace(/\/$/, "");

  function errorMessage(err) {
    if (!err) return "request failed";
    if (typeof err === "string") return err;
    if (err.detail) return err.detail;
    if (err.message) return err.message;
    return "request failed";
  }

  function ErrorLine(message, retry) {
    if (!message) return null;
    return h("div", { style: { display: "flex", alignItems: "center", gap: "8px", color: "#fca5a5", fontSize: "12px" } },
      h("span", null, message),
      retry ? h(C.Button, { onClick: retry, style: { padding: "2px 8px", fontSize: "12px" } }, "Retry") : null);
  }

  function toneColor(value) {
    if (value === "connected" || value === "on" || value === "idle") return "#166534";
    if (value === "running" || value === "ready" || value === "installed") return "#166534";
    if (value === "unknown" || value === "off" || value === "disconnected") return "#334155";
    return "#854d0e";
  }

  function Pill(label, value) {
    var text = value === undefined || value === null || value === "" ? "—" : String(value);
    return h("div", {
      style: {
        display: "flex",
        alignItems: "center",
        gap: "6px",
        minHeight: "28px",
        padding: "3px 9px",
        border: "1px solid #1f2937",
        background: "#020617",
      },
    },
      h("span", { style: { color: "#94a3b8", fontSize: "12px" } }, label),
      h("span", { style: { color: "#e5e7eb", fontSize: "13px", fontWeight: 600 } }, text));
  }

  function Field(label, child) {
    return h("label", { style: { display: "flex", flexDirection: "column", gap: "6px", flex: "1 1 240px", minWidth: 0 } },
      h("span", { style: { color: "#94a3b8", fontSize: "12px" } }, label),
      child);
  }

  function shortPath(path) {
    if (!path) return "";
    var parts = path.split("/").filter(Boolean);
    if (parts.length <= 3) return path;
    return "…/" + parts.slice(-3).join("/");
  }

  function Section(title, children) {
    return h(C.Card, null,
      h(C.CardHeader, null, h(C.CardTitle, null, title)),
      h(C.CardContent, null, children));
  }

  function TranscriptionPanel() {
    var m = useState({ active: "" });
    var asrData = m[0], setAsrData = m[1];
    var d = useState({});
    var downloading = d[0], setDownloading = d[1];
    var e = useState("");
    var error = e[0], setError = e[1];

    function loadModels() {
      setError("");
      fetchJSON(BASE + "/asr/models").then(function (data) {
        setAsrData(data);
      }).catch(function (err) {
        setError("Models: " + errorMessage(err));
      });
    }

    useEffect(function () {
      loadModels();
    }, []);

    function setActive(name) {
      fetchJSON(BASE + "/asr/set/" + encodeURIComponent(name), {
        method: "POST",
      }).then(loadModels).catch(function (err) {
        setError("Set active: " + errorMessage(err));
      });
    }

    function download(name) {
      setError("");
      setDownloading(function (prev) {
        var next = Object.assign({}, prev);
        next[name] = true;
        return next;
      });
      fetchJSON(BASE + "/asr/download/" + encodeURIComponent(name), {
        method: "POST",
      }).then(function () {
        setDownloading(function (prev) {
          var next = Object.assign({}, prev);
          delete next[name];
          return next;
        });
        loadModels();
      }).catch(function (err) {
        setDownloading(function (prev) {
          var next = Object.assign({}, prev);
          delete next[name];
          return next;
        });
        setError("Download: " + errorMessage(err));
        loadModels();
      });
    }

    var models = asrData.models || [];
    var activeModel = asrData.active || "";
    var sidecar = asrData.sidecar || {};
    var sidecarReady = !!sidecar.installed;
    var sidecarText = sidecarReady ? "sidecar: installed" : "sidecar: not installed";
    if (sidecar.path) sidecarText += " (" + shortPath(sidecar.path) + ")";

    var sidecarIndicator = h("div", { style: { fontSize: "12px", color: sidecarReady ? "#22c55e" : "#94a3b8", marginBottom: "8px" } },
      sidecarText);

    var modelRows = models.map(function (model) {
      var isActive = model.name === activeModel;
      var isDownloading = !!downloading[model.name];
      var isSidecarModel = model.backend === "fluidaudio";
      var isReady = model.installed || (isSidecarModel && model.sidecar_installed);
      var canDownload = !isReady && model.downloadable !== false && !isDownloading;
      var canSetActive = isReady && !isActive;
      return h("div", {
        key: model.name,
        style: {
          display: "flex",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "10px",
          padding: "6px 0",
          borderBottom: "1px solid #1e293b",
        },
      },
        h("div", { style: { display: "flex", flexDirection: "column", gap: "2px", flex: 1, minWidth: 0 } },
          h("span", { style: { fontWeight: isActive ? "600" : "400", overflow: "hidden", textOverflow: "ellipsis" } },
            (isActive ? "● " : "○ ") + model.name),
          h("span", { style: { color: "#94a3b8", fontSize: "12px" } },
            model.backend + (model.lang ? " · " + model.lang : ""))),
        isActive
          ? h(C.Badge, { style: { marginRight: "4px", background: "#166534" } }, "active")
          : null,
        isReady && !isActive
          ? h(C.Badge, { style: { marginRight: "4px" } }, "ready")
          : null,
        !isReady && model.downloadable === false
          ? h("span", { style: { fontSize: "12px", color: "#94a3b8" } }, "unavailable")
          : null,
        canDownload
          ? h(C.Button, {
              onClick: function () { download(model.name); },
              style: { padding: "2px 10px", fontSize: "12px" },
            }, isSidecarModel ? "Install sidecar" : "Download")
          : null,
        isDownloading
          ? h("span", { style: { fontSize: "12px", color: "#94a3b8" } }, "downloading…")
          : null,
        canSetActive
          ? h(C.Button, {
              onClick: function () { setActive(model.name); },
              style: { padding: "2px 10px", fontSize: "12px" },
            }, "Set active")
          : null);
    });

    return Section("Transcription model",
      h("div", null,
        sidecarIndicator,
        ErrorLine(error, loadModels),
        !asrData.models
          ? h("span", { style: { color: "#94a3b8", fontSize: "13px" } }, "Loading models…")
          : models.length === 0
            ? h("span", { style: { color: "#94a3b8", fontSize: "13px" } }, "No transcription models found.")
          : h("div", null, modelRows)));
  }

  function fetchGatewayStatus() {
    if (SDK.api && SDK.api.getStatus) {
      return SDK.api.getStatus().catch(function () {
        return fetchJSON("/api/status");
      });
    }
    return fetchJSON("/api/status");
  }

  function gatewayState(data) {
    var platforms = (data && (data.gateway_platforms || data.platforms)) || {};
    var g2 = platforms.even_g2 || platforms["even_g2"] || {};
    return g2.state || "unknown";
  }

  function EvenG2Page() {
    var s = useState({ connected: 0, mic: "off", active_session: "" });
    var status = s[0], setStatus = s[1];
    var g = useState("unknown");
    var gateway = g[0], setGateway = g[1];
    var c = useState({ ws_host: "", ws_port: 8765 });
    var cfg = c[0], setCfg = c[1];
    var e = useState({ status: "", config: "" });
    var errors = e[0], setErrors = e[1];
    var sv = useState("idle");
    var saveState = sv[0], setSaveState = sv[1];
    var copied = useState(false);
    var didCopy = copied[0], setDidCopy = copied[1];

    useEffect(function () {
      function poll() {
        fetchJSON(BASE + "/status").then(function (data) {
          setStatus(data);
          setErrors(function (prev) { return Object.assign({}, prev, { status: "" }); });
        }).catch(function (err) {
          setErrors(function (prev) {
            return Object.assign({}, prev, { status: "Status: " + errorMessage(err) });
          });
        });
        fetchGatewayStatus().then(function (data) {
          setGateway(gatewayState(data));
        }).catch(function (err) {
          setGateway("unknown");
          setErrors(function (prev) {
            return Object.assign({}, prev, { status: "Gateway: " + errorMessage(err) });
          });
        });
      }
      poll();
      var id = setInterval(poll, 3000);
      fetchJSON(BASE + "/config").then(function (data) {
        setCfg(data);
        setErrors(function (prev) { return Object.assign({}, prev, { config: "" }); });
      }).catch(function (err) {
        setErrors(function (prev) {
          return Object.assign({}, prev, { config: "Config: " + errorMessage(err) });
        });
      });
      return function () { clearInterval(id); };
    }, []);

    function save() {
      setSaveState("saving");
      setErrors(function (prev) { return Object.assign({}, prev, { config: "" }); });
      fetchJSON(BASE + "/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      }).then(function (data) {
        setCfg(data);
        setSaveState("saved");
        setTimeout(function () { setSaveState("idle"); }, 1600);
      }).catch(function (err) {
        setSaveState("idle");
        setErrors(function (prev) {
          return Object.assign({}, prev, { config: "Save: " + errorMessage(err) });
        });
      });
    }
    function set(k) { return function (e) {
      var v = e.target.value;
      setCfg(Object.assign({}, cfg, k === "ws_port" ? { ws_port: parseInt(v, 10) || 0 } : (function () { var o = {}; o[k] = v; return o; })()));
    }; }

    function markCopied() {
      setDidCopy(true);
      setTimeout(function () { setDidCopy(false); }, 1400);
    }

    function fallbackCopyUrl(value) {
      var textarea = document.createElement("textarea");
      textarea.value = value;
      textarea.setAttribute("readonly", "");
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      try {
        if (document.execCommand("copy")) markCopied();
      } finally {
        document.body.removeChild(textarea);
      }
    }

    function copyUrl() {
      if (!status.connect_url) return;
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(status.connect_url).then(markCopied).catch(function () {
          fallbackCopyUrl(status.connect_url);
        });
        return;
      }
      fallbackCopyUrl(status.connect_url);
    }

    var gatewayConnected = gateway === "connected";
    var saveLabel = saveState === "saving" ? "Saving…" : saveState === "saved" ? "Saved" : "Save";

    return h("div", { style: { display: "flex", flexDirection: "column", gap: "12px" } },
      Section("Live status",
        h("div", { style: { display: "flex", flexDirection: "column", gap: "8px" } },
          h("div", { style: { display: "flex", gap: "24px", flexWrap: "wrap" } },
            h(C.Badge, { style: { background: gatewayConnected ? "#166534" : "#334155" } }, "Gateway: " + gateway),
            h(C.Badge, null, "Glasses: " + status.connected + " connected"),
            h(C.Badge, { style: { background: toneColor(status.mic) } }, "Mic: " + status.mic),
            h(C.Badge, { style: { background: toneColor(status.asr_active ? "ready" : "unknown") } }, "ASR: " + (status.asr_active || "—"))),
          h("div", { style: { display: "flex", gap: "8px", flexWrap: "wrap" } },
            Pill("session", status.active_session || "—"),
            Pill("updated", status.updated_at ? new Date(status.updated_at * 1000).toLocaleTimeString() : "—")),
          ErrorLine(errors.status, function () {
            fetchJSON(BASE + "/status").then(setStatus).catch(function (err) {
              setErrors(function (prev) {
                return Object.assign({}, prev, { status: "Status: " + errorMessage(err) });
              });
            });
          }))),
      Section("Connection",
        h("div", { style: { display: "flex", flexDirection: "column", gap: "10px" } },
          h("div", { style: { display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" } },
            h(C.Label, null, "Glasses URL"),
            h("code", { style: { flex: "1 1 280px", minWidth: 0, fontSize: "13px", background: "#0f172a", padding: "3px 8px", borderRadius: "4px", color: "#e2e8f0", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "100%" } }, status.connect_url || "—"),
            status.connect_url
              ? h(C.Button, { onClick: copyUrl, style: { padding: "2px 10px", fontSize: "12px" } }, didCopy ? "Copied" : "Copy")
              : null,
            (status.tailscale_dns || status.tailscale_ip)
              ? h(C.Badge, { style: { background: "#1e3a8a" } }, "tailscale: " + (status.tailscale_dns || status.tailscale_ip))
              : h("span", { style: { fontSize: "12px", color: "#94a3b8" } }, "LAN only"),
            h("span", { style: { fontSize: "12px", color: "#94a3b8" } }, "(" + (status.net_mode || "both") + ")")),
          h("div", { style: { display: "flex", gap: "12px", alignItems: "flex-end", flexWrap: "wrap" } },
            Field("Host", h(C.Input, { value: cfg.ws_host, onChange: set("ws_host") })),
            Field("Port", h(C.Input, { value: String(cfg.ws_port), onChange: set("ws_port") }))),
          ErrorLine(errors.config, null))),
      h(TranscriptionPanel, null),
      h(C.Button, { onClick: save, disabled: saveState === "saving" }, saveLabel));
  }

  window.__HERMES_PLUGINS__.register("hermes-evenhub-bridge", EvenG2Page);
})();
