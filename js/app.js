const $ = (id) => document.getElementById(id);

const state = {
  history: [],
  sending: false,
};

function appendMessage(role, text, sources = []) {
  const log = $("chat-log");
  if (!log) return;

  const item = document.createElement("div");
  item.className = `message ${role}`;

  const roleEl = document.createElement("div");
  roleEl.className = "message-role";
  roleEl.textContent = role === "user" ? "You" : "Tenant Shield AI";

  const textEl = document.createElement("div");
  textEl.className = "message-text";
  textEl.textContent = text;

  item.appendChild(roleEl);
  item.appendChild(textEl);

  if (role === "assistant" && Array.isArray(sources) && sources.length) {
    const sourcesEl = document.createElement("div");
    sourcesEl.className = "message-sources";

    for (const src of sources) {
      const chip = document.createElement(src.url ? "a" : "span");
      chip.className = `source-chip ${src.type === "public" ? "public" : ""}`.trim();
      chip.textContent = src.label || "Source";
      if (src.url) {
        chip.href = src.url;
        chip.target = "_blank";
        chip.rel = "noreferrer noopener";
      }
      sourcesEl.appendChild(chip);
    }

    item.appendChild(sourcesEl);
  }

  log.appendChild(item);
  log.scrollTop = log.scrollHeight;
}

function setTyping(show) {
  const log = $("chat-log");
  if (!log) return;
  const existing = $("typing-indicator");
  if (show) {
    if (existing) return;
    const el = document.createElement("div");
    el.id = "typing-indicator";
    el.className = "typing";
    el.textContent = "Tenant Shield AI is thinking...";
    log.appendChild(el);
    log.scrollTop = log.scrollHeight;
    return;
  }
  if (existing) existing.remove();
}

function lockInput(lock) {
  const input = $("chat-input");
  const send = $("send-btn");
  if (input) input.disabled = lock;
  if (send) send.disabled = lock;
  state.sending = lock;
}

async function sendMessage() {
  if (state.sending) return;
  const input = $("chat-input");
  if (!input) return;
  const message = input.value.trim();
  if (!message) return;

  appendMessage("user", message);
  state.history.push({ role: "user", content: message });
  input.value = "";

  lockInput(true);
  setTyping(true);

  try {
    const res = await fetch("/api/rating-chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message,
        history: state.history,
      }),
    });

    let data;
    try {
      data = await res.json();
    } catch {
      const text = await res.text();
      appendMessage("assistant", text || "AI returned an unreadable response.");
      state.history.push({ role: "assistant", content: text || "AI returned an unreadable response." });
      return;
    }

    const answer = data?.answer || "No response generated.";
    const sources = Array.isArray(data?.sources) ? data.sources : [];
    appendMessage("assistant", answer, sources);
    state.history.push({ role: "assistant", content: answer });
  } catch {
    const msg = "Network error: unable to reach chat service.";
    appendMessage("assistant", msg);
    state.history.push({ role: "assistant", content: msg });
  } finally {
    setTyping(false);
    lockInput(false);
    input.focus();
  }
}

function initChat() {
  appendMessage(
    "assistant",
    "Hi, I am Tenant Shield AI. Ask me anything about your Rhode Island lease, deposits, repairs, notices, or eviction process."
  );

  $("send-btn")?.addEventListener("click", sendMessage);
  $("chat-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
}

window.addEventListener("DOMContentLoaded", initChat);