import { NavLink, Outlet } from "react-router-dom";


const tabs = [["今天", "/study"]];


export default function StudyLayout() {
  return (
    <div className="study-layout">
      <nav className="study-subnav" aria-label="学习管理导航">
        {tabs.map(([label, path]) => (
          <NavLink end key={path} to={path} className={({ isActive }) => isActive ? "active" : undefined}>
            {label}
          </NavLink>
        ))}
      </nav>
      <Outlet />
    </div>
  );
}
