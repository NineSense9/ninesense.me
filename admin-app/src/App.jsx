import { AuthProvider, useAuth } from "./auth/AuthContext.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import RecoveryCodesPage from "./pages/RecoveryCodesPage.jsx";


function AppContent() {
  const { session, loading, recoveryCodes } = useAuth();
  if (loading) return <main className="bootstrap-screen"><p>NINESENSE / PRIVATE CONSOLE</p><h1>正在验证会话</h1></main>;
  if (!session) return <LoginPage />;
  if (recoveryCodes) return <RecoveryCodesPage />;
  return <main className="bootstrap-screen"><p>NINESENSE / PRIVATE CONSOLE</p><h1>已经安全登录</h1></main>;
}


export default function App() {
  return <AuthProvider><AppContent /></AuthProvider>;
}
