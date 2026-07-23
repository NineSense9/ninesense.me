import { useAuth } from "../auth/AuthContext.jsx";


export default function RecoveryCodesPage() {
  const { recoveryCodes, acknowledgeRecoveryCodes } = useAuth();
  return (
    <main className="recovery-screen">
      <section className="recovery-card">
        <p>SECURITY / ONE-TIME DISPLAY</p>
        <h1>保存恢复码</h1>
        <span>每个恢复码只能使用一次。请保存在密码管理器或其他安全位置，离开本页后不会再次显示。</span>
        <div className="recovery-grid">
          {recoveryCodes.map(code => <code data-testid="recovery-code" key={code}>{code}</code>)}
        </div>
        <button type="button" onClick={acknowledgeRecoveryCodes}>我已保存，进入后台</button>
      </section>
    </main>
  );
}
