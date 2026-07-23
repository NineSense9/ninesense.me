import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client.js";


const statusLabels = {
  pending: "待处理",
  published: "已公开",
  handled: "已处理",
  archived: "已归档",
  rejected: "已拒绝"
};


function formatDate(value) {
  return value ? new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short"
  }).format(new Date(value)) : "—";
}


export default function InboxPage() {
  const [items, setItems] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [selected, setSelected] = useState(null);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [kindFilter, setKindFilter] = useState("");
  const [search, setSearch] = useState("");
  const [reply, setReply] = useState("");
  const [contact, setContact] = useState(null);
  const [reauthVisible, setReauthVisible] = useState(false);
  const [reauthPassword, setReauthPassword] = useState("");
  const [reauthCode, setReauthCode] = useState("");
  const [message, setMessage] = useState("");

  const loadMessages = useCallback(async (append = false, cursor = null) => {
    const params = new URLSearchParams({ limit: "20" });
    if (statusFilter) params.set("status", statusFilter);
    if (kindFilter) params.set("kind", kindFilter);
    if (search.trim()) params.set("q", search.trim());
    if (append && cursor) params.set("cursor", cursor);
    try {
      const result = await api(`/api/admin/messages?${params}`);
      setItems(current => append ? [...current, ...result.items] : result.items);
      setNextCursor(result.next_cursor);
    } catch (error) {
      setMessage(error.message);
    }
  }, [kindFilter, search, statusFilter]);

  useEffect(() => {
    const timeout = window.setTimeout(() => loadMessages(false), 200);
    return () => window.clearTimeout(timeout);
  }, [loadMessages]);

  async function selectMessage(id) {
    setMessage("");
    setContact(null);
    setReauthVisible(false);
    try {
      const detail = await api(`/api/admin/messages/${id}`);
      setSelected(detail);
      setReply(detail.reply || "");
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function refreshSelected() {
    if (!selected) return;
    const detail = await api(`/api/admin/messages/${selected.id}`);
    setSelected(detail);
    setReply(detail.reply || "");
  }

  async function changeStatus(status, includedReply = null) {
    const body = { status };
    if (includedReply !== null) body.reply = includedReply;
    try {
      const detail = await api(`/api/admin/messages/${selected.id}/status`, {
        method: "PATCH",
        body: JSON.stringify(body)
      });
      setSelected(detail);
      setReply(detail.reply || "");
      setMessage("已保存。");
      await loadMessages(false);
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function publishWithReply() {
    const value = reply.trim();
    if (value.length < 2) {
      setMessage("请先填写至少 2 个字的公开回复。");
      return;
    }
    await changeStatus("published", value);
  }

  async function saveReply() {
    try {
      const detail = await api(`/api/admin/messages/${selected.id}/reply`, {
        method: "PUT",
        body: JSON.stringify({ reply: reply.trim() })
      });
      setSelected(detail);
      setMessage("回复已保存。");
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function removeReply() {
    if (!window.confirm("确认删除公开回复？")) return;
    try {
      const detail = await api(`/api/admin/messages/${selected.id}/reply`, {
        method: "DELETE"
      });
      setSelected(detail);
      setReply("");
      setMessage("回复已删除。");
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function requestContact() {
    try {
      const result = await api(`/api/admin/messages/${selected.id}/contact`, {
        method: "POST"
      });
      setContact(result.contact || "未填写");
      setReauthVisible(false);
    } catch (error) {
      if (error.status === 403) {
        setReauthVisible(true);
        setMessage("查看联系方式前需要重新验证身份。");
      } else {
        setMessage(error.message);
      }
    }
  }

  async function reauthenticateAndReveal(event) {
    event.preventDefault();
    try {
      await api("/api/admin/session/reauthenticate", {
        method: "POST",
        body: JSON.stringify({ password: reauthPassword, code: reauthCode })
      });
      setReauthPassword("");
      setReauthCode("");
      await requestContact();
      setMessage("");
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function retryNotification() {
    try {
      await api(`/api/admin/outbox/${selected.id}/retry`, { method: "POST" });
      await refreshSelected();
      setMessage("已经安排重新发送提醒。");
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function deleteMessage() {
    if (!window.confirm("彻底删除后无法恢复，确认继续？")) return;
    try {
      await api(`/api/admin/messages/${selected.id}`, { method: "DELETE" });
      setSelected(null);
      setContact(null);
      await loadMessages(false);
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <main className="admin-page inbox-page">
      <header className="page-heading"><div><p>INBOX / MODERATION</p><h1>互动中心</h1></div><span>{items.length} ITEMS</span></header>
      <section className="inbox-toolbar" aria-label="互动筛选">
        <label>状态<select value={statusFilter} onChange={event => setStatusFilter(event.target.value)}><option value="pending">待处理</option><option value="published">已公开</option><option value="handled">已处理</option><option value="archived">已归档</option><option value="rejected">已拒绝</option><option value="">全部</option></select></label>
        <label>类型<select value={kindFilter} onChange={event => setKindFilter(event.target.value)}><option value="">全部</option><option value="public">公开留言</option><option value="private">私信</option></select></label>
        <label>搜索<input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="昵称或正文" /></label>
      </section>
      <div className="inbox-workspace">
        <section className="message-list" aria-label="互动列表">
          {items.length === 0 ? <p className="empty-copy">当前筛选下没有内容</p> : items.map(item => (
            <button className={selected?.id === item.id ? "message-row active" : "message-row"} type="button" key={item.id} onClick={() => selectMessage(item.id)}>
              <span><strong>{item.nickname}</strong><small>{item.kind === "public" ? "公开" : "私信"}</small></span>
              <p>{item.content_preview}</p>
              <time>{formatDate(item.submitted_at)}</time>
            </button>
          ))}
          {nextCursor && <button className="load-more" type="button" onClick={() => loadMessages(true, nextCursor)}>继续加载</button>}
        </section>
        <section className="message-detail" aria-label="互动详情">
          {!selected ? <p className="empty-copy">从左侧选择一条内容查看详情</p> : (
            <>
              <div className="detail-heading"><div><span>{selected.kind === "public" ? "PUBLIC MESSAGE" : "PRIVATE LETTER"}</span><h2>{selected.nickname}</h2></div><strong>{statusLabels[selected.status]}</strong></div>
              <time>{formatDate(selected.submitted_at)}</time>
              <p className="message-content">{selected.content}</p>
              {selected.has_contact && (
                <section className="contact-panel">
                  <div><strong>联系方式</strong><span>仅后台可见</span></div>
                  {contact ? <p>{contact}</p> : <button type="button" onClick={requestContact}>查看联系方式</button>}
                </section>
              )}
              {reauthVisible && (
                <form className="contact-reauth" onSubmit={reauthenticateAndReveal}>
                  <h2>重新验证后查看</h2>
                  <label htmlFor="contact-password">验证密码</label>
                  <input id="contact-password" type="password" value={reauthPassword} onChange={event => setReauthPassword(event.target.value)} required />
                  <label htmlFor="contact-code">验证动态码</label>
                  <input id="contact-code" value={reauthCode} onChange={event => setReauthCode(event.target.value)} minLength="6" maxLength="32" required />
                  <button type="submit">验证并查看</button>
                </form>
              )}
              {selected.kind === "public" && (
                <section className="reply-panel">
                  <label htmlFor="public-reply">公开回复</label>
                  <textarea id="public-reply" value={reply} onChange={event => setReply(event.target.value)} maxLength="500" rows="4" />
                  {selected.status === "published" && <div><button type="button" onClick={saveReply}>保存回复</button><button type="button" onClick={removeReply}>删除回复</button></div>}
                </section>
              )}
              {selected.notification && (
                <section className="delivery-panel"><div><strong>邮件提醒</strong><span>{selected.notification.sent_at ? "已发送" : `${selected.notification.attempts} 次尝试`}</span></div>{selected.notification.last_error && <p>{selected.notification.last_error}</p>}{!selected.notification.sent_at && <button type="button" onClick={retryNotification}>重新发送提醒</button>}</section>
              )}
              <div className="moderation-actions">
                {selected.kind === "public" && selected.status === "pending" && <><button type="button" onClick={() => changeStatus("published")}>通过并公开</button><button type="button" onClick={publishWithReply}>通过并回复</button><button type="button" onClick={() => changeStatus("rejected")}>拒绝</button></>}
                {selected.kind === "public" && selected.status === "published" && <><button type="button" onClick={() => changeStatus("pending")}>撤回公开</button><button type="button" onClick={() => changeStatus("archived")}>归档</button></>}
                {selected.kind === "private" && selected.status === "pending" && <><button type="button" onClick={() => changeStatus("handled")}>标记已处理</button><button type="button" onClick={() => changeStatus("rejected")}>拒绝</button></>}
                {selected.kind === "private" && selected.status === "handled" && <button type="button" onClick={() => changeStatus("archived")}>归档</button>}
                <button className="danger" type="button" onClick={deleteMessage}>彻底删除</button>
              </div>
            </>
          )}
          <output className="detail-output" aria-live="polite">{message}</output>
        </section>
      </div>
    </main>
  );
}
