import { useState } from "react";

// tabs: [{ label, content }]  (content is a node; only the active one is rendered)
export default function Tabs({ tabs }) {
  const [active, setActive] = useState(0);
  return (
    <div>
      <div className="tabs">
        {tabs.map((t, i) => (
          <button key={t.label} className={i === active ? "active" : ""} onClick={() => setActive(i)}>
            {t.label}
          </button>
        ))}
      </div>
      <div className="tab-body">{tabs[active].content}</div>
    </div>
  );
}
