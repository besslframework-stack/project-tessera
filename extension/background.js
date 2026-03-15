// Tessera Chrome Extension — Background Service Worker

const DEFAULT_URL = "http://localhost:8394";

// Create context menu on install
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "tessera-save",
    title: "Save to Tessera",
    contexts: ["selection"],
  });
});

// Handle context menu click
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId !== "tessera-save") return;

  const text = info.selectionText;
  if (!text || text.trim().length < 5) return;

  const pageUrl = tab?.url || "";
  const pageTitle = tab?.title || "";
  const source = `web:${new URL(pageUrl).hostname}`;
  const content = `${text}\n\n— Source: ${pageTitle} (${pageUrl})`;

  try {
    const result = await saveToTessera(content, ["web-clip", source]);
    // Notify content script of success
    chrome.tabs.sendMessage(tab.id, {
      type: "tessera-saved",
      success: true,
      message: "Saved to Tessera",
    });
  } catch (err) {
    chrome.tabs.sendMessage(tab.id, {
      type: "tessera-saved",
      success: false,
      message: err.message,
    });
  }
});

// Handle messages from popup/content scripts
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "tessera-save") {
    saveToTessera(message.content, message.tags)
      .then((result) => sendResponse({ success: true, data: result }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true; // async response
  }

  if (message.type === "tessera-search") {
    searchTessera(message.query)
      .then((result) => sendResponse({ success: true, data: result }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }

  if (message.type === "tessera-health") {
    checkHealth()
      .then((result) => sendResponse({ success: true, data: result }))
      .catch((err) => sendResponse({ success: false, error: err.message }));
    return true;
  }
});

async function getConfig() {
  const result = await chrome.storage.local.get(["tesseraUrl", "tesseraApiKey"]);
  return {
    url: result.tesseraUrl || DEFAULT_URL,
    apiKey: result.tesseraApiKey || "",
  };
}

async function saveToTessera(content, tags) {
  const config = await getConfig();
  const headers = { "Content-Type": "application/json" };
  if (config.apiKey) headers["X-API-Key"] = config.apiKey;

  const resp = await fetch(`${config.url}/remember`, {
    method: "POST",
    headers,
    body: JSON.stringify({ content, tags }),
  });

  if (!resp.ok) throw new Error(`Tessera API error: ${resp.status}`);
  return resp.json();
}

async function searchTessera(query) {
  const config = await getConfig();
  const headers = { "Content-Type": "application/json" };
  if (config.apiKey) headers["X-API-Key"] = config.apiKey;

  const resp = await fetch(`${config.url}/recall`, {
    method: "POST",
    headers,
    body: JSON.stringify({ query, top_k: 5 }),
  });

  if (!resp.ok) throw new Error(`Tessera API error: ${resp.status}`);
  return resp.json();
}

async function checkHealth() {
  const config = await getConfig();
  const resp = await fetch(`${config.url}/health`);
  if (!resp.ok) throw new Error(`Tessera not reachable: ${resp.status}`);
  return resp.json();
}
