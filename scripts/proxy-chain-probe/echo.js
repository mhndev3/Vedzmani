// Stand-in for the Django backend AND the Next.js frontend: answers with the headers/peer it received, so the
// probe can feed them to the real get_client_ip(). Listens on 8000 (backend) and 3000 (frontend).
const http = require("http");

const handler = (req, res) => {
  const h = req.headers;
  const body = JSON.stringify({
    peer: (req.socket.remoteAddress || "").replace("::ffff:", ""),
    headers: {
      "x-forwarded-for": h["x-forwarded-for"] || null,
      "x-real-ip": h["x-real-ip"] || null,
      "x-forwarded-proto": h["x-forwarded-proto"] || null,
      "cf-connecting-ip": h["cf-connecting-ip"] || null,
      host: h["host"] || null,
    },
  });
  res.writeHead(200, { "content-type": "application/json" });
  res.end(body);
};

http.createServer(handler).listen(8000);
http.createServer(handler).listen(3000);
