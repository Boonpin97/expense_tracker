import { useEffect, useRef } from "react";

export type MobileTabKey =
  | "overview"
  | "transactions"
  | "income"
  | "goals"
  | "projects"
  | "charts"
  | "budget"
  | "plans";

/**
 * Tabs in strip order. Priority screens first so the ones used most on a phone
 * are visible without scrolling; the rest trail off to the right.
 */
export const MOBILE_TABS: { key: MobileTabKey; label: string; title: string }[] = [
  { key: "overview", label: "Overview", title: "Overview" },
  { key: "transactions", label: "Expenses", title: "All Expenses" },
  { key: "income", label: "Income", title: "Income" },
  { key: "goals", label: "Goals", title: "Goals" },
  { key: "projects", label: "Projects", title: "Long-Term Projects" },
  { key: "charts", label: "Charts", title: "Charts" },
  { key: "budget", label: "Budget", title: "Budget" },
  { key: "plans", label: "Subscriptions", title: "Subscriptions" },
];

/**
 * Horizontally scrollable tab strip.
 *
 * Deliberately NOT built on shadcn's TabsList: its base class carries `h-9`,
 * which survives a `grid`/`flex` override via tailwind-merge and is what makes
 * the desktop 8-tab bar spill outside its own container on a narrow screen.
 */
export function MobileTabStrip({
  active,
  onChange,
}: {
  active: MobileTabKey;
  onChange: (key: MobileTabKey) => void;
}) {
  const refs = useRef<Partial<Record<MobileTabKey, HTMLButtonElement | null>>>({});

  // Keep the selected tab in view — otherwise tabs near the end of the strip
  // stay off-screen after being selected from elsewhere.
  useEffect(() => {
    refs.current[active]?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
      inline: "center",
    });
  }, [active]);

  return (
    <div
      role="tablist"
      aria-label="Dashboard sections"
      className="-mx-4 flex gap-1 overflow-x-auto px-4 pb-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
    >
      {MOBILE_TABS.map((tab) => {
        const selected = tab.key === active;
        return (
          <button
            key={tab.key}
            ref={(node) => {
              refs.current[tab.key] = node;
            }}
            type="button"
            role="tab"
            aria-selected={selected}
            onClick={() => onChange(tab.key)}
            className={`min-h-11 shrink-0 whitespace-nowrap rounded-full px-4 text-sm font-medium transition-colors ${
              selected
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground active:bg-secondary"
            }`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
