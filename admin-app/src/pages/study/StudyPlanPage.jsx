import { useEffect, useState } from "react";
import { getPlan, updatePlanItem } from "./studyApi.js";


function todayText() {
  return new Intl.DateTimeFormat("sv-SE", { timeZone: "Asia/Shanghai" }).format(new Date());
}

function itemsFor(day) {
  return day.groups.flatMap(group => group.items).filter(item => !item.optional);
}

export default function StudyPlanPage() {
  const [plan, setPlan] = useState(null);
  const [planId, setPlanId] = useState("");
  const [availablePlans, setAvailablePlans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [reload, setReload] = useState(0);
  const [selectedDate, setSelectedDate] = useState(todayText());
  const [error, setError] = useState("");
  const [pending, setPending] = useState({});
  const [messages, setMessages] = useState({});

  useEffect(() => {
    let cancelled = false;
    setError("");
    setLoading(true);
    setPlan(null);
    setMessages({});
    getPlan(planId).then(result => {
      if (cancelled) return;
      setPlan(result);
      setAvailablePlans(result.available_plans || []);
      setSelectedDate(current => current < result.start_date ? result.start_date : current > result.end_date ? result.end_date : current);
    }).catch(value => { if (!cancelled) setError(value.message); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [planId, reload]);

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
  const months = plan ? [...new Set(plan.days.map(value => value.date.slice(0, 7)))] : [];
  const saving = Object.values(pending).some(Boolean);

  return (
    <main className="admin-page study-admin-page strengthening-page">
      <header className="page-heading"><div><p>STUDY PLAN</p><h1>{plan?.title || "复习计划"}</h1></div><span>{plan ? `${plan.start_date.slice(5).replace("-", ".")} — ${plan.end_date.slice(5).replace("-", ".")}` : ""}</span></header>
      {availablePlans.length > 1 && <div className="plan-switch"><label htmlFor="selected-plan">查看计划</label><select id="selected-plan" value={plan?.id || planId || availablePlans[0].id} disabled={loading || saving} onChange={event => setPlanId(event.target.value)}>{availablePlans.map(value => <option key={value.id} value={value.id}>{value.title}</option>)}</select></div>}
      {error && <div className="page-error" role="alert">{error}<button type="button" onClick={() => setReload(value => value + 1)}>重新读取</button></div>}
      {!plan ? <p className="empty-copy">{error ? "计划暂时无法读取。" : "正在读取计划…"}</p> : (
        <>
          <section className="plan-overview" aria-label="计划整体进度">
            <div><span>必做任务进度</span><strong>{completed} <small>/ {allItems.length} 项</small></strong></div>
            <div><span>当前日期</span><strong>{dayCompleted} <small>/ {dayItems.length} 项</small></strong></div>
            <p>{plan.note || "完成一项就勾选，自动保存。计时由你自行控制。"}</p>
            <progress value={completed} max={allItems.length} aria-label="全部任务完成进度" />
          </section>
          {plan.guidelines?.length > 0 && <details className="plan-guidance"><summary>执行规则与套卷安排</summary><ul>{plan.guidelines.map(value => <li key={value}>{value}</li>)}</ul></details>}
          {months.length > 1 && <div className="plan-switch"><label htmlFor="plan-month">选择月份</label><select id="plan-month" value={selectedDate.slice(0, 7)} onChange={event => setSelectedDate(plan.days.find(value => value.date.startsWith(event.target.value)).date)}>{months.map(value => <option key={value} value={value}>{value.replace("-", " 年 ")} 月</option>)}</select></div>}
          <nav className="plan-day-nav" aria-label="选择计划日期">
            {plan.days.filter(value => value.date.startsWith(selectedDate.slice(0, 7))).map(value => {
              const items = itemsFor(value);
              const done = items.filter(item => item.completed).length;
              return <button type="button" key={value.date} className={`${value.date === selectedDate ? "is-selected" : ""} ${done === items.length ? "is-complete" : ""}`} onClick={() => setSelectedDate(value.date)} aria-pressed={value.date === selectedDate}>
                <span>{value.date.slice(5).replace("-", ".")}</span><small>{done}/{items.length}</small>
              </button>;
            })}
          </nav>
          {day && <>
            <div className="plan-date-heading"><button type="button" disabled={index <= 0} onClick={() => setSelectedDate(plan.days[index - 1].date)}>前一天</button><div><h2>{selectedDate.replaceAll("-", ".")}</h2><span>{selectedDate === todayText() ? "今天" : "按日期记录"} · 已完成 {dayCompleted}/{dayItems.length} 项</span></div><button type="button" disabled={index >= plan.days.length - 1} onClick={() => setSelectedDate(plan.days[index + 1].date)}>后一天</button></div>
            {day.note && <p className="plan-day-note">{day.note}</p>}
            <div className="plan-groups">
              {day.groups.map(group => <section className="plan-group" key={group.key} aria-labelledby={`plan-${group.key}`}>
                <header><h2 id={`plan-${group.key}`}>{group.label}</h2><span>{group.items.every(item => item.optional) ? "不计入必做进度" : `${group.items.filter(item => !item.optional && item.completed).length}/${group.items.filter(item => !item.optional).length} 必做完成`}</span><p>{group.source}</p></header>
                <ul className="plan-checklist">{group.items.map(item => <li key={item.id} className={item.completed ? "is-checked" : ""}>
                  <label><input type="checkbox" checked={item.completed} disabled={Boolean(pending[item.id])} onChange={event => check(item, event.target.checked)} /><span><strong>{item.optional && <small className="plan-optional">可选</small>}{item.title}</strong><span className="plan-item-description">{item.description}</span></span></label>
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
