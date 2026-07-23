import { AuthProvider, useAuth } from "./auth/AuthContext.jsx";
import { Navigate, Route, Routes } from "react-router-dom";
import AdminShell from "./layout/AdminShell.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import FutureModule from "./pages/FutureModule.jsx";
import LoginPage from "./pages/LoginPage.jsx";
import NotificationsPage from "./pages/NotificationsPage.jsx";
import RecoveryCodesPage from "./pages/RecoveryCodesPage.jsx";
import SecurityPage from "./pages/SecurityPage.jsx";


function AppContent() {
  const { session, loading, recoveryCodes } = useAuth();
  if (loading) return <main className="bootstrap-screen"><p>NINESENSE / PRIVATE CONSOLE</p><h1>正在验证会话</h1></main>;
  if (!session) return <LoginPage />;
  if (recoveryCodes) return <RecoveryCodesPage />;
  return (
    <Routes>
      <Route element={<AdminShell />}>
        <Route index element={<DashboardPage />} />
        <Route path="inbox" element={<FutureModule name="互动" />} />
        <Route path="notifications" element={<NotificationsPage />} />
        <Route path="security" element={<SecurityPage />} />
        <Route path="content" element={<FutureModule name="内容" />} />
        <Route path="pages" element={<FutureModule name="页面" />} />
        <Route path="media" element={<FutureModule name="媒体" />} />
        <Route path="publishing" element={<FutureModule name="发布" />} />
        <Route path="analytics" element={<FutureModule name="统计" />} />
        <Route path="operations" element={<FutureModule name="运维" />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}


export default function App() {
  return <AuthProvider><AppContent /></AuthProvider>;
}
