import { useEffect, useState } from "react";
import { getPlan, updatePlanItem } from "./studyApi.js";


function todayText() {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(new Date());
}

function itemsFor(day) {
  return day.groups.flatMap(group => group.items);
}

export default function StudyPlanPage() {
  const [plan, setPlan] = useState(null);
  const [selectedDate, setSelectedDate] = useState(todayText());
  const [error, setError] = useState("");
  const [pending, setPending] = useState({});
  const [messages, setMessages] = useState({});

  async function load() {
    setError("");
    try {
      const result = await getPlan();
      setPlan(result);
      setSelectedDate(current => current < result.start_date ? result.start_date : current > result.end_date ? result.end_date : current);
    } catch (value) {
      setError(value.message);
    }
  }

  useEffect(() => { load(); }, []);

  async function check(item, checked) {
    setPending(current => ({ ...current, [item.id]: true }));
    setMessages(current => ({ ...current, [item.id]: "" }));
    try {
      const saved = await updatePlanItem(item.id, checked);
      setPlan(current => ({ ...current, days: current.days.map(day => ({
        ...day, groups: day.groups.map(group => ({
          ...group, items: group.items.map(value => value.id === saved.id ? { ...value, completed: saved.completed } : value)
        }))
      })) }));
      setMessages(current => ({ ...current, [item.id]: checked ? "已保存" : "已撤销" }));
    } catch (value) {
      setMessages(current => ({ ...current, [item.id]: `保存失败：${value.message}，请重新勾选。` }));
    } finally {
      setPending(current => ({ ...current, [item.id]: false }));
    }
  }

  const day = plan?.days.find(value => value.date === selectedDate);
  const allItems = plan ? plan.days.flatMap(itemsFor) : [];
  const completed = allItems.filter(item => item.completed).length;
  const dayItems = day ? itemsFor(day) : [];
  const dayCompleted = dayItems.filter(item => item.completed).length;
  const index = plan?.days.findIndex(value => value.date === selectedDate) ?? -1;

  return (
    <main className="admin-page study-admin-page strengthening-page">
      <header className="page-heading"><div><p>STRENGTHENING PLAN</p><h1>十月强化计划</h1></div><span>10.09 — 10.31</span></header>
      {error && <div className="page-error" role="alert">{error}<button type="button" onClick={load}>重新读取</button></div>}
      {!plan ? <p className="empty-copy">{error ? "计划暂时无法读取。" : "正在读取计划…"}</p> : (
        <>
          <section className="plan-overview" aria-label="计划整体进度">
            <div><span>总进度</span><strong>{completed} <small>/ {allItems.length} 项</small></strong></div>
            <div><span>当前日期</span><strong>{dayCompleted} <small>/ {dayItems.length} 项</small></strong></div>
            <p>完成一项就勾选，自动保存；未完成的可以以后补上。计时由你自行控制。</p>
            <progress value={completed} max={allItems.length} aria-label="全部任务完成进度" />
          </section>
          <nav className="plan-day-nav" aria-label="选择计划日期">
            {plan.days.map(value => {
              const items = itemsFor(value);
              const done = items.filter(item => item.completed).length;
              return <button type="button" key={value.date} className={`${value.date === selectedDate ? "is-selected" : ""} ${done === items.length ? "is-complete" : ""}`} onClick={() => setSelectedDate(value.date)} aria-pressed={value.date === selectedDate}>
                <span>{value.date.slice(5).replace("-", ".")}</span><small>{done}/{items.length}</small>
              </button>;
            })}
          </nav>
          {day && <>
            <div className="plan-date-heading"><button type="button" disabled={index <= 0} onClick={() => setSelectedDate(plan.days[index - 1].date)}>前一天</button><div><h2>{selectedDate.replaceAll("-", ".")}</h2><span>{selectedDate === todayText() ? "今天" : "按日期记录"} · 已完成 {dayCompleted}/{dayItems.length} 项</span></div><button type="button" disabled={index >= plan.days.length - 1} onClick={() => setSelectedDate(plan.days[index + 1].date)}>后一天</button></div>
            <div className="plan-groups">
              {day.groups.map(group => <section className="plan-group" key={group.key} aria-labelledby={`plan-${group.key}`}>
                <header><h2 id={`plan-${group.key}`}>{group.label}</h2><span>{group.items.filter(item => item.completed).length}/{group.items.length} 完成</span><p>{group.source}</p></header>
                <ul className="plan-checklist">{group.items.map(item => <li key={item.id} className={item.completed ? "is-checked" : ""}>
                  <label><input type="checkbox" checked={item.completed} disabled={Boolean(pending[item.id])} onChange={event => check(item, event.target.checked)} /><span><strong>{item.title}</strong><span className="plan-item-description">{item.description}</span></span></label>
                  <output aria-live="polite">{pending[item.id] ? "正在保存…" : messages[item.id]}</output>
                </li>)}</ul>
              </section>)}
            </div>
          </>}
        </>
      )}
    </main>
  );
}
