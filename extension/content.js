// Tessera Chrome Extension — Content Script
// Shows toast notifications when saving to Tessera

chrome.runtime.onMessage.addListener((message) => {
  if (message.type === "tessera-saved") {
    showToast(message.message, message.success);
  }
});

function showToast(text, success) {
  const existing = document.getElementById("tessera-toast");
  if (existing) existing.remove();

  const toast = document.createElement("div");
  toast.id = "tessera-toast";
  toast.textContent = success ? `\u2713 ${text}` : `\u2717 ${text}`;
  toast.style.cssText = `
    position: fixed;
    bottom: 24px;
    right: 24px;
    padding: 12px 20px;
    border-radius: 8px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px;
    color: #f1f5f9;
    background: ${success ? "#1e293b" : "#7f1d1d"};
    border: 1px solid ${success ? "#334155" : "#991b1b"};
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    z-index: 2147483647;
    opacity: 0;
    transform: translateY(10px);
    transition: opacity 0.3s, transform 0.3s;
  `;

  document.body.appendChild(toast);

  // Animate in
  requestAnimationFrame(() => {
    toast.style.opacity = "1";
    toast.style.transform = "translateY(0)";
  });

  // Animate out after 3s
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transform = "translateY(10px)";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
