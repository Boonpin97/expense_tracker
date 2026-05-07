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
  Plus,
  TrendingUp,
  TrendingDown,
  Wallet,
  Target,
  LogOut,
  Loader2,
  CalendarIcon,
  Filter,
} from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Checkbox } from "@/components/ui/checkbox";
import { Calendar } from "@/components/ui/calendar";
import { endOfDay, format, startOfDay, startOfMonth, startOfYear, subDays } from "date-fns";
import { cn } from "@/lib/utils";
import type { DateRange } from "react-day-picker";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
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
      { title: "BudgetFlow â€” Expense Tracking & Budgeting Dashboard" },
      {
        name: "description",
        content:
          "Track daily, weekly, and monthly expenses, visualize spending trends, and stay on top of your budget.",
      },
    ],
  }),
  component: DashboardRoute,
});

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});
const HISTORY_START = new Date("1970-01-01T00:00:00+08:00");
const TRANSACTIONS_PAGE_SIZE = 25;

type DashboardTab = "overview" | "charts" | "budget" | "transactions";
type RangeKey = "current-month" | "30d" | "90d" | "ytd" | "custom";
type TransactionSortKey =
  | "date-desc"
  | "date-asc"
  | "category-asc"
  | "category-desc"
  | "amount-desc"
  | "amount-asc";

function colorForCategory(index: number) {
  const hue = (index * 137.508) % 360;
  const lightness = [0.6, 0.68, 0.74][index % 3];
  const chroma = [0.2, 0.16, 0.13][index % 3];
  return `oklch(${lightness} ${chroma} ${hue})`;
}

function getRange(key: RangeKey, custom?: DateRange): { from: Date; to: Date } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (key === "current-month") {
    return { from: startOfMonth(today), to: endOfDay(today) };
  }
  if (key === "30d") {
    return { from: startOfDay(subDays(today, 29)), to: endOfDay(today) };
  }
  if (key === "90d") {
    return { from: startOfDay(subDays(today, 89)), to: endOfDay(today) };
  }
  if (key === "ytd") {
    return { from: startOfYear(today), to: endOfDay(today) };
  }
  const customFrom = custom?.from ? startOfDay(custom.from) : today;
  const customTo = custom?.to ? endOfDay(custom.to) : endOfDay(custom?.from ?? today);
  return { from: customFrom, to: customTo };
}

function buildFilledDailySeries(
  transactions: DashboardTransaction[],
  from: Date,
  to: Date,
  selectedCategories: string[],
) {
  const allowedCategories = new Set(selectedCategories);
  const perDay = new Map<string, number>();

  for (const transaction of transactions) {
    if (transaction.timestamp < from || transaction.timestamp > to) {
      continue;
    }
    if (!allowedCategories.has(transaction.category)) {
      continue;
    }
    const key = startOfDay(transaction.timestamp).toISOString();
    perDay.set(key, (perDay.get(key) ?? 0) + transaction.amount);
  }

  const series: { date: string; amount: number }[] = [];
  for (
    let cursor = startOfDay(from);
    cursor <= to;
    cursor = startOfDay(new Date(cursor.getTime() + 86400000))
  ) {
    const key = cursor.toISOString();
    series.push({
      date: format(cursor, "MMM d"),
      amount: Number((perDay.get(key) ?? 0).toFixed(2)),
    });
  }
  return series;
}

function sortTransactions(transactions: DashboardTransaction[], sortKey: TransactionSortKey) {
  return [...transactions].sort((left, right) => {
    switch (sortKey) {
      case "date-desc":
        return right.timestamp.getTime() - left.timestamp.getTime();
      case "date-asc":
        return left.timestamp.getTime() - right.timestamp.getTime();
      case "category-asc":
        return (
          left.category.localeCompare(right.category) ||
          right.timestamp.getTime() - left.timestamp.getTime()
        );
      case "category-desc":
        return (
          right.category.localeCompare(left.category) ||
          right.timestamp.getTime() - left.timestamp.getTime()
        );
      case "amount-desc":
        return right.amount - left.amount || right.timestamp.getTime() - left.timestamp.getTime();
      case "amount-asc":
        return left.amount - right.amount || right.timestamp.getTime() - left.timestamp.getTime();
    }
  });
}

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
    return () => {
      active = false;
    };
  }, []);

  if (sessionState.status === "loading") {
    return <CenteredState title="Checking session" detail="Connecting to the dashboard backend." />;
  }
  if (sessionState.status === "anonymous") {
    return (
      <SignInScreen
        onSignedIn={(session) => setSessionState({ status: "authenticated", session })}
      />
    );
  }
  return (
    <DashboardShell
      session={sessionState.session}
      onSignedOut={() => setSessionState({ status: "anonymous" })}
    />
  );
}

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

function DashboardShell({
  session,
  onSignedOut,
}: {
  session: DashboardSession;
  onSignedOut: () => void;
}) {
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
      fetchDashboardTransactions({ start: HISTORY_START, end: endOfDay(now) }),
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

    return () => {
      active = false;
    };
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
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");

  const catColorMap = useMemo(() => {
    const map: Record<string, string> = {};
    categories.forEach((category, index) => {
      map[category.name] = colorForCategory(index);
    });
    return map;
  }, [categories]);

  const monthSummaries = useMemo(() => {
    const now = new Date();
    const from = startOfMonth(now);
    const to = endOfDay(now);
    const summaries: Record<string, number> = {};
    transactions
      .filter((transaction) => transaction.timestamp >= from && transaction.timestamp <= to)
      .forEach((transaction) => {
        summaries[transaction.category] =
          (summaries[transaction.category] ?? 0) + transaction.amount;
      });
    return summaries;
  }, [transactions]);

  const monthTotal = Object.values(monthSummaries).reduce((sum, value) => sum + value, 0);
  const budgetTotal = Object.values(budgets).reduce((sum, value) => sum + value, 0);
  const budgetRemaining = Math.max(budgetTotal - monthTotal, 0);

  const recentTransactions = useMemo(
    () =>
      [...transactions]
        .sort((left, right) => right.timestamp.getTime() - left.timestamp.getTime())
        .slice(0, 5),
    [transactions],
  );

  const budgetRows = useMemo(
    () =>
      categories
        .map((category, index) => {
          const spent = monthSummaries[category.name] ?? 0;
          const budget = budgets[category.name] ?? 0;
          return {
            category,
            spent,
            budget,
            ratio: budget > 0 ? spent / budget : Number.NEGATIVE_INFINITY,
            index,
          };
        })
        .sort((left, right) => {
          const leftHasBudget = left.budget > 0;
          const rightHasBudget = right.budget > 0;
          if (leftHasBudget !== rightHasBudget) {
            return leftHasBudget ? -1 : 1;
          }
          if (leftHasBudget && rightHasBudget && left.ratio !== right.ratio) {
            return right.ratio - left.ratio;
          }
          return left.index - right.index;
        }),
    [categories, monthSummaries, budgets],
  );

  const pieData = useMemo(
    () =>
      categories
        .map((category) => ({
          name: `${category.emoji} ${category.name}`,
          value: Number((monthSummaries[category.name] ?? 0).toFixed(2)),
          color: catColorMap[category.name],
        }))
        .filter((entry) => entry.value > 0),
    [categories, monthSummaries, catColorMap],
  );

  const dailyData = useMemo(() => {
    const now = new Date();
    return Array.from({ length: 7 }, (_, index) => {
      const day = subDays(now, 6 - index);
      const from = startOfDay(day);
      const to = endOfDay(day);
      const amount = transactions
        .filter((transaction) => transaction.timestamp >= from && transaction.timestamp <= to)
        .reduce((sum, transaction) => sum + transaction.amount, 0);
      return { day: format(day, "EEE"), amount: Number(amount.toFixed(2)) };
    });
  }, [transactions]);

  return (
    <div className="min-h-screen bg-secondary/40">
      <header className="border-b border-border bg-background">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 py-5 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-primary">BudgetFlow</h1>
            <p className="text-xs sm:text-sm text-muted-foreground">
              Your financial command center
            </p>
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

        <Tabs
          value={activeTab}
          onValueChange={(value) => setActiveTab(value as DashboardTab)}
          className="space-y-6"
        >
          <TabsList className="grid w-full grid-cols-2 sm:w-auto sm:grid-cols-4 sm:inline-grid">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="charts">Charts</TabsTrigger>
            <TabsTrigger value="budget">Budget</TabsTrigger>
            <TabsTrigger value="transactions">Transactions</TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <OverviewCards transactions={transactions} budgetTotal={budgetTotal} />

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent Transactions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  <CenteredListMessage label="Loading transactionsâ€¦" />
                ) : recentTransactions.length === 0 ? (
                  <CenteredListMessage label="No transactions found." />
                ) : (
                  <>
                    <div className="space-y-1">
                      {recentTransactions.map((transaction) => (
                        <div
                          key={transaction.id}
                          className="flex items-center justify-between py-3 border-b border-border last:border-0"
                        >
                          <div className="flex items-center gap-3 min-w-0">
                            <div className="h-9 w-9 rounded-full bg-secondary flex items-center justify-center shrink-0 text-base leading-none">
                              {categories.find((category) => category.name === transaction.category)
                                ?.emoji ?? "ðŸ’³"}
                            </div>
                            <div className="min-w-0">
                              <p className="font-medium text-sm truncate">{transaction.item}</p>
                              <p className="text-xs text-muted-foreground">
                                {transaction.category} Â· {format(transaction.timestamp, "MMM d")}
                              </p>
                            </div>
                          </div>
                          <p className="font-semibold text-sm shrink-0">
                            {currency.format(transaction.amount)}
                          </p>
                        </div>
                      ))}
                    </div>
                    <div className="flex justify-center">
                      <Button variant="ghost" onClick={() => setActiveTab("transactions")}>
                        Show all
                      </Button>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="charts" className="space-y-6">
            <TrendCard
              transactions={transactions}
              categories={categories}
              catColorMap={catColorMap}
              loading={loading}
            />

            <div className="grid lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Daily Spending (this week)</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-72 w-full">
                    {loading ? (
                      <CenteredChartMessage label="Loadingâ€¦" />
                    ) : (
                      <ResponsiveContainer>
                        <BarChart data={dailyData}>
                          <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.92 0.01 256)" />
                          <XAxis dataKey="day" stroke="oklch(0.55 0.04 257)" fontSize={12} />
                          <YAxis
                            stroke="oklch(0.55 0.04 257)"
                            fontSize={12}
                            tickFormatter={(value) => currency.format(Number(value))}
                          />
                          <Tooltip
                            contentStyle={{
                              borderRadius: 8,
                              border: "1px solid oklch(0.92 0.01 256)",
                            }}
                            formatter={(value: number) => currency.format(value)}
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
                      <CenteredChartMessage
                        label={loading ? "Loadingâ€¦" : "No data for this month."}
                      />
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
                            {pieData.map((entry) => (
                              <Cell key={entry.name} fill={entry.color} />
                            ))}
                          </Pie>
                          <Tooltip
                            contentStyle={{
                              borderRadius: 8,
                              border: "1px solid oklch(0.92 0.01 256)",
                            }}
                            formatter={(value: number) => currency.format(value)}
                          />
                          <Legend
                            layout="vertical"
                            align="right"
                            verticalAlign="middle"
                            wrapperStyle={{ fontSize: 12 }}
                            formatter={(value, entry: { payload?: { value?: number } }) => (
                              <span className="text-foreground">
                                {value}{" "}
                                <span className="text-muted-foreground">
                                  â€” {currency.format(entry?.payload?.value ?? 0)}
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

          <TabsContent value="budget" className="space-y-6">
            <div className="grid sm:grid-cols-3 gap-4">
              <StatCard
                label="Total Budget"
                value={currency.format(budgetTotal)}
                sub="Monthly limit"
                icon={Target}
                trend="down"
              />
              <StatCard
                label="Spent"
                value={currency.format(monthTotal)}
                sub={`${budgetTotal > 0 ? Math.round((monthTotal / budgetTotal) * 100) : 0}% used`}
                icon={Wallet}
                trend="up"
              />
              <StatCard
                label="Remaining"
                value={currency.format(budgetRemaining)}
                sub={`${Math.round((budgetRemaining / Math.max(budgetTotal, 1)) * 100)}% left`}
                icon={TrendingDown}
                trend="down"
              />
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Budget by Category</CardTitle>
              </CardHeader>
              <CardContent className="space-y-5">
                {loading ? (
                  <CenteredListMessage label="Loading budget dataâ€¦" />
                ) : categories.length === 0 ? (
                  <CenteredListMessage label="No categories found." />
                ) : (
                  budgetRows.map(({ category, spent, budget }) => {
                    const pct = budget > 0 ? Math.min((spent / budget) * 100, 100) : 0;
                    const over = budget > 0 && spent > budget;
                    return (
                      <div key={category.name} className="space-y-2">
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex items-center gap-2 min-w-0">
                            <div className="h-8 w-8 rounded-md bg-secondary flex items-center justify-center shrink-0 text-sm leading-none">
                              {category.emoji}
                            </div>
                            <p className="font-medium text-sm">{category.name}</p>
                          </div>
                          <p
                            className={`text-sm font-semibold shrink-0 ${over ? "text-destructive" : "text-foreground"}`}
                          >
                            {currency.format(spent)}{" "}
                            <span className="text-muted-foreground font-normal">
                              {budget > 0 ? `/ ${currency.format(budget)}` : ""}
                            </span>
                          </p>
                        </div>
                        <Progress
                          value={pct}
                          className={over ? "[&>div]:bg-destructive" : "[&>div]:bg-accent"}
                        />
                      </div>
                    );
                  })
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="transactions" className="space-y-6">
            <TransactionsTab
              transactions={transactions}
              categories={categories}
              catColorMap={catColorMap}
              loading={loading}
            />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

function OverviewCards({
  transactions,
  budgetTotal,
}: {
  transactions: DashboardTransaction[];
  budgetTotal: number;
}) {
  const [visible, setVisible] = useState(["today", "week", "month", "budget"]);

  const stats = useMemo(() => {
    const now = new Date();
    const end = endOfDay(now);
    const sumFrom = (from: Date) =>
      transactions
        .filter((transaction) => transaction.timestamp >= from && transaction.timestamp <= end)
        .reduce((sum, transaction) => sum + transaction.amount, 0);
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

  const statCards = [
    {
      key: "today",
      label: "Today",
      value: currency.format(stats.todayTotal),
      sub: "Spent today",
      icon: Wallet,
      trend: "up" as const,
    },
    {
      key: "week",
      label: "This Week",
      value: currency.format(stats.weekTotal),
      sub: "Last 7 days",
      icon: TrendingDown,
      trend: "down" as const,
    },
    {
      key: "month",
      label: "This Month",
      value: currency.format(stats.monthTotal),
      sub: "Current month",
      icon: TrendingUp,
      trend: "up" as const,
    },
    {
      key: "budget",
      label: "Budget Left",
      value: currency.format(stats.remaining),
      sub:
        budgetTotal > 0
          ? `${Math.round((stats.remaining / budgetTotal) * 100)}% left`
          : "No budget set",
      icon: Target,
      trend: "down" as const,
    },
    {
      key: "30d",
      label: "Last 30 Days",
      value: currency.format(stats.d30Total),
      sub: "Rolling 30 days",
      icon: TrendingDown,
      trend: "down" as const,
    },
    {
      key: "90d",
      label: "Last 90 Days",
      value: currency.format(stats.d90Total),
      sub: "Rolling 90 days",
      icon: TrendingUp,
      trend: "up" as const,
    },
    {
      key: "ytd",
      label: "Year to Date",
      value: currency.format(stats.ytdTotal),
      sub: "This year",
      icon: TrendingUp,
      trend: "up" as const,
    },
  ];

  const cards = statCards.filter((card) => visible.includes(card.key));
  const toggle = (key: string) =>
    setVisible((prev) =>
      prev.includes(key) ? prev.filter((value) => value !== key) : [...prev, key],
    );

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
              {statCards.map((card) => (
                <label key={card.key} className="flex items-center gap-2 text-sm cursor-pointer">
                  <Checkbox
                    checked={visible.includes(card.key)}
                    onCheckedChange={() => toggle(card.key)}
                  />
                  {card.label}
                </label>
              ))}
            </div>
          </PopoverContent>
        </Popover>
      </div>
      {cards.length > 0 ? (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          {cards.map((card) => (
            <StatCard
              key={card.key}
              label={card.label}
              value={card.value}
              sub={card.sub}
              icon={card.icon}
              trend={card.trend}
            />
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground text-center py-8">No cards selected.</p>
      )}
    </div>
  );
}

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
    setSelected(categories.map((category) => category.name));
  }, [categories]);

  const { from, to } = useMemo(() => getRange(rangeKey, custom), [rangeKey, custom]);

  const data = useMemo(
    () => buildFilledDailySeries(transactions, from, to, selected),
    [transactions, from, to, selected],
  );

  const toggleCategory = (categoryName: string) => {
    setSelected((prev) =>
      prev.includes(categoryName)
        ? prev.filter((value) => value !== categoryName)
        : [...prev, categoryName],
    );
  };

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 space-y-0">
        <CardTitle className="text-lg">Spending Trend</CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          <RangeSelector
            rangeKey={rangeKey}
            custom={custom}
            onRangeKeyChange={setRangeKey}
            onCustomChange={setCustom}
          />
          <CategoryFilterPopover
            categories={categories}
            selected={selected}
            catColorMap={catColorMap}
            onToggle={toggleCategory}
          />
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-96 w-full">
          {loading ? (
            <CenteredChartMessage label="Loading trend dataâ€¦" />
          ) : selected.length === 0 ? (
            <CenteredChartMessage label="Select at least one category." />
          ) : (
            <ResponsiveContainer>
              <LineChart data={data}>
                <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.92 0.01 256)" />
                <XAxis dataKey="date" stroke="oklch(0.55 0.04 257)" fontSize={12} minTickGap={24} />
                <YAxis
                  stroke="oklch(0.55 0.04 257)"
                  fontSize={12}
                  tickFormatter={(value) => currency.format(Number(value))}
                />
                <Tooltip
                  contentStyle={{ borderRadius: 8, border: "1px solid oklch(0.92 0.01 256)" }}
                  formatter={(value: number) => currency.format(value)}
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

function TransactionsTab({
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
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [sortKey, setSortKey] = useState<TransactionSortKey>("date-desc");
  const [page, setPage] = useState(1);

  useEffect(() => {
    setSelectedCategories(categories.map((category) => category.name));
  }, [categories]);

  const { from, to } = useMemo(() => getRange(rangeKey, custom), [rangeKey, custom]);
  const minValue = minAmount.trim() === "" ? null : Number(minAmount);
  const maxValue = maxAmount.trim() === "" ? null : Number(maxAmount);

  const filteredTransactions = useMemo(() => {
    const selectedSet = new Set(selectedCategories);
    const filtered = transactions.filter((transaction) => {
      if (transaction.timestamp < from || transaction.timestamp > to) {
        return false;
      }
      if (!selectedSet.has(transaction.category)) {
        return false;
      }
      if (minValue !== null && !Number.isNaN(minValue) && transaction.amount < minValue) {
        return false;
      }
      if (maxValue !== null && !Number.isNaN(maxValue) && transaction.amount > maxValue) {
        return false;
      }
      return true;
    });
    return sortTransactions(filtered, sortKey);
  }, [transactions, from, to, selectedCategories, minValue, maxValue, sortKey]);

  useEffect(() => {
    setPage(1);
  }, [rangeKey, custom, selectedCategories, minAmount, maxAmount, sortKey]);

  const totalPages = Math.max(1, Math.ceil(filteredTransactions.length / TRANSACTIONS_PAGE_SIZE));

  useEffect(() => {
    if (page > totalPages) {
      setPage(totalPages);
    }
  }, [page, totalPages]);

  const pageRows = useMemo(() => {
    const startIndex = (page - 1) * TRANSACTIONS_PAGE_SIZE;
    return filteredTransactions.slice(startIndex, startIndex + TRANSACTIONS_PAGE_SIZE);
  }, [filteredTransactions, page]);

  const toggleCategory = (categoryName: string) => {
    setSelectedCategories((prev) =>
      prev.includes(categoryName)
        ? prev.filter((value) => value !== categoryName)
        : [...prev, categoryName],
    );
  };

  return (
    <Card>
      <CardHeader className="space-y-4">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <CardTitle className="text-lg">All Transactions</CardTitle>
          <div className="flex flex-wrap items-center gap-2">
            <RangeSelector
              rangeKey={rangeKey}
              custom={custom}
              onRangeKeyChange={setRangeKey}
              onCustomChange={setCustom}
            />
            <CategoryFilterPopover
              categories={categories}
              selected={selectedCategories}
              catColorMap={catColorMap}
              onToggle={toggleCategory}
            />
            <Select
              value={sortKey}
              onValueChange={(value) => setSortKey(value as TransactionSortKey)}
            >
              <SelectTrigger className="w-[170px] h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="date-desc">Date (Newest)</SelectItem>
                <SelectItem value="date-asc">Date (Oldest)</SelectItem>
                <SelectItem value="category-asc">Category (A-Z)</SelectItem>
                <SelectItem value="category-desc">Category (Z-A)</SelectItem>
                <SelectItem value="amount-desc">Amount (High-Low)</SelectItem>
                <SelectItem value="amount-asc">Amount (Low-High)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:max-w-md">
          <div className="space-y-2">
            <Label htmlFor="min-amount">Min amount</Label>
            <Input
              id="min-amount"
              inputMode="decimal"
              onChange={(event) => setMinAmount(event.target.value)}
              placeholder="0.00"
              type="number"
              value={minAmount}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="max-amount">Max amount</Label>
            <Input
              id="max-amount"
              inputMode="decimal"
              onChange={(event) => setMaxAmount(event.target.value)}
              placeholder="No limit"
              type="number"
              value={maxAmount}
            />
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <CenteredListMessage label="Loading transactionsâ€¦" />
        ) : pageRows.length === 0 ? (
          <CenteredListMessage label="No transactions found for the selected filters." />
        ) : (
          <>
            <div className="rounded-xl border border-border/70">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-[120px]">Date</TableHead>
                    <TableHead>Item</TableHead>
                    <TableHead>Category</TableHead>
                    <TableHead className="text-right">Amount</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pageRows.map((transaction) => (
                    <TableRow key={transaction.id}>
                      <TableCell className="whitespace-nowrap">
                        {format(transaction.timestamp, "MMM d, yyyy")}
                      </TableCell>
                      <TableCell className="font-medium">{transaction.item}</TableCell>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span
                            className="h-2.5 w-2.5 rounded-sm shrink-0"
                            style={{
                              background: catColorMap[transaction.category] ?? colorForCategory(0),
                            }}
                          />
                          <span className="truncate">
                            {categories.find((category) => category.name === transaction.category)
                              ?.emoji ?? "ðŸ’³"}{" "}
                            {transaction.category}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right font-semibold">
                        {currency.format(transaction.amount)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-muted-foreground">
                Showing {(page - 1) * TRANSACTIONS_PAGE_SIZE + 1}-
                {Math.min(page * TRANSACTIONS_PAGE_SIZE, filteredTransactions.length)} of{" "}
                {filteredTransactions.length}
              </p>
              <Pagination className="mx-0 w-auto justify-end">
                <PaginationContent>
                  <PaginationItem>
                    <PaginationPrevious
                      href="#"
                      aria-disabled={page === 1}
                      className={page === 1 ? "pointer-events-none opacity-50" : ""}
                      onClick={(event) => {
                        event.preventDefault();
                        if (page > 1) {
                          setPage(page - 1);
                        }
                      }}
                    />
                  </PaginationItem>
                  <PaginationItem>
                    <span className="px-3 text-sm text-muted-foreground">
                      Page {page} of {totalPages}
                    </span>
                  </PaginationItem>
                  <PaginationItem>
                    <PaginationNext
                      href="#"
                      aria-disabled={page === totalPages}
                      className={page === totalPages ? "pointer-events-none opacity-50" : ""}
                      onClick={(event) => {
                        event.preventDefault();
                        if (page < totalPages) {
                          setPage(page + 1);
                        }
                      }}
                    />
                  </PaginationItem>
                </PaginationContent>
              </Pagination>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

function RangeSelector({
  rangeKey,
  custom,
  onRangeKeyChange,
  onCustomChange,
}: {
  rangeKey: RangeKey;
  custom: DateRange | undefined;
  onRangeKeyChange: (value: RangeKey) => void;
  onCustomChange: (value: DateRange | undefined) => void;
}) {
  return (
    <>
      <Select value={rangeKey} onValueChange={(value) => onRangeKeyChange(value as RangeKey)}>
        <SelectTrigger className="w-[170px] h-9">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="current-month">Current Month</SelectItem>
          <SelectItem value="30d">Last 30 Days</SelectItem>
          <SelectItem value="90d">Last 90 Days</SelectItem>
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
              className={cn(
                "h-9 justify-start text-left font-normal",
                !custom && "text-muted-foreground",
              )}
            >
              <CalendarIcon className="mr-2 h-4 w-4" />
              {custom?.from
                ? custom.to
                  ? `${format(custom.from, "MMM d")} â€“ ${format(custom.to, "MMM d")}`
                  : format(custom.from, "MMM d")
                : "Pick dates"}
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-auto p-0" align="start">
            <Calendar
              mode="range"
              selected={custom}
              onSelect={onCustomChange}
              numberOfMonths={2}
              className={cn("p-3 pointer-events-auto")}
            />
          </PopoverContent>
        </Popover>
      )}
    </>
  );
}

function CategoryFilterPopover({
  categories,
  selected,
  catColorMap,
  onToggle,
}: {
  categories: DashboardCategory[];
  selected: string[];
  catColorMap: Record<string, string>;
  onToggle: (categoryName: string) => void;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-9">
          <Filter className="mr-2 h-4 w-4" />
          Categories ({selected.length}/{categories.length})
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56" align="end">
        <div className="space-y-2">
          {categories.map((category) => (
            <label key={category.name} className="flex items-center gap-2 text-sm cursor-pointer">
              <Checkbox
                checked={selected.includes(category.name)}
                onCheckedChange={() => onToggle(category.name)}
              />
              <span
                className="h-2.5 w-2.5 rounded-sm shrink-0"
                style={{ background: catColorMap[category.name] ?? colorForCategory(0) }}
              />
              {category.emoji} {category.name}
            </label>
          ))}
        </div>
      </PopoverContent>
    </Popover>
  );
}

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
            <p
              className={`text-xs mt-1 flex items-center gap-1 ${trend === "up" ? "text-destructive" : "text-accent"}`}
            >
              {trend === "up" ? (
                <TrendingUp className="h-3 w-3" />
              ) : (
                <TrendingDown className="h-3 w-3" />
              )}
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
  return (
    <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
      {label}
    </div>
  );
}

function CenteredListMessage({ label }: { label: string }) {
  return <div className="py-16 text-center text-sm text-muted-foreground">{label}</div>;
}
