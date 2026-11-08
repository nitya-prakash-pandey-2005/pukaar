// Responsive app shell: sidebar on desktop (>900px), top bar + bottom tab bar on phones.
// Everything project-specific comes in through props, so the shell itself never changes.
//
// <AppShell
//   path={route.path}
//   brand={{ name: "Acme", sub: "Ops console", logo: "/icons/icon.svg", href: "#/" }}
//   nav={[{ group: "Workspace", items: [{ to: "/app", label: "Home", icon: Home, exact: true, badge: 3 }] }]}
//   titles={[["/app/settings", "Settings", "Theme and account"], ["/app", "Home", "Overview"]]}
//   mobileTabs={[...]}            // optional; defaults to the first 5 nav items
//   topRight={<YourButtons />}    // optional; right side of the top bar
//   footer={<YourSidebarFooter />} // optional; bottom of the sidebar
//   fab={{ label: "Demo", icon: FlaskConical, onClick }} // optional floating button
// >{page}</AppShell>
import { Hud } from "../ui";

export default function AppShell({ path, brand, nav, titles = [], mobileTabs, topRight, footer, fab, children }) {
  const active = (it) => (it.exact ? path === it.to : path === it.to || path.startsWith(it.to + "/"));
  const [title, sub] = (titles.find(([p]) => path === p || path.startsWith(p + "/")) || [null, brand?.name, ""]).slice(1);
  const tabs = (mobileTabs || nav.flatMap((g) => g.items)).slice(0, 5);

  return (
    <div className="shell">
      <aside className="sidebar">
        <a href={brand?.href || "#/"} className="brand">
          <span className="logo">{brand?.logo ? <img src={brand.logo} width="26" height="26" alt="" /> : null}</span>
          <span><b>{brand?.name}</b>{brand?.sub && <div className="sub">{brand.sub}</div>}</span>
        </a>
        {nav.map((g) => (
          <div className="nav-group" key={g.group}>
            {g.group && <Hud>{g.group}</Hud>}
            {g.items.map((it) => (
              <a key={it.to} href={`#${it.to}`} className={`nav-link ${active(it) ? "on" : ""}`} data-tour={`nav-${it.to.split("/").pop() || "home"}`}>
                {it.icon && <it.icon size={18} />}{it.label}
                {it.badge ? <span className="count">{it.badge}</span> : null}
              </a>
            ))}
          </div>
        ))}
        {footer && <div className="foot">{footer}</div>}
      </aside>

      <div className="main">
        <header className="topbar">
          <a href={brand?.href || "#/"} className="mobile-only" aria-label={brand?.name}>{brand?.logo && <img src={brand.logo} width="30" height="30" alt="" />}</a>
          <div className="title grow"><b>{title}</b><span>{sub}</span></div>
          {topRight}
        </header>
        <main className="content">{children}</main>
      </div>

      <nav className="bottomnav">
        {tabs.map((t) => (
          <a key={t.to} href={`#${t.to}`} className={active(t) ? "on" : ""}>{t.icon && <t.icon size={21} />}{t.short || t.label}</a>
        ))}
      </nav>

      {fab && (
        <button className="demo-fab" onClick={fab.onClick} data-tour="demo-fab">
          <span className="ring">{fab.icon && <fab.icon size={16} />}</span>{fab.label}
        </button>
      )}
    </div>
  );
}
