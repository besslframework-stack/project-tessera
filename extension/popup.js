// Tessera Chrome Extension — Popup Script

document.addEventListener("DOMContentLoaded", async () => {
  // Load settings
  const stored = await chrome.storage.local.get(["tesseraUrl", "tesseraApiKey"]);
  const urlInput = document.getElementById("url");
  const keyInput = document.getElementById("apikey");
  urlInput.value = stored.tesseraUrl || "http://localhost:8394";
  keyInput.value = stored.tesseraApiKey || "";

  // Check health
  checkHealth();

  // Save button
  document.getElementById("save-btn").addEventListener("click", saveMemory);
  document.getElementById("search-btn").addEventListener("click", searchMemories);
  document.getElementById("save-settings").addEventListener("click", saveSettings);

  // Enter key shortcuts
  document.getElementById("content").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) saveMemory();
  });
  document.getElementById("query").addEventListener("keydown", (e) => {
    if (e.key === "Enter") searchMemories();
  });
});

async function checkHealth() {
  const dot = document.getElementById("status-dot");
  const text = document.getElementById("status-text");

  try {
    const resp = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "tessera-health" }, (r) => {
        if (r && r.success) resolve(r.data);
        else reject(new Error(r?.error || "Not reachable"));
      });
    });

    dot.classList.add("ok");
    text.textContent = "Connected to Tessera";
  } catch (err) {
    dot.classList.add("err");
    text.textContent = "Not connected — start Tessera API";
  }
}

async function saveMemory() {
  const btn = document.getElementById("save-btn");
  const msg = document.getElementById("msg");
  const content = document.getElementById("content").value.trim();
  const tagsStr = document.getElementById("tags").value.trim();

  if (!content) return;

  const tags = tagsStr ? tagsStr.split(",").map((t) => t.trim()).filter(Boolean) : [];

  btn.disabled = true;
  btn.textContent = "Saving...";

  try {
    const result = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage(
        { type: "tessera-save", content, tags },
        (r) => {
          if (r && r.success) resolve(r.data);
          else reject(new Error(r?.error || "Save failed"));
        }
      );
    });

    msg.className = "msg ok";
    msg.textContent = "Saved to Tessera!";
    document.getElementById("content").value = "";
    document.getElementById("tags").value = "";
  } catch (err) {
    msg.className = "msg err";
    msg.textContent = err.message;
  }

  btn.disabled = false;
  btn.textContent = "Save to Tessera";
}

async function searchMemories() {
  const query = document.getElementById("query").value.trim();
  const results = document.getElementById("results");
  if (!query) return;

  results.textContent = "Searching...";

  try {
    const resp = await new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ type: "tessera-search", query }, (r) => {
        if (r && r.success) resolve(r.data);
        else reject(new Error(r?.error || "Search failed"));
      });
    });

    const data = resp.data || "";
    if (typeof data === "string" && data.includes("don't have any memories")) {
      results.textContent = "No results found.";
    } else {
      results.innerHTML = escapeHtml(typeof data === "string" ? data : JSON.stringify(data))
        .replace(/\n/g, "<br>")
        .substring(0, 1000);
    }
  } catch (err) {
    results.textContent = `Error: ${err.message}`;
  }
}

async function saveSettings() {
  const url = document.getElementById("url").value.trim();
  const apiKey = document.getElementById("apikey").value.trim();

  await chrome.storage.local.set({
    tesseraUrl: url || "http://localhost:8394",
    tesseraApiKey: apiKey,
  });

  checkHealth();
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
