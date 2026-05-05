import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Plus, TrendingUp, TrendingDown, Wallet, Target, LogOut, Loader2,
  CalendarIcon, Filter,
} from "lucide-react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Calendar } from "@/components/ui/calendar";
import { endOfDay, format, startOfDay, startOfMonth, startOfYear, subDays } from "date-fns";
import { cn } from "@/lib/utils";
import type { DateRange } from "react-day-picker";
import {
  BarChart, Bar, LineChart, Line, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import {
  DashboardApiError,
  fetchDashboardBudgets,
  fetchDashboardCategories,
  fetchDashboardSession,
  fetchDashboardTransactions,
  loginToDashboard,
  logoutFromDashboard,
  type DashboardCategory,
  type DashboardSession,
  type DashboardTransaction,
} from "@/lib/dashboard-api";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "BudgetFlow — Expense Tracking & Budgeting Dashboard" },
      { name: "description", content: "Track daily, weekly, and monthly expenses, visualize spending trends, and stay on top of your budget." },
    ],
  }),
  component: DashboardRoute,
});

const currency = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 2 });

const CAT_PALETTE = [
  "oklch(0.65 0.18 254)",
  "oklch(0.32 0.13 265)",
  "oklch(0.7 0.15 180)",
  "oklch(0.75 0.16 60)",
  "oklch(0.6 0.2 20)",
  "oklch(0.65 0.18 120)",
  "oklch(0.55 0.15 300)",
];

type RangeKey = "current-month" | "30d" | "60d" | "ytd" | "custom";

function getRange(key: RangeKey, custom?: DateRange): { from: Date; to: Date } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (key === "current-month") {
    return { from: startOfMonth(today), to: endOfDay(today) };
  }
  if (key === "30d") {
    return { from: startOfDay(subDays(today, 29)), to: endOfDay(today) };
  }
  if (key === "60d") {
    return { from: startOfDay(subDays(today, 59)), to: endOfDay(today) };
  }
  if (key === "ytd") {
    return { from: startOfYear(today), to: endOfDay(today) };
  }
  return {
    from: custom?.from ? startOfDay(custom.from) : today,
    to: custom?.to ? endOfDay(custom.to) : endOfDay(today),
  };
}

// ─── Session management ───────────────────────────────────────────────────────

type SessionState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; session: DashboardSession };

function DashboardRoute() {
  const [sessionState, setSessionState] = useState<SessionState>({ status: "loading" });

  useEffect(() => {
    let active = true;
    void fetchDashboardSession()
      .then((session) => {
        if (!active) return;
        setSessionState(session ? { status: "authenticated", session } : { status: "anonymous" });
      })
      .catch(() => {
        if (!active) return;
        setSessionState({ status: "anonymous" });
      });
    return () => { active = false; };
  }, []);

  if (sessionState.status === "loading") {
    return <CenteredState title="Checking session" detail="Connecting to the dashboard backend." />;
  }
  if (sessionState.status === "anonymous") {
    return <SignInScreen onSignedIn={(session) => setSessionState({ status: "authenticated", session })} />;
  }
  return (
    <DashboardShell
      session={sessionState.session}
      onSignedOut={() => setSessionState({ status: "anonymous" })}
    />
  );
}

// ─── Sign-in screen ───────────────────────────────────────────────────────────

function SignInScreen({ onSignedIn }: { onSignedIn: (session: DashboardSession) => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const session = await loginToDashboard(username, password);
      onSignedIn(session);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen bg-secondary/40 px-4 py-10">
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] max-w-md items-center">
        <Card className="w-full border-border/60 bg-background shadow-sm">
          <CardContent className="p-8 sm:p-10">
            <div className="flex flex-col items-center text-center">
              <img alt="BudgetFlow" className="h-14 w-14 rounded-2xl" src="/logo.png" />
              <h1 className="mt-5 text-xl font-semibold tracking-tight text-primary">BudgetFlow</h1>
              <p className="mt-1 text-sm text-muted-foreground">Sign in to continue</p>
            </div>
            <form className="mt-8 space-y-5" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <Label htmlFor="username">Username</Label>
                <Input
                  id="username"
                  autoComplete="username"
                  onChange={(e) => setUsername(e.target.value)}
                  placeholder="Enter your username"
                  required
                  value={username}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  autoComplete="current-password"
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter your password"
                  required
                  type="password"
                  value={password}
                />
              </div>
              {error ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              ) : null}
              <Button className="h-11 w-full" disabled={submitting} type="submit">
                {submitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Continue
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// ─── Data shell ───────────────────────────────────────────────────────────────

function DashboardShell({ session, onSignedOut }: { session: DashboardSession; onSignedOut: () => void }) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categories, setCategories] = useState<DashboardCategory[]>([]);
  const [budgets, setBudgets] = useState<Record<string, number>>({});
  const [transactions, setTransactions] = useState<DashboardTransaction[]>([]);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    const now = new Date();
    void Promise.all([
      fetchDashboardCategories(),
      fetchDashboardBudgets(),
      // Fetch ~365 days to cover all stat card time ranges
      fetchDashboardTransactions({ start: startOfDay(subDays(now, 365)), end: endOfDay(now) }),
    ])
      .then(([cats, buds, txns]) => {
        if (!active) return;
        setCategories(cats);
        setBudgets(buds);
        setTransactions(txns);
        setLoading(false);
      })
      .catch((caught) => {
        if (!active) return;
        const message =
          caught instanceof DashboardApiError && caught.status === 401
            ? "Session expired. Please sign in again."
            : caught instanceof Error
              ? caught.message
              : "Unable to load dashboard data.";
        setError(message);
        setLoading(false);
      });

    return () => { active = false; };
  }, [session.chatId]);

  async function handleLogout() {
    await logoutFromDashboard();
    onSignedOut();
  }

  return (
    <DashboardLayout
      session={session}
      loading={loading}
      error={error}
      categories={categories}
      budgets={budgets}
      transactions={transactions}
      onLogout={() => void handleLogout()}
    />
  );
}

// ─── Dashboard layout (restored from original) ───────────────────────────────

function DashboardLayout({
  session,
  loading,
  error,
  categories,
  budgets,
  transactions,
  onLogout,
}: {
  session: DashboardSession;
  loading: boolean;
  error: string | null;
  categories: DashboardCategory[];
  budgets: Record<string, number>;
  transactions: DashboardTransaction[];
  onLogout: () => void;
}) {
  const catColorMap = useMemo(() => {
    const m: Record<string, string> = {};
    categories.forEach((cat, i) => { m[cat.name] = CAT_PALETTE[i % CAT_PALETTE.length]; });
    return m;
  }, [categories]);

  // Current-month summaries (used for pie chart and budget tab)
  const monthSummaries = useMemo(() => {
    const now = new Date();
    const from = startOfMonth(now);
    const end = endOfDay(now);
    const m: Record<string, number> = {};
    transactions
      .filter((t) => t.timestamp >= from && t.timestamp <= end)
      .forEach((t) => { m[t.category] = (m[t.category] ?? 0) + t.amount; });
    return m;
  }, [transactions]);

  const monthTotal = Object.values(monthSummaries).reduce((s, v) => s + v, 0);
  const budgetTotal = Object.values(budgets).reduce((s, v) => s + v, 0);
  const budgetRemaining = Math.max(budgetTotal - monthTotal, 0);

  const recentTransactions = useMemo(
    () => [...transactions].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime()).slice(0, 5),
    [transactions],
  );

  const pieData = useMemo(
    () =>
      categories
        .map((cat, i) => ({
          name: `${cat.emoji} ${cat.name}`,
          value: Number((monthSummaries[cat.name] ?? 0).toFixed(2)),
          color: CAT_PALETTE[i % CAT_PALETTE.length],
        }))
        .filter((d) => d.value > 0),
    [categories, monthSummaries],
  );

  const dailyData = useMemo(() => {
    const now = new Date();
    return Array.from({ length: 7 }, (_, i) => {
      const d = subDays(now, 6 - i);
      const from = startOfDay(d);
      const to = endOfDay(d);
      const amount = transactions
        .filter((t) => t.timestamp >= from && t.timestamp <= to)
        .reduce((s, t) => s + t.amount, 0);
      return { day: format(d, "EEE"), amount: Number(amount.toFixed(2)) };
    });
  }, [transactions]);

  return (
    <div className="min-h-screen bg-secondary/40">
      <header className="border-b border-border bg-background">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary">BudgetFlow</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">Your financial command center</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden lg:block text-sm text-muted-foreground">
              Signed in as <span className="font-medium text-foreground">{session.username}</span>
            </div>
            <Button className="gap-2" size="sm" variant="outline">
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">Add Expense</span>
            </Button>
            <Button onClick={onLogout} size="sm" variant="outline">
              <LogOut className="mr-2 h-4 w-4" />
              Sign out
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6">
        {error ? (
          <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        ) : null}

        <Tabs defaultValue="overview" className="space-y-6">
          <TabsList className="grid w-full sm:w-auto grid-cols-3 sm:inline-grid">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="charts">Charts</TabsTrigger>
            <TabsTrigger value="budget">Budget</TabsTrigger>
          </TabsList>

          {/* OVERVIEW */}
          <TabsContent value="overview" className="space-y-6">
            <OverviewCards transactions={transactions} budgetTotal={budgetTotal} />

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent Transactions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-1">
                {loading ? (
                  <CenteredListMessage label="Loading transactions…" />
                ) : recentTransactions.length === 0 ? (
                  <CenteredListMessage label="No transactions found." />
                ) : (
                  recentTransactions.map((t) => (
                    <div key={t.id} className="flex items-center justify-between py-3 border-b border-border last:border-0">
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="h-9 w-9 rounded-full bg-secondary flex items-center justify-center shrink-0 text-base leading-none">
                          {categories.find((c) => c.name === t.category)?.emoji ?? "💳"}
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium text-sm truncate">{t.item}</p>
                          <p className="text-xs text-muted-foreground">{t.category} · {format(t.timestamp, "MMM d")}</p>
                        </div>
                      </div>
                      <p className="font-semibold text-sm shrink-0">{currency.format(t.amount)}</p>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* CHARTS */}
          <TabsContent value="charts" className="space-y-6">
            <TrendCard transactions={transactions} categories={categories} catColorMap={catColorMap} loading={loading} />

            <div className="grid lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Daily Spending (this week)</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-72 w-full">
                    {loading ? (
                      <CenteredChartMessage label="Loading…" />
                    ) : (
                      <ResponsiveContainer>
                        <BarChart data={dailyData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.92 0.01 256)" />
                          <XAxis dataKey="day" stroke="oklch(0.55 0.04 257)" fontSize={12} />
                          <YAxis
                            stroke="oklch(0.55 0.04 257)"
                            fontSize={12}
                            tickFormatter={(v) => currency.format(Number(v))}
                          />
                          <Tooltip
                            contentStyle={{ borderRadius: 8, border: "1px solid oklch(0.92 0.01 256)" }}
                            formatter={(v: number) => currency.format(v)}
                          />
                          <Bar dataKey="amount" fill="oklch(0.65 0.18 254)" radius={[6, 6, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">By Category</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-72 w-full">
                    {loading || pieData.length === 0 ? (
                      <CenteredChartMessage label={loading ? "Loading…" : "No data for this month."} />
                    ) : (
                      <ResponsiveContainer>
                        <PieChart>
                          <Pie
                            data={pieData}
                            dataKey="value"
                            nameKey="name"
                            innerRadius={50}
                            outerRadius={85}
                            paddingAngle={2}
                            label={({ percent }) => `${((percent ?? 0) * 100).toFixed(0)}%`}
                            labelLine={false}
                          >
                            {pieData.map((c, i) => <Cell key={i} fill={c.color} />)}
                          </Pie>
                          <Tooltip
                            contentStyle={{ borderRadius: 8, border: "1px solid oklch(0.92 0.01 256)" }}
                            formatter={(v: number) => currency.format(v)}
                          />
                          <Legend
                            layout="vertical"
                            align="right"
                            verticalAlign="middle"
                            wrapperStyle={{ fontSize: 12 }}
                            formatter={(value, entry: any) => (
                              <span className="text-foreground">
                                {value}{" "}
                                <span className="text-muted-foreground">
                                  — {currency.format(entry?.payload?.value ?? 0)}
                                </span>
                              </span>
                            )}
                          />
                        </PieChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* BUDGET */}
          <TabsContent value="budget" className="space-y-6">
            <div className="grid sm:grid-cols-3 gap-4">
              <StatCard label="Total Budget" value={currency.format(budgetTotal)} sub="Monthly limit" icon={Target} trend="down" />
              <StatCard
                label="Spent"
                value={currency.format(monthTotal)}
                sub={`${budgetTotal > 0 ? Math.round((monthTotal / budgetTotal) * 100) : 0}% used`}
                icon={Wallet}
                trend="up"
              />
              <StatCard label="Remaining" value={currency.format(budgetRemaining)} sub={`${Math.round((budgetRemaining / Math.max(budgetTotal, 1)) * 100)}% left`} icon={TrendingDown} trend="down" />
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Budget by Category</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {loading ? (
                  <CenteredListMessage label="Loading budget data…" />
                ) : categories.length === 0 ? (
                  <CenteredListMessage label="No categories found." />
                ) : (
                  categories.map((cat) => {
                    const spent = monthSummaries[cat.name] ?? 0;
                    const budget = budgets[cat.name] ?? 0;
                    const pct = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
                    const over = budget > 0 && spent > budget;
                    return (
                      <div key={cat.name} className="space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2 min-w-0">
                            <div className="h-8 w-8 rounded-md bg-secondary flex items-center justify-center shrink-0 text-sm leading-none">
                              {cat.emoji}
                            </div>
                            <p className="font-medium text-sm">{cat.name}</p>
                          </div>
                          <p className={`text-sm font-semibold shrink-0 ${over ? "text-destructive" : "text-foreground"}`}>
                            {currency.format(spent)}{" "}
                            <span className="text-muted-foreground font-normal">
                              {budget > 0 ? `/ ${currency.format(budget)}` : ""}
                            </span>
                          </p>
                        </div>
                        <Progress value={pct} className={over ? "[&>div]:bg-destructive" : "[&>div]:bg-accent"} />
                      </div>
                    );
                  })
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

// ─── Overview stat cards with Info toggle (restored from original) ────────────

function OverviewCards({ transactions, budgetTotal }: { transactions: DashboardTransaction[]; budgetTotal: number }) {
  const [visible, setVisible] = useState(["today", "week", "month", "budget"]);

  const stats = useMemo(() => {
    const now = new Date();
    const end = endOfDay(now);
    const sumFrom = (from: Date) =>
      transactions.filter((t) => t.timestamp >= from && t.timestamp <= end).reduce((s, t) => s + t.amount, 0);
    const monthTotal = sumFrom(startOfMonth(now));
    const remaining = Math.max(budgetTotal - monthTotal, 0);
    return {
      todayTotal: sumFrom(startOfDay(now)),
      weekTotal: sumFrom(startOfDay(subDays(now, 6))),
      monthTotal,
      d30Total: sumFrom(startOfDay(subDays(now, 29))),
      d90Total: sumFrom(startOfDay(subDays(now, 89))),
      ytdTotal: sumFrom(startOfYear(now)),
      remaining,
    };
  }, [transactions, budgetTotal]);

  const STAT_CARDS = [
    { key: "today", label: "Today", value: currency.format(stats.todayTotal), sub: "Spent today", icon: Wallet, trend: "up" as const },
    { key: "week", label: "This Week", value: currency.format(stats.weekTotal), sub: "Last 7 days", icon: TrendingDown, trend: "down" as const },
    { key: "month", label: "This Month", value: currency.format(stats.monthTotal), sub: "Current month", icon: TrendingUp, trend: "up" as const },
    { key: "budget", label: "Budget Left", value: currency.format(stats.remaining), sub: budgetTotal > 0 ? `${Math.round((stats.remaining / budgetTotal) * 100)}% left` : "No budget set", icon: Target, trend: "down" as const },
    { key: "30d", label: "Last 30 Days", value: currency.format(stats.d30Total), sub: "Rolling 30 days", icon: TrendingDown, trend: "down" as const },
    { key: "90d", label: "Last 90 Days", value: currency.format(stats.d90Total), sub: "Rolling 90 days", icon: TrendingUp, trend: "up" as const },
    { key: "ytd", label: "Year to Date", value: currency.format(stats.ytdTotal), sub: "This year", icon: TrendingUp, trend: "up" as const },
  ];

  const cards = STAT_CARDS.filter((c) => visible.includes(c.key));
  const toggle = (k: string) => setVisible((p) => p.includes(k) ? p.filter((x) => x !== k) : [...p, k]);

  return (
    <div className="space-y-5">
      <div className="flex justify-start">
        <Popover>
          <PopoverTrigger asChild>
            <Button variant="outline" size="sm" className="h-9 text-left">
              <Filter className="mr-2 h-4 w-4" />
              Info
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-56" align="start">
            <div className="space-y-2">
              {STAT_CARDS.map((c) => (
                <label key={c.key} className="flex items-center gap-2 text-sm cursor-pointer">
                  <Checkbox checked={visible.includes(c.key)} onCheckedChange={() => toggle(c.key)} />
                  {c.label}
                </label>
              ))}
            </div>
          </PopoverContent>
        </Popover>
      </div>
      {cards.length > 0 ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {cards.map((c) => (
            <StatCard key={c.key} label={c.label} value={c.value} sub={c.sub} icon={c.icon} trend={c.trend} />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground text-center py-8">No cards selected.</p>
      )}
    </div>
  );
}

// ─── Spending Trend card with range + category filter (restored from original) ─

function TrendCard({
  transactions,
  categories,
  catColorMap,
  loading,
}: {
  transactions: DashboardTransaction[];
  categories: DashboardCategory[];
  catColorMap: Record<string, string>;
  loading: boolean;
}) {
  const [rangeKey, setRangeKey] = useState<RangeKey>("current-month");
  const [custom, setCustom] = useState<DateRange | undefined>();
  const [selected, setSelected] = useState<string[]>([]);

  useEffect(() => {
    setSelected(categories.map((c) => c.name));
  }, [categories]);

  const { from, to } = useMemo(() => getRange(rangeKey, custom), [rangeKey, custom]);

  const data = useMemo(() => {
    const filtered = transactions.filter((t) => t.timestamp >= from && t.timestamp <= to);
    const dayMap = new Map<string, { date: Date; perCat: Record<string, number> }>();
    filtered.forEach((t) => {
      const key = format(t.timestamp, "yyyy-MM-dd");
      if (!dayMap.has(key)) dayMap.set(key, { date: startOfDay(t.timestamp), perCat: {} });
      const entry = dayMap.get(key)!;
      entry.perCat[t.category] = (entry.perCat[t.category] ?? 0) + t.amount;
    });
    return [...dayMap.values()]
      .sort((a, b) => a.date.getTime() - b.date.getTime())
      .map((d) => ({
        date: format(d.date, "MMM d"),
        amount: Number(selected.reduce((s, cat) => s + (d.perCat[cat] ?? 0), 0).toFixed(2)),
      }));
  }, [transactions, from, to, selected]);

  const toggleCat = (cat: string) =>
    setSelected((prev) => prev.includes(cat) ? prev.filter((c) => c !== cat) : [...prev, cat]);

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 space-y-0">
        <CardTitle className="text-lg">Spending Trend</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <Select value={rangeKey} onValueChange={(v) => setRangeKey(v as RangeKey)}>
            <SelectTrigger className="w-[170px] h-9">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="current-month">Current Month</SelectItem>
              <SelectItem value="30d">Last 30 Days</SelectItem>
              <SelectItem value="60d">Last 60 Days</SelectItem>
              <SelectItem value="ytd">Year to Date</SelectItem>
              <SelectItem value="custom">Custom Range</SelectItem>
            </SelectContent>
          </Select>

          {rangeKey === "custom" && (
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className={cn("h-9 justify-start text-left font-normal", !custom && "text-muted-foreground")}
                >
                  <CalendarIcon className="mr-2 h-4 w-4" />
                  {custom?.from
                    ? custom.to
                      ? `${format(custom.from, "MMM d")} – ${format(custom.to, "MMM d")}`
                      : format(custom.from, "MMM d")
                    : "Pick dates"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="range"
                  selected={custom}
                  onSelect={setCustom}
                  numberOfMonths={2}
                  className={cn("p-3 pointer-events-auto")}
                />
              </PopoverContent>
            </Popover>
          )}

          <Popover>
            <PopoverTrigger asChild>
              <Button variant="outline" size="sm" className="h-9">
                <Filter className="mr-2 h-4 w-4" />
                Categories ({selected.length}/{categories.length})
              </Button>
            </PopoverTrigger>
            <PopoverContent className="w-56" align="end">
              <div className="space-y-2">
                {categories.map((cat) => (
                  <label key={cat.name} className="flex items-center gap-2 text-sm cursor-pointer">
                    <Checkbox
                      checked={selected.includes(cat.name)}
                      onCheckedChange={() => toggleCat(cat.name)}
                    />
                    <span
                      className="h-2.5 w-2.5 rounded-sm shrink-0"
                      style={{ background: catColorMap[cat.name] ?? CAT_PALETTE[0] }}
                    />
                    {cat.emoji} {cat.name}
                  </label>
                ))}
              </div>
            </PopoverContent>
          </Popover>
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-96 w-full">
          {loading ? (
            <CenteredChartMessage label="Loading trend data…" />
          ) : data.length === 0 ? (
            <CenteredChartMessage label="No transactions in this range." />
          ) : (
            <ResponsiveContainer>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.92 0.01 256)" />
                <XAxis dataKey="date" stroke="oklch(0.55 0.04 257)" fontSize={12} minTickGap={24} />
                <YAxis
                  stroke="oklch(0.55 0.04 257)"
                  fontSize={12}
                  tickFormatter={(v) => currency.format(Number(v))}
                />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: "1px solid oklch(0.92 0.01 256)" }}
                  formatter={(v: number) => currency.format(v)}
                />
                <Line
                  type="linear"
                  dataKey="amount"
                  stroke="oklch(0.32 0.13 265)"
                  strokeWidth={2.5}
                  dot={{ r: 3, fill: "oklch(0.32 0.13 265)" }}
                  activeDot={{ r: 5 }}
                />
              </LineChart>
            </ResponsiveContainer>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ─── Shared components ────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  sub,
  icon: Icon,
  trend,
}: {
  label: string;
  value: string;
  sub: string;
  icon: React.ComponentType<{ className?: string }>;
  trend?: "up" | "down";
}) {
  return (
    <Card className="border-border/60">
      <CardContent className="p-5">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{label}</p>
            <p className="text-2xl font-bold mt-1 text-foreground">{value}</p>
            <p className={`text-xs mt-1 flex items-center gap-1 ${trend === "up" ? "text-destructive" : "text-accent"}`}>
              {trend === "up" ? <TrendingUp className="h-3 w-3" /> : <TrendingDown className="h-3 w-3" />}
              {sub}
            </p>
          </div>
          <div className="h-10 w-10 rounded-lg bg-accent/10 flex items-center justify-center text-accent">
            <Icon className="h-5 w-5" />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function CenteredState({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-secondary/30 px-4">
      <Card className="w-full max-w-md border-border/70 bg-background/95">
        <CardContent className="flex flex-col items-center gap-4 p-10 text-center">
          <Loader2 className="h-8 w-8 animate-spin text-foreground" />
          <div>
            <h2 className="text-xl font-semibold tracking-tight text-foreground">{title}</h2>
            <p className="mt-2 text-sm text-muted-foreground">{detail}</p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CenteredChartMessage({ label }: { label: string }) {
  return <div className="flex h-full items-center justify-center text-sm text-muted-foreground">{label}</div>;
}

function CenteredListMessage({ label }: { label: string }) {
  return <div className="py-16 text-center text-sm text-muted-foreground">{label}</div>;
}
