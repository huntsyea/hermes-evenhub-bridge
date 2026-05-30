(function () {
  var SDK = window.__HERMES_PLUGIN_SDK__;
  var React = SDK.React;
  var h = React.createElement;
  var useState = SDK.hooks.useState, useEffect = SDK.hooks.useEffect;
  var C = SDK.components;
  var fetchJSON = SDK.fetchJSON;
  var BASE = "/api/plugins/hermes-evenhub-bridge";

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

  function Section(title, children) {
    return h(C.Card, null,
      h(C.CardHeader, null, h(C.CardTitle, null, title)),
      h(C.CardContent, null, children));
  }

  function TranscriptionPanel() {
    var m = useState({ models: [], active: "" });
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
    if (sidecar.path) sidecarText += " (" + sidecar.path + ")";

    var sidecarIndicator = h("div", { style: { fontSize: "12px", color: sidecarReady ? "#22c55e" : "#94a3b8", marginBottom: "8px" } },
      sidecarText);

    var modelRows = models.map(function (model) {
      var isActive = model.name === activeModel;
      var isDownloading = !!downloading[model.name];
      var canDownload = (!model.installed || model.backend === "fluidaudio") && model.downloadable !== false && !isDownloading;
      return h("div", {
        key: model.name,
        style: {
          display: "flex",
          alignItems: "center",
          gap: "10px",
          padding: "6px 0",
          borderBottom: "1px solid #1e293b",
        },
      },
        h("span", { style: { fontWeight: isActive ? "600" : "400", flex: 1 } },
          (isActive ? "● " : "○ ") + model.name,
          model.lang ? h("span", { style: { color: "#94a3b8", fontSize: "12px", marginLeft: "6px" } }, "[" + model.lang + "]") : null),
        model.installed
          ? h(C.Badge, { style: { marginRight: "4px" } }, "installed")
          : null,
        !model.installed && model.downloadable === false
          ? h("span", { style: { fontSize: "12px", color: "#94a3b8" } }, "unavailable")
          : null,
        canDownload
          ? h(C.Button, {
              onClick: function () { download(model.name); },
              style: { padding: "2px 10px", fontSize: "12px" },
            }, "Download")
          : null,
        !model.installed && isDownloading
          ? h("span", { style: { fontSize: "12px", color: "#94a3b8" } }, "downloading…")
          : null,
        model.installed && !isActive
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
        models.length === 0
          ? h("span", { style: { color: "#94a3b8", fontSize: "13px" } }, "Loading models…")
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
    var platforms = (data && data.platforms) || {};
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
      setErrors(function (prev) { return Object.assign({}, prev, { config: "" }); });
      fetchJSON(BASE + "/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      }).then(function (data) {
        setCfg(data);
      }).catch(function (err) {
        setErrors(function (prev) {
          return Object.assign({}, prev, { config: "Save: " + errorMessage(err) });
        });
      });
    }
    function set(k) { return function (e) {
      var v = e.target.value;
      setCfg(Object.assign({}, cfg, k === "ws_port" ? { ws_port: parseInt(v, 10) || 0 } : (function () { var o = {}; o[k] = v; return o; })()));
    }; }

    var gatewayConnected = gateway === "connected";

    return h("div", { style: { display: "flex", flexDirection: "column", gap: "12px" } },
      Section("Live status",
        h("div", { style: { display: "flex", flexDirection: "column", gap: "8px" } },
          h("div", { style: { display: "flex", gap: "24px", flexWrap: "wrap" } },
            h(C.Badge, { style: { background: gatewayConnected ? "#166534" : "#334155" } }, "Gateway: " + gateway),
            h(C.Badge, null, "Glasses: " + status.connected + " connected"),
            h("span", null, "mic: " + status.mic),
            h("span", null, "session: " + (status.active_session || "—"))),
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
            h("code", { style: { fontSize: "13px", background: "#0f172a", padding: "3px 8px", borderRadius: "4px", color: "#e2e8f0" } }, status.connect_url || "—"),
            (status.tailscale_dns || status.tailscale_ip)
              ? h(C.Badge, { style: { background: "#1e3a8a" } }, "tailscale: " + (status.tailscale_dns || status.tailscale_ip))
              : h("span", { style: { fontSize: "12px", color: "#94a3b8" } }, "LAN only"),
            h("span", { style: { fontSize: "12px", color: "#94a3b8" } }, "(" + (status.net_mode || "both") + ")")),
          h("div", { style: { display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" } },
            h(C.Label, null, "Host"),
            h(C.Input, { value: cfg.ws_host, onChange: set("ws_host") }),
            h(C.Label, null, "Port"),
            h(C.Input, { value: String(cfg.ws_port), onChange: set("ws_port") })),
          ErrorLine(errors.config, null))),
      h(TranscriptionPanel, null),
      h(C.Button, { onClick: save }, "Save"));
  }

  window.__HERMES_PLUGINS__.register("hermes-evenhub-bridge", EvenG2Page);
})();
