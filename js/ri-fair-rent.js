/**
 * ri-fair-rent.js — PVD Tenant Board
 * Uses Supabase for forum data when configured; falls back to localStorage.
 * Wired to app backend: /zips, /api/ai-answer, /api/board-config
 */

const $ = (id) => document.getElementById(id);

// ── SUPABASE ──────────────────────────────────────────────────────
let supabase = null;

async function initSupabase() {
  try {
    const res = await fetch("/api/board-config");
    const cfg = await res.json();
    if (cfg.supabaseUrl && cfg.supabaseAnonKey && window.supabase?.createClient) {
      supabase = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnonKey);
    }
  } catch {}
}

function getVoterId() {
  let id = localStorage.getItem("pvd-voter-id");
  if (!id) {
    id = "v_" + Math.random().toString(36).slice(2) + "_" + Date.now();
    localStorage.setItem("pvd-voter-id", id);
  }
  return id;
}

function dbToPost(row, replies = []) {
  return {
    id: row.id,
    type: row.type,
    name: row.name || "Anonymous",
    zip: row.zip || "",
    title: row.title,
    body: row.body || "",
    topic: row.topic || "",
    budget: row.budget,
    movein: row.movein,
    seeking: row.seeking,
    lifestyle: row.lifestyle || [],
    contact: row.contact || "",
    votes: row.vote_count ?? 0,
    ts: new Date(row.created_at).getTime(),
    replies: replies.map((r) => ({ text: r.text, isAI: r.is_ai, ts: new Date(r.created_at).getTime() })),
  };
}

// ── SEED DATA ────────────────────────────────────────────────────
const SEED = [
  {
    id: "s1",
    type: "roommate",
    name: "QuietGradStudent",
    zip: "02906",
    title: "Looking for a room near College Hill — $950/mo budget",
    body: "PhD student at Brown, mostly home evenings studying. Very clean, no parties. Would love a calm place within walking distance of campus.",
    budget: 950,
    movein: "2026-03",
    seeking: "Room in existing place",
    lifestyle: ["Quiet", "Early bird", "Student", "Non-smoker"],
    contact: "Email: gradstudent@example.com",
    votes: 5,
    replies: [],
    ts: Date.now() - 86400000 * 2,
  },
  {
    id: "s2",
    type: "tenant",
    name: "Anonymous",
    zip: "02906",
    title: 'Landlord kept my full $1,400 deposit for "cleaning" — is this legal?',
    body: "Moved out in November, left the place cleaner than I found it. Got a letter saying they kept everything for cleaning and repainting. No itemized list.",
    topic: "Deposits",
    votes: 18,
    ts: Date.now() - 86400000 * 10,
    replies: [
      {
        text: "Under RIGL 34-18-19, your landlord must return your deposit within 20 days of vacating with an itemized written list of deductions. Normal wear and tear — including painting — cannot be deducted. Send a certified demand letter. If they don't respond in 10 days, you can sue in small claims court for double the deposit amount plus attorney fees.",
        isAI: true,
        ts: Date.now() - 86400000 * 10 + 300000,
      },
      {
        text: "This happened to me too. Sent the demand letter citing that statute and had my money back in 5 days. They fold immediately when they realize you know the law.",
        isAI: false,
        ts: Date.now() - 86400000 * 9,
      },
    ],
  },
  {
    id: "s3",
    type: "roommate",
    name: "RemoteDevPVD",
    zip: "02903",
    title: "Co-applicant wanted for Downtown 2BR — up to $1,300/mo",
    body: "Software dev working from home. Have a small dog (15lb, very chill). Looking for someone social but fine with daytime calls. Hoping to find a place March/April.",
    budget: 1300,
    movein: "2026-03",
    seeking: "Co-applicant for new place",
    lifestyle: ["WFH", "Social", "Pet-friendly", "Non-smoker"],
    contact: "Signal: @remotedevpvd",
    votes: 7,
    replies: [],
    ts: Date.now() - 86400000 * 1,
  },
  {
    id: "s4",
    type: "tenant",
    name: "Anonymous",
    zip: "02909",
    title: "No heat for 3 days, landlord not responding — what can I do?",
    body: "Radiators stopped working Tuesday. Texted landlord twice, no answer. It's been below 30°F at night. I have a toddler.",
    topic: "Heat",
    votes: 31,
    ts: Date.now() - 86400000 * 3,
    replies: [
      {
        text: "RI law requires landlords to maintain heat capable of 68°F (6am–11pm) and 65°F at night, September through June. After 3 days with no response you have three options: (1) repair-and-deduct — hire someone, keep receipts, deduct from rent, (2) escrow your rent with the court until fixed, or (3) terminate the lease without penalty. Call Providence Code Enforcement at (401) 680-5327 and document everything with timestamped photos. With a toddler in the home this rises to an emergency — they must respond faster.",
        isAI: true,
        ts: Date.now() - 86400000 * 3 + 180000,
      },
    ],
  },
  {
    id: "s5",
    type: "roommate",
    name: "NurseNightShift",
    zip: "02912",
    title: "Seeking quiet roommate near Miriam Hospital — $1,100/mo",
    body: "RN at Miriam, work nights so I sleep days. Need someone who respects sleep schedules. Super clean, keep to myself. Open to splitting a 2BR.",
    budget: 1100,
    movein: "2026-04",
    seeking: "Either",
    lifestyle: ["Night owl", "Quiet", "Non-smoker", "No pets"],
    contact: "Text only: respond via board",
    votes: 4,
    replies: [],
    ts: Date.now() - 86400000 * 5,
  },
  {
    id: "s6",
    type: "tenant",
    name: "Anonymous",
    zip: "02912",
    title: "Landlord entering my apartment without notice — is this legal?",
    body: "Found things moved around twice this week while I was at work. Nothing in my lease about entry. What can I do?",
    topic: "Entry",
    votes: 12,
    ts: Date.now() - 86400000 * 7,
    replies: [
      {
        text: "Under RIGL 34-18-26, landlords must give at least 2 days written notice before entering, except in genuine emergencies. Entering without notice is a clear violation. Send a written letter citing this statute. If it continues, it may constitute harassment and grounds to terminate the lease without penalty. Document each incident with dates.",
        isAI: true,
        ts: Date.now() - 86400000 * 7 + 600000,
      },
    ],
  },
];

// ── STATE ────────────────────────────────────────────────────────
let currentFilter = "all";
let expandedPosts = new Set();
let selectedLS = [];

// ── STORAGE (Supabase or localStorage fallback) ───────────────────
async function loadPosts() {
  if (supabase) {
    try {
      const { data: rows, error } = await supabase.from("posts").select("*").order("created_at", { ascending: false });
      if (error) throw error;
      if (!rows?.length) return [];
      const postIds = rows.map((r) => r.id);
      const { data: replyRows } = await supabase.from("replies").select("*").in("post_id", postIds).order("created_at", { ascending: true });
      const repliesByPost = {};
      (replyRows || []).forEach((r) => {
        if (!repliesByPost[r.post_id]) repliesByPost[r.post_id] = [];
        repliesByPost[r.post_id].push(r);
      });
      return rows.map((r) => dbToPost(r, repliesByPost[r.id] || []));
    } catch {
      return loadPostsLocal();
    }
  }
  return loadPostsLocal();
}

async function loadPostsLocal() {
  try {
    const raw = localStorage.getItem("pvd-posts");
    return raw ? JSON.parse(raw) : SEED;
  } catch {
    return SEED;
  }
}

async function loadVotes() {
  if (supabase) {
    try {
      const vid = getVoterId();
      const { data: rows } = await supabase.from("votes").select("post_id, direction").eq("voter_fingerprint", vid);
      const out = {};
      (rows || []).forEach((r) => { out[r.post_id] = r.direction === 1 ? "up" : "down"; });
      return out;
    } catch {
      return loadVotesLocal();
    }
  }
  return loadVotesLocal();
}

async function loadVotesLocal() {
  try {
    const raw = localStorage.getItem("pvd-votes");
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

// ── RENDER ───────────────────────────────────────────────────────
async function render() {
  const feed = document.getElementById("feed");
  if (!feed) return;

  const posts = await loadPosts();
  const votes = await loadVotes();

  let filtered = posts;
  if (currentFilter === "roommate") filtered = posts.filter((p) => p.type === "roommate");
  else if (currentFilter === "tenant") filtered = posts.filter((p) => p.type === "tenant");
  else if (currentFilter.startsWith("0")) filtered = posts.filter((p) => p.zip === currentFilter);

  if (!filtered.length) {
    feed.innerHTML = `<div class="empty">No posts here yet — be the first!</div>`;
    return;
  }

  feed.innerHTML = filtered
    .sort((a, b) => b.ts - a.ts)
    .map((p) => postHTML(p, votes[p.id]))
    .join("");
}

function postHTML(p, userVote) {
  const isExpanded = expandedPosts.has(p.id);
  const replyCount = (p.replies || []).length;

  const metaRow =
    p.type === "roommate"
      ? `<div class="roommate-details">
        <div class="detail-item"><div class="detail-label">Budget</div><div class="detail-value">$${p.budget}/mo</div></div>
        <div class="detail-item"><div class="detail-label">Move-in</div><div class="detail-value">${p.movein || "Flexible"}</div></div>
        <div class="detail-item"><div class="detail-label">Seeking</div><div class="detail-value">${p.seeking}</div></div>
        <div class="detail-item"><div class="detail-label">Area</div><div class="detail-value">${p.zip}</div></div>
       </div>
       ${(p.lifestyle || []).length ? `<div class="tags">${p.lifestyle.map((t) => `<span class="tag">${t}</span>`).join("")}</div>` : ""}`
      : `<div class="tags">
        <span style="padding:2px 9px;border-radius:3px;font-size:10px;font-weight:600;letter-spacing:1px;background:var(--tenant-bg);color:var(--tenant);border:1px solid var(--tenant-border);">${p.topic}</span>
        ${p.zip ? `<span class="tag">${p.zip}</span>` : ""}
       </div>`;

  const repliesHTML = isExpanded
    ? `
    <div class="replies-section">
      ${(p.replies || [])
        .map(
          (r) => `
        <div class="reply-item">
          <div class="reply-indicator ${r.isAI ? "ind-ai" : "ind-community"}"></div>
          <div class="reply-content">
            <div class="reply-text">${esc(r.text)}</div>
            <div class="reply-meta">
              ${r.isAI ? '<span class="ai-label">RI LAW AI</span>' : "Community"}
              · ${timeAgo(r.ts)}
            </div>
          </div>
        </div>`
        )
        .join("")}
      ${
        p.type === "roommate"
          ? `
        <div class="reply-compose">
          <input class="reply-input" id="reply-${p.id}" placeholder="Ask a question about this listing..."/>
          <button class="reply-submit" onclick="submitReply('${p.id}')">Reply</button>
        </div>`
          : `
        <div class="reply-compose">
          <input class="reply-input" id="reply-${p.id}" placeholder="Add your answer anonymously..."/>
          <button class="reply-submit" onclick="submitReply('${p.id}')">Post</button>
          <button class="ai-answer-btn" id="ai-btn-${p.id}" onclick="getAI('${p.id}')">⚡ Ask AI</button>
        </div>`
      }
    </div>`
    : "";

  return `
  <div class="post fade-up" id="post-${p.id}">
    <div class="post-stripe ${p.type === "roommate" ? "stripe-roommate" : "stripe-tenant"}"></div>
    <div class="post-main">
      <div class="post-meta">
        <span class="post-type-badge ${p.type === "roommate" ? "badge-roommate" : "badge-tenant"}">
          ${p.type === "roommate" ? "🏠 Roommate" : "💬 Q&A"}
        </span>
        <span class="post-author">${esc(p.name)}</span>
        <span class="post-time">${timeAgo(p.ts)}</span>
      </div>
      <div class="post-title" onclick="toggleExpand('${p.id}')">${esc(p.title)}</div>
      ${p.body ? `<div class="post-body">${esc(isExpanded ? p.body : p.body.slice(0, 140) + (p.body.length > 140 ? "…" : ""))}</div>` : ""}
      ${metaRow}
      <div class="post-footer">
        <div class="vote-group">
          <button class="vote-btn ${userVote === "up" ? "voted-up" : ""}" onclick="vote('${p.id}','up')">▲</button>
          <span class="vote-count">${p.votes}</span>
          <button class="vote-btn ${userVote === "down" ? "voted-down" : ""}" onclick="vote('${p.id}','down')">▼</button>
        </div>
        <button class="reply-btn" onclick="toggleExpand('${p.id}')">
          ${isExpanded ? "Hide" : "View"} replies
        </button>
        <span class="reply-count">${replyCount} ${replyCount === 1 ? "reply" : "replies"}</span>
        ${p.type === "roommate" ? `<button class="contact-btn" onclick="showContact('${esc(p.contact || "")}','${esc(p.name)}')">Contact</button>` : ""}
      </div>
    </div>
    ${repliesHTML}
  </div>`;
}

// ── INTERACTIONS ─────────────────────────────────────────────────
function toggleExpand(id) {
  expandedPosts.has(id) ? expandedPosts.delete(id) : expandedPosts.add(id);
  render();
}

async function vote(id, dir) {
  const vid = getVoterId();
  const direction = dir === "up" ? 1 : -1;

  if (supabase) {
    try {
      const { data: existing } = await supabase.from("votes").select("direction").eq("post_id", id).eq("voter_fingerprint", vid).single();
      const prev = existing?.direction;
      if (prev === direction) {
        await supabase.from("votes").delete().eq("post_id", id).eq("voter_fingerprint", vid);
      } else {
        await supabase.from("votes").upsert({ post_id: id, voter_fingerprint: vid, direction }, { onConflict: "post_id,voter_fingerprint" });
      }
      render();
      return;
    } catch {}
  }

  const posts = await loadPostsLocal();
  const votes = await loadVotesLocal();
  const p = posts.find((x) => x.id === id);
  if (!p) return;
  const prev = votes[id];
  if (prev === dir) {
    votes[id] = null;
    p.votes += dir === "up" ? -1 : 1;
  } else {
    if (prev) p.votes += prev === "up" ? -1 : 1;
    votes[id] = dir;
    p.votes += dir === "up" ? 1 : -1;
  }
  localStorage.setItem("pvd-posts", JSON.stringify(posts));
  localStorage.setItem("pvd-votes", JSON.stringify(votes));
  render();
}

async function submitReply(id) {
  const input = document.getElementById(`reply-${id}`);
  const text = input?.value?.trim();
  if (!text) return;

  if (supabase) {
    try {
      await supabase.from("replies").insert({ post_id: id, text, is_ai: false });
      if (input) input.value = "";
      expandedPosts.add(id);
      render();
      return;
    } catch {}
  }

  const posts = await loadPostsLocal();
  const p = posts.find((x) => x.id === id);
  if (!p) return;
  p.replies = p.replies || [];
  p.replies.push({ text, isAI: false, ts: Date.now() });
  localStorage.setItem("pvd-posts", JSON.stringify(posts));
  if (input) input.value = "";
  expandedPosts.add(id);
  render();
}

async function getAI(id) {
  const btn = document.getElementById(`ai-btn-${id}`);
  if (btn) {
    btn.textContent = "⚡ Thinking...";
    btn.disabled = true;
  }
  const posts = await loadPosts();
  const p = posts.find((x) => x.id === id);
  if (!p) return;
  try {
    const res = await fetch("/api/ai-answer", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: p.title,
        body: p.body || "",
        topic: p.topic,
      }),
    });
    if (!res.ok) throw new Error("AI unavailable");
    const data = await res.json();
    const text = data.answer || "Unable to generate answer.";

    if (supabase) {
      await supabase.from("replies").insert({ post_id: id, text, is_ai: true });
    } else {
      const localPosts = await loadPostsLocal();
      const lp = localPosts.find((x) => x.id === id);
      if (lp) {
        lp.replies = lp.replies || [];
        lp.replies.push({ text, isAI: true, ts: Date.now() });
        localStorage.setItem("pvd-posts", JSON.stringify(localPosts));
      }
    }
    expandedPosts.add(id);
    render();
  } catch {
    alert("AI unavailable right now. Community answers still work!");
  }
  if (btn) {
    btn.textContent = "⚡ Ask AI";
    btn.disabled = false;
  }
}

function showContact(contact, name) {
  alert(`Contact for ${name}:\n\n${contact || "No contact info provided."}`);
}

// ── FILTERS ──────────────────────────────────────────────────────
function setFilter(f, btn) {
  currentFilter = f;
  document.querySelectorAll(".filter-btn").forEach((b) => {
    b.className = "filter-btn";
  });
  if (f === "all") btn.className = "filter-btn active-all";
  else if (f === "roommate") btn.className = "filter-btn active-roommate";
  else if (f === "tenant") btn.className = "filter-btn active-tenant";
  else btn.className = "filter-btn active-all";
  render();
}

// ── SUBMIT ROOMMATE ───────────────────────────────────────────────
async function submitRoommate() {
  const name = $("rm-name")?.value?.trim();
  const budget = parseInt($("rm-budget")?.value, 10);
  if (!name || !budget) {
    alert("Please enter a name and budget.");
    return;
  }

  const payload = {
    type: "roommate",
    name,
    zip: $("rm-zip")?.value || "",
    title: `Looking for ${($("rm-seeking")?.value || "").toLowerCase()} — $${budget}/mo budget`,
    body: $("rm-bio")?.value?.trim() || "",
    budget,
    movein: $("rm-movein")?.value || null,
    seeking: $("rm-seeking")?.value || null,
    lifestyle: [...selectedLS],
    contact: $("rm-contact")?.value?.trim() || "",
  };

  if (supabase) {
    try {
      const { data, error } = await supabase.from("posts").insert(payload).select("id").single();
      if (error) throw error;
      expandedPosts.add(data.id);
      closeModal("modal-roommate");
      ["rm-name", "rm-budget", "rm-bio", "rm-contact"].forEach((id) => { const el = $(id); if (el) el.value = ""; });
      selectedLS = [];
      document.querySelectorAll(".ls-btn").forEach((b) => b.classList.remove("on"));
      currentFilter = "all";
      render();
      return;
    } catch {}
  }

  const post = { ...payload, id: "rm-" + Date.now(), votes: 0, replies: [], ts: Date.now() };
  const posts = await loadPostsLocal();
  posts.unshift(post);
  localStorage.setItem("pvd-posts", JSON.stringify(posts));
  closeModal("modal-roommate");
  ["rm-name", "rm-budget", "rm-bio", "rm-contact"].forEach((id) => { const el = $(id); if (el) el.value = ""; });
  selectedLS = [];
  document.querySelectorAll(".ls-btn").forEach((b) => b.classList.remove("on"));
  currentFilter = "all";
  render();
}

// ── SUBMIT TENANT ─────────────────────────────────────────────────
async function submitTenant() {
  const title = $("qa-title")?.value?.trim();
  if (!title) {
    alert("Please enter a question.");
    return;
  }

  const payload = {
    type: "tenant",
    name: "Anonymous",
    zip: $("qa-zip")?.value || "",
    title,
    body: $("qa-body")?.value?.trim() || "",
    topic: $("qa-topic")?.value || "Other",
  };

  let postId;

  if (supabase) {
    try {
      const { data, error } = await supabase.from("posts").insert(payload).select("id").single();
      if (error) throw error;
      postId = data.id;
      closeModal("modal-tenant");
      ["qa-title", "qa-body"].forEach((id) => { const el = $(id); if (el) el.value = ""; });
      expandedPosts.add(postId);
      render();
      setTimeout(() => getAI(postId), 600);
      return;
    } catch {}
  }

  const post = { ...payload, id: "qa-" + Date.now(), votes: 0, replies: [], ts: Date.now() };
  const posts = await loadPostsLocal();
  posts.unshift(post);
  localStorage.setItem("pvd-posts", JSON.stringify(posts));
  closeModal("modal-tenant");
  ["qa-title", "qa-body"].forEach((id) => { const el = $(id); if (el) el.value = ""; });
  expandedPosts.add(post.id);
  render();
  setTimeout(() => getAI(post.id), 600);
}

// ── LIFESTYLE TOGGLE ──────────────────────────────────────────────
function toggleLS(btn) {
  const val = btn.dataset.val;
  btn.classList.toggle("on");
  selectedLS = btn.classList.contains("on") ? [...selectedLS, val] : selectedLS.filter((v) => v !== val);
}

// ── MODALS ────────────────────────────────────────────────────────
function openModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.add("open");
}
function closeModal(id) {
  const el = document.getElementById(id);
  if (el) el.classList.remove("open");
}

// ── HELPERS ───────────────────────────────────────────────────────
function timeAgo(ts) {
  const d = Math.floor((Date.now() - ts) / 86400000);
  const h = Math.floor((Date.now() - ts) / 3600000);
  const m = Math.floor((Date.now() - ts) / 60000);
  if (d > 0) return `${d}d ago`;
  if (h > 0) return `${h}h ago`;
  if (m > 0) return `${m}m ago`;
  return "just now";
}
function esc(s) {
  return String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

// ── ZIP POPULATION (from backend) ──────────────────────────────────
async function populateZips() {
  try {
    const res = await fetch("/zips");
    const zips = await res.json();
    const rmZip = $("rm-zip");
    const qaZip = $("qa-zip");
    const opts = zips.map(
      (z) =>
        `<option value="${z.zip}">${z.zip}${z.neighborhood ? " — " + z.neighborhood : ""}</option>`
    );
    if (rmZip) {
      const current = rmZip.value;
      rmZip.innerHTML = opts.join("");
      rmZip.value = current || (opts[0] ? zips[0].zip : "");
    }
    if (qaZip) {
      qaZip.innerHTML = '<option value="">Any</option>' + opts.join("");
    }
  } catch {}
}

// ── INIT ──────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", async () => {
  document.querySelectorAll(".overlay").forEach((o) => {
    o.addEventListener("click", (e) => {
      if (e.target === o) o.classList.remove("open");
    });
  });
  await initSupabase();
  await populateZips();
  render();
});
