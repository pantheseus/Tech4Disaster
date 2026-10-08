// Shared helpers. Same-origin by default; set window.API_BASE = "https://your-api.onrender.com" if you host the frontend separately.
const API = (window.API_BASE || "") + "/api";

async function http(path, options = {}) {
  const res = await fetch(API + path, options);
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return res.status === 204 ? null : res.json();
}
const getJSON = (p) => http(p);
const sendJSON = (p, body, method = "POST") =>
  http(p, { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const sendForm = (p, formData) => http(p, { method: "POST", body: formData });

// ALWAYS escape user-provided text before putting it into innerHTML (prevents XSS)
function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function timeAgo(iso) {
  const s = Math.floor((Date.now() - new Date(iso + (iso.endsWith("Z") ? "" : "Z")).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return Math.floor(s / 60) + " min ago";
  if (s < 86400) return Math.floor(s / 3600) + " h ago";
  return Math.floor(s / 86400) + " d ago";
}
const SEV_COLORS = { 1: "#5bd18a", 2: "#a8d85b", 3: "#ffd400", 4: "#ff8a00", 5: "#ff3b3b" };

function navbar(active) {
  const links = [
    ["index.html", "Dashboard"],
    ["controlroom.html", "Control Room"],
    ["supervisor.html", "Supervisor"],
    ["report.html", "Report Emergency"],
    ["chat.html", "Safety Assistant"]
  ];
  document.getElementById("nav").innerHTML = `
  <nav class="navbar navbar-expand-md navbar-dark">
    <div class="container-fluid px-3">
      <a class="navbar-brand" href="index.html">TECH<span>4</span>DISASTER</a>
      <button class="navbar-toggler" data-bs-toggle="collapse" data-bs-target="#nv"><span class="navbar-toggler-icon"></span></button>
      <div class="collapse navbar-collapse" id="nv"><ul class="navbar-nav ms-auto">
        ${links.map(([h, t]) => `<li class="nav-item"><a class="nav-link ${h === active ? "active" : ""}" href="${h}">${t}</a></li>`).join("")}
      </ul></div>
    </div>
  </nav>`;
}
