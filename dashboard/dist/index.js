(function () {
  var SDK = window.__HERMES_PLUGIN_SDK__;
  var React = SDK.React;
  var h = React.createElement;
  var useState = SDK.hooks.useState, useEffect = SDK.hooks.useEffect;
  var C = SDK.components;
  var fetchJSON = SDK.fetchJSON;
  var BASE = "/api/plugins/hermes-evenhub-bridge";

  function Section(title, children) {
    return h(C.Card, null,
      h(C.CardHeader, null, h(C.CardTitle, null, title)),
      h(C.CardContent, null, children));
  }

  function EvenG2Page() {
    var s = useState({ connected: 0, mic: "off", active_session: "" });
    var status = s[0], setStatus = s[1];
    var c = useState({ ws_host: "", ws_port: 8765, asr_model: "base" });
    var cfg = c[0], setCfg = c[1];

    useEffect(function () {
      function poll() {
        fetchJSON(BASE + "/status").then(setStatus).catch(function () {});
      }
      poll();
      var id = setInterval(poll, 3000);
      fetchJSON(BASE + "/config").then(setCfg).catch(function () {});
      return function () { clearInterval(id); };
    }, []);

    function save() {
      fetchJSON(BASE + "/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(cfg),
      }).catch(function () {});
    }
    function set(k) { return function (e) {
      var v = e.target.value;
      setCfg(Object.assign({}, cfg, k === "ws_port" ? { ws_port: parseInt(v, 10) || 0 } : (function () { var o = {}; o[k] = v; return o; })()));
    }; }

    return h("div", { style: { display: "flex", flexDirection: "column", gap: "12px" } },
      Section("Live status",
        h("div", { style: { display: "flex", gap: "24px", flexWrap: "wrap" } },
          h(C.Badge, null, status.connected + " connected"),
          h("span", null, "mic: " + status.mic),
          h("span", null, "session: " + (status.active_session || "—")))),
      Section("Connection",
        h("div", { style: { display: "flex", gap: "12px", alignItems: "center", flexWrap: "wrap" } },
          h(C.Label, null, "Host"),
          h(C.Input, { value: cfg.ws_host, onChange: set("ws_host") }),
          h(C.Label, null, "Port"),
          h(C.Input, { value: String(cfg.ws_port), onChange: set("ws_port") }))),
      Section("Voice / transcription",
        h("div", { style: { display: "flex", gap: "12px", alignItems: "center" } },
          h(C.Label, null, "Model"),
          h(C.Select, { value: cfg.asr_model, onChange: set("asr_model") },
            h(C.SelectOption, { value: "base" }, "base"),
            h(C.SelectOption, { value: "small" }, "small"),
            h(C.SelectOption, { value: "medium" }, "medium")))),
      h(C.Button, { onClick: save }, "Save"));
  }

  window.__HERMES_PLUGINS__.register("hermes-evenhub-bridge", EvenG2Page);
})();
