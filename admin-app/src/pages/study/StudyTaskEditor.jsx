import { useEffect, useState } from "react";

import { createTask, deleteTask, updateTask } from "./studyApi.js";


const subjects = [
  ["math", "高数"],
  ["408", "408"],
  ["english", "英语"],
  ["politics", "政治"]
];

const statuses = [
  ["planned", "待开始"],
  ["in_progress", "进行中"],
  ["completed", "已完成"],
  ["incomplete", "未完成"],
  ["cancelled", "已取消"]
];


function initialTask(task) {
  return {
    kind: task.kind,
    subject: task.subject || "408",
    start_time: task.start_time,
    end_time: task.end_time,
    title: task.title,
    description: task.description || "",
    status: task.status,
    position: task.position
  };
}


function taskPayload(form) {
  return {
    kind: form.kind,
    subject: form.kind === "rest" ? null : form.subject,
    start_time: form.start_time,
    end_time: form.end_time,
    title: form.title.trim(),
    description: form.description.trim(),
    status: form.status,
    position: Number(form.position)
  };
}


function TaskRow({ task, onChange }) {
  const [form, setForm] = useState(() => initialTask(task));
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => setForm(initialTask(task)), [task]);

  function setField(field, value) {
    setForm(current => ({ ...current, [field]: value }));
  }

  async function save() {
    const next = taskPayload(form);
    if (!next.title || next.end_time <= next.start_time) {
      setMessage("请检查标题和起止时间。");
      return;
    }
    const previous = taskPayload(initialTask(task));
    const changed = Object.fromEntries(Object.entries(next).filter(([key, value]) => value !== previous[key]));
    if (!Object.keys(changed).length) {
      setMessage("没有需要保存的修改。");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await updateTask(task.id, changed);
      setMessage("已保存。");
      await onChange();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`确认删除任务“${task.title}”？`)) return;
    setBusy(true);
    try {
      await deleteTask(task.id);
      await onChange();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="study-task-editor-row">
      <div className="task-editor-grid">
        <label>类型<select value={form.kind} onChange={event => setField("kind", event.target.value)}><option value="study">学习</option><option value="rest">休息</option></select></label>
        {form.kind === "study" && <label>科目<select value={form.subject} onChange={event => setField("subject", event.target.value)}>{subjects.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>}
        <label>开始<input type="time" value={form.start_time} onChange={event => setField("start_time", event.target.value)} /></label>
        <label>结束<input type="time" value={form.end_time} onChange={event => setField("end_time", event.target.value)} /></label>
        <label className="task-title-field">标题<input value={form.title} maxLength="120" onChange={event => setField("title", event.target.value)} /></label>
        <label>状态<select value={form.status} onChange={event => setField("status", event.target.value)}>{statuses.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <label>排序<input type="number" min="0" max="10000" value={form.position} onChange={event => setField("position", event.target.value)} /></label>
        <label className="task-description-field">具体内容<textarea rows="2" maxLength="2000" value={form.description} onChange={event => setField("description", event.target.value)} /></label>
      </div>
      <div className="task-editor-actions">
        <button type="button" onClick={save} disabled={busy}>保存修改</button>
        <button type="button" className="danger-button" onClick={remove} disabled={busy}>删除</button>
        <output aria-live="polite">{message}</output>
      </div>
    </article>
  );
}


function NewTask({ date, onChange, onClose }) {
  const [form, setForm] = useState({
    kind: "study",
    subject: "408",
    start_time: "08:30",
    end_time: "10:00",
    title: "",
    description: "",
    status: "planned",
    position: 10
  });
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  function setField(field, value) {
    setForm(current => ({ ...current, [field]: value }));
  }

  async function submit(event) {
    event.preventDefault();
    const payload = taskPayload(form);
    if (!payload.title || payload.end_time <= payload.start_time) {
      setMessage("请填写标题，并确保结束时间晚于开始时间。");
      return;
    }
    setBusy(true);
    setMessage("");
    try {
      await createTask(date, payload);
      await onChange();
      onClose();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="new-study-task" onSubmit={submit}>
      <div className="task-editor-grid">
        <label>类型<select value={form.kind} onChange={event => setField("kind", event.target.value)}><option value="study">学习</option><option value="rest">休息</option></select></label>
        {form.kind === "study" && <label>科目<select value={form.subject} onChange={event => setField("subject", event.target.value)}>{subjects.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>}
        <label>开始<input type="time" value={form.start_time} onChange={event => setField("start_time", event.target.value)} /></label>
        <label>结束<input type="time" value={form.end_time} onChange={event => setField("end_time", event.target.value)} /></label>
        <label className="task-title-field">标题<input required maxLength="120" value={form.title} onChange={event => setField("title", event.target.value)} /></label>
        <label>状态<select value={form.status} onChange={event => setField("status", event.target.value)}>{statuses.map(([value, label]) => <option value={value} key={value}>{label}</option>)}</select></label>
        <label>排序<input type="number" min="0" max="10000" value={form.position} onChange={event => setField("position", event.target.value)} /></label>
        <label className="task-description-field">具体内容<textarea rows="2" maxLength="2000" value={form.description} onChange={event => setField("description", event.target.value)} /></label>
      </div>
      <div className="task-editor-actions"><button className="primary-button" type="submit" disabled={busy}>新增任务</button><button type="button" onClick={onClose}>取消</button><output aria-live="polite">{message}</output></div>
    </form>
  );
}


export default function StudyTaskEditor({ day, date, onChange }) {
  const [adding, setAdding] = useState(false);
  return (
    <section className="study-task-editor" aria-labelledby="task-editor-title">
      <div className="study-panel-heading">
        <div><p>DAILY PLAN</p><h2 id="task-editor-title">今日任务</h2></div>
        <button type="button" onClick={() => setAdding(value => !value)}>{adding ? "收起" : "新增任务"}</button>
      </div>
      {adding && <NewTask date={date} onChange={onChange} onClose={() => setAdding(false)} />}
      <div className="study-task-editor-list">
        {!day?.tasks?.length ? <p className="empty-copy">今天还没有任务</p> : day.tasks.map(task => <TaskRow key={task.id} task={task} onChange={onChange} />)}
      </div>
    </section>
  );
}
