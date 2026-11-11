/* Backup & restore (added by the Nov 2026 health check). Self-contained: reads this tool's saved records from the
   artifact database and offers them as one JSON file; Restore writes the records in a backup file back.
   Restore overwrites records with the same name and never deletes anything. */
(function () {
  var CFG = window.__BACKUP_CFG; if (!CFG) return;
  if (!window.claude || !claude.use) return;
  var LV = (document.documentElement.lang || "").slice(0, 2) === "lv";
  var T = LV ? { b: "Dublējums", t: "Dublējums un atjaunošana", d: "Lejupielādēt dublējumu", r: "Atjaunot no faila…", c: "Aizvērt", w: "Strādāju…", ok: "Dublējums lejupielādēts: ", rec: " ieraksti", bad: "Šis nav derīgs šī rīka dublējuma fails.", other: "Šis dublējums ir no cita rīka: ", ask: "Failā ir {n} ieraksti no {d}. Atjaunošana pārraksta ierakstus ar tādu pašu nosaukumu un neko nedzēš.", go: "Atjaunot", no: "Atcelt", done: "Atjaunoti {n} ieraksti. Pārlādē lapu.", rl: "Pārlādēt", err: "Neizdevās: ", nodb: "Datubāze šajā skatā nav pieejama.", tip: "Dublējums ir viens JSON fails ar visiem šī rīka saglabātajiem datiem. Glabā to drošā vietā." }
             : { b: "Backup", t: "Backup and restore", d: "Download backup", r: "Restore from a file…", c: "Close", w: "Working…", ok: "Backup downloaded: ", rec: " records", bad: "This is not a valid backup file for this tool.", other: "This backup is from another tool: ", ask: "The file holds {n} records from {d}. Restoring overwrites records with the same name and deletes nothing.", go: "Restore", no: "Cancel", done: "Restored {n} records. Reload the page.", rl: "Reload", err: "Failed: ", nodb: "The database is not available in this view.", tip: "A backup is one JSON file with everything this tool has saved. Keep it somewhere safe." };
  var el = function (tag, css, text) { var e = document.createElement(tag); if (css) e.style.cssText = css; if (text != null) e.textContent = text; return e; };
  var BTN = "font:12px system-ui,sans-serif;padding:6px 10px;border-radius:7px;border:1px solid #5a6170;background:#2a2f3a;color:#f2f2f2;cursor:pointer;";
  var pill = el("button", "position:fixed;left:10px;bottom:10px;z-index:2147483000;opacity:.6;" + BTN + "padding:4px 9px;font-size:11px;", T.b);
  pill.setAttribute("aria-label", T.t);
  var box = el("div", "position:fixed;left:10px;bottom:10px;z-index:2147483001;width:min(330px,calc(100vw - 20px));background:#1c2029;color:#f2f2f2;border:1px solid #5a6170;border-radius:10px;padding:12px;font:13px/1.45 system-ui,sans-serif;box-shadow:0 10px 40px rgba(0,0,0,.45);display:none");
  var msg = el("div", "margin:8px 0 0;min-height:18px;color:#c9d1e0;font-size:12px"), row = el("div", "display:flex;flex-wrap:wrap;gap:6px;margin-top:8px"), extra = el("div", "display:flex;gap:6px;margin-top:8px");
  var bD = el("button", BTN + "background:#e8a33d;color:#1a1304;border-color:#e8a33d;font-weight:600", T.d), bR = el("button", BTN, T.r), bC = el("button", BTN + "margin-left:auto", T.c);
  var file = el("input", "display:none"); file.type = "file"; file.accept = ".json,application/json";
  box.append(el("b", "", T.t), el("div", "color:#9aa3b5;font-size:12px;margin-top:4px", T.tip), row, msg, extra, file); row.append(bD, bR, bC);
  var mount = function () { document.body.append(pill, box); }; if (document.body) mount(); else document.addEventListener("DOMContentLoaded", mount);
  pill.onclick = function () { box.style.display = "block"; pill.style.display = "none"; msg.textContent = ""; extra.replaceChildren(); };
  bC.onclick = function () { box.style.display = "none"; pill.style.display = ""; };
  async function ctx() { var db = await claude.use("db"); if (!db) throw new Error(T.nodb); var base = ""; if (CFG.user) { var u = await claude.use("user"), id = u && (await u.id()); if (!id) throw new Error(T.nodb); base = "data/users/" + id; } return { db: db, base: base }; }
  async function readCol(db, path) {
    var c = db.collection(path), snap;
    if (typeof c.get === "function") snap = await c.get();
    else snap = await new Promise(function (res, rej) { var done = false, un; un = c.onSnapshot(function (s) { if (done) return; done = true; res(s); try { if (typeof un === "function") un(); } catch (e) {} }, rej); });
    var out = {}; (snap.docs || []).forEach(function (d) { out[d.id] = d.data(); }); return out;
  }
  var count = function (d) { var n = Object.keys(d.docs || {}).length; for (var k in d.cols || {}) n += Object.keys(d.cols[k]).length; return n; };
  async function exportAll() {
    var x = await ctx(), data = { docs: {}, cols: {} }, i;
    for (i = 0; i < (CFG.docs || []).length; i++) { var s = await x.db.doc(CFG.docs[i]).get(); if (s && s.exists !== false && typeof s.data === "function") { var v = s.data(); if (v) data.docs[CFG.docs[i]] = v; } }
    for (i = 0; i < (CFG.cols || []).length; i++) data.cols[CFG.cols[i]] = await readCol(x.db, CFG.cols[i]);
    if (CFG.user) data.cols["@user"] = await readCol(x.db, x.base);
    if (CFG.ls) { data.ls = {}; try { for (i = 0; i < localStorage.length; i++) { var k = localStorage.key(i); if (k && k.indexOf(CFG.ls) === 0) data.ls[k] = localStorage.getItem(k); } } catch (e) {} }
    return { app: "claude-artifact-backup", tool: CFG.name, version: 1, exported: new Date().toISOString(), data: JSON.parse(JSON.stringify(data)) };
  }
  async function saveFile(name, text) {
    var blob = new Blob([text], { type: "application/json" }), dl = null;
    try { dl = await claude.use("downloads"); } catch (e) {}
    if (dl) { await dl.save({ filename: name, data: blob }); return; }
    var a = el("a"); a.href = URL.createObjectURL(blob); a.download = name; document.body.append(a); a.click(); a.remove();
  }
  bD.onclick = async function () {
    msg.textContent = T.w; extra.replaceChildren();
    try { var b = await exportAll(); await saveFile(CFG.name + "_backup_" + b.exported.slice(0, 10) + ".json", JSON.stringify(b, null, 1)); msg.textContent = T.ok + count(b.data) + T.rec; }
    catch (e) { msg.textContent = e && e.code === "declined" ? "" : T.err + (e && e.message || e); }
  };
  bR.onclick = function () { file.value = ""; file.click(); };
  file.onchange = async function () {
    var f = file.files[0]; if (!f) return; extra.replaceChildren(); var b;
    try { b = JSON.parse(await f.text()); } catch (e) { msg.textContent = T.bad; return; }
    if (!b || b.app !== "claude-artifact-backup" || !b.data) { msg.textContent = T.bad; return; }
    if (b.tool !== CFG.name) { msg.textContent = T.other + b.tool; return; }
    msg.textContent = T.ask.replace("{n}", count(b.data)).replace("{d}", String(b.exported || "").slice(0, 10));
    var go = el("button", BTN + "background:#e8a33d;color:#1a1304;border-color:#e8a33d;font-weight:600", T.go), no = el("button", BTN, T.no); extra.append(go, no);
    no.onclick = function () { extra.replaceChildren(); msg.textContent = ""; };
    go.onclick = async function () {
      extra.replaceChildren(); msg.textContent = T.w; var n = 0;
      try {
        var x = await ctx(), d = b.data, k, id;
        for (k in d.docs || {}) { if ((CFG.docs || []).indexOf(k) < 0) continue; await x.db.doc(k).set(d.docs[k]); n++; }
        for (k in d.cols || {}) { var path = k === "@user" ? x.base : k; if (k === "@user" && !CFG.user) continue; if (k !== "@user" && (CFG.cols || []).indexOf(k) < 0) continue; for (id in d.cols[k]) { await x.db.collection(path).doc(id).set(d.cols[k][id]); n++; } }
        if (d.ls && CFG.ls) { try { for (k in d.ls) if (k.indexOf(CFG.ls) === 0) localStorage.setItem(k, d.ls[k]); } catch (e) {} }
        msg.textContent = T.done.replace("{n}", n); var rl = el("button", BTN, T.rl); rl.onclick = function () { location.reload(); }; extra.append(rl);
      } catch (e) { msg.textContent = T.err + (e && e.message || e) + " (" + n + ")"; }
    };
  };
})();
