import { useEffect, useState } from "react";

import { api } from "../api/client.js";


export default function DashboardPage() {
  const [summary, setSummary] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api("/api/admin/dashboard").then(setSummary).catch(value => setError(value.message));
  }, []);

  return (
    <main className="admin-page">
      <header className="page-heading">
        <div><p>OVERVIEW / NINESENSE</p><h1>总览</h1></div>
        <span>网站管理平台</span>
      </header>
      {error && <p className="page-error" role="alert">{error}</p>}
      <section className="summary-grid" aria-label="网站状态摘要">
        <article><span>待处理互动</span><strong>{summary?.pending_interactions ?? "—"}</strong></article>
        <article><span>未读通知</span><strong>{summary?.unread_notifications ?? "—"}</strong></article>
        <article><span>活动会话</span><strong>{summary?.active_sessions ?? "—"}</strong></article>
      </section>
      <section className="panel">
        <div className="panel-heading"><h2>近期安全记录</h2><span>RECENT SECURITY</span></div>
        {!summary ? <p className="empty-copy">正在读取…</p> : summary.recent_security_events.length === 0 ? (
          <p className="empty-copy">暂时没有安全记录</p>
        ) : (
          <ul className="event-list">
            {summary.recent_security_events.map((event, index) => (
              <li key={`${event.created_at}-${index}`}><strong>{event.action}</strong><span>{event.outcome}</span><time>{new Date(event.created_at).toLocaleString("zh-CN")}</time></li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
