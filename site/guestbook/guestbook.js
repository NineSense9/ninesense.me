(() => {
  "use strict";

  const form = document.querySelector("#guestbook-form");
  const content = document.querySelector("#content");
  const counter = document.querySelector("#content-counter");
  const statusRegion = document.querySelector("#form-status");
  const privacyNote = document.querySelector("#privacy-note");
  const feed = document.querySelector("#message-feed");
  const loadMore = document.querySelector("#load-more");
  const submitButton = form.querySelector("button[type='submit']");
  const fields = ["nickname", "contact", "content"];

  let formStartedAt = Date.now() / 1000;
  let idempotencyKey = createIdempotencyKey();
  let nextCursor = null;
  let feedController = null;
  let feedLoading = false;

  function initBlurTitle() {
    const title = document.querySelector("[data-blur-title]");
    if (!title) return;

    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reducedMotion) return;

    let wordIndex = 0;
    title.querySelectorAll("[data-blur-text]").forEach(line => {
      const text = line.dataset.blurText || line.textContent || "";
      const words = text.trim().split(/\s+/).filter(Boolean);
      const fragment = document.createDocumentFragment();

      words.forEach(word => {
        const item = document.createElement("span");
        item.className = "blur-word";
        item.textContent = word;
        item.setAttribute("aria-hidden", "true");
        item.style.setProperty("--blur-index", String(wordIndex));
        wordIndex += 1;
        fragment.append(item);
      });
      line.replaceChildren(fragment);
    });

    const words = Array.from(title.querySelectorAll(".blur-word"));
    const lastWord = words.at(-1);
    if (!lastWord) return;

    title.classList.add("is-prepared");
    lastWord.addEventListener("animationend", event => {
      if (event.animationName !== "blur-word-in") return;
      title.classList.remove("is-active");
      title.classList.add("is-settled");
    }, { once: true });

    const play = () => title.classList.add("is-active");
    if ("IntersectionObserver" in window) {
      const observer = new IntersectionObserver(entries => {
        if (!entries.some(entry => entry.isIntersecting)) return;
        play();
        observer.disconnect();
      }, { threshold: 0.1 });
      observer.observe(title);
    } else {
      play();
    }
  }

  function createIdempotencyKey() {
    if (crypto.randomUUID) return crypto.randomUUID();
    const bytes = crypto.getRandomValues(new Uint8Array(16));
    return Array.from(bytes, value => value.toString(16).padStart(2, "0")).join("");
  }

  function selectedKind() {
    return form.elements.kind.value;
  }

  function updatePrivacyNote() {
    privacyNote.textContent = selectedKind() === "private"
      ? "这条内容只会出现在我的管理后台，不会被公开。联系方式也只对我可见。"
      : "公开留言会在审核通过后展示，联系方式不会公开。";
  }

  function updateCounter() {
    counter.textContent = String(Array.from(content.value).length);
  }

  function setStatus(message, type = "") {
    statusRegion.textContent = message;
    statusRegion.className = `form-status ${type}`.trim();
  }

  function clearErrors() {
    fields.forEach(name => {
      const input = form.elements[name];
      input.removeAttribute("aria-invalid");
      document.querySelector(`#${name}-error`).textContent = "";
    });
  }

  function setFieldError(name, message) {
    if (!fields.includes(name)) return;
    const input = form.elements[name];
    input.setAttribute("aria-invalid", "true");
    document.querySelector(`#${name}-error`).textContent = message;
  }

  function validateForm() {
    clearErrors();
    let valid = true;
    const nicknameLength = Array.from(form.elements.nickname.value.trim()).length;
    const contentLength = Array.from(content.value.trim()).length;
    if (nicknameLength < 2 || nicknameLength > 24) {
      setFieldError("nickname", "称呼请填写 2—24 个字符。");
      valid = false;
    }
    if (contentLength < 2 || contentLength > 500) {
      setFieldError("content", "内容请填写 2—500 个字符。");
      valid = false;
    }
    return valid;
  }

  async function submitMessage(event) {
    event.preventDefault();
    if (!validateForm()) {
      setStatus("还有内容需要调整，请看看标出的字段。", "error");
      return;
    }

    submitButton.disabled = true;
    setStatus("正在发送……");
    const payload = {
      kind: selectedKind(),
      nickname: form.elements.nickname.value,
      contact: form.elements.contact.value,
      content: content.value,
      idempotency_key: idempotencyKey,
      website: form.elements.website.value,
      form_started_at: formStartedAt
    };

    try {
      const response = await fetch("/api/guestbook/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const result = await response.json().catch(() => ({}));
      if (response.status === 422 && Array.isArray(result.detail)) {
        result.detail.forEach(issue => {
          const name = issue.loc?.at(-1);
          setFieldError(name, "这里的内容格式不太对，请检查一下。");
        });
        throw new Error("还有内容需要调整，请看看标出的字段。");
      }
      if (!response.ok) throw new Error(result.detail || "暂时没有发送成功，请稍后再试。");

      const wasPrivate = payload.kind === "private";
      content.value = "";
      updateCounter();
      idempotencyKey = createIdempotencyKey();
      formStartedAt = Date.now() / 1000;
      setStatus(
        wasPrivate
          ? "已经收到，这条内容只会在后台显示。"
          : "已经收到，公开留言会在审核后出现。",
        "success"
      );
    } catch (error) {
      setStatus(error.message || "网络似乎断开了，填写的内容还在，可以稍后重试。", "error");
    } finally {
      submitButton.disabled = false;
    }
  }

  function createTextElement(tag, className, value) {
    const element = document.createElement(tag);
    element.className = className;
    element.textContent = value;
    return element;
  }

  function renderMessage(message) {
    const article = document.createElement("article");
    article.className = "message-card";
    article.setAttribute("role", "listitem");

    const avatar = createTextElement("div", "message-avatar", message.nickname.slice(0, 1));
    avatar.setAttribute("aria-hidden", "true");
    const body = document.createElement("div");
    const meta = document.createElement("div");
    meta.className = "message-meta";
    meta.append(
      createTextElement("span", "message-name", message.nickname),
      createTextElement("time", "message-date", message.date.replaceAll("-", "."))
    );
    body.append(meta, createTextElement("p", "message-content", message.content));

    if (message.reply) {
      const reply = document.createElement("div");
      reply.className = "owner-reply";
      const replyMeta = document.createElement("div");
      replyMeta.className = "reply-meta";
      replyMeta.append(
        createTextElement("span", "", "NINESENSE / REPLY"),
        createTextElement("time", "", (message.reply_date || "").replaceAll("-", "."))
      );
      reply.append(replyMeta, createTextElement("p", "reply-content", message.reply));
      body.append(reply);
    }
    article.append(avatar, body);
    return article;
  }

  function renderEmptyState(message = "还没有公开留言") {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    empty.append(
      createTextElement("strong", "", message),
      createTextElement("span", "", "如果愿意，你可以成为第一个在这里留下文字的人。")
    );
    feed.replaceChildren(empty);
  }

  async function loadMessages({ append = false } = {}) {
    if (feedLoading) return;
    feedLoading = true;
    loadMore.disabled = true;
    if (!append) {
      feedController?.abort();
      feedController = new AbortController();
      feed.setAttribute("aria-busy", "true");
    }

    try {
      const query = new URLSearchParams({ limit: "10" });
      if (append && nextCursor) query.set("cursor", nextCursor);
      const response = await fetch(`/api/guestbook/messages?${query}`, {
        signal: feedController?.signal
      });
      if (!response.ok) throw new Error("留言暂时没有加载出来。");
      const result = await response.json();
      if (!append) feed.replaceChildren();
      result.items.forEach(message => feed.append(renderMessage(message)));
      nextCursor = result.next_cursor;
      loadMore.hidden = !nextCursor;
      if (!append && result.items.length === 0) renderEmptyState();
    } catch (error) {
      if (error.name !== "AbortError") renderEmptyState("留言暂时没有加载出来");
    } finally {
      feedLoading = false;
      loadMore.disabled = false;
      feed.setAttribute("aria-busy", "false");
    }
  }

  form.addEventListener("submit", submitMessage);
  form.addEventListener("input", event => {
    if (event.target === content) updateCounter();
    if (fields.includes(event.target.name)) {
      event.target.removeAttribute("aria-invalid");
      document.querySelector(`#${event.target.name}-error`).textContent = "";
    }
  });
  form.elements.kind.forEach(input => input.addEventListener("change", updatePrivacyNote));
  loadMore.addEventListener("click", () => loadMessages({ append: true }));

  initBlurTitle();
  updateCounter();
  updatePrivacyNote();
  loadMessages();
})();
