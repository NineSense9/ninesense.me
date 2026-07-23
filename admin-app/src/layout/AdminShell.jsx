import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext.jsx";


const navigation = [
  ["总览", "/"],
  ["互动", "/inbox"],
  ["内容", "/content"],
  ["页面", "/pages"],
  ["媒体", "/media"],
  ["发布", "/publishing"],
  ["通知", "/notifications"],
  ["统计", "/analytics"],
  ["运维", "/operations"],
  ["设置与安全", "/security"]
];


export default function AdminShell() {
  const { session, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  return (
    <div className="admin-shell">
      <aside className={menuOpen ? "admin-sidebar is-open" : "admin-sidebar"}>
        <div className="admin-brand">
          <strong>NineSense</strong>
          <span>PRIVATE CONSOLE</span>
        </div>
        <nav aria-label="后台主导航">
          {navigation.map(([label, path]) => (
            <NavLink
              end={path === "/"}
              key={path}
              to={path}
              onClick={() => setMenuOpen(false)}
              className={({ isActive }) => isActive ? "active" : undefined}
            >
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="admin-account">
          <span>{session.username}</span>
          <button type="button" onClick={logout}>退出登录</button>
        </div>
      </aside>
      <div className="admin-main">
        <header className="admin-mobile-header">
          <strong>NineSense</strong>
          <button type="button" aria-expanded={menuOpen} onClick={() => setMenuOpen(value => !value)}>
            {menuOpen ? "关闭" : "菜单"}
          </button>
        </header>
        <Outlet />
      </div>
    </div>
  );
}
