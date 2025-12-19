(function () {
  const collected = { voices: [], videos: [] };
  const seen = new Set();

  const originalFetch = window.fetch;
  window.fetch = async function (...args) {
    const response = await originalFetch.apply(this, args);

    try {
      const url = args[0]?.toString() || "";
      if (url.includes("api.vk.com/method/messages.getHistory")) {
        response.clone().json().then(processHistory).catch(() => {});
      }
    } catch (_) {}

    return response;
  };

  function processHistory(data) {
    const items = data?.response?.items;
    if (!Array.isArray(items)) return;

    for (const msg of items) {
      for (const att of msg.attachments || []) {
        if (att.type === "audio_message") {
          const url = att.audio_message?.link_ogg;
          if (url && !seen.has(url)) {
            seen.add(url);
            collected.voices.push({ url, date: msg.date });
          }
        }

        if (att.type === "video") {
          const files = att.video?.files || {};
          const url = files.mp4_720 || files.mp4_480 || files.mp4_360;
          if (url && !seen.has(url)) {
            seen.add(url);
            collected.videos.push({ url, date: msg.date });
          }
        }
      }
    }
  }

  function addButton() {
    if (document.getElementById("vk-media-dump-btn")) return;
    const header = document.querySelector(".im-page--chat-header");
    if (!header) return;

    const btn = document.createElement("button");
    btn.id = "vk-media-dump-btn";
    btn.textContent = "💾 Скачать медиа";
    btn.onclick = send;
    header.appendChild(btn);
  }

  async function send() {
    if (!collected.voices.length && !collected.videos.length) {
      alert("Медиа не найдено. Пролистай диалог вверх.");
      return;
    }

    const btn = document.getElementById("vk-media-dump-btn");
    btn.disabled = true;
    btn.textContent = "⏳ Готовлю архив...";

    try {
      const res = await fetch("http://127.0.0.1:8765/dump", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collected)
      });

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "vk_media_dump.zip";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      alert("Python-сервис не запущен");
    } finally {
      btn.disabled = false;
      btn.textContent = "💾 Скачать медиа";
    }
  }

  new MutationObserver(addButton)
    .observe(document.body, { childList: true, subtree: true });
})();