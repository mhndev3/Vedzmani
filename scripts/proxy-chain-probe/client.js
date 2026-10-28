// One request through Nginx. usage: node client.js <http|https> <nginx-host> [Header-Name=value ...]
// Prints one JSON line: {status, echo:{peer, headers}} (what the "backend" received) or {error}.
const [, , scheme, target, ...pairs] = process.argv;
const headers = {};
for (const pair of pairs) {
  const i = pair.indexOf("=");
  headers[pair.slice(0, i)] = pair.slice(i + 1);
}
if (scheme === "https") headers["Host"] = "vedzmani.ir";

const req = require(scheme).request(
  {
    host: target,
    port: scheme === "https" ? 443 : 80,
    path: "/api/ping",
    method: "GET",
    headers,
    rejectUnauthorized: false, // self-signed probe certificate, local throwaway network only
    servername: "vedzmani.ir",
  },
  (res) => {
    let data = "";
    res.on("data", (c) => (data += c));
    res.on("end", () => {
      let echo = null;
      try { echo = JSON.parse(data); } catch (_) {}
      console.log(JSON.stringify({ status: res.statusCode, echo }));
    });
  },
);
req.on("error", (e) => console.log(JSON.stringify({ error: String(e.message) })));
req.end();
