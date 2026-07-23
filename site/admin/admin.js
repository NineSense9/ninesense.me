(() => {
  "use strict";

  const loginView = document.querySelector("#login-view");
  const loginForm = document.querySelector("#login-form");
  const loginStatus = document.querySelector("#login-status");
  const dashboard = document.querySelector("#dashboard");
  const list = document.querySelector("#message-list");
  const loadMore = document.querySelector("#admin-load-more");
  const statusFilter = document.querySelector("#status-filter");
  const kindFilter = document.querySelector("#kind-filter");
  const search = document.querySelector("#message-search");
  const detailEmpty = document.querySelector("#detail-empty");
  const detailContent = document.querySelector("#detail-content");
  const detailActions = document.querySelector("#detail-actions");
  const detailStatusMessage = document.querySelector("#detail-status-message");
  const replyEditor = document.querySelector("#reply-editor");
  const replyText = document.querySelector("#reply-text");
  const confirmDialog = document.querySelector("#confirm-dialog");

  let csrfToken = "";
  let nextCursor = null;
  let selectedMessage = null;
  let pendingConfirmation = null;
  let searchTimer = null;

  function setText(selector, value) {
    document.querySelector(selector).textContent = value ?? "—";
  }

  function formatDate(value) {
    if (!value) return "—";
    return new Intl.DateTimeFormat("zh-CN", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
  }

  async function api(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const headers = new Headers(options.headers || {});
    if (options.body) headers.set("Content-Type", "application/json");
    if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) {
      headers.set("X-CSRF-Token", csrfToken);
    }
    const response = await fetch(path, { ...options, method, headers });
    const data = response.status === 204 ? null : await response.json().catch(() => ({}));
    if (response.status === 401) {
      showLogin("登录已失效，请重新登录。");
      throw new Error("登录已失效，请重新登录。");
    }
    if (!response.ok) throw new Error(data?.detail || "操作没有完成，请稍后再试。");
    return data;
  }

  function showLogin(message = "") {
    csrfToken = "";
    selectedMessage = null;
    dashboard.hidden = true;
    loginView.hidden = false;
    loginStatus.textContent = message;
  }

  async function showDashboard(session) {
    csrfToken = session.csrf_token;
    setText("#admin-identity", session.username);
    loginView.hidden = true;
    dashboard.hidden = false;
    await loadMessages();
  }

  async function restoreSession() {
    try {
      const session = await api("/api/admin/session");
      await showDashboard(session);
    } catch (error) {
      if (!loginView.hidden) return;
      showLogin();
    }
  }

  async function handleLogin(event) {
    event.preventDefault();
    const button = loginForm.querySelector("button[type='submit']");
    button.disabled = true;
    loginStatus.textContent = "正在验证……";
    try {
      const session = await api("/api/admin/session", {
        method: "POST",
        body: JSON.stringify({
          username: loginForm.elements.username.value,
          password: loginForm.elements.password.value
        })
      });
      loginForm.elements.password.value = "";
      await showDashboard({ ...session, username: loginForm.elements.username.value });
    } catch (error) {
      loginStatus.textContent = error.message;
    } finally {
      button.disabled = false;
    }
  }

  async function logout() {
    try {
      await api("/api/admin/session", { method: "DELETE" });
    } finally {
      showLogin("已经安全退出。");
    }
  }

  function createInboxItem(message) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "inbox-item";
    button.setAttribute("role", "listitem");
    button.dataset.messageId = message.id;
    if (selectedMessage?.id === message.id) button.classList.add("active");

    const top = document.createElement("div");
    top.className = "item-top";
    const name = document.createElement("span");
    name.className = "item-name";
    name.textContent = message.nickname;
    const kind = document.createElement("span");
    kind.className = "item-kind";
    kind.textContent = message.kind === "public" ? "PUBLIC" : "PRIVATE";
    top.append(name, kind);

    const preview = document.createElement("p");
    preview.className = "item-preview";
    preview.textContent = message.content_preview;
    const meta = document.createElement("div");
    meta.className = "item-meta";
    const date = document.createElement("span");
    date.textContent = formatDate(message.submitted_at);
    const indicators = document.createElement("span");
    indicators.textContent = `${message.has_contact ? "CONTACT" : "NO CONTACT"}${message.has_reply ? " / REPLIED" : ""}`;
    meta.append(date, indicators);
    button.append(top, preview, meta);
    button.addEventListener("click", () => selectMessage(message.id));
    return button;
  }

  async function loadMessages({ append = false } = {}) {
    list.setAttribute("aria-busy", "true");
    if (!append) list.replaceChildren();
    const params = new URLSearchParams({ limit: "20" });
    if (statusFilter.value) params.set("status", statusFilter.value);
    if (kindFilter.value) params.set("kind", kindFilter.value);
    if (search.value.trim()) params.set("q", search.value.trim());
    if (append && nextCursor) params.set("cursor", nextCursor);

    try {
      const result = await api(`/api/admin/messages?${params}`);
      result.items.forEach(message => list.append(createInboxItem(message)));
      nextCursor = result.next_cursor;
      loadMore.hidden = !nextCursor;
      setText("#result-count", `${list.children.length} ITEMS`);
      if (!append && result.items.length === 0) {
        const empty = document.createElement("div");
        empty.className = "list-empty";
        empty.textContent = "当前筛选条件下没有内容";
        list.append(empty);
      }
    } catch (error) {
      const empty = document.createElement("div");
      empty.className = "list-empty";
      empty.textContent = error.message;
      list.replaceChildren(empty);
    } finally {
      list.setAttribute("aria-busy", "false");
    }
  }

  function setDetailStatus(message = "") {
    detailStatusMessage.textContent = message;
  }

  async function selectMessage(messageId) {
    setDetailStatus("正在读取……");
    try {
      selectedMessage = await api(`/api/admin/messages/${messageId}`);
      renderDetail(selectedMessage);
      document.querySelectorAll(".inbox-item").forEach(item => {
        item.classList.toggle("active", item.dataset.messageId === messageId);
      });
      setDetailStatus("");
    } catch (error) {
      setDetailStatus(error.message);
    }
  }

  function renderNotification(notification) {
    const retry = document.querySelector("#retry-notification");
    if (!notification) {
      setText("#notification-state", "NO RECORD");
      setText("#notification-detail", "没有对应的邮件提醒记录。");
      retry.hidden = true;
      return;
    }
    if (notification.sent_at) {
      setText("#notification-state", "SENT");
      setText("#notification-detail", `发送于 ${formatDate(notification.sent_at)}`);
      retry.hidden = true;
    } else if (notification.last_error) {
      setText("#notification-state", "RETRYING");
      setText("#notification-detail", `已尝试 ${notification.attempts} 次；下次计划：${formatDate(notification.next_attempt_at)}`);
      retry.hidden = false;
    } else {
      setText("#notification-state", "WAITING");
      setText("#notification-detail", `等待发送；计划时间：${formatDate(notification.next_attempt_at)}`);
      retry.hidden = true;
    }
  }

  function actionButton(label, action, { primary = false, danger = false } = {}) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    if (primary) button.classList.add("primary");
    if (danger) button.classList.add("danger");
    button.addEventListener("click", action);
    return button;
  }

  function renderActions(message) {
    detailActions.replaceChildren();
    const canComposeReply = message.kind === "public" && ["pending", "published"].includes(message.status);
    replyEditor.hidden = !canComposeReply;
    replyText.value = message.reply || "";
    document.querySelector("#save-reply").hidden = message.status !== "published";
    document.querySelector("#remove-reply").hidden = !message.reply;

    if (message.kind === "public" && message.status === "pending") {
      detailActions.append(actionButton("审核通过", () => changeStatus("published"), { primary: true }));
      detailActions.append(actionButton("通过并回复", () => publishWithReply(), { primary: true }));
      detailActions.append(actionButton("拒绝", () => confirmChange("rejected", "拒绝这条留言", "内容会保留 30 天后自动清理。"), { danger: true }));
    } else if (message.kind === "public" && message.status === "published") {
      detailActions.append(actionButton("撤回公开", () => confirmChange("pending", "撤回公开展示", "留言会立即从公开页面消失。")));
      detailActions.append(actionButton("归档", () => confirmChange("archived", "归档这条留言", "归档后不再公开展示。")));
    } else if (message.kind === "private" && message.status === "pending") {
      detailActions.append(actionButton("标记已处理", () => changeStatus("handled"), { primary: true }));
      detailActions.append(actionButton("拒绝", () => confirmChange("rejected", "拒绝这封私信", "内容会保留 30 天后自动清理。"), { danger: true }));
    } else if (message.kind === "private" && message.status === "handled") {
      detailActions.append(actionButton("归档", () => confirmChange("archived", "归档这封私信", "归档不会删除内容。"), { primary: true }));
    }
    detailActions.append(actionButton("彻底删除", () => confirmDelete(), { danger: true }));
  }

  function renderDetail(message) {
    detailEmpty.hidden = true;
    detailContent.hidden = false;
    setText("#detail-kind", message.kind === "public" ? "PUBLIC MESSAGE" : "PRIVATE LETTER");
    setText("#detail-title", message.nickname);
    setText("#detail-status", message.status.toUpperCase());
    setText("#detail-date", formatDate(message.submitted_at));
    setText("#detail-message", message.content);
    setText("#contact-value", message.contact || "未填写");
    renderNotification(message.notification);
    renderActions(message);
  }

  async function mutate(path, options) {
    setDetailStatus("正在保存……");
    try {
      selectedMessage = await api(path, options);
      renderDetail(selectedMessage);
      await loadMessages();
      setDetailStatus("已保存。");
    } catch (error) {
      setDetailStatus(error.message);
    }
  }

  function changeStatus(status, reply) {
    const body = { status };
    if (reply) body.reply = reply;
    return mutate(`/api/admin/messages/${selectedMessage.id}/status`, {
      method: "PATCH",
      body: JSON.stringify(body)
    });
  }

  function publishWithReply() {
    const reply = replyText.value.trim();
    if (reply.length < 2) {
      replyEditor.hidden = false;
      replyText.focus();
      setDetailStatus("请先填写至少 2 个字的公开回复。");
      return;
    }
    changeStatus("published", reply);
  }

  function askConfirmation(title, copy, label, action) {
    setText("#confirm-title", title);
    setText("#confirm-copy", copy);
    setText("#confirm-submit", label);
    pendingConfirmation = action;
    confirmDialog.showModal();
  }

  function confirmChange(status, title, copy) {
    askConfirmation(title, copy, "确认操作", () => changeStatus(status));
  }

  function confirmDelete() {
    askConfirmation("彻底删除这条内容", "删除后无法从后台恢复，请确认已经不再需要它。", "确认删除", async () => {
      try {
        await api(`/api/admin/messages/${selectedMessage.id}`, { method: "DELETE" });
        selectedMessage = null;
        detailContent.hidden = true;
        detailEmpty.hidden = false;
        await loadMessages();
      } catch (error) {
        setDetailStatus(error.message);
      }
    });
  }

  async function saveReply() {
    const reply = replyText.value.trim();
    if (reply.length < 2) {
      setDetailStatus("公开回复至少需要 2 个字。");
      return;
    }
    await mutate(`/api/admin/messages/${selectedMessage.id}/reply`, {
      method: "PUT",
      body: JSON.stringify({ reply })
    });
  }

  function removeReply() {
    askConfirmation("删除公开回复", "留言本身会保留，只删除站长回复。", "确认删除", () => mutate(
      `/api/admin/messages/${selectedMessage.id}/reply`, { method: "DELETE" }
    ));
  }

  async function retryNotification() {
    setDetailStatus("正在安排重试……");
    try {
      await api(`/api/admin/outbox/${selectedMessage.id}/retry`, { method: "POST" });
      await selectMessage(selectedMessage.id);
      setDetailStatus("已经安排重新发送。");
    } catch (error) {
      setDetailStatus(error.message);
    }
  }

  loginForm.addEventListener("submit", handleLogin);
  document.querySelector("#logout-button").addEventListener("click", logout);
  document.querySelector("#refresh-button").addEventListener("click", () => loadMessages());
  statusFilter.addEventListener("change", () => loadMessages());
  kindFilter.addEventListener("change", () => loadMessages());
  search.addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => loadMessages(), 300);
  });
  loadMore.addEventListener("click", () => loadMessages({ append: true }));
  document.querySelector("#save-reply").addEventListener("click", saveReply);
  document.querySelector("#remove-reply").addEventListener("click", removeReply);
  document.querySelector("#retry-notification").addEventListener("click", retryNotification);
  confirmDialog.addEventListener("close", () => {
    if (confirmDialog.returnValue === "confirm" && pendingConfirmation) pendingConfirmation();
    pendingConfirmation = null;
  });

  restoreSession();
})();
