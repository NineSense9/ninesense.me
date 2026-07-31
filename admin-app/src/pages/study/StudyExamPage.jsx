import { useCallback, useEffect, useState } from "react";

import { createExam, deleteExam, getExams, updateExam } from "./studyApi.js";


const kinds = [
  ["registration", "网上报名"],
  ["confirmation", "网上确认"],
  ["admission_ticket", "准考证"],
  ["exam", "初试"],
  ["score", "成绩查询"],
  ["custom", "自定义"]
];


function todayText() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}


function emptyForm() {
  return {
    kind: "registration",
    title: "",
    date_status: "estimated",
    start_date: todayText(),
    end_date: "",
    description: "",
    source_url: "",
    countdown_target: false,
    position: 10,
    active: true
  };
}


function fromEvent(event) {
  return {
    kind: event.kind,
    title: event.title,
    date_status: event.date_status,
    start_date: event.start_date,
    end_date: event.end_date || "",
    description: event.description || "",
    source_url: event.source_url || "",
    countdown_target: event.countdown_target,
    position: event.position,
    active: event.active
  };
}


function payload(form) {
  return {
    kind: form.kind,
    title: form.title.trim(),
    date_status: form.date_status,
    start_date: form.start_date,
    end_date: form.end_date || null,
    description: form.description.trim(),
    source_url: form.source_url.trim() || null,
    countdown_target: form.countdown_target,
    position: Number(form.position),
    active: form.active
  };
}


function ExamFields({ form, setForm }) {
  const setField = (field, value) => setForm(current => ({ ...current, [field]: value }));
  return (
    <div className="exam-form-grid">
      <label>节点类型<select value={form.kind} onChange={event => setField("kind", event.target.value)}>{kinds.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="wide-field">标题<input maxLength="120" value={form.title} onChange={event => setField("title", event.target.value)} /></label>
      <label>日期状态<select value={form.date_status} onChange={event => setField("date_status", event.target.value)}><option value="estimated">预计</option><option value="confirmed">已确认</option></select></label>
      <label>开始日期<input type="date" value={form.start_date} onChange={event => setField("start_date", event.target.value)} /></label>
      <label>结束日期<input type="date" value={form.end_date} onChange={event => setField("end_date", event.target.value)} /></label>
      <label>排序<input type="number" min="0" max="10000" value={form.position} onChange={event => setField("position", event.target.value)} /></label>
      <label className="checkbox-field"><input type="checkbox" checked={form.active} onChange={event => setForm(current => ({ ...current, active: event.target.checked, countdown_target: event.target.checked ? current.countdown_target : false }))} />启用</label>
      <label className="checkbox-field"><input type="checkbox" checked={form.countdown_target} disabled={!form.active} onChange={event => setField("countdown_target", event.target.checked)} />设为倒计时目标</label>
      <label className="full-field">官方来源<input type="url" maxLength="500" placeholder="https://" value={form.source_url} onChange={event => setField("source_url", event.target.value)} /></label>
      <label className="full-field">说明<textarea rows="3" maxLength="2000" value={form.description} onChange={event => setField("description", event.target.value)} /></label>
    </div>
  );
}


function ExamRow({ event, onChange }) {
  const [form, setForm] = useState(() => fromEvent(event));
  const [message, setMessage] = useState("");

  useEffect(() => setForm(fromEvent(event)), [event]);

  async function save() {
    const data = payload(form);
    if (!data.title || (data.end_date && data.end_date < data.start_date)) {
      setMessage("请检查标题和日期范围。");
      return;
    }
    try {
      await updateExam(event.id, data);
      setMessage(data.countdown_target ? "已保存，并替换原倒计时目标。" : "已保存。");
      await onChange();
    } catch (error) {
      setMessage(error.message);
    }
  }

  async function remove() {
    if (!window.confirm(`确认删除时间节点“${event.title}”？`)) return;
    try {
      await deleteExam(event.id);
      await onChange();
    } catch (error) {
      setMessage(error.message);
    }
  }

  return <article className="exam-editor-row"><ExamFields form={form} setForm={setForm} /><div className="task-editor-actions"><button type="button" onClick={save}>保存</button><button type="button" className="danger-button" onClick={remove}>删除</button><output>{message}</output></div></article>;
}


export default function StudyExamPage() {
  const [items, setItems] = useState([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(() => emptyForm());
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      setItems((await getExams()).items);
    } catch (error) {
      setMessage(error.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function add(event) {
    event.preventDefault();
    const data = payload(form);
    if (!data.title || (data.end_date && data.end_date < data.start_date)) {
      setMessage("请检查标题和日期范围。");
      return;
    }
    try {
      await createExam(data);
      setForm(emptyForm());
      setAdding(false);
      setMessage(data.countdown_target ? "节点已新增，并设为新的倒计时目标。" : "节点已新增。");
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <main className="admin-page study-admin-page">
      <header className="page-heading"><div><p>EXAM CALENDAR</p><h1>考研时间表</h1></div><button type="button" onClick={() => setAdding(value => !value)}>{adding ? "收起" : "新增节点"}</button></header>
      <p className="study-page-note">设置新的倒计时目标时，原目标会自动取消；预计日期后续可以直接改为已确认。</p>
      {adding && <form className="study-form-panel" onSubmit={add}><ExamFields form={form} setForm={setForm} /><div className="task-editor-actions"><button className="primary-button" type="submit">新增节点</button><button type="button" onClick={() => setAdding(false)}>取消</button></div></form>}
      <output className="study-page-output" aria-live="polite">{message}</output>
      <section className="exam-editor-list">
        {!items.length ? <p className="empty-copy">还没有考试时间节点</p> : items.map(event => <ExamRow event={event} onChange={load} key={event.id} />)}
      </section>
    </main>
  );
}
