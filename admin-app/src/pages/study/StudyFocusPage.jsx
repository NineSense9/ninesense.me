import { useCallback, useEffect, useState } from "react";

import { createFocus, deleteFocus, getFocus, updateFocus } from "./studyApi.js";


const subjects = [["math", "高数"], ["408", "408"], ["english", "英语"], ["politics", "政治"]];
const subjectLabels = Object.fromEntries(subjects);


function dateText(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}


function currentMonthRange() {
  const now = new Date();
  return { from: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`, to: dateText(now) };
}


function duration(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours} 小时 ${minutes} 分钟` : `${minutes} 分钟`;
}


function localInputValue(date = new Date()) {
  const offset = date.getTimezoneOffset() * 60000;
  return new Date(date.getTime() - offset).toISOString().slice(0, 16);
}


function FocusRow({ row, onChange }) {
  const [editing, setEditing] = useState(false);
  const [minutes, setMinutes] = useState(Math.max(1, Math.round(row.effective_seconds / 60)));
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");

  async function save() {
    if (reason.trim().length < 2) {
      setMessage("请填写修正理由。");
      return;
    }
    try {
      await updateFocus(row.id, { effective_seconds: Number(minutes) * 60, reason: reason.trim() });
      setEditing(false);
      setReason("");
      await onChange();
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function remove() {
    const text = `${subjectLabels[row.subject]} · ${new Date(row.started_at).toLocaleDateString("zh-CN")} · ${duration(row.effective_seconds)}`;
    if (!window.confirm(`确认删除这条专注记录？\n${text}`)) return;
    try {
      await deleteFocus(row.id);
      await onChange();
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <article className="focus-record-row">
      <div className="focus-record-summary"><strong>{subjectLabels[row.subject]}</strong><span>{duration(row.effective_seconds)}</span><time>{new Date(row.started_at).toLocaleString("zh-CN")}</time><small>{row.source === "manual" ? "手工补录" : row.completion_kind}</small></div>
      {editing ? <div className="focus-correction"><label>有效分钟<input type="number" min="1" max="720" value={minutes} onChange={event => setMinutes(event.target.value)} /></label><label>修正理由<input maxLength="160" value={reason} onChange={event => setReason(event.target.value)} /></label><button type="button" onClick={save}>保存修正</button><button type="button" onClick={() => setEditing(false)}>取消</button></div> : <p>{row.correction_reason || "无修正说明"}</p>}
      <div className="task-editor-actions"><button type="button" onClick={() => setEditing(value => !value)}>修正</button><button type="button" className="danger-button" onClick={remove}>删除</button><output>{message}</output></div>
    </article>
  );
}


export default function StudyFocusPage() {
  const range = currentMonthRange();
  const [from, setFrom] = useState(range.from);
  const [to, setTo] = useState(range.to);
  const [subject, setSubject] = useState("");
  const [items, setItems] = useState([]);
  const [nextCursor, setNextCursor] = useState(null);
  const [message, setMessage] = useState("");
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({
    subject: "408",
    started_at: localInputValue(new Date(Date.now() - 60 * 60000)),
    ended_at: localInputValue(),
    effective_minutes: 60,
    reason: ""
  });

  const load = useCallback(async (append = false, cursor = null) => {
    const params = { from, to, limit: "50" };
    if (subject) params.subject = subject;
    if (append && cursor) params.cursor = cursor;
    try {
      const result = await getFocus(params);
      setItems(current => append ? [...current, ...result.items] : result.items);
      setNextCursor(result.next_cursor);
      setMessage("");
    } catch (error) {
      setMessage(error.message);
    }
  }, [from, subject, to]);

  useEffect(() => { load(); }, [load]);

  function setField(field, value) {
    setForm(current => ({ ...current, [field]: value }));
  }

  async function add(event) {
    event.preventDefault();
    try {
      await createFocus({
        subject: form.subject,
        started_at: new Date(form.started_at).toISOString(),
        ended_at: new Date(form.ended_at).toISOString(),
        effective_seconds: Number(form.effective_minutes) * 60,
        reason: form.reason.trim()
      });
      setAdding(false);
      setMessage("专注记录已补录。");
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <main className="admin-page study-admin-page">
      <header className="page-heading"><div><p>FOCUS HISTORY</p><h1>专注记录</h1></div><button type="button" onClick={() => setAdding(value => !value)}>{adding ? "收起" : "手工补录"}</button></header>
      <form className="study-filter-bar" onSubmit={event => { event.preventDefault(); load(); }}>
        <label>开始日期<input type="date" value={from} onChange={event => setFrom(event.target.value)} /></label>
        <label>结束日期<input type="date" value={to} onChange={event => setTo(event.target.value)} /></label>
        <label>科目<select value={subject} onChange={event => setSubject(event.target.value)}><option value="">全部</option>{subjects.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <button className="primary-button" type="submit">筛选</button>
      </form>
      <div className="study-export-links"><a href="/api/admin/study/export.json">完整 JSON</a><a href="/api/admin/study/focus.csv">专注 CSV</a><a href="/api/admin/study/tasks.csv">任务 CSV</a></div>
      {adding && <form className="study-form-panel focus-add-form" onSubmit={add}><label>科目<select value={form.subject} onChange={event => setField("subject", event.target.value)}>{subjects.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label><label>开始时间<input type="datetime-local" value={form.started_at} onChange={event => setField("started_at", event.target.value)} /></label><label>结束时间<input type="datetime-local" value={form.ended_at} onChange={event => setField("ended_at", event.target.value)} /></label><label>有效分钟<input type="number" min="1" max="720" value={form.effective_minutes} onChange={event => setField("effective_minutes", event.target.value)} /></label><label className="wide-field">补录理由<input required minLength="2" maxLength="160" value={form.reason} onChange={event => setField("reason", event.target.value)} /></label><button className="primary-button" type="submit">保存补录</button></form>}
      <output className="study-page-output" aria-live="polite">{message}</output>
      <section className="focus-record-list">
        {!items.length ? <p className="empty-copy">当前筛选下没有专注记录</p> : items.map(row => <FocusRow row={row} onChange={load} key={row.id} />)}
        {nextCursor && <button className="study-load-more" type="button" onClick={() => load(true, nextCursor)}>继续加载</button>}
      </section>
    </main>
  );
}
