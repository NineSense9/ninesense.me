let csrfToken = "";


export function setCsrfToken(value) {
  csrfToken = value || "";
}


export async function api(path, options = {}) {
  const { preserveSessionOnUnauthorized = false, ...requestOptions } = options;
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(requestOptions.headers || {});
  if (requestOptions.body) headers.set("Content-Type", "application/json");
  if (!["GET", "HEAD", "OPTIONS"].includes(method) && csrfToken) {
    headers.set("X-CSRF-Token", csrfToken);
  }
  const response = await fetch(path, { ...requestOptions, method, headers });
  const data = response.status === 204 ? null : await response.json().catch(() => ({}));
  if (response.status === 401 && !preserveSessionOnUnauthorized) {
    setCsrfToken("");
    window.dispatchEvent(new Event("ninesense:session-expired"));
  }
  if (!response.ok) {
    const error = new Error(data?.detail || "操作没有完成，请稍后再试。");
    error.status = response.status;
    throw error;
  }
  return data;
}
