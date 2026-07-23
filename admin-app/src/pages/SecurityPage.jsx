import { useCallback, useEffect, useState } from "react";

import { api } from "../api/client.js";


export default function SecurityPage() {
  const [sessions, setSessions] = useState([]);
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [status, setStatus] = useState("");
  const [recoveryCodes, setRecoveryCodes] = useState(null);

  const loadSessions = useCallback(() => api("/api/admin/sessions").then(result => setSessions(result.items)), []);
  useEffect(() => { loadSessions().catch(error => setStatus(error.message)); }, [loadSessions]);

  async function reauthenticate(event) {
    event.preventDefault();
    setStatus("");
    try {
      await api("/api/admin/session/reauthenticate", {
        method: "POST",
        body: JSON.stringify({ password, code })
      });
      setPassword("");
      setCode("");
      setStatus("身份验证已更新，五分钟内可以执行敏感操作。");
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function revoke(publicId) {
    if (!window.confirm("确认撤销这个会话？")) return;
    await api(`/api/admin/sessions/${publicId}`, { method: "DELETE" });
    await loadSessions();
  }

  async function regenerate() {
    try {
      const result = await api("/api/admin/mfa/recovery-codes", { method: "POST" });
      setRecoveryCodes(result.recovery_codes);
      setStatus("新的恢复码已经生成，旧恢复码全部失效。");
    } catch (error) {
      setStatus(error.message);
    }
  }

  async function disableMfa() {
    if (!window.confirm("关闭两步验证并撤销其他会话？")) return;
    try {
      await api("/api/admin/mfa", { method: "DELETE" });
      setStatus("两步验证已关闭；下次密码登录时必须重新设置。");
      await loadSessions();
    } catch (error) {
      setStatus(error.message);
    }
  }

  return (
    <main className="admin-page">
      <header className="page-heading"><div><p>ACCOUNT / SECURITY</p><h1>设置与安全</h1></div></header>
      <div className="security-grid">
        <section className="panel">
          <div className="panel-heading"><h2>登录会话</h2><span>{sessions.length} DEVICES</span></div>
          <div className="session-list">
            {sessions.map(item => (
              <article key={item.public_id}>
                <div><strong>{item.client_label}</strong>{item.current && <span>当前会话</span>}</div>
                <p>最近使用：{new Date(item.last_seen_at).toLocaleString("zh-CN")}</p>
                {!item.current && <button type="button" onClick={() => revoke(item.public_id)}>撤销</button>}
              </article>
            ))}
          </div>
        </section>
        <section className="panel">
          <div className="panel-heading"><h2>敏感操作验证</h2><span>VALID FOR 5 MIN</span></div>
          <form className="reauth-form" onSubmit={reauthenticate}>
            <label htmlFor="reauth-password">密码</label>
            <input id="reauth-password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required />
            <label htmlFor="reauth-code">动态验证码或恢复码</label>
            <input id="reauth-code" value={code} onChange={event => setCode(event.target.value)} minLength="6" maxLength="32" required />
            <button type="submit">重新验证身份</button>
          </form>
          <div className="security-actions">
            <button type="button" onClick={regenerate}>生成新的恢复码</button>
            <button className="danger" type="button" onClick={disableMfa}>关闭两步验证</button>
          </div>
          <output aria-live="polite">{status}</output>
        </section>
      </div>
      {recoveryCodes && (
        <section className="panel recovery-inline">
          <div className="panel-heading"><h2>新的恢复码</h2><button type="button" onClick={() => setRecoveryCodes(null)}>我已保存</button></div>
          <div className="recovery-grid">{recoveryCodes.map(value => <code key={value}>{value}</code>)}</div>
        </section>
      )}
    </main>
  );
}
