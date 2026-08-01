import { useEffect, useMemo, useRef, useState } from "react";

import {
  discardTimer,
  finishTimer,
  pauseTimer,
  resumeTimer,
  startBreak,
  startTimer
} from "./studyApi.js";


const subjects = [
  ["math", "高数"],
  ["408", "408"],
  ["english", "英语"],
  ["politics", "政治"]
];

const presets = {
  "25_5": { label: "25 / 5", focus: 25, rest: 5 },
  "50_10": { label: "50 / 10", focus: 50, rest: 10 },
  custom: { label: "自定义", focus: 40, rest: 10 }
};


function initialReminderState() {
  return {
    enabled: window.localStorage.getItem("studyReminderEnabled") === "true",
    notificationPermission: globalThis.Notification?.permission || "unsupported"
  };
}


export function remainingSeconds(timer, now = Date.now()) {
  if (!timer || timer.state === "paused") return timer?.remaining_seconds ?? 0;
  return Math.max(0, Math.ceil((Date.parse(timer.planned_end_at) - now) / 1000));
}


function formatClock(value) {
  const seconds = Math.max(0, value);
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  if (hours) return `${hours}:${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
  return `${String(minutes).padStart(2, "0")}:${String(remainder).padStart(2, "0")}`;
}


function idempotencyKey() {
  return globalThis.crypto?.randomUUID?.().replaceAll("-", "") || `${Date.now()}${Math.random()}`.replace(".", "").padEnd(32, "0").slice(0, 32);
}


export default function StudyTimerPanel({ timer, onChange }) {
  const [subject, setSubject] = useState("408");
  const [preset, setPreset] = useState("25_5");
  const [customFocus, setCustomFocus] = useState(40);
  const [customBreak, setCustomBreak] = useState(10);
  const [remaining, setRemaining] = useState(() => remainingSeconds(timer));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [reminders, setReminders] = useState(initialReminderState);
  const notifiedTimer = useRef(null);

  const selectedPreset = useMemo(() => preset === "custom"
    ? { focus: Number(customFocus), rest: Number(customBreak) }
    : presets[preset], [customBreak, customFocus, preset]);

  useEffect(() => {
    setRemaining(remainingSeconds(timer));
    if (!timer) notifiedTimer.current = null;
  }, [timer]);

  useEffect(() => {
    const tick = window.setInterval(() => setRemaining(remainingSeconds(timer)), 1000);
    const poll = window.setInterval(onChange, 15000);
    const handleVisibility = () => {
      if (document.visibilityState === "visible") onChange();
    };
    document.addEventListener("visibilitychange", handleVisibility);
    return () => {
      window.clearInterval(tick);
      window.clearInterval(poll);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [onChange, timer]);

  useEffect(() => {
    if (!timer || remaining > 0 || !reminders.enabled || notifiedTimer.current === timer.id) return;
    notifiedTimer.current = timer.id;
    const title = timer.phase === "focus" ? "本次专注结束" : "休息时间结束";
    const body = timer.phase === "focus" ? "记录已由服务器保存。" : "可以开始下一轮学习。";
    if (reminders.notificationPermission === "granted") {
      new Notification(title, { body });
    }
    if (globalThis.navigator?.vibrate) {
      navigator.vibrate([180, 80, 180]);
    }
    try {
      const audioContext = new (globalThis.AudioContext || globalThis.webkitAudioContext)();
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      oscillator.type = "sine";
      oscillator.frequency.value = timer.phase === "focus" ? 740 : 520;
      gain.gain.setValueAtTime(0.001, audioContext.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.06, audioContext.currentTime + 0.03);
      gain.gain.exponentialRampToValueAtTime(0.001, audioContext.currentTime + 0.55);
      oscillator.connect(gain);
      gain.connect(audioContext.destination);
      oscillator.start();
      oscillator.stop(audioContext.currentTime + 0.6);
      oscillator.addEventListener("ended", () => audioContext.close());
    } catch {
      // Audio is best-effort; browser policies may block it until the user interacts again.
    }
  }, [remaining, reminders.enabled, reminders.notificationPermission, timer]);

  async function run(action, successMessage = "") {
    setBusy(true);
    setMessage("");
    try {
      await action();
      setMessage(successMessage);
      await onChange();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  function startFocus() {
    const focusMinutes = Math.max(1, Math.min(240, Number(selectedPreset.focus) || 1));
    const breakMinutes = Math.max(0, Math.min(60, Number(selectedPreset.rest) || 0));
    run(() => startTimer({
      subject,
      preset,
      focus_seconds: focusMinutes * 60,
      break_seconds: breakMinutes * 60,
      idempotency_key: idempotencyKey()
    }), `已开始专注 ${subjects.find(item => item[0] === subject)?.[1] || subject}`);
  }

  function startRest() {
    const minutes = Math.max(1, Math.min(60, Number(selectedPreset.rest) || 1));
    run(() => startBreak({
      break_seconds: minutes * 60,
      idempotency_key: idempotencyKey()
    }), `已开始休息 ${minutes} 分钟`);
  }

  async function enableNotifications() {
    window.localStorage.setItem("studyReminderEnabled", "true");
    if (!globalThis.Notification) {
      setReminders({ enabled: true, notificationPermission: "unsupported" });
      setMessage("系统提醒不可用，已启用网页内声音和振动提醒。");
      return;
    }
    try {
      const permission = await Notification.requestPermission();
      setReminders({ enabled: true, notificationPermission: permission });
      setMessage(permission === "granted"
        ? "系统提醒已开启，同时保留网页内声音和振动提醒。"
        : "系统提醒未授权，已启用网页内声音和振动提醒。");
    } catch {
      setReminders({ enabled: true, notificationPermission: "unsupported" });
      setMessage("系统提醒不可用，已启用网页内声音和振动提醒。");
    }
  }

  const activeLabel = timer?.phase === "break"
    ? "休息中"
    : `正在专注 ${subjects.find(item => item[0] === timer?.subject)?.[1] || timer?.subject || ""}`;

  return (
    <section className="study-timer-panel" aria-labelledby="timer-title">
      <div className="study-panel-heading">
        <div><p>FOCUS TIMER</p><h2 id="timer-title">专注计时</h2></div>
        <button type="button" className="quiet-button" onClick={enableNotifications} disabled={reminders.enabled}>
          {reminders.enabled ? "提醒已开启" : "开启提醒"}
        </button>
      </div>

      {timer ? (
        <div className="active-timer">
          <div>
            <span>{activeLabel}</span>
            <strong>{formatClock(remaining)}</strong>
            <small>{timer.state === "paused" ? "已暂停" : "服务器持续计时"}</small>
          </div>
          <div className="timer-actions">
            {timer.state === "running" ? (
              <button type="button" onClick={() => run(pauseTimer)} disabled={busy}>暂停</button>
            ) : (
              <button type="button" onClick={() => run(resumeTimer)} disabled={busy}>继续</button>
            )}
            {timer.phase === "focus" ? (
              <>
                <button type="button" onClick={() => run(() => finishTimer(true), "本次专注已保存。") } disabled={busy}>保存本次</button>
                <button type="button" className="danger-button" onClick={() => run(() => finishTimer(false), "本次专注已放弃。") } disabled={busy}>放弃本次</button>
              </>
            ) : (
              <button type="button" className="danger-button" onClick={() => run(discardTimer)} disabled={busy}>结束休息</button>
            )}
          </div>
        </div>
      ) : (
        <div className="timer-setup">
          <fieldset>
            <legend>科目</legend>
            <div className="subject-segments">
              {subjects.map(([value, label]) => (
                <button type="button" className={subject === value ? "active" : ""} key={value} onClick={() => setSubject(value)}>{label}</button>
              ))}
            </div>
          </fieldset>
          <fieldset>
            <legend>时长</legend>
            <div className="preset-segments">
              {Object.entries(presets).map(([value, item]) => (
                <button type="button" className={preset === value ? "active" : ""} key={value} onClick={() => setPreset(value)}>{item.label}</button>
              ))}
            </div>
          </fieldset>
          {preset === "custom" && (
            <div className="custom-timer-inputs">
              <label>专注分钟<input type="number" min="1" max="240" value={customFocus} onChange={event => setCustomFocus(event.target.value)} /></label>
              <label>休息分钟<input type="number" min="0" max="60" value={customBreak} onChange={event => setCustomBreak(event.target.value)} /></label>
            </div>
          )}
          <div className="timer-start-actions">
            <button type="button" className="primary-button" onClick={startFocus} disabled={busy}>开始专注</button>
            <button type="button" onClick={startRest} disabled={busy || Number(selectedPreset.rest) < 1}>开始休息</button>
          </div>
        </div>
      )}
      <output className="study-inline-output" aria-live="polite">{message}</output>
    </section>
  );
}
