'use strict';
/* Riviera Gunship — server di gioco.
   - Serve il gioco (cartella ../public) via HTTP.
   - /ws: WebSocket con stanze (max 6 piloti), matchmaking rapido e relay degli eventi.
   - Nessuna logica di gioco sul server: i client restano sincronizzati con lo stesso
     protocollo del multiplayer co-op (presenza + eventi), il server fa da relay con
     validazione, limiti di dimensione e anti-flood. */
const http = require('http');
const fs = require('fs');
const path = require('path');
const { WebSocketServer } = require('ws');

const PORT = +process.env.PORT || 8080;
const PUBLIC = path.resolve(__dirname, process.env.PUBLIC_DIR || '../public');
const MAX_PLAYERS = 6;
const MAX_MSG = 16 * 1024;
const ORIGINS = (process.env.ALLOWED_ORIGINS || '').split(',').map(s => s.trim()).filter(Boolean);
const TOPICS = new Set(['hello', 'state', 'dmg', 'kill', 'pow', 'goal', 'win', 'next', 'cpk', 'snap']);
const MIME = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.json': 'application/json',
  '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon', '.css': 'text/css; charset=utf-8', '.txt': 'text/plain; charset=utf-8'
};

const rooms = new Map();            // code -> {code, pub, clients:Map(id->client)}
let seq = 0;
const stats = { started: Date.now(), connections: 0 };

const server = http.createServer((req, res) => {
  const url = new URL(req.url, 'http://x');
  if (url.pathname === '/health') {
    res.writeHead(200, { 'content-type': 'application/json' });
    let players = 0; for (const r of rooms.values()) players += r.clients.size;
    return res.end(JSON.stringify({ ok: true, rooms: rooms.size, players, uptime: Math.round((Date.now() - stats.started) / 1000) }));
  }
  let p = decodeURIComponent(url.pathname);
  if (p.endsWith('/')) p += 'index.html';
  const file = path.resolve(PUBLIC, '.' + p);
  if (!file.startsWith(PUBLIC + path.sep) && file !== PUBLIC) { res.writeHead(403); return res.end(); }
  fs.readFile(file, (err, buf) => {
    if (err) { res.writeHead(404, { 'content-type': 'text/plain' }); return res.end('Non trovato'); }
    const ext = path.extname(file).toLowerCase();
    const h = { 'content-type': MIME[ext] || 'application/octet-stream', 'x-content-type-options': 'nosniff' };
    h['cache-control'] = (ext === '.html' || path.basename(file) === 'sw.js') ? 'no-cache' : 'public, max-age=86400';
    res.writeHead(200, h); res.end(buf);
  });
});

const wss = new WebSocketServer({ server, path: '/ws', maxPayload: MAX_MSG, perMessageDeflate: false });

const send = (c, o) => { if (c.ws.readyState === 1) c.ws.send(JSON.stringify(o)); };
const cleanCode = s => String(s || '').toUpperCase().replace(/[^A-Z0-9_-]/g, '').slice(0, 16);

function pickRoom(code) {
  code = cleanCode(code);
  if (code) {                                   // stanza privata (su invito)
    let r = rooms.get(code);
    if (!r) { r = { code, pub: false, clients: new Map() }; rooms.set(code, r); }
    return r.clients.size >= MAX_PLAYERS ? null : r;
  }
  for (const r of rooms.values()) if (r.pub && r.clients.size < MAX_PLAYERS) return r;   // matchmaking rapido
  const c = 'PUB' + (++seq);
  const r = { code: c, pub: true, clients: new Map() };
  rooms.set(c, r); return r;
}

function leave(c) {
  const r = c.room; if (!r) return;
  r.clients.delete(c.id); c.room = null;
  for (const o of r.clients.values()) send(o, { k: 'left', id: c.id });
  if (!r.clients.size) rooms.delete(r.code);
}

wss.on('connection', (ws, req) => {
  const origin = req.headers.origin;
  if (ORIGINS.length && origin && !ORIGINS.includes(origin)) return ws.close(1008, 'origin');
  const c = { ws, id: 'p' + String(++seq).padStart(8, '0'), room: null, pres: {}, tok: 80, last: Date.now(), alive: true };
  stats.connections++;
  ws.on('pong', () => { c.alive = true; });
  ws.on('message', (raw, isBin) => {
    if (isBin) return;
    const now = Date.now();
    c.tok = Math.min(120, c.tok + (now - c.last) / 1000 * 70); c.last = now;   // ~70 msg/s sostenuti
    if (--c.tok < 0) return;
    let m; try { m = JSON.parse(raw.toString()); } catch (e) { return; }
    if (!m || typeof m !== 'object') return;
    if (m.k === 'join') {
      if (c.room) return;
      const r = pickRoom(m.room);
      if (!r) return send(c, { k: 'full' });
      c.room = r; r.clients.set(c.id, c);
      send(c, { k: 'welcome', id: c.id, room: r.code, peers: [...r.clients.values()].map(o => ({ peer: o.id, p: o.pres })) });
      for (const o of r.clients.values()) if (o !== c) send(o, { k: 'join', peer: c.id });
      return;
    }
    if (!c.room) return;
    if (m.k === 'p') {
      if (!m.d || typeof m.d !== 'object' || Array.isArray(m.d)) return;
      c.pres = m.d;
      for (const o of c.room.clients.values()) if (o !== c) send(o, { k: 'p', id: c.id, d: m.d });
    } else if (m.k === 'e') {
      if (!TOPICS.has(m.t)) return;
      for (const o of c.room.clients.values()) if (o !== c) send(o, { k: 'e', from: c.id, t: m.t, d: m.d });
    }
  });
  ws.on('close', () => leave(c));
  ws.on('error', () => leave(c));
});

setInterval(() => {                                // heartbeat: chiude le connessioni morte
  for (const ws of wss.clients) {
    if (ws._dead) { ws.terminate(); continue; }
    ws._dead = true; ws.ping();
    ws.once('pong', () => { ws._dead = false; });
  }
}, 20000);

server.listen(PORT, () => console.log('Riviera Gunship server su :' + PORT + '  (public: ' + PUBLIC + ')'));
