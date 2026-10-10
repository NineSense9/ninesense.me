const SUBJECT_LABELS = {
  math: "高数",
  "408": "408",
  english: "英语",
  politics: "政治",
};

const nodes = {
  status: document.getElementById("study-status"),
  countdownValue: document.getElementById("countdown-value"),
  countdownLabel: document.getElementById("countdown-label"),
  currentStatus: document.getElementById("current-study-status"),
  nextEvent: document.getElementById("next-exam-event"),
  updatedAt: document.getElementById("study-updated-at"),
  todaySummary: document.getElementById("today-summary"),
  todayReflection: document.getElementById("today-reflection"),
  todaySubjects: document.getElementById("today-subjects"),
  allTimeTotal: document.getElementById("all-time-total"),
  monthTotal: document.getElementById("month-total"),
  focusTrend: document.getElementById("focus-trend"),
  subjectBreakdown: document.getElementById("subject-breakdown"),
  recentHeatmap: document.getElementById("recent-heatmap"),
  examTimeline: document.getElementById("exam-timeline"),
  planSummary: document.getElementById("plan-summary"),
  planProgress: document.getElementById("plan-progress"),
  planGroups: document.getElementById("plan-groups"),
  planToday: document.getElementById("plan-today"),
};

function setText(node, value, fallback = "—") {
  if (node) node.textContent = value ?? fallback;
}

function formatDuration(seconds) {
  const safeSeconds = Math.max(0, Number(seconds) || 0);
  const hours = Math.floor(safeSeconds / 3600);
  const minutes = Math.floor((safeSeconds % 3600) / 60);
  if (hours && minutes) return `${hours} 小时 ${minutes} 分钟`;
  if (hours) return `${hours} 小时`;
  return `${minutes} 分钟`;
}

function formatDate(value) {
  if (!value) return "—";
  const parts = value.slice(0, 10).split("-");
  return parts.length === 3 ? `${parts[0]}.${parts[1]}.${parts[2]}` : value;
}

function formatUpdatedAt(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(`请求失败（${response.status}）`);
  return response.json();
}

function retryState(container, message, retry) {
  container.replaceChildren();
  const wrapper = document.createElement("div");
  wrapper.className = "section-error";
  const text = document.createElement("span");
  setText(text, message, "暂时无法读取数据");
  const button = document.createElement("button");
  button.type = "button";
  button.className = "retry-button";
  button.textContent = "重新读取";
  button.addEventListener("click", retry, { once: true });
  wrapper.append(text, button);
  container.append(wrapper);
}

function emptyState(container, message) {
  container.replaceChildren();
  const empty = document.createElement("p");
  empty.className = "empty-state";
  setText(empty, message);
  container.append(empty);
}

function renderToday(today) {
  setText(nodes.countdownValue, today.countdown_days === null ? "—" : String(today.countdown_days));
  setText(
    nodes.countdownLabel,
    today.countdown_target ? `${today.countdown_target} · 剩余天数` : "等待时间节点",
  );
  setText(
    nodes.currentStatus,
    today.active_subject ? `正在专注 ${SUBJECT_LABELS[today.active_subject]}` : "当前没有进行中的专注",
  );
  setText(
    nodes.nextEvent,
    today.next_exam_event
      ? `${formatDate(today.next_exam_event.start_date)} · ${today.next_exam_event.title}`
      : "最近节点待更新",
  );
  setText(nodes.updatedAt, formatUpdatedAt(today.updated_at));
  setText(
    nodes.todaySummary,
    `今日学习 · ${formatDuration(today.total_focus_seconds)}`,
  );
  setText(nodes.todayReflection, today.reflection || "今天还没有留下复盘。");

  renderSubjects(nodes.todaySubjects, today.subjects);
  setText(nodes.status, "今日记录已更新");
}

function buildMonthDays(month, daily) {
  const [year, monthValue] = month.split("-").map(Number);
  const count = new Date(year, monthValue, 0).getDate();
  const values = new Map(daily.map((item) => [Number(item.date.slice(-2)), item.seconds]));
  return Array.from({ length: count }, (_, index) => ({
    day: index + 1,
    seconds: values.get(index + 1) || 0,
  }));
}

function renderOverview(month) {
  setText(
    nodes.allTimeTotal,
    Number.isFinite(month.all_time_seconds)
      ? `累计学习 · ${formatDuration(month.all_time_seconds)}`
      : "累计学习时长暂不可用",
  );
  setText(
    nodes.monthTotal,
    `${month.month.replace("-", " 年 ")} 月 · ${formatDuration(month.total_seconds)}`,
  );

  const days = buildMonthDays(month.month, month.daily || []);
  const maximum = Math.max(...days.map((item) => item.seconds), 1);
  nodes.focusTrend.replaceChildren();
  nodes.focusTrend.style.setProperty("--days", String(days.length));
  days.forEach((item) => {
    const bar = document.createElement("span");
    bar.className = "focus-bar";
    bar.style.setProperty("--height", `${Math.max(1.5, (item.seconds / maximum) * 100)}%`);
    bar.dataset.day = String(item.day);
    if (item.day === 1 || item.day % 5 === 0 || item.day === days.length) bar.dataset.label = "true";
    bar.title = `${item.day} 日 · ${formatDuration(item.seconds)}`;
    nodes.focusTrend.append(bar);
  });

  renderSubjects(nodes.subjectBreakdown, month.subjects, month.all_time_subjects);
}

function renderSubjects(container, subjects = {}, allTimeSubjects) {
  container.replaceChildren();
  const subjectMaximum = Math.max(...Object.values(subjects), 1);
  Object.entries(SUBJECT_LABELS).forEach(([key, label]) => {
    const seconds = subjects[key] || 0;
    const row = document.createElement("div");
    row.className = "subject-row";
    const header = document.createElement("div");
    header.className = "subject-row-header";
    const name = document.createElement("span");
    name.textContent = label;
    const value = document.createElement("span");
    value.textContent = formatDuration(seconds);
    if (allTimeSubjects) {
      const values = document.createElement("div");
      values.className = "subject-values";
      value.textContent = `本月 ${formatDuration(seconds)}`;
      const total = document.createElement("span");
      total.className = "subject-total";
      total.textContent = `累计 ${formatDuration(allTimeSubjects[key] || 0)}`;
      values.append(value, total);
      header.append(name, values);
    } else {
      header.append(name, value);
    }
    const track = document.createElement("div");
    track.className = "subject-track";
    const fill = document.createElement("div");
    fill.className = "subject-fill";
    fill.style.setProperty("--width", `${(seconds / subjectMaximum) * 100}%`);
    track.append(fill);
    row.append(header, track);
    container.append(row);
  });
}

function heatLevel(seconds) {
  if (!seconds) return "0";
  if (seconds < 1800) return "1";
  if (seconds < 3600) return "2";
  if (seconds < 7200) return "3";
  return "4";
}

function recentDates(lastDate) {
  const end = new Date(`${lastDate}T00:00:00+08:00`);
  return Array.from({ length: 30 }, (_, index) => {
    const current = new Date(end);
    current.setDate(end.getDate() - (29 - index));
    return `${current.getFullYear()}-${String(current.getMonth() + 1).padStart(2, "0")}-${String(current.getDate()).padStart(2, "0")}`;
  });
}

function renderRecent(payload) {
  const items = payload.items || [];
  const latestDate = items[0]?.date || new Date().toISOString().slice(0, 10);
  const byDate = new Map(items.map((item) => [item.date, item]));
  nodes.recentHeatmap.replaceChildren();
  recentDates(latestDate).forEach((date) => {
    const item = byDate.get(date);
    const cell = document.createElement("span");
    cell.className = "heat-cell";
    cell.dataset.level = heatLevel(item?.total_focus_seconds || 0);
    cell.title = `${formatDate(date)} · ${formatDuration(item?.total_focus_seconds || 0)}`;
    nodes.recentHeatmap.append(cell);
  });

}

function renderExams(payload) {
  const items = payload.items || [];
  nodes.examTimeline.replaceChildren();
  if (!items.length) {
    emptyState(nodes.examTimeline, "考研时间节点还没有录入。");
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("li");
    row.className = "exam-event";
    const date = document.createElement("time");
    date.dateTime = item.start_date;
    date.textContent = item.end_date
      ? `${formatDate(item.start_date)} — ${formatDate(item.end_date)}`
      : formatDate(item.start_date);
    const content = document.createElement("div");
    const title = document.createElement("h3");
    title.textContent = item.title;
    const description = document.createElement("p");
    description.textContent = item.description || "";
    content.append(title, description);
    if (item.source_url) {
      try {
        const url = new URL(item.source_url);
        if (url.protocol === "https:" || url.protocol === "http:") {
          const source = document.createElement("a");
          source.className = "exam-source";
          source.href = url.href;
          source.target = "_blank";
          source.rel = "noopener noreferrer";
          source.textContent = "查看来源 ↗";
          content.append(source);
        }
      } catch {
        // Ignore invalid source links while keeping the event readable.
      }
    }
    const status = document.createElement("span");
    status.className = "exam-status";
    status.textContent = item.date_status === "confirmed" ? "已确认" : "预计日期";
    row.append(date, content, status);
    nodes.examTimeline.append(row);
  });
}

async function loadToday() {
  try {
    const today = await fetchJson("/api/study/today");
    renderToday(today);
    await loadOverview(today.date.slice(0, 7));
  } catch (error) {
    setText(nodes.status, "今日记录读取失败");
    retryState(nodes.todaySubjects, error.message, loadToday);
  }
}

async function loadOverview(month) {
  try {
    renderOverview(await fetchJson(`/api/study/months/${month}`));
  } catch (error) {
    setText(nodes.allTimeTotal, "累计学习时长读取失败");
    setText(nodes.monthTotal, "月度学习时长读取失败");
    retryState(nodes.focusTrend, error.message, () => loadOverview(month));
    nodes.subjectBreakdown.replaceChildren();
  }
}

async function loadRecent() {
  try {
    renderRecent(await fetchJson("/api/study/recent?days=30"));
  } catch (error) {
    retryState(nodes.recentHeatmap, error.message, loadRecent);
  }
}

async function loadExams() {
  try {
    renderExams(await fetchJson("/api/study/exams"));
  } catch (error) {
    retryState(nodes.examTimeline, error.message, loadExams);
  }
}

async function loadStudyPage() {
  await loadToday();
  await Promise.all([loadRecent(), loadExams(), loadPlan()]);
}

async function loadPlan() {
  try {
    const plan = await fetchJson("/api/study/plan");
    const percent = plan.total ? Math.round(plan.completed / plan.total * 100) : 0;
    setText(nodes.planSummary, `${plan.completed}/${plan.total} 项已完成 · ${percent}%`);
    nodes.planProgress.max = plan.total || 1;
    nodes.planProgress.value = plan.completed;
    nodes.planGroups.replaceChildren();
    Object.values(plan.groups).forEach(group => {
      const row = document.createElement("div");
      const label = document.createElement("span");
      const count = document.createElement("strong");
      label.textContent = group.label;
      count.textContent = `${group.completed}/${group.total} 项`;
      row.append(label, count);
      nodes.planGroups.append(row);
    });
    setText(nodes.planToday, plan.today.total ? `今日任务 · ${plan.today.completed}/${plan.today.total} 项已完成` : `计划周期 · ${formatDate(plan.start_date)} — ${formatDate(plan.end_date)}`);
  } catch (error) {
    setText(nodes.planSummary, "计划进度读取失败");
    retryState(nodes.planGroups, error.message, loadPlan);
  }
}

loadStudyPage();
