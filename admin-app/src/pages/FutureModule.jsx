export default function FutureModule({ name }) {
  return (
    <main className="admin-page">
      <header className="page-heading"><div><p>NINESENSE / ROADMAP</p><h1>{name}</h1></div></header>
      <section className="panel future-panel"><strong>{name}将在后续阶段启用</strong><p>基础导航已经预留，当前阶段先完成账户、安全、通知和互动管理。</p></section>
    </main>
  );
}
