import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client.js";


export default function NotificationsPage() {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");

  const load = useCallback(() => {
    setError("");
    return api("/api/admin/notifications?limit=50")
      .then(result => setItems(result.items))
      .catch(value => setError(value.message));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function markRead(id) {
    await api(`/api/admin/notifications/${id}/read`, { method: "PATCH" });
    await load();
  }

  async function readAll() {
    await api("/api/admin/notifications/read-all", { method: "POST" });
    await load();
  }

  return (
    <main className="admin-page">
      <header className="page-heading">
        <div><p>INBOX / SYSTEM</p><h1>通知中心</h1></div>
        <button type="button" onClick={readAll}>全部标为已读</button>
      </header>
      {error && <p className="page-error" role="alert">{error}</p>}
      <section className="panel notification-list">
        {items.length === 0 ? <p className="empty-copy">暂时没有通知</p> : items.map(item => (
          <article className={item.read_at ? "notification-item is-read" : "notification-item"} key={item.id}>
            <div><span>{item.category} / {item.severity}</span><time>{new Date(item.created_at).toLocaleString("zh-CN")}</time></div>
            <h2>{item.title}</h2>
            <p>{item.message}</p>
            {!item.read_at && <button type="button" onClick={() => markRead(item.id)}>标为已读</button>}
          </article>
        ))}
      </section>
    </main>
  );
}
