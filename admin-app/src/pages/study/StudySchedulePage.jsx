import { useCallback, useEffect, useState } from "react";

import { createSchedule, deleteSchedule, getSchedule, updateSchedule } from "./studyApi.js";


const weekdays = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
const subjects = [["math", "高数"], ["408", "408"], ["english", "英语"], ["politics", "政治"]];


function todayText() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-${String(now.getDate()).padStart(2, "0")}`;
}


function emptyForm(weekday = 0) {
  return {
    weekday,
    kind: "study",
    subject: "408",
    start_time: "08:30",
    end_time: "10:00",
    title: "",
    description: "",
    effective_from: todayText(),
    effective_until: "",
    position: 10,
    active: true
  };
}


function fromEntry(entry) {
  return {
    weekday: entry.weekday,
    kind: entry.kind,
    subject: entry.subject || "408",
    start_time: entry.start_time,
    end_time: entry.end_time,
    title: entry.title,
    description: entry.description || "",
    effective_from: entry.effective_from,
    effective_until: entry.effective_until || "",
    position: entry.position,
    active: entry.active
  };
}


function payload(form) {
  return {
    weekday: Number(form.weekday),
    kind: form.kind,
    subject: form.kind === "rest" ? null : form.subject,
    start_time: form.start_time,
    end_time: form.end_time,
    title: form.title.trim(),
    description: form.description.trim(),
    effective_from: form.effective_from,
    effective_until: form.effective_until || null,
    position: Number(form.position),
    active: form.active
  };
}


function ScheduleFields({ form, setForm }) {
  const setField = (field, value) => setForm(current => ({ ...current, [field]: value }));
  return (
    <div className="schedule-form-grid">
      <label>星期<select value={form.weekday} onChange={event => setField("weekday", event.target.value)}>{weekdays.map((label, index) => <option value={index} key={label}>{label}</option>)}</select></label>
      <label>类型<select value={form.kind} onChange={event => setField("kind", event.target.value)}><option value="study">学习</option><option value="rest">休息</option></select></label>
      {form.kind === "study" && <label>科目<select value={form.subject} onChange={event => setField("subject", event.target.value)}>{subjects.map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>}
      <label>开始<input type="time" value={form.start_time} onChange={event => setField("start_time", event.target.value)} /></label>
      <label>结束<input type="time" value={form.end_time} onChange={event => setField("end_time", event.target.value)} /></label>
      <label className="wide-field">标题<input maxLength="120" value={form.title} onChange={event => setField("title", event.target.value)} /></label>
      <label>生效日期<input type="date" value={form.effective_from} onChange={event => setField("effective_from", event.target.value)} /></label>
      <label>结束日期<input type="date" value={form.effective_until} onChange={event => setField("effective_until", event.target.value)} /></label>
      <label>排序<input type="number" min="0" max="10000" value={form.position} onChange={event => setField("position", event.target.value)} /></label>
      <label className="checkbox-field"><input type="checkbox" checked={form.active} onChange={event => setField("active", event.target.checked)} />启用</label>
      <label className="full-field">具体内容<textarea rows="2" maxLength="2000" value={form.description} onChange={event => setField("description", event.target.value)} /></label>
    </div>
  );
}


function ScheduleRow({ entry, onChange }) {
  const [form, setForm] = useState(() => fromEntry(entry));
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => setForm(fromEntry(entry)), [entry]);

  async function save() {
    const data = payload(form);
    if (!data.title || data.end_time <= data.start_time) {
      setMessage("请检查标题和起止时间。");
      return;
    }
    setBusy(true);
    try {
      await updateSchedule(entry.id, data);
      setMessage("已保存，只影响尚未生成的日期。");
      await onChange();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm(`确认删除“${entry.title}”这条周计划？`)) return;
    setBusy(true);
    try {
      await deleteSchedule(entry.id);
      await onChange();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="schedule-row">
      <ScheduleFields form={form} setForm={setForm} />
      <div className="task-editor-actions"><button type="button" onClick={save} disabled={busy}>保存</button><button type="button" className="danger-button" onClick={remove} disabled={busy}>删除</button><output>{message}</output></div>
    </article>
  );
}


export default function StudySchedulePage() {
  const [items, setItems] = useState([]);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState(() => emptyForm());
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      setItems((await getSchedule()).items);
    } catch (error) {
      setMessage(error.message);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function add(event) {
    event.preventDefault();
    const data = payload(form);
    if (!data.title || data.end_time <= data.start_time) {
      setMessage("请填写标题，并确保结束时间晚于开始时间。");
      return;
    }
    try {
      await createSchedule(data);
      setForm(emptyForm(Number(form.weekday)));
      setAdding(false);
      setMessage("周计划已新增。");
      await load();
    } catch (error) {
      setMessage(error.message);
    }
  }

  return (
    <main className="admin-page study-admin-page">
      <header className="page-heading"><div><p>WEEKLY TEMPLATE</p><h1>周计划</h1></div><button type="button" onClick={() => setAdding(value => !value)}>{adding ? "收起" : "新增计划"}</button></header>
      <p className="study-page-note">模板修改只影响尚未生成的日期，已经生成的每日记录不会被回写。</p>
      {adding && <form className="study-form-panel" onSubmit={add}><ScheduleFields form={form} setForm={setForm} /><div className="task-editor-actions"><button className="primary-button" type="submit">新增计划</button><button type="button" onClick={() => setAdding(false)}>取消</button></div></form>}
      <output className="study-page-output" aria-live="polite">{message}</output>
      <div className="schedule-week">
        {weekdays.map((label, weekday) => {
          const rows = items.filter(item => item.weekday === weekday);
          return (
            <section className="schedule-day" key={label}>
              <div className="study-panel-heading"><div><p>DAY {weekday + 1}</p><h2>{label}</h2></div><span>{rows.length} 项</span></div>
              {rows.length ? rows.map(entry => <ScheduleRow entry={entry} onChange={load} key={entry.id} />) : <p className="empty-copy">没有安排</p>}
            </section>
          );
        })}
      </div>
    </main>
  );
}
