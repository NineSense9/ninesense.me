import { useCallback, useEffect, useState } from "react";

import { getHistory } from "./studyApi.js";


const subjectLabels = { math: "高数", "408": "408", english: "英语", politics: "政治" };
const statusLabels = { planned: "待开始", in_progress: "进行中", completed: "已完成", incomplete: "未完成", cancelled: "已取消" };


function dateText(value) {
  const date = new Date(value);
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}


function defaultRange() {
  const now = new Date();
  return {
    from: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}-01`,
    to: dateText(now)
  };
}


function duration(seconds) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return hours ? `${hours} 小时 ${minutes} 分钟` : `${minutes} 分钟`;
}


export default function StudyHistoryPage() {
  const initial = defaultRange();
  const [from, setFrom] = useState(initial.from);
  const [to, setTo] = useState(initial.to);
  const [items, setItems] = useState([]);
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async (start = from, end = to) => {
    const days = Math.round((new Date(`${end}T00:00:00`) - new Date(`${start}T00:00:00`)) / 86400000);
    if (days < 0 || days > 365) {
      setMessage("单次查询范围必须在 366 天以内。");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      setItems((await getHistory(start, end)).items);
    } catch (error) {
      setMessage(error.message);
    } finally {
      setLoading(false);
    }
  }, [from, to]);

  useEffect(() => { load(initial.from, initial.to); }, []);

  function submit(event) {
    event.preventDefault();
    load();
  }

  return (
    <main className="admin-page study-admin-page">
      <header className="page-heading"><div><p>COMPLETE HISTORY</p><h1>历史记录</h1></div><span>{items.length} 天</span></header>
      <form className="study-filter-bar" onSubmit={submit}>
        <label>开始日期<input type="date" value={from} onChange={event => setFrom(event.target.value)} /></label>
        <label>结束日期<input type="date" value={to} onChange={event => setTo(event.target.value)} /></label>
        <button className="primary-button" type="submit">查询记录</button>
      </form>
      <output className="study-page-output" aria-live="polite">{message}</output>
      {loading ? <p className="empty-copy">正在读取历史记录…</p> : !items.length ? <p className="empty-copy">这个日期范围内没有记录</p> : (
        <div className="study-history-list">
          {items.map((day, index) => (
            <details className="history-day" key={day.id} open={index === 0}>
              <summary>
                <span><strong>{day.date}</strong><small>{day.tasks.length} 项任务</small></span>
                <span>{duration(day.total_focus_seconds)} · {day.completion.completed}/{day.completion.closed || 0} 完成</span>
              </summary>
              <div className="history-day-body">
                <section>
                  <h2>任务</h2>
                  {!day.tasks.length ? <p className="empty-copy">没有任务</p> : <ul className="history-task-list">{day.tasks.map(task => <li key={task.id}><time>{task.start_time}–{task.end_time}</time><strong>{task.kind === "rest" ? "休息" : subjectLabels[task.subject]} · {task.title}</strong><span>{statusLabels[task.status]}</span><p>{task.description}</p></li>)}</ul>}
                </section>
                <section>
                  <h2>复盘</h2>
                  <p className="history-reflection">{day.reflection || "没有留下复盘。"}</p>
                  <h2>专注明细</h2>
                  {!day.focus.length ? <p className="empty-copy">没有专注记录</p> : <ul className="history-focus-list">{day.focus.map(row => <li key={row.id}><strong>{subjectLabels[row.subject]}</strong><span>{duration(row.effective_seconds)}</span><time>{new Date(row.started_at).toLocaleString("zh-CN")}</time></li>)}</ul>}
                </section>
              </div>
            </details>
          ))}
        </div>
      )}
    </main>
  );
}
