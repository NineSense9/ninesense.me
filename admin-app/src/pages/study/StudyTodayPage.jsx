import { useCallback, useEffect, useState } from "react";

import StudyTaskEditor from "./StudyTaskEditor.jsx";
import StudyTimerPanel from "./StudyTimerPanel.jsx";
import { getTimer, getToday, updateReflection } from "./studyApi.js";


function localDate() {
  const now = new Date();
  const year = now.getFullYear();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}


function ReflectionEditor({ date, value, onSaved }) {
  const [reflection, setReflection] = useState(value || "");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => setReflection(value || ""), [value]);

  async function save() {
    setBusy(true);
    setMessage("");
    try {
      await updateReflection(date, reflection);
      setMessage("复盘已保存。");
      await onSaved();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="study-reflection-panel" aria-labelledby="reflection-title">
      <div className="study-panel-heading"><div><p>DAILY REVIEW</p><h2 id="reflection-title">今天复盘</h2></div></div>
      <textarea value={reflection} onChange={event => setReflection(event.target.value)} maxLength="4000" rows="10" placeholder="今天学了什么，哪里没有做好，明天要怎么调整。" />
      <div className="reflection-actions"><span>{reflection.length} / 4000</span><button type="button" onClick={save} disabled={busy}>保存复盘</button></div>
      <output className="study-inline-output" aria-live="polite">{message}</output>
    </section>
  );
}


export default function StudyTodayPage() {
  const date = localDate();
  const [day, setDay] = useState(null);
  const [timer, setTimer] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    setError("");
    try {
      const [dayResult, timerResult] = await Promise.all([getToday(date), getTimer()]);
      setDay(dayResult);
      setTimer(timerResult.timer);
    } catch (value) {
      setError(value.message);
    } finally {
      setLoading(false);
    }
  }, [date]);

  useEffect(() => {
    reload();
  }, [reload]);

  return (
    <main className="admin-page study-admin-page">
      <header className="page-heading">
        <div><p>STUDY MANAGEMENT</p><h1>今天</h1></div>
        <span>{date}</span>
      </header>
      {error && <p className="page-error" role="alert">{error}</p>}
      {loading ? <p className="empty-copy">正在读取今日计划…</p> : (
        <>
          <StudyTimerPanel timer={timer} onChange={reload} />
          <div className="study-today-grid">
            <StudyTaskEditor day={day} date={date} onChange={reload} />
            <ReflectionEditor date={date} value={day?.reflection || ""} onSaved={reload} />
          </div>
        </>
      )}
    </main>
  );
}
