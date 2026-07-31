import { api } from "../../api/client.js";


export const getToday = date => api(`/api/admin/study/days/${date}`);
export const getTimer = () => api("/api/admin/study/timer");
export const startTimer = payload => api("/api/admin/study/timer/start", {
  method: "POST",
  body: JSON.stringify(payload)
});
export const startBreak = payload => api("/api/admin/study/timer/break", {
  method: "POST",
  body: JSON.stringify(payload)
});
export const pauseTimer = () => api("/api/admin/study/timer/pause", { method: "POST" });
export const resumeTimer = () => api("/api/admin/study/timer/resume", { method: "POST" });
export const finishTimer = save => api("/api/admin/study/timer/finish", {
  method: "POST",
  body: JSON.stringify({ save })
});
export const discardTimer = () => api("/api/admin/study/timer/discard", { method: "POST" });
export const createTask = (date, payload) => api(`/api/admin/study/days/${date}/tasks`, {
  method: "POST",
  body: JSON.stringify(payload)
});
export const updateTask = (id, payload) => api(`/api/admin/study/tasks/${id}`, {
  method: "PATCH",
  body: JSON.stringify(payload)
});
export const deleteTask = id => api(`/api/admin/study/tasks/${id}`, { method: "DELETE" });
export const updateReflection = (date, reflection) => api(`/api/admin/study/days/${date}/reflection`, {
  method: "PATCH",
  body: JSON.stringify({ reflection })
});
