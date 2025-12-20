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
            updateButtonText();
          }
        }

        if (att.type === "video") {
          const files = att.video?.files || {};
          const url = files.mp4_720 || files.mp4_480 || files.mp4_360 || files.mp4_240;
          if (url && !seen.has(url)) {
            seen.add(url);
            collected.videos.push({ url, date: msg.date });
            updateButtonText();
          }
        }
      }
    }
  }

  function updateButtonText() {
    const btn = document.getElementById("vk-media-dump-btn");
    if (btn && !btn.disabled) {
      const total = collected.voices.length + collected.videos.length;
      if (total > 0) {
        btn.textContent = `💾 Скачать медиа (${total})`;
      } else {
        btn.textContent = "💾 Скачать медиа";
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
    updateButtonText();
  }

  // Функция для fetch с таймаутом (совместима со старыми браузерами)
  async function fetchWithTimeout(url, options = {}, timeout = 5000) {
    return Promise.race([
      fetch(url, options),
      new Promise((_, reject) =>
        setTimeout(() => reject(new Error('Timeout')), timeout)
      )
    ]);
  }

  async function send() {
    if (!collected.voices.length && !collected.videos.length) {
      alert("Медиа не найдено. Пролистай диалог вверх, чтобы загрузить старые сообщения.");
      return;
    }

    const btn = document.getElementById("vk-media-dump-btn");
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = "⏳ Готовлю архив...";

    try {
      // Проверяем доступность сервера
      const healthCheck = await fetchWithTimeout(
        "http://127.0.0.1:8765/health",
        { method: "GET" },
        3000
      ).catch(() => null);

      if (!healthCheck || !healthCheck.ok) {
        throw new Error("Server not available");
      }

      // Отправляем данные
      const res = await fetchWithTimeout(
        "http://127.0.0.1:8765/dump",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(collected)
        },
        120000 // 2 минуты на обработку
      );

      if (!res.ok) {
        const errorText = await res.text().catch(() => 'Unknown error');
        throw new Error(`Server error: ${res.status} - ${errorText}`);
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `vk_media_dump_${Date.now()}.zip`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      
      // Небольшая задержка перед очисткой URL
      setTimeout(() => URL.revokeObjectURL(url), 1000);

      // Показываем уведомление об успехе
      btn.textContent = "✅ Готово!";
      setTimeout(() => {
        btn.textContent = originalText;
        btn.disabled = false;
      }, 2000);

    } catch (error) {
      console.error("Download error:", error);
      
      let errorMsg = "Ошибка: Убедись, что программа VK Media Dump запущена и попробуй снова.";
      
      if (error.message === 'Timeout') {
        errorMsg = "Превышено время ожидания. Попробуй скачать меньше файлов за раз или проверь соединение.";
      } else if (error.message.includes('Server error')) {
        errorMsg = `Ошибка сервера: ${error.message}`;
      } else if (error.message.includes('not available')) {
        errorMsg = "Сервер недоступен. Запусти программу VK Media Dump и попробуй снова.";
      }
      
      alert(errorMsg);
      
      btn.disabled = false;
      btn.textContent = originalText;
    }
  }

  // Запускаем наблюдатель за изменениями DOM
  new MutationObserver(addButton)
    .observe(document.body, { childList: true, subtree: true });
  
  // Пытаемся добавить кнопку сразу
  addButton();
})();
