import { useEffect, useMemo, useRef, useState } from "react";
import QRCode from "qrcode";

import { useAuth } from "../auth/AuthContext.jsx";


function setupSecret(uri) {
  if (!uri) return "";
  return new URL(uri).searchParams.get("secret") || "";
}


export default function LoginPage() {
  const { startLogin, completeMfa } = useAuth();
  const [stage, setStage] = useState("password");
  const [username, setUsername] = useState("ninesense");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [challenge, setChallenge] = useState(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const canvasRef = useRef(null);
  const secret = useMemo(() => setupSecret(challenge?.setup_uri), [challenge]);

  useEffect(() => {
    if (!canvasRef.current || !challenge?.setup_uri) return;
    QRCode.toCanvas(canvasRef.current, challenge.setup_uri, {
      width: 220,
      margin: 1,
      color: { dark: "#141310", light: "#f0ede4" }
    }).catch(() => setStatus("二维码生成失败，请使用下方密钥手动添加。"));
  }, [challenge]);

  async function submitPassword(event) {
    event.preventDefault();
    setBusy(true);
    setStatus("");
    try {
      const next = await startLogin(username.trim(), password);
      setPassword("");
      setChallenge(next);
      setStage(next.stage === "mfa_setup_required" ? "setup" : "mfa");
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function submitCode(event) {
    event.preventDefault();
    setBusy(true);
    setStatus("");
    try {
      await completeMfa(challenge.challenge_token, code.trim());
      setCode("");
      setChallenge(null);
    } catch (error) {
      setStatus(error.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login-screen">
      <section className="login-intro">
        <p>NINESENSE / PRIVATE CONSOLE</p>
        <h1>回来整理<br />网站内容</h1>
        <span>仅站长可访问。登录后可以管理内容、互动和网站状态。</span>
      </section>
      {stage === "password" ? (
        <form className="auth-card" onSubmit={submitPassword}>
          <p>01 / ACCOUNT</p>
          <h2>登录管理平台</h2>
          <label htmlFor="username">账户</label>
          <input id="username" autoComplete="username" value={username} onChange={event => setUsername(event.target.value)} required />
          <label htmlFor="password">密码</label>
          <input id="password" type="password" autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} required />
          <button type="submit" disabled={busy}>继续</button>
          <output aria-live="polite">{status}</output>
        </form>
      ) : (
        <form className="auth-card auth-card-wide" onSubmit={submitCode}>
          <p>02 / TWO-STEP VERIFICATION</p>
          <h2>{stage === "setup" ? "设置两步验证" : "输入动态验证码"}</h2>
          {stage === "setup" && (
            <div className="mfa-setup">
              <canvas ref={canvasRef} aria-label="两步验证二维码" />
              <label htmlFor="setup-secret">无法扫码时手动输入</label>
              <input id="setup-secret" value={secret} readOnly />
            </div>
          )}
          <label htmlFor="otp-code">动态验证码</label>
          <input id="otp-code" inputMode="numeric" autoComplete="one-time-code" value={code} onChange={event => setCode(event.target.value)} minLength="6" maxLength="32" required />
          <button type="submit" disabled={busy}>{stage === "setup" ? "启用并登录" : "验证并登录"}</button>
          <output aria-live="polite">{status}</output>
        </form>
      )}
    </main>
  );
}
