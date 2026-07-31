import { NavLink, Outlet } from "react-router-dom";


const tabs = [
  ["今天", "/study"],
  ["周计划", "/study/schedule"],
  ["历史记录", "/study/history"],
  ["专注记录", "/study/focus"],
  ["考研时间表", "/study/exams"]
];


export default function StudyLayout() {
  return (
    <div className="study-layout">
      <nav className="study-subnav" aria-label="学习管理导航">
        {tabs.map(([label, path]) => (
          <NavLink end={path === "/study"} key={path} to={path} className={({ isActive }) => isActive ? "active" : undefined}>
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
