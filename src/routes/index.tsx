import { createFileRoute } from "@tanstack/react-router";
import { Fragment, useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useIsMobile } from "@/hooks/use-mobile";
import { MobileLayout } from "@/components/mobile/MobileLayout";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  TrendingUp,
  TrendingDown,
  Wallet,
  Target,
  LogOut,
  Loader2,
  CalendarIcon,
  Filter,
  ListFilter,
  Pencil,
  Plus,
  Repeat2,
  Trash2,
  ChevronUp,
  ChevronDown,
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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  createDashboardCategory,
  createDashboardGoal,
  createDashboardInflow,
  createDashboardProject,
  createDashboardTransaction,
  deleteDashboardBudget,
  deleteDashboardCategory,
  deleteDashboardGoal,
  deleteDashboardInflow,
  deleteDashboardPlan,
  deleteDashboardProject,
  deleteDashboardTransaction,
  fetchDashboardBudgets,
  fetchDashboardCategories,
  fetchDashboardGoals,
  fetchDashboardInflows,
  fetchDashboardPlans,
  fetchDashboardPreferences,
  fetchDashboardProjects,
  fetchDashboardSession,
  fetchDashboardTransactions,
  loginToDashboard,
  logoutFromDashboard,
  moveDashboardCategory,
  moveDashboardGoal,
  moveDashboardProject,
  updateDashboardBudget,
  updateDashboardCategory,
  updateDashboardGoal,
  updateDashboardPreferences,
  updateDashboardPlan,
  updateDashboardProject,
  updateDashboardTransaction,
  type DashboardCategory,
  type DashboardGoal,
  type DashboardInflow,
  type DashboardPaymentType,
  type DashboardPreferences,
  type DashboardPlan,
  type DashboardProject,
  type DashboardSession,
  type DashboardTransaction,
} from "@/lib/dashboard-api";
import {
  colorForCategory,
  currency,
  deadlineLabel,
  formatDateTimeInputValue,
} from "@/lib/dashboard-format";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "BudgetFlow - Expense Tracking & Budgeting Dashboard" },
      {
        name: "description",
        content:
          "Track daily, weekly, and monthly expenses, visualize spending trends, and stay on top of your budget.",
      },
    ],
  }),
  component: DashboardRoute,
});

const HISTORY_START = new Date("1970-01-01T00:00:00+08:00");
const TRANSACTIONS_PAGE_SIZE = 25;

type DashboardTab =
  | "overview"
  | "charts"
  | "budget"
  | "transactions"
  | "income"
  | "goals"
  | "projects"
  | "plans";
type RangeKey = "today" | "yesterday" | "weekly" | "current-month" | "30d" | "ytd" | "custom";
type TxnJump = {
  category: string | null;
  rangeKey: RangeKey;
  custom?: DateRange;
  version: number;
};
type TransactionSortKey =
  | "date-desc"
  | "date-asc"
  | "category-asc"
  | "category-desc"
  | "amount-desc"
  | "amount-asc";



function getRange(key: RangeKey, custom?: DateRange): { from: Date; to: Date } {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  if (key === "today") {
    return { from: startOfDay(today), to: endOfDay(today) };
  }
  if (key === "yesterday") {
    const yesterday = subDays(today, 1);
    return { from: startOfDay(yesterday), to: endOfDay(yesterday) };
  }
  if (key === "weekly") {
    return { from: startOfDay(subDays(today, 6)), to: endOfDay(today) };
  }
  if (key === "current-month") {
    return { from: startOfMonth(today), to: endOfDay(today) };
  }
  if (key === "30d") {
    return { from: startOfDay(subDays(today, 29)), to: endOfDay(today) };
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

  const series: { date: string; isoDate: string; amount: number }[] = [];
  for (
    let cursor = startOfDay(from);
    cursor <= to;
    cursor = startOfDay(new Date(cursor.getTime() + 86400000))
  ) {
    const key = cursor.toISOString();
    series.push({
      date: format(cursor, "MMM d"),
      isoDate: key,
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
  const isMobile = useIsMobile();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [categories, setCategories] = useState<DashboardCategory[]>([]);
  const [budgets, setBudgets] = useState<Record<string, number>>({});
  const [transactions, setTransactions] = useState<DashboardTransaction[]>([]);
  const [inflows, setInflows] = useState<DashboardInflow[]>([]);
  const [goals, setGoals] = useState<DashboardGoal[]>([]);
  const [projects, setProjects] = useState<DashboardProject[]>([]);
  const [plans, setPlans] = useState<DashboardPlan[]>([]);
  const [preferences, setPreferences] = useState<DashboardPreferences>({
    overviewVisibleCards: [],
  });

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    const now = new Date();
    void Promise.all([
      fetchDashboardCategories(),
      fetchDashboardBudgets(),
      fetchDashboardTransactions({ start: HISTORY_START, end: endOfDay(now) }),
      fetchDashboardInflows({ start: HISTORY_START, end: endOfDay(now) }),
      fetchDashboardGoals(),
      fetchDashboardProjects(),
      fetchDashboardPlans(),
      fetchDashboardPreferences(),
    ])
      .then(([cats, buds, txns, infs, gls, prjs, pls, prefs]) => {
        if (!active) return;
        setCategories(cats);
        setBudgets(buds);
        setTransactions(txns);
        setInflows(infs);
        setGoals(gls);
        setProjects(prjs);
        setPlans(pls);
        setPreferences(prefs);
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

  async function handleUpdateTransaction(
    transactionId: string,
    payload: {
      item: string;
      amount: number;
      category: string;
      timestamp: Date;
    },
  ) {
    await updateDashboardTransaction(transactionId, payload);
    setTransactions((current) =>
      current.map((transaction) =>
        transaction.id === transactionId ? { ...transaction, ...payload } : transaction,
      ),
    );
  }

  async function handleDeleteTransaction(transactionId: string) {
    await deleteDashboardTransaction(transactionId);
    setTransactions((current) => current.filter((transaction) => transaction.id !== transactionId));
  }

  async function handleCreateTransaction(payload: {
    item: string;
    amount: number;
    category: string;
    timestamp: Date;
    paymentType: DashboardPaymentType;
    dayOfMonth?: number;
    startDate?: string;
    numberOfMonths?: number;
    createFirstTransactionNow?: boolean;
  }) {
    await createDashboardTransaction(payload);
    const end = endOfDay(new Date(Math.max(Date.now(), payload.timestamp.getTime())));
    const [txns, pls] = await Promise.all([
      fetchDashboardTransactions({ start: HISTORY_START, end }),
      fetchDashboardPlans(),
    ]);
    setTransactions(txns);
    setPlans(pls);
  }

  const refreshGoals = useCallback(async () => {
    try {
      setGoals(await fetchDashboardGoals());
    } catch {
      // silent — stale progress remains visible until the next refresh
    }
  }, []);

  const refreshProjects = useCallback(async () => {
    try {
      setProjects(await fetchDashboardProjects());
    } catch {
      // silent — stale progress remains visible until the next refresh
    }
  }, []);

  const refreshCategories = useCallback(async () => {
    try {
      setCategories(await fetchDashboardCategories());
    } catch {
      // silent — stale data remains visible
    }
  }, []);

  async function handleCreateInflow(payload: {
    item: string;
    amount: number;
    timestamp: Date;
    goalId?: string | null;
    projectId?: string | null;
  }) {
    await createDashboardInflow(payload);
    const end = endOfDay(new Date(Math.max(Date.now(), payload.timestamp.getTime())));
    setInflows(await fetchDashboardInflows({ start: HISTORY_START, end }));
    await Promise.all([refreshGoals(), refreshProjects()]);
  }

  async function handleDeleteInflow(inflowId: string) {
    await deleteDashboardInflow(inflowId);
    setInflows((current) => current.filter((inflow) => inflow.id !== inflowId));
    await Promise.all([refreshGoals(), refreshProjects()]);
  }

  async function handleCreateGoal(payload: { name: string; targetAmount: number; emoji: string }) {
    await createDashboardGoal(payload);
    await refreshGoals();
  }

  async function handleUpdateGoal(
    goalId: string,
    payload: { name?: string; targetAmount?: number; emoji?: string },
  ) {
    await updateDashboardGoal(goalId, payload);
    await refreshGoals();
  }

  async function handleDeleteGoal(goalId: string) {
    await deleteDashboardGoal(goalId);
    setGoals((current) => current.filter((goal) => goal.id !== goalId));
  }

  async function handleMoveGoal(goalId: string, direction: -1 | 1) {
    await moveDashboardGoal(goalId, direction);
    await refreshGoals();
  }

  async function handleCreateProject(payload: {
    name: string;
    targetAmount: number;
    initialAmount: number;
    deadline: string;
    emoji: string;
  }) {
    await createDashboardProject(payload);
    await refreshProjects();
  }

  async function handleUpdateProject(
    projectId: string,
    payload: {
      name?: string;
      targetAmount?: number;
      initialAmount?: number;
      deadline?: string;
      emoji?: string;
    },
  ) {
    await updateDashboardProject(projectId, payload);
    await refreshProjects();
  }

  async function handleDeleteProject(projectId: string) {
    await deleteDashboardProject(projectId);
    setProjects((current) => current.filter((project) => project.id !== projectId));
  }

  async function handleMoveProject(projectId: string, direction: -1 | 1) {
    await moveDashboardProject(projectId, direction);
    await refreshProjects();
  }

  async function handleCreateCategory(payload: { name: string; emoji: string }) {
    await createDashboardCategory(payload);
    await refreshCategories();
  }

  async function handleUpdateCategory(categoryName: string, payload: { name: string; emoji: string }) {
    await updateDashboardCategory(categoryName, payload);
    await refreshCategories();
  }

  async function handleDeleteCategory(categoryName: string) {
    await deleteDashboardCategory(categoryName);
    await refreshCategories();
  }

  async function handleMoveCategory(categoryName: string, direction: -1 | 1) {
    await moveDashboardCategory(categoryName, direction);
    await refreshCategories();
  }

  const refreshBudgets = useCallback(async () => {
    try {
      const buds = await fetchDashboardBudgets();
      setBudgets(buds);
    } catch {
      // silent — stale data remains visible
    }
  }, []);

  async function handleUpdatePlan(
    planId: string,
    payload: {
      item?: string;
      category?: string;
      dayOfMonth?: number;
      startDate?: string;
      amount?: number;
      totalAmount?: number;
      installmentCount?: number;
    },
  ) {
    await updateDashboardPlan(planId, payload);
    setPlans(await fetchDashboardPlans());
  }

  async function handleDeletePlan(planId: string, mode: "future" | "all") {
    await deleteDashboardPlan(planId, mode);
    setPlans((current) => current.filter((plan) => plan.id !== planId));
  }

  async function handleUpdatePreferences(next: DashboardPreferences) {
    setPreferences(next);
    await updateDashboardPreferences({
      overviewVisibleCards: next.overviewVisibleCards,
    });
  }

  const layoutProps = {
    session,
    loading,
    error,
    categories,
    budgets,
    transactions,
    inflows,
    goals,
    projects,
    plans,
    preferences,
    onDeleteTransaction: handleDeleteTransaction,
    onLogout: () => void handleLogout(),
    onUpdateTransaction: handleUpdateTransaction,
    onCreateTransaction: handleCreateTransaction,
    onCreateInflow: handleCreateInflow,
    onDeleteInflow: handleDeleteInflow,
    onRefreshBudgets: refreshBudgets,
    onUpdatePlan: handleUpdatePlan,
    onDeletePlan: handleDeletePlan,
    onUpdatePreferences: handleUpdatePreferences,
    onCreateGoal: handleCreateGoal,
    onUpdateGoal: handleUpdateGoal,
    onDeleteGoal: handleDeleteGoal,
    onMoveGoal: handleMoveGoal,
    onCreateProject: handleCreateProject,
    onUpdateProject: handleUpdateProject,
    onDeleteProject: handleDeleteProject,
    onMoveProject: handleMoveProject,
    onCreateCategory: handleCreateCategory,
    onUpdateCategory: handleUpdateCategory,
    onDeleteCategory: handleDeleteCategory,
    onMoveCategory: handleMoveCategory,
  };

  // Separate presentation trees; DashboardShell above stays the single
  // owner of data fetching and every mutation handler.
  if (isMobile) {
    return <MobileLayout {...layoutProps} />;
  }

  return (
    <DashboardLayout
      session={session}
      loading={loading}
      error={error}
      categories={categories}
      budgets={budgets}
      transactions={transactions}
      inflows={inflows}
      goals={goals}
      projects={projects}
      plans={plans}
      preferences={preferences}
      onDeleteTransaction={handleDeleteTransaction}
      onLogout={() => void handleLogout()}
      onUpdateTransaction={handleUpdateTransaction}
      onCreateTransaction={handleCreateTransaction}
      onCreateInflow={handleCreateInflow}
      onDeleteInflow={handleDeleteInflow}
      onRefreshBudgets={refreshBudgets}
      onUpdatePlan={handleUpdatePlan}
      onDeletePlan={handleDeletePlan}
      onUpdatePreferences={handleUpdatePreferences}
      onCreateGoal={handleCreateGoal}
      onUpdateGoal={handleUpdateGoal}
      onDeleteGoal={handleDeleteGoal}
      onMoveGoal={handleMoveGoal}
      onCreateProject={handleCreateProject}
      onUpdateProject={handleUpdateProject}
      onDeleteProject={handleDeleteProject}
      onMoveProject={handleMoveProject}
      onCreateCategory={handleCreateCategory}
      onUpdateCategory={handleUpdateCategory}
      onDeleteCategory={handleDeleteCategory}
      onMoveCategory={handleMoveCategory}
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
  inflows,
  goals,
  projects,
  plans,
  preferences,
  onDeleteTransaction,
  onLogout,
  onUpdateTransaction,
  onCreateTransaction,
  onCreateInflow,
  onDeleteInflow,
  onRefreshBudgets,
  onUpdatePlan,
  onDeletePlan,
  onUpdatePreferences,
  onCreateGoal,
  onUpdateGoal,
  onDeleteGoal,
  onMoveGoal,
  onCreateProject,
  onUpdateProject,
  onDeleteProject,
  onMoveProject,
  onCreateCategory,
  onUpdateCategory,
  onDeleteCategory,
  onMoveCategory,
}: {
  session: DashboardSession;
  loading: boolean;
  error: string | null;
  categories: DashboardCategory[];
  budgets: Record<string, number>;
  transactions: DashboardTransaction[];
  inflows: DashboardInflow[];
  goals: DashboardGoal[];
  projects: DashboardProject[];
  plans: DashboardPlan[];
  preferences: DashboardPreferences;
  onDeleteTransaction: (transactionId: string) => Promise<void>;
  onLogout: () => void;
  onUpdateTransaction: (
    transactionId: string,
    payload: {
      item: string;
      amount: number;
      category: string;
      timestamp: Date;
    },
  ) => Promise<void>;
  onCreateTransaction: (payload: {
    item: string;
    amount: number;
    category: string;
    timestamp: Date;
    paymentType: DashboardPaymentType;
    dayOfMonth?: number;
    startDate?: string;
    numberOfMonths?: number;
    createFirstTransactionNow?: boolean;
  }) => Promise<void>;
  onCreateInflow: (payload: {
    item: string;
    amount: number;
    timestamp: Date;
    goalId?: string | null;
    projectId?: string | null;
  }) => Promise<void>;
  onDeleteInflow: (inflowId: string) => Promise<void>;
  onRefreshBudgets: () => Promise<void>;
  onUpdatePlan: (
    planId: string,
    payload: {
      item?: string;
      category?: string;
      dayOfMonth?: number;
      startDate?: string;
      amount?: number;
      totalAmount?: number;
      installmentCount?: number;
    },
  ) => Promise<void>;
  onDeletePlan: (planId: string, mode: "future" | "all") => Promise<void>;
  onUpdatePreferences: (next: DashboardPreferences) => Promise<void>;
  onCreateGoal: (payload: { name: string; targetAmount: number; emoji: string }) => Promise<void>;
  onUpdateGoal: (
    goalId: string,
    payload: { name?: string; targetAmount?: number; emoji?: string },
  ) => Promise<void>;
  onDeleteGoal: (goalId: string) => Promise<void>;
  onMoveGoal: (goalId: string, direction: -1 | 1) => Promise<void>;
  onCreateProject: (payload: {
    name: string;
    targetAmount: number;
    initialAmount: number;
    deadline: string;
    emoji: string;
  }) => Promise<void>;
  onUpdateProject: (
    projectId: string,
    payload: {
      name?: string;
      targetAmount?: number;
      initialAmount?: number;
      deadline?: string;
      emoji?: string;
    },
  ) => Promise<void>;
  onDeleteProject: (projectId: string) => Promise<void>;
  onMoveProject: (projectId: string, direction: -1 | 1) => Promise<void>;
  onCreateCategory: (payload: { name: string; emoji: string }) => Promise<void>;
  onUpdateCategory: (categoryName: string, payload: { name: string; emoji: string }) => Promise<void>;
  onDeleteCategory: (categoryName: string) => Promise<void>;
  onMoveCategory: (categoryName: string, direction: -1 | 1) => Promise<void>;
}) {
  const [activeTab, setActiveTab] = useState<DashboardTab>("overview");
  const [visibleOverviewCards, setVisibleOverviewCards] = useState<string[]>([]);
  const [txnJump, setTxnJump] = useState<TxnJump | null>(null);
  const [editingBudgetCategory, setEditingBudgetCategory] = useState<string | null>(null);
  const [editingBudgetAmount, setEditingBudgetAmount] = useState("");
  const [savingBudget, setSavingBudget] = useState(false);
  const [deletingBudgetCategory, setDeletingBudgetCategory] = useState<string | null>(null);
  const [budgetActionError, setBudgetActionError] = useState<string | null>(null);
  const [addTransactionOpen, setAddTransactionOpen] = useState(false);
  const [addInflowOpen, setAddInflowOpen] = useState(false);
  const [newInflowItem, setNewInflowItem] = useState("");
  const [newInflowAmount, setNewInflowAmount] = useState("");
  const [newInflowTimestamp, setNewInflowTimestamp] = useState(formatDateTimeInputValue(new Date()));
  // Goal and project are independent: income can count toward both at once, matching the bot.
  const [newInflowGoal, setNewInflowGoal] = useState("none");
  const [newInflowProject, setNewInflowProject] = useState("none");
  const [creatingInflow, setCreatingInflow] = useState(false);
  const [createInflowError, setCreateInflowError] = useState<string | null>(null);
  const [newItem, setNewItem] = useState("");
  const [newCategory, setNewCategory] = useState("");
  const [newAmount, setNewAmount] = useState("");
  const [newTimestamp, setNewTimestamp] = useState(formatDateTimeInputValue(new Date()));
  const [newPaymentType, setNewPaymentType] = useState<DashboardPaymentType>("one_time");
  const [newStartDate, setNewStartDate] = useState("");
  const [newInstallmentCount, setNewInstallmentCount] = useState("");
  const [createFirstTransactionNow, setCreateFirstTransactionNow] = useState(true);
  const [creatingTransaction, setCreatingTransaction] = useState(false);
  const [createTransactionError, setCreateTransactionError] = useState<string | null>(null);
  const [editingPlanId, setEditingPlanId] = useState<string | null>(null);
  const [planEditItem, setPlanEditItem] = useState("");
  const [planEditCategory, setPlanEditCategory] = useState("");
  const [planEditStartDate, setPlanEditStartDate] = useState("");
  const [planEditAmount, setPlanEditAmount] = useState("");
  const [planEditMonths, setPlanEditMonths] = useState("");
  const [savingPlanEdit, setSavingPlanEdit] = useState(false);
  const [planEditError, setPlanEditError] = useState<string | null>(null);

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

  const budgetTotal = budgetRows.reduce((sum, row) => sum + row.budget, 0);
  const budgetSpentTotal = budgetRows.reduce((sum, row) => sum + (row.budget > 0 ? row.spent : 0), 0);
  const budgetRemaining = Math.max(budgetTotal - budgetSpentTotal, 0);

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
      return { day: format(day, "EEE"), date: day, amount: Number(amount.toFixed(2)) };
    });
  }, [transactions]);

  useEffect(() => {
    setVisibleOverviewCards(preferences.overviewVisibleCards);
  }, [preferences]);

  const editingPlan = useMemo(
    () => plans.find((plan) => plan.id === editingPlanId) ?? null,
    [plans, editingPlanId],
  );

  function resetAddTransactionForm() {
    setNewItem("");
    setNewCategory(categories[0]?.name ?? "");
    setNewAmount("");
    setNewTimestamp(formatDateTimeInputValue(new Date()));
    setNewPaymentType("one_time");
    setNewStartDate("");
    setNewInstallmentCount("");
    setCreateFirstTransactionNow(true);
    setCreateTransactionError(null);
  }

  function openAddTransactionDialog() {
    resetAddTransactionForm();
    setAddTransactionOpen(true);
  }

  function closeAddTransactionDialog() {
    if (creatingTransaction) return;
    setAddTransactionOpen(false);
    setCreateTransactionError(null);
  }

  function openAddInflowDialog() {
    setNewInflowItem("");
    setNewInflowAmount("");
    setNewInflowTimestamp(formatDateTimeInputValue(new Date()));
    setNewInflowGoal("none");
    setNewInflowProject("none");
    setCreateInflowError(null);
    setAddInflowOpen(true);
  }

  async function handleCreateInflowSubmit() {
    setCreateInflowError(null);
    const trimmed = newInflowItem.trim();
    const parsedAmount = Number(newInflowAmount);
    if (!trimmed) { setCreateInflowError("Description is required."); return; }
    if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) { setCreateInflowError("Amount must be a positive number."); return; }
    const when = new Date(newInflowTimestamp);
    if (Number.isNaN(when.getTime())) { setCreateInflowError("Date is invalid."); return; }
    const goalId = newInflowGoal === "none" ? null : newInflowGoal;
    const projectId = newInflowProject === "none" ? null : newInflowProject;
    setCreatingInflow(true);
    try {
      await onCreateInflow({ item: trimmed, amount: parsedAmount, timestamp: when, goalId, projectId });
      setAddInflowOpen(false);
    } catch (caught) {
      setCreateInflowError(caught instanceof Error ? caught.message : "Could not add inflow.");
    } finally {
      setCreatingInflow(false);
    }
  }

  async function handleOverviewVisibleCardsChange(next: string[]) {
    setVisibleOverviewCards(next);
    try {
      await onUpdatePreferences({ overviewVisibleCards: next });
    } catch {
      // keep optimistic state visible; next reload will reconcile if needed
    }
  }

  function openPlanEditDialog(plan: DashboardPlan) {
    setPlanEditError(null);
    setEditingPlanId(plan.id);
    setPlanEditItem(plan.item);
    setPlanEditCategory(plan.category);
    setPlanEditStartDate(
      `${plan.startYear.toString().padStart(4, "0")}-${plan.startMonth
        .toString()
        .padStart(2, "0")}-${plan.dayOfMonth.toString().padStart(2, "0")}`,
    );
    setPlanEditAmount(plan.planType === "recurring" ? String(plan.amount) : String(plan.totalAmount));
    setPlanEditMonths(plan.planType === "split_payment" ? String(plan.installmentCount) : "");
  }

  function openPlanEditById(planId: string) {
    const plan = plans.find((entry) => entry.id === planId);
    if (!plan || plan.status !== "active") {
      return false;
    }
    openPlanEditDialog(plan);
    return true;
  }

  function closePlanEditDialog() {
    if (savingPlanEdit) return;
    setEditingPlanId(null);
    setPlanEditError(null);
  }

  async function handleSavePlanEdit() {
    if (!editingPlan) return;
    if (!planEditItem.trim()) {
      setPlanEditError("Name cannot be empty.");
      return;
    }

    const isSplit = editingPlan.planType === "split_payment";
    let amount: number | undefined;
    let totalAmount: number | undefined;
    let installmentCount: number | undefined;
    let startDate: string | undefined;

    if (!planEditStartDate || Number.isNaN(new Date(planEditStartDate).getTime())) {
      setPlanEditError("Start date is required.");
      return;
    }
    startDate = planEditStartDate;

    if (!isSplit) {
      amount = parseFloat(planEditAmount);
      if (Number.isNaN(amount) || amount <= 0) {
        setPlanEditError("Amount must be a positive number.");
        return;
      }
    } else {
      totalAmount = parseFloat(planEditAmount);
      installmentCount = parseInt(planEditMonths, 10);
      if (Number.isNaN(totalAmount) || totalAmount <= 0) {
        setPlanEditError("Total amount must be a positive number.");
        return;
      }
      if (Number.isNaN(installmentCount) || installmentCount < 1) {
        setPlanEditError("Months must be at least 1.");
        return;
      }
      if (installmentCount < editingPlan.currentInstallmentNumber) {
        setPlanEditError(
          `Months cannot be less than already posted installments (${editingPlan.currentInstallmentNumber}).`,
        );
        return;
      }
    }

    setSavingPlanEdit(true);
    setPlanEditError(null);
    try {
      await onUpdatePlan(editingPlan.id, {
        item: planEditItem.trim(),
        category: planEditCategory,
        ...(startDate !== undefined ? { startDate } : {}),
        ...(amount !== undefined ? { amount } : {}),
        ...(totalAmount !== undefined ? { totalAmount } : {}),
        ...(installmentCount !== undefined ? { installmentCount } : {}),
      });
      closePlanEditDialog();
    } catch (err) {
      setPlanEditError(err instanceof Error ? err.message : "Failed to update plan.");
    } finally {
      setSavingPlanEdit(false);
    }
  }

  function openEditBudget(categoryName: string, currentAmount: number) {
    setBudgetActionError(null);
    setEditingBudgetCategory(categoryName);
    setEditingBudgetAmount(currentAmount > 0 ? String(currentAmount) : "");
  }

  async function handleSaveBudgetEdit() {
    if (!editingBudgetCategory) return;
    const parsed = parseFloat(editingBudgetAmount);
    if (isNaN(parsed) || parsed <= 0) {
      setBudgetActionError("Enter a valid amount greater than 0.");
      return;
    }
    setSavingBudget(true);
    setBudgetActionError(null);
    try {
      await updateDashboardBudget(editingBudgetCategory, parsed);
      await onRefreshBudgets();
      setEditingBudgetCategory(null);
    } catch (err) {
      setBudgetActionError(err instanceof DashboardApiError ? err.message : "Failed to update budget.");
    } finally {
      setSavingBudget(false);
    }
  }

  async function handleCreateTransactionSubmit() {
    const item = newItem.trim();
    const category = newCategory.trim();
    const amount = Number(newAmount);
    const timestamp = new Date(newTimestamp);
    const needsPlanFields = newPaymentType !== "one_time";
    const isSplit = newPaymentType === "split_payment";
    const numberOfMonths = isSplit ? parseInt(newInstallmentCount, 10) : undefined;
    const startDate = needsPlanFields ? newStartDate : undefined;

    if (!item) {
      setCreateTransactionError("Item is required.");
      return;
    }
    if (!category) {
      setCreateTransactionError("Category is required.");
      return;
    }
    if (Number.isNaN(amount) || amount <= 0) {
      setCreateTransactionError(
        isSplit ? "Total amount must be a positive number." : "Amount must be a positive number.",
      );
      return;
    }
    if (Number.isNaN(timestamp.getTime())) {
      setCreateTransactionError("Date is invalid.");
      return;
    }
    if (needsPlanFields && (!startDate || Number.isNaN(new Date(startDate).getTime()))) {
      setCreateTransactionError("Start date is required.");
      return;
    }
    if (isSplit && (numberOfMonths === undefined || Number.isNaN(numberOfMonths) || numberOfMonths < 1)) {
      setCreateTransactionError("Number of months must be at least 1.");
      return;
    }

    setCreatingTransaction(true);
    setCreateTransactionError(null);
    try {
      await onCreateTransaction({
        item,
        amount,
        category,
        timestamp,
        paymentType: newPaymentType,
        ...(startDate ? { startDate } : {}),
        ...(numberOfMonths !== undefined ? { numberOfMonths } : {}),
        ...(needsPlanFields ? { createFirstTransactionNow } : {}),
      });
      setAddTransactionOpen(false);
      resetAddTransactionForm();
    } catch (caught) {
      setCreateTransactionError(
        caught instanceof Error ? caught.message : "Unable to create transaction.",
      );
    } finally {
      setCreatingTransaction(false);
    }
  }

  async function handleDeleteBudgetClick(categoryName: string) {
    if (!window.confirm(`Remove budget for "${categoryName}"?`)) return;
    setDeletingBudgetCategory(categoryName);
    try {
      await deleteDashboardBudget(categoryName);
      await onRefreshBudgets();
    } finally {
      setDeletingBudgetCategory(null);
    }
  }

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
          <TabsList className="grid w-full grid-cols-3 sm:w-auto sm:grid-cols-8 sm:inline-grid">
            <TabsTrigger value="overview">Overview</TabsTrigger>
            <TabsTrigger value="charts">Charts</TabsTrigger>
            <TabsTrigger value="budget">Budget</TabsTrigger>
            <TabsTrigger value="transactions">Expenses</TabsTrigger>
            <TabsTrigger value="income">Income</TabsTrigger>
            <TabsTrigger value="goals">Goals</TabsTrigger>
            <TabsTrigger value="projects">Long-Term Projects</TabsTrigger>
            <TabsTrigger value="plans">Subscriptions</TabsTrigger>
          </TabsList>
          <div className="flex min-h-9 items-center justify-start gap-2">
            <div className="flex items-center gap-2">
              <Button
                onClick={openAddTransactionDialog}
                size="sm"
                className="shrink-0 gap-1 bg-orange-700 hover:bg-orange-800 text-white"
              >
                <Plus className="h-4 w-4" />
                Expense
              </Button>
              <Button
                onClick={openAddInflowDialog}
                size="sm"
                className="shrink-0 gap-1 bg-emerald-700 hover:bg-emerald-800 text-white"
              >
                <Plus className="mr-1 h-4 w-4" />
                Income
              </Button>
              {activeTab === "transactions" ? (
                <OverviewInfoPopover
                  visible={visibleOverviewCards}
                  onVisibleChange={handleOverviewVisibleCardsChange}
                />
              ) : null}
            </div>
          </div>

          <TabsContent value="overview" className="space-y-6">
            <OverviewHero
              transactions={transactions}
              inflows={inflows}
              budgetTotal={budgetTotal}
            />

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">Recent Expenses</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {loading ? (
                  <CenteredListMessage label="Loading expenses..." />
                ) : recentTransactions.length === 0 ? (
                  <CenteredListMessage label="No expenses found." />
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
                                ?.emoji ?? "$"}
                            </div>
                            <div className="min-w-0">
                              <p className="font-medium text-sm truncate">{transaction.item}</p>
                              <p className="text-xs text-muted-foreground">
                                {transaction.category} - {format(transaction.timestamp, "MMM d")}
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
                        Show all expenses
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
              onPointClick={(date) => {
                setTxnJump({ category: null, rangeKey: "custom", custom: { from: date, to: date }, version: Date.now() });
                setActiveTab("transactions");
              }}
            />

            <div className="grid lg:grid-cols-2 gap-6">
              <Card>
                <CardHeader>
                  <CardTitle className="text-lg">Daily Spending (this week)</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="h-72 w-full">
                    {loading ? (
                      <CenteredChartMessage label="Loading..." />
                    ) : (
                      <ResponsiveContainer>
                        <BarChart data={dailyData} style={{ cursor: "pointer" }}>
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
                          <Bar
                            dataKey="amount"
                            fill="oklch(0.65 0.18 254)"
                            radius={[6, 6, 0, 0]}
                            onClick={(data: { date: Date }) => {
                              const day = data.date;
                              setTxnJump({
                                category: null,
                                rangeKey: "custom",
                                custom: { from: startOfDay(day), to: endOfDay(day) },
                                version: Date.now(),
                              });
                              setActiveTab("transactions");
                            }}
                          />
                        </BarChart>
                      </ResponsiveContainer>
                    )}
                  </div>
                </CardContent>
              </Card>

              <CategoryPieCard
                transactions={transactions}
                categories={categories}
                catColorMap={catColorMap}
                loading={loading}
                onSliceClick={(categoryName, rangeKey, custom) => {
                  setTxnJump({ category: categoryName, rangeKey, custom, version: Date.now() });
                  setActiveTab("transactions");
                }}
              />
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
                value={currency.format(budgetSpentTotal)}
                sub={`${budgetTotal > 0 ? Math.round((budgetSpentTotal / budgetTotal) * 100) : 0}% used`}
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
                  <CenteredListMessage label="Loading budget data..." />
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
                            <button
                              className="h-8 w-8 rounded-md bg-secondary flex items-center justify-center shrink-0 text-sm leading-none hover:bg-secondary/80 transition-colors cursor-pointer"
                              aria-label={`View ${category.name} transactions`}
                              onClick={() => {
                                setTxnJump({ category: category.name, rangeKey: "current-month", version: Date.now() });
                                setActiveTab("transactions");
                              }}
                            >
                              {category.emoji}
                            </button>
                            <p className="font-medium text-sm">{category.name}</p>
                          </div>
                          <div className="flex items-center gap-1 shrink-0">
                            <p
                              className={`text-sm font-semibold ${over ? "text-destructive" : "text-foreground"}`}
                            >
                              {currency.format(spent)}{" "}
                              <span className="text-muted-foreground font-normal">
                                {budget > 0 ? `/ ${currency.format(budget)}` : ""}
                              </span>
                            </p>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7"
                              aria-label={`Edit budget for ${category.name}`}
                              onClick={() => openEditBudget(category.name, budget)}
                            >
                              <Pencil className="h-3.5 w-3.5" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-7 w-7 text-destructive hover:text-destructive"
                              aria-label={`Delete budget for ${category.name}`}
                              disabled={deletingBudgetCategory === category.name}
                              onClick={() => void handleDeleteBudgetClick(category.name)}
                            >
                              {deletingBudgetCategory === category.name ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Trash2 className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          </div>
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
            <ExpenseSummaryCards
              transactions={transactions}
              inflows={inflows}
              budgetTotal={budgetTotal}
              visible={visibleOverviewCards}
            />
            <TransactionsTab
              transactions={transactions}
              categories={categories}
              catColorMap={catColorMap}
              loading={loading}
              onDeleteTransaction={onDeleteTransaction}
              onUpdateTransaction={onUpdateTransaction}
              onEditPlanTransaction={openPlanEditById}
              jump={txnJump}
            />
          </TabsContent>

          <TabsContent value="income" className="space-y-6">
            <IncomeTab
              inflows={inflows}
              goals={goals}
              projects={projects}
              loading={loading}
              onDeleteInflow={onDeleteInflow}
            />
          </TabsContent>

          <TabsContent value="goals" className="space-y-6">
            <GoalsTab
              goals={goals}
              loading={loading}
              onCreateGoal={onCreateGoal}
              onUpdateGoal={onUpdateGoal}
              onDeleteGoal={onDeleteGoal}
              onMoveGoal={onMoveGoal}
            />
          </TabsContent>

          <TabsContent value="projects" className="space-y-6">
            <ProjectsTab
              projects={projects}
              inflows={inflows}
              loading={loading}
              onCreateProject={onCreateProject}
              onUpdateProject={onUpdateProject}
              onDeleteProject={onDeleteProject}
              onMoveProject={onMoveProject}
            />
          </TabsContent>

          <TabsContent value="plans" className="space-y-6">
            <PlansTab
              plans={plans}
              categories={categories}
              loading={loading}
              onEditPlan={openPlanEditDialog}
              onDeletePlan={onDeletePlan}
            />
          </TabsContent>
        </Tabs>

        <Dialog
          open={addTransactionOpen}
          onOpenChange={(open) => {
            if (!open) {
              closeAddTransactionDialog();
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Transaction</DialogTitle>
              <DialogDescription>
                Create a one-time expense or set up a recurring or split payment plan.
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="new-item">Item</Label>
                <Input
                  id="new-item"
                  value={newItem}
                  onChange={(e) => setNewItem(e.target.value)}
                  disabled={creatingTransaction}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-category">Category</Label>
                <Select
                  value={newCategory}
                  onValueChange={setNewCategory}
                  disabled={creatingTransaction}
                >
                  <SelectTrigger id="new-category">
                    <SelectValue placeholder="Select a category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((category) => (
                      <SelectItem key={category.name} value={category.name}>
                        {category.emoji} {category.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-payment-type">Payment Type</Label>
                <Select
                  value={newPaymentType}
                  onValueChange={(value) => setNewPaymentType(value as DashboardPaymentType)}
                  disabled={creatingTransaction}
                >
                  <SelectTrigger id="new-payment-type">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="one_time">One-time</SelectItem>
                    <SelectItem value="split_payment">Split payment</SelectItem>
                    <SelectItem value="recurring">Recurring</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-amount">
                  {newPaymentType === "split_payment" ? "Total Amount" : "Amount"}
                </Label>
                <Input
                  id="new-amount"
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={newAmount}
                  onChange={(e) => setNewAmount(e.target.value)}
                  disabled={creatingTransaction}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-date">Date</Label>
                <Input
                  id="new-date"
                  type="datetime-local"
                  value={newTimestamp}
                  onChange={(e) => setNewTimestamp(e.target.value)}
                  disabled={creatingTransaction}
                />
              </div>
              {newPaymentType !== "one_time" ? (
                <>
                  <div className="space-y-2">
                    <Label htmlFor="new-start-date">Start Date</Label>
                    <Input
                      id="new-start-date"
                      type="date"
                      value={newStartDate}
                      onChange={(e) => setNewStartDate(e.target.value)}
                      disabled={creatingTransaction}
                    />
                  </div>
                  {newPaymentType === "split_payment" ? (
                    <>
                      <div className="space-y-2">
                        <Label htmlFor="new-installment-count">Number of Months</Label>
                        <Input
                          id="new-installment-count"
                          type="number"
                          inputMode="numeric"
                          min="1"
                          step="1"
                          value={newInstallmentCount}
                          onChange={(e) => setNewInstallmentCount(e.target.value)}
                          disabled={creatingTransaction}
                        />
                      </div>
                    </>
                  ) : null}
                  <div className="rounded-xl border border-border/70 bg-secondary/30 px-4 py-3">
                    <label className="flex items-start gap-3 text-sm">
                      <Checkbox
                        checked={createFirstTransactionNow}
                        onCheckedChange={(checked) => setCreateFirstTransactionNow(!!checked)}
                        disabled={creatingTransaction}
                      />
                      <span className="leading-5 text-muted-foreground">
                        Create the first transaction now.
                        <span className="block">
                          If unchecked, only the plan is created and the first charge will post on
                          the next assigned monthly day.
                        </span>
                      </span>
                    </label>
                  </div>
                </>
              ) : null}
              {createTransactionError ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {createTransactionError}
                </div>
              ) : null}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={closeAddTransactionDialog}
                disabled={creatingTransaction}
              >
                Cancel
              </Button>
              <Button
                onClick={() => void handleCreateTransactionSubmit()}
                disabled={creatingTransaction}
              >
                {creatingTransaction ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Create
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog open={addInflowOpen} onOpenChange={(open) => { if (!open && !creatingInflow) setAddInflowOpen(false); }}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add Income</DialogTitle>
              <DialogDescription>Record income such as salary, cashback, or a refund.</DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-2">
              <div className="space-y-2">
                <Label htmlFor="new-inflow-item">Description</Label>
                <Input
                  id="new-inflow-item"
                  placeholder="Salary"
                  value={newInflowItem}
                  onChange={(e) => setNewInflowItem(e.target.value)}
                  disabled={creatingInflow}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-inflow-amount">Amount</Label>
                <Input
                  id="new-inflow-amount"
                  type="number"
                  min="0"
                  step="0.01"
                  placeholder="2000"
                  value={newInflowAmount}
                  onChange={(e) => setNewInflowAmount(e.target.value)}
                  disabled={creatingInflow}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-inflow-timestamp">Date & Time</Label>
                <Input
                  id="new-inflow-timestamp"
                  type="datetime-local"
                  value={newInflowTimestamp}
                  onChange={(e) => setNewInflowTimestamp(e.target.value)}
                  disabled={creatingInflow}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-inflow-goal">Assign to goal (monthly)</Label>
                <Select
                  value={newInflowGoal}
                  onValueChange={setNewInflowGoal}
                  disabled={creatingInflow || goals.length === 0}
                >
                  <SelectTrigger id="new-inflow-goal">
                    <SelectValue placeholder="None" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {goals.map((goal) => (
                      <SelectItem key={goal.id} value={goal.id}>
                        {goal.emoji} {goal.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="new-inflow-project">Assign to project (long-term)</Label>
                <Select
                  value={newInflowProject}
                  onValueChange={setNewInflowProject}
                  disabled={creatingInflow || projects.length === 0}
                >
                  <SelectTrigger id="new-inflow-project">
                    <SelectValue placeholder="None" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">None</SelectItem>
                    {projects.map((project) => (
                      <SelectItem key={project.id} value={project.id}>
                        {project.emoji} {project.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Income can count toward a goal and a project at the same time.
                </p>
              </div>
              {createInflowError && <p className="text-sm text-destructive">{createInflowError}</p>}
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setAddInflowOpen(false)} disabled={creatingInflow}>
                Cancel
              </Button>
              <Button
                onClick={() => void handleCreateInflowSubmit()}
                disabled={creatingInflow}
                className="bg-emerald-500 hover:bg-emerald-600 text-white"
              >
                {creatingInflow ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Add Income
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog
          open={editingPlan !== null}
          onOpenChange={(open) => {
            if (!open) {
              closePlanEditDialog();
            }
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit plan</DialogTitle>
              <DialogDescription>
                {editingPlan?.planType === "split_payment"
                  ? "Update name, category, day, total amount, or number of months."
                  : "Update name, category, start date, or amount."}
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-2">
              <div className="space-y-2">
                <Label>Name</Label>
                <Input
                  value={planEditItem}
                  onChange={(e) => setPlanEditItem(e.target.value)}
                  disabled={savingPlanEdit}
                />
              </div>
              <div className="space-y-2">
                <Label>Category</Label>
                <Select
                  value={planEditCategory}
                  onValueChange={setPlanEditCategory}
                  disabled={savingPlanEdit}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select a category" />
                  </SelectTrigger>
                  <SelectContent>
                    {categories.map((category) => (
                      <SelectItem key={category.name} value={category.name}>
                        {category.emoji} {category.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {editingPlan ? (
                <div className="space-y-2">
                  <Label>Start Date</Label>
                  <Input
                    type="date"
                    value={planEditStartDate}
                    onChange={(e) => setPlanEditStartDate(e.target.value)}
                    disabled={savingPlanEdit}
                  />
                  <p className="text-xs text-muted-foreground">
                    Sets when the plan starts and the monthly posting day.
                  </p>
                </div>
              ) : null}
              {editingPlan?.planType === "recurring" ? (
                <div className="space-y-2">
                  <Label>Monthly Amount</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    min="0.01"
                    step="0.01"
                    value={planEditAmount}
                    onChange={(e) => setPlanEditAmount(e.target.value)}
                    disabled={savingPlanEdit}
                  />
                </div>
              ) : editingPlan ? (
                <>
                  <div className="space-y-2">
                    <Label>Total Amount</Label>
                    <Input
                      type="number"
                      inputMode="decimal"
                      min="0.01"
                      step="0.01"
                      value={planEditAmount}
                      onChange={(e) => setPlanEditAmount(e.target.value)}
                      disabled={savingPlanEdit}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Months</Label>
                    <Input
                      type="number"
                      inputMode="numeric"
                      min={Math.max(1, editingPlan.currentInstallmentNumber)}
                      step="1"
                      value={planEditMonths}
                      onChange={(e) => setPlanEditMonths(e.target.value)}
                      disabled={savingPlanEdit}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Saving a split-plan edit recalculates the schedule and rewrites this plan&apos;s
                    auto-generated charges to stay consistent.
                  </p>
                </>
              ) : null}
              {planEditError ? (
                <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {planEditError}
                </div>
              ) : null}
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={closePlanEditDialog}
                disabled={savingPlanEdit}
              >
                Cancel
              </Button>
              <Button onClick={() => void handleSavePlanEdit()} disabled={savingPlanEdit}>
                {savingPlanEdit ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
                Save
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <Dialog
          open={editingBudgetCategory !== null}
          onOpenChange={(open) => {
            if (!open && !savingBudget) setEditingBudgetCategory(null);
          }}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>
                Edit Budget
                {editingBudgetCategory
                  ? ` — ${categories.find((c) => c.name === editingBudgetCategory)?.emoji ?? ""} ${editingBudgetCategory}`
                  : ""}
              </DialogTitle>
            </DialogHeader>
            <div className="space-y-4 pt-2">
              {budgetActionError && <p className="text-sm text-destructive">{budgetActionError}</p>}
              <div className="space-y-2">
                <Label>Budget Amount</Label>
                <Input
                  type="number"
                  inputMode="decimal"
                  min="0.01"
                  step="0.01"
                  value={editingBudgetAmount}
                  onChange={(e) => setEditingBudgetAmount(e.target.value)}
                  disabled={savingBudget}
                />
              </div>
            </div>
            <DialogFooter>
              <Button
                variant="outline"
                onClick={() => setEditingBudgetCategory(null)}
                disabled={savingBudget}
              >
                Cancel
              </Button>
              <Button onClick={() => void handleSaveBudgetEdit()} disabled={savingBudget}>
                {savingBudget ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin mr-2" />
                    Saving…
                  </>
                ) : (
                  "Save"
                )}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </main>
    </div>
  );
}

function OverviewHero({
  transactions,
  inflows,
  budgetTotal,
}: {
  transactions: DashboardTransaction[];
  inflows: DashboardInflow[];
  budgetTotal: number;
}) {
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
      remaining,
    };
  }, [transactions, budgetTotal]);

  const monthIncome = useMemo(() => {
    const now = new Date();
    const from = startOfMonth(now);
    const end = endOfDay(now);
    return inflows
      .filter((inflow) => inflow.timestamp >= from && inflow.timestamp <= end)
      .reduce((sum, inflow) => sum + inflow.amount, 0);
  }, [inflows]);

  const monthNet = monthIncome - stats.monthTotal;

  return (
    <div className="space-y-5">
      {/* Net hero banner — always visible */}
      <Card className="overflow-hidden border-0 shadow-md">
        <div className="relative px-6 pt-6 pb-5 bg-gradient-to-br from-accent/10 via-accent/5 to-background">
          {/* Decorative blurred orb */}
          <div className="pointer-events-none absolute -top-6 -right-6 h-36 w-36 rounded-full blur-3xl opacity-30 bg-accent" />

          {/* Net headline */}
          <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
            Net this month
          </p>
          <p className="mt-1 text-3xl font-extrabold tracking-tight leading-none text-foreground">
            {monthNet < 0 ? "-" : "+"}
            {currency.format(Math.abs(monthNet))}
          </p>

          {/* Expenses / Inflow pills */}
          <div className="mt-5 flex flex-col gap-2 sm:flex-row sm:gap-4">
            {/* Expenses pill */}
            <div className="flex flex-1 items-center gap-3 rounded-xl border border-border/50 bg-background/60 px-4 py-3 backdrop-blur-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-destructive/10">
                <TrendingDown className="h-4 w-4 text-destructive" />
              </div>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">Expenses</p>
                <p className="text-lg font-bold text-destructive leading-tight">
                  -{currency.format(stats.monthTotal)}
                </p>
              </div>
            </div>

            {/* Inflow pill */}
            <div className="flex flex-1 items-center gap-3 rounded-xl border border-border/50 bg-background/60 px-4 py-3 backdrop-blur-sm">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-500/10">
                <TrendingUp className="h-4 w-4 text-emerald-500" />
              </div>
              <div className="min-w-0">
                <p className="text-xs text-muted-foreground">Inflow</p>
                <p className="text-lg font-bold text-emerald-500 leading-tight">
                  +{currency.format(monthIncome)}
                </p>
              </div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

function ExpenseSummaryCards({
  transactions,
  inflows,
  budgetTotal,
  visible,
}: {
  transactions: DashboardTransaction[];
  inflows: DashboardInflow[];
  budgetTotal: number;
  visible: string[];
}) {
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

  const monthIncome = useMemo(() => {
    const now = new Date();
    const from = startOfMonth(now);
    const end = endOfDay(now);
    return inflows
      .filter((inflow) => inflow.timestamp >= from && inflow.timestamp <= end)
      .reduce((sum, inflow) => sum + inflow.amount, 0);
  }, [inflows]);

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
  const showInflowCard = visible.includes("inflow");
  const hasCards = cards.length > 0 || showInflowCard;

  return hasCards ? (
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
      {showInflowCard ? (
        <StatCard
          label="Inflow"
          value={currency.format(monthIncome)}
          sub="This month"
          icon={TrendingUp}
          trend="up"
        />
      ) : null}
    </div>
  ) : (
    <p className="text-sm text-muted-foreground text-center py-8">No cards selected.</p>
  );
}

function OverviewInfoPopover({
  visible,
  onVisibleChange,
}: {
  visible: string[];
  onVisibleChange: (value: string[]) => void | Promise<void>;
}) {
  const statCards = [
    { key: "today", label: "Today" },
    { key: "week", label: "This Week" },
    { key: "month", label: "This Month" },
    { key: "budget", label: "Budget Left" },
    { key: "inflow", label: "Inflow" },
    { key: "30d", label: "Last 30 Days" },
    { key: "90d", label: "Last 90 Days" },
    { key: "ytd", label: "Year to Date" },
  ];

  const toggle = (key: string) =>
    onVisibleChange(
      visible.includes(key) ? visible.filter((value) => value !== key) : [...visible, key],
    );

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-9 text-left">
          <Filter className="mr-2 h-4 w-4" />
          Show
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
  );
}

function interleaveBySize<T extends { value: number }>(arr: T[]): T[] {
  const sorted = [...arr].sort((a, b) => b.value - a.value);
  const result: T[] = [];
  let lo = 0, hi = sorted.length - 1;
  let pickLarge = true;
  while (lo <= hi) {
    result.push(pickLarge ? sorted[lo++] : sorted[hi--]);
    pickLarge = !pickLarge;
  }
  return result;
}

function CategoryPieCard({
  transactions,
  categories,
  catColorMap,
  loading,
  onSliceClick,
}: {
  transactions: DashboardTransaction[];
  categories: DashboardCategory[];
  catColorMap: Record<string, string>;
  loading: boolean;
  onSliceClick?: (categoryName: string, rangeKey: RangeKey, custom?: DateRange) => void;
}) {
  const [rangeKey, setRangeKey] = useState<RangeKey>("current-month");
  const [custom, setCustom] = useState<DateRange | undefined>();
  const isMobile = useIsMobile();

  const { from, to } = useMemo(() => getRange(rangeKey, custom), [rangeKey, custom]);

  const pieData = useMemo(() => {
    const summaries: Record<string, number> = {};
    transactions
      .filter((tx) => tx.timestamp >= from && tx.timestamp <= to)
      .forEach((tx) => {
        summaries[tx.category] = (summaries[tx.category] ?? 0) + tx.amount;
      });
    return categories
      .map((cat) => ({
        name: `${cat.emoji} ${cat.name}`,
        rawName: cat.name,
        emoji: cat.emoji,
        value: Number((summaries[cat.name] ?? 0).toFixed(2)),
        color: catColorMap[cat.name],
      }))
      .filter((entry) => entry.value > 0);
  }, [transactions, categories, catColorMap, from, to]);

  const chartData = useMemo(() => interleaveBySize(pieData), [pieData]);
  const legendData = useMemo(() => [...pieData].sort((a, b) => b.value - a.value), [pieData]);

  const total = pieData.reduce((sum, entry) => sum + entry.value, 0);
  const hasData = !loading && pieData.length > 0;

  return (
    <Card>
      <CardHeader className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 space-y-0">
        <CardTitle className="text-lg">By Category</CardTitle>
        <RangeSelector
          rangeKey={rangeKey}
          custom={custom}
          onRangeKeyChange={setRangeKey}
          onCustomChange={setCustom}
        />
      </CardHeader>
      <CardContent>
        <div className={isMobile ? undefined : "flex items-center gap-4"}>
          <div className={isMobile ? "h-56 w-full" : "h-80 w-[55%] flex-none"}>
            {loading ? (
              <CenteredChartMessage label="Loading..." />
            ) : pieData.length === 0 ? (
              <CenteredChartMessage label="No data for this period." />
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={chartData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={50}
                    outerRadius={85}
                    paddingAngle={2}
                    label={
                      isMobile
                        ? (props: Parameters<typeof renderEmojiSliceLabel>[0]) =>
                            renderEmojiSliceLabel(props)
                        : (props: Parameters<typeof renderDesktopSliceLabel>[0]) =>
                            renderDesktopSliceLabel(props)
                    }
                    labelLine={false}
                    cursor={onSliceClick ? "pointer" : undefined}
                    onClick={
                      onSliceClick
                        ? (entry: { rawName: string }) => onSliceClick(entry.rawName, rangeKey, custom)
                        : undefined
                    }
                  >
                    {chartData.map((entry) => (
                      <Cell key={entry.name} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{ borderRadius: 8, border: "1px solid oklch(0.92 0.01 256)" }}
                    formatter={(value: number) => currency.format(value)}
                  />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
          {!isMobile && hasData && (
            <div className="flex-1 min-w-0 max-h-80 overflow-y-auto">
              <MobilePieLegend data={legendData} total={total} className="" />
            </div>
          )}
        </div>
        {isMobile && hasData && <MobilePieLegend data={legendData} total={total} />}
      </CardContent>
    </Card>
  );
}

function renderEmojiSliceLabel(props: {
  cx?: number;
  cy?: number;
  midAngle?: number;
  outerRadius?: number;
  percent?: number;
  payload?: { emoji?: string };
}) {
  const { cx = 0, cy = 0, midAngle = 0, outerRadius = 0, percent = 0, payload } = props;
  const emoji = payload?.emoji;
  const pct = Math.round(percent * 100);
  if (!emoji || pct === 0) return null;
  const RADIAN = Math.PI / 180;
  const radius = outerRadius + 22;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text textAnchor="middle" fontSize={11} pointerEvents="none">
      <tspan x={x} y={y} dy="-0.6em">{emoji}</tspan>
      <tspan x={x} dy="1.2em">{pct}%</tspan>
    </text>
  );
}

function renderDesktopSliceLabel(props: {
  cx?: number;
  cy?: number;
  midAngle?: number;
  outerRadius?: number;
  percent?: number;
  payload?: { emoji?: string };
}) {
  const { cx = 0, cy = 0, midAngle = 0, outerRadius = 0, percent = 0, payload } = props;
  const emoji = payload?.emoji;
  const pct = Math.round(percent * 100);
  if (pct === 0) return null;
  const RADIAN = Math.PI / 180;
  const radius = outerRadius + 28;
  const x = cx + radius * Math.cos(-midAngle * RADIAN);
  const y = cy + radius * Math.sin(-midAngle * RADIAN);
  return (
    <text textAnchor="middle" fontSize={18} pointerEvents="none">
      <tspan x={x} y={y} dy="-0.6em">{emoji}</tspan>
      <tspan x={x} dy="1.2em">{pct}%</tspan>
    </text>
  );
}

function MobilePieLegend({
  data,
  total,
  className = "mt-3",
}: {
  data: { rawName: string; emoji: string; value: number; color: string }[];
  total: number;
  className?: string;
}) {
  return (
    <div className={`grid grid-cols-[auto_auto_1fr_auto_auto] items-center gap-x-2 gap-y-1.5 text-xs ${className}`}>
      {data.map((entry) => {
        const pct = Math.round((entry.value / Math.max(total, 1)) * 100);
        return (
          <Fragment key={entry.rawName}>
            <span
              className="inline-block h-3 w-3 rounded-sm"
              style={{ backgroundColor: entry.color }}
              aria-hidden
            />
            <span className="leading-none">{entry.emoji}</span>
            <span className="text-foreground truncate">{entry.rawName}</span>
            <span className="text-muted-foreground text-right tabular-nums">{pct}%</span>
            <span className="text-foreground text-right tabular-nums">
              {currency.format(entry.value)}
            </span>
          </Fragment>
        );
      })}
    </div>
  );
}

function TrendCard({
  transactions,
  categories,
  catColorMap,
  loading,
  onPointClick,
}: {
  transactions: DashboardTransaction[];
  categories: DashboardCategory[];
  catColorMap: Record<string, string>;
  loading: boolean;
  onPointClick?: (date: Date) => void;
}) {
  const [rangeKey, setRangeKey] = useState<RangeKey>("current-month");
  const [custom, setCustom] = useState<DateRange | undefined>();
  const [selected, setSelected] = useState<string[]>([]);
  const [isAllMode, setIsAllMode] = useState(true);

  useEffect(() => {
    setSelected(categories.map((category) => category.name));
    setIsAllMode(true);
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

  const toggleAll = (all: boolean) => {
    if (all) {
      setSelected(categories.map((c) => c.name));
      setIsAllMode(true);
    } else {
      setSelected([]);
      setIsAllMode(false);
    }
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
            isAllMode={isAllMode}
            onToggleAll={toggleAll}
          />
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-96 w-full">
          {loading ? (
            <CenteredChartMessage label="Loading trend data..." />
          ) : selected.length === 0 ? (
            <CenteredChartMessage label="Select at least one category." />
          ) : (
            <ResponsiveContainer>
              <LineChart
                data={data}
                style={onPointClick ? { cursor: "pointer" } : undefined}
                onClick={
                  onPointClick
                    ? (chartData: { activePayload?: { payload: { isoDate: string } }[] }) => {
                        const isoDate = chartData?.activePayload?.[0]?.payload?.isoDate;
                        if (isoDate) onPointClick(new Date(isoDate));
                      }
                    : undefined
                }
              >
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
  onDeleteTransaction,
  onUpdateTransaction,
  onEditPlanTransaction,
  jump,
}: {
  transactions: DashboardTransaction[];
  categories: DashboardCategory[];
  catColorMap: Record<string, string>;
  loading: boolean;
  onDeleteTransaction: (transactionId: string) => Promise<void>;
  onUpdateTransaction: (
    transactionId: string,
    payload: {
      item: string;
      amount: number;
      category: string;
      timestamp: Date;
    },
  ) => Promise<void>;
  onEditPlanTransaction: (planId: string) => boolean;
  jump?: TxnJump | null;
}) {
  const [rangeKey, setRangeKey] = useState<RangeKey>("current-month");
  const [custom, setCustom] = useState<DateRange | undefined>();
  const [selectedCategories, setSelectedCategories] = useState<string[]>([]);
  const [isCategoryAllMode, setIsCategoryAllMode] = useState(true);
  const [searchQuery, setSearchQuery] = useState("");
  const [minAmount, setMinAmount] = useState("");
  const [maxAmount, setMaxAmount] = useState("");
  const [sortKey, setSortKey] = useState<TransactionSortKey>("date-desc");
  const [page, setPage] = useState(1);
  const [editingTransactionId, setEditingTransactionId] = useState<string | null>(null);
  const [editingItem, setEditingItem] = useState("");
  const [editingAmount, setEditingAmount] = useState("");
  const [editingCategory, setEditingCategory] = useState("");
  const [editingTimestamp, setEditingTimestamp] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [savingTransaction, setSavingTransaction] = useState(false);
  const [deletingTransactionId, setDeletingTransactionId] = useState<string | null>(null);

  useEffect(() => {
    setSelectedCategories(categories.map((category) => category.name));
    setIsCategoryAllMode(true);
  }, [categories]);

  useEffect(() => {
    if (!jump) return;
    setRangeKey(jump.rangeKey);
    setCustom(jump.custom);
    if (jump.category !== null) {
      setSelectedCategories([jump.category]);
      setIsCategoryAllMode(false);
    } else {
      setSelectedCategories(categories.map((c) => c.name));
      setIsCategoryAllMode(true);
    }
  }, [jump]);

  const { from, to } = useMemo(() => getRange(rangeKey, custom), [rangeKey, custom]);
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const minValue = minAmount.trim() === "" ? null : Number(minAmount);
  const maxValue = maxAmount.trim() === "" ? null : Number(maxAmount);

  const filteredTransactions = useMemo(() => {
    const selectedSet = new Set(selectedCategories);
    const normalizedQuery = deferredSearchQuery.trim().toLowerCase();
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
      if (normalizedQuery) {
        const searchable = [
          transaction.item,
          transaction.category,
          format(transaction.timestamp, "MMM d, yyyy"),
          format(transaction.timestamp, "yyyy-MM-dd"),
        ]
          .join(" ")
          .toLowerCase();
        if (!searchable.includes(normalizedQuery)) {
          return false;
        }
      }
      return true;
    });
    return sortTransactions(filtered, sortKey);
  }, [transactions, from, to, selectedCategories, minValue, maxValue, deferredSearchQuery, sortKey]);

  useEffect(() => {
    setPage(1);
  }, [rangeKey, custom, selectedCategories, searchQuery, minAmount, maxAmount, sortKey]);

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

  const editingTransaction = useMemo(
    () => transactions.find((transaction) => transaction.id === editingTransactionId) ?? null,
    [transactions, editingTransactionId],
  );

  const toggleCategory = (categoryName: string) => {
    setSelectedCategories((prev) =>
      prev.includes(categoryName)
        ? prev.filter((value) => value !== categoryName)
        : [...prev, categoryName],
    );
  };

  const toggleAllCategories = (all: boolean) => {
    if (all) {
      setSelectedCategories(categories.map((c) => c.name));
      setIsCategoryAllMode(true);
    } else {
      setSelectedCategories([]);
      setIsCategoryAllMode(false);
    }
  };

  function openEditDialog(transaction: DashboardTransaction) {
    setActionError(null);
    if (
      (transaction.sourceType === "recurring" || transaction.sourceType === "split_payment") &&
      transaction.sourcePlanId
    ) {
      if (!onEditPlanTransaction(transaction.sourcePlanId)) {
        setActionError("Linked plan not found.");
      }
      return;
    }
    setEditingTransactionId(transaction.id);
    setEditingItem(transaction.item);
    setEditingAmount(String(transaction.amount));
    setEditingCategory(transaction.category);
    setEditingTimestamp(formatDateTimeInputValue(transaction.timestamp));
  }

  function closeEditDialog() {
    if (savingTransaction) {
      return;
    }
    setEditingTransactionId(null);
    setEditingItem("");
    setEditingAmount("");
    setEditingCategory("");
    setEditingTimestamp("");
    setActionError(null);
  }

  async function handleSaveTransactionEdit() {
    if (!editingTransactionId) {
      return;
    }

    const amount = Number(editingAmount);
    const timestamp = new Date(editingTimestamp);

    if (!editingItem.trim()) {
      setActionError("Item name cannot be empty.");
      return;
    }
    if (!editingCategory.trim()) {
      setActionError("Category is required.");
      return;
    }
    if (Number.isNaN(amount) || amount <= 0) {
      setActionError("Amount must be a positive number.");
      return;
    }
    if (Number.isNaN(timestamp.getTime())) {
      setActionError("Date is invalid.");
      return;
    }

    setSavingTransaction(true);
    setActionError(null);
    try {
      await onUpdateTransaction(editingTransactionId, {
        item: editingItem.trim(),
        amount,
        category: editingCategory,
        timestamp,
      });
      closeEditDialog();
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Unable to update transaction.");
    } finally {
      setSavingTransaction(false);
    }
  }

  async function handleDeleteTransactionClick(transaction: DashboardTransaction) {
    const confirmed = window.confirm(`Delete "${transaction.item}"?`);
    if (!confirmed) {
      return;
    }
    setDeletingTransactionId(transaction.id);
    setActionError(null);
    try {
      await onDeleteTransaction(transaction.id);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Unable to delete transaction.");
    } finally {
      setDeletingTransactionId(null);
    }
  }

  return (
    <>
      <div className="space-y-2">
        <Label htmlFor="transaction-search">Search expenses</Label>
        <Input
          id="transaction-search"
          value={searchQuery}
          onChange={(event) => setSearchQuery(event.target.value)}
          placeholder="Search by item, category, or date"
          className="max-w-md"
        />
      </div>
      <Card>
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle className="text-lg">All Expenses</CardTitle>
              {!loading && (
                <p className="text-sm text-muted-foreground mt-0.5">
                  {filteredTransactions.length} expense{filteredTransactions.length !== 1 ? "s" : ""} &middot;{" "}
                  <span className="font-semibold text-foreground">
                    {currency.format(filteredTransactions.reduce((sum, tx) => sum + tx.amount, 0))}
                  </span>
                </p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex items-center gap-2 rounded-md border border-input bg-background px-3 py-1.5">
                <span className="text-sm text-muted-foreground">Min</span>
                <Input
                  id="min-amount"
                  className="h-8 w-14 self-center border-0 px-0 text-sm leading-none shadow-none [appearance:textfield] focus-visible:ring-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  inputMode="decimal"
                  onChange={(event) => setMinAmount(event.target.value)}
                  placeholder="0.00"
                  type="number"
                  value={minAmount}
                />
                <span className="text-sm text-muted-foreground">-</span>
                <span className="text-sm text-muted-foreground">Max</span>
                <Input
                  id="max-amount"
                  className="h-8 w-14 self-center border-0 px-0 text-sm leading-none shadow-none [appearance:textfield] focus-visible:ring-0 [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
                  inputMode="decimal"
                  onChange={(event) => setMaxAmount(event.target.value)}
                  placeholder="Limit"
                  type="number"
                  value={maxAmount}
                />
              </div>
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
                isAllMode={isCategoryAllMode}
                onToggleAll={toggleAllCategories}
              />
              <Select
                value={sortKey}
                onValueChange={(value) => setSortKey(value as TransactionSortKey)}
              >
                <SelectTrigger className="h-9 w-[112px] px-3">
                  <div className="flex items-center gap-2 pr-4">
                    <ListFilter className="h-4 w-4" />
                    <span>Sort</span>
                  </div>
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
        </CardHeader>
        <CardContent className="space-y-4">
          {actionError ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {actionError}
            </div>
          ) : null}
          {loading ? (
            <CenteredListMessage label="Loading expenses..." />
          ) : pageRows.length === 0 ? (
            <CenteredListMessage label="No expenses found for the selected filters." />
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
                      <TableHead className="w-[96px] text-right">Actions</TableHead>
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
                                background:
                                  catColorMap[transaction.category] ?? colorForCategory(0),
                              }}
                            />
                            <span className="truncate">
                              {categories.find((category) => category.name === transaction.category)
                                ?.emoji ?? "$"}{" "}
                              {transaction.category}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-semibold">
                          {currency.format(transaction.amount)}
                        </TableCell>
                        <TableCell>
                          <div className="flex justify-end gap-1">
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8"
                              aria-label={`Edit ${transaction.item}`}
                              onClick={() => openEditDialog(transaction)}
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            <Button
                              size="icon"
                              variant="ghost"
                              className="h-8 w-8 text-destructive hover:text-destructive"
                              aria-label={`Delete ${transaction.item}`}
                              disabled={deletingTransactionId === transaction.id}
                              onClick={() => void handleDeleteTransactionClick(transaction)}
                            >
                              {deletingTransactionId === transaction.id ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Trash2 className="h-4 w-4" />
                              )}
                            </Button>
                          </div>
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

      <Dialog
        open={editingTransaction !== null}
        onOpenChange={(open) => {
          if (!open) {
            closeEditDialog();
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit transaction</DialogTitle>
            <DialogDescription>Update the item, category, amount, and date.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="edit-item">Item</Label>
              <Input
                id="edit-item"
                value={editingItem}
                onChange={(event) => setEditingItem(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-category">Category</Label>
              <Select value={editingCategory} onValueChange={setEditingCategory}>
                <SelectTrigger>
                  <SelectValue placeholder="Select a category" />
                </SelectTrigger>
                <SelectContent>
                  {categories.map((category) => (
                    <SelectItem key={category.name} value={category.name}>
                      {category.emoji} {category.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-amount">Amount</Label>
              <Input
                id="edit-amount"
                type="number"
                inputMode="decimal"
                value={editingAmount}
                onChange={(event) => setEditingAmount(event.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-date">Date</Label>
              <Input
                id="edit-date"
                type="datetime-local"
                value={editingTimestamp}
                onChange={(event) => setEditingTimestamp(event.target.value)}
              />
            </div>
            {actionError ? (
              <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                {actionError}
              </div>
            ) : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={closeEditDialog} disabled={savingTransaction}>
              Cancel
            </Button>
            <Button onClick={() => void handleSaveTransactionEdit()} disabled={savingTransaction}>
              {savingTransaction ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

function PlansTab({
  plans,
  categories,
  loading,
  onEditPlan,
  onDeletePlan,
}: {
  plans: DashboardPlan[];
  categories: DashboardCategory[];
  loading: boolean;
  onEditPlan: (plan: DashboardPlan) => void;
  onDeletePlan: (planId: string, mode: "future" | "all") => Promise<void>;
}) {
  const [deletingPlan, setDeletingPlan] = useState<DashboardPlan | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const recurringPlans = plans.filter((p) => p.planType === "recurring");
  const splitPlans = plans.filter((p) => p.planType === "split_payment");

  async function handleDeleteConfirm(mode: "future" | "all") {
    if (!deletingPlan) return;
    setDeletingId(deletingPlan.id);
    try {
      await onDeletePlan(deletingPlan.id, mode);
      setDeletingPlan(null);
    } finally {
      setDeletingId(null);
    }
  }

  function formatNextDue(plan: DashboardPlan) {
    if (!plan.nextDueDate) return plan.status === "completed" ? "Completed" : "—";
    try {
      return format(new Date(plan.nextDueDate), "MMM d, yyyy");
    } catch {
      return "—";
    }
  }

  function PlanRow({ plan }: { plan: DashboardPlan }) {
    const isActive = plan.status === "active";
    const emoji = categories.find((c) => c.name === plan.category)?.emoji ?? "🏷️";
    const amountLabel =
      plan.planType === "recurring"
        ? `${currency.format(plan.amount)}/mo`
        : `${currency.format(plan.totalAmount)} total`;
    const progressLabel =
      plan.planType === "split_payment"
        ? `${plan.currentInstallmentNumber}/${plan.installmentCount} paid`
        : null;

    return (
      <TableRow className={!isActive ? "opacity-50" : undefined}>
        <TableCell>
          <div className="flex items-center gap-2">
            <span className="text-base">{emoji}</span>
            <div>
              <p className="font-medium text-sm">{plan.item}</p>
              <p className="text-xs text-muted-foreground">{plan.category}</p>
            </div>
          </div>
        </TableCell>
        <TableCell className="text-sm">
          <div>{amountLabel}</div>
          {progressLabel ? (
            <div className="text-xs text-muted-foreground">{progressLabel}</div>
          ) : null}
        </TableCell>
        <TableCell className="text-sm text-muted-foreground">Day {plan.dayOfMonth}</TableCell>
        <TableCell className="text-sm text-muted-foreground">{formatNextDue(plan)}</TableCell>
        <TableCell>
          <div className="flex justify-end gap-1">
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8"
              disabled={!isActive}
              aria-label={`Edit ${plan.item}`}
              onClick={() => onEditPlan(plan)}
            >
              <Pencil className="h-4 w-4" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              className="h-8 w-8 text-destructive hover:text-destructive"
              disabled={!isActive || deletingId === plan.id}
              aria-label={`Delete ${plan.item}`}
              onClick={() => setDeletingPlan(plan)}
            >
              {deletingId === plan.id ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4" />
              )}
            </Button>
          </div>
        </TableCell>
      </TableRow>
    );
  }

  function PlanTable({ title, items }: { title: string; items: DashboardPlan[] }) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-lg">
            <Repeat2 className="h-4 w-4" />
            {title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <CenteredListMessage label="Loading plans..." />
          ) : items.length === 0 ? (
            <CenteredListMessage label="No plans found." />
          ) : (
            <div className="rounded-xl border border-border/70">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Day</TableHead>
                    <TableHead>Next Due</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((plan) => (
                    <PlanRow key={plan.id} plan={plan} />
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    );
  }

  return (
    <>
      <PlanTable title="Recurring Plans" items={recurringPlans} />
      <PlanTable title="Split Payment Plans" items={splitPlans} />

      {/* Delete dialog */}
      <Dialog open={deletingPlan !== null} onOpenChange={(open) => { if (!open && !deletingId) setDeletingPlan(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete plan</DialogTitle>
            <DialogDescription>
              <strong>{deletingPlan?.item}</strong>
              {deletingPlan?.planType === "split_payment"
                ? " — this will cancel the plan and remove all auto-generated charges."
                : " — choose how to stop this plan."}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col gap-2 sm:flex-row">
            <Button variant="outline" onClick={() => setDeletingPlan(null)} disabled={!!deletingId}>
              Cancel
            </Button>
            {deletingPlan?.planType === "recurring" ? (
              <>
                <Button
                  variant="outline"
                  onClick={() => void handleDeleteConfirm("future")}
                  disabled={!!deletingId}
                >
                  {deletingId ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Stop future only
                </Button>
                <Button
                  variant="destructive"
                  onClick={() => void handleDeleteConfirm("all")}
                  disabled={!!deletingId}
                >
                  {deletingId ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                  Stop + remove past
                </Button>
              </>
            ) : (
              <Button
                variant="destructive"
                onClick={() => void handleDeleteConfirm("all")}
                disabled={!!deletingId}
              >
                {deletingId ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
                Stop + remove all charges
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
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
          <SelectItem value="today">Today</SelectItem>
          <SelectItem value="yesterday">Yesterday</SelectItem>
          <SelectItem value="weekly">Weekly</SelectItem>
          <SelectItem value="current-month">Current Month</SelectItem>
          <SelectItem value="30d">Last 30 Days</SelectItem>
          <SelectItem value="ytd">Year to Date</SelectItem>
          <SelectItem value="custom">Current Range</SelectItem>
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
                  ? `${format(custom.from, "MMM d")} - ${format(custom.to, "MMM d")}`
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
  isAllMode,
  onToggleAll,
}: {
  categories: DashboardCategory[];
  selected: string[];
  catColorMap: Record<string, string>;
  onToggle: (categoryName: string) => void;
  isAllMode: boolean;
  onToggleAll: (all: boolean) => void;
}) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" size="sm" className="h-9">
          <Filter className="mr-2 h-4 w-4" />
          Categories ({isAllMode ? categories.length : selected.length}/{categories.length})
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-56" align="end">
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm cursor-pointer font-medium">
            <Checkbox
              checked={isAllMode}
              onCheckedChange={(checked) => onToggleAll(!!checked)}
            />
            All
          </label>
          <hr className="border-border" />
          {categories.map((category) => (
            <label
              key={category.name}
              className={`flex items-center gap-2 text-sm ${isAllMode ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
            >
              <Checkbox
                checked={isAllMode || selected.includes(category.name)}
                onCheckedChange={() => !isAllMode && onToggle(category.name)}
                disabled={isAllMode}
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

function IncomeTab({
  inflows,
  goals,
  projects,
  loading,
  onDeleteInflow,
}: {
  inflows: DashboardInflow[];
  goals: DashboardGoal[];
  projects: DashboardProject[];
  loading: boolean;
  onDeleteInflow: (inflowId: string) => Promise<void>;
}) {
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const targetLabels = useMemo(() => {
    const map: Record<string, string> = {};
    goals.forEach((goal) => {
      map[`goal:${goal.id}`] = `${goal.emoji} ${goal.name}`;
    });
    projects.forEach((project) => {
      map[`project:${project.id}`] = `${project.emoji} ${project.name}`;
    });
    return map;
  }, [goals, projects]);

  const sorted = useMemo(
    () => [...inflows].sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime()),
    [inflows],
  );
  const total = useMemo(
    () => inflows.reduce((sum, inflow) => sum + inflow.amount, 0),
    [inflows],
  );

  async function handleDelete(inflowId: string) {
    setDeletingId(inflowId);
    try {
      await onDeleteInflow(inflowId);
    } catch {
      // Row remains; the next refresh reconciles state.
    } finally {
      setDeletingId(null);
    }
  }

  function assignmentLabels(inflow: DashboardInflow) {
    // An inflow can be tagged to a goal and a project at once, so show both badges.
    const labels: string[] = [];
    if (inflow.goalId) {
      const label = targetLabels[`goal:${inflow.goalId}`];
      if (label) labels.push(label);
    }
    if (inflow.projectId) {
      const label = targetLabels[`project:${inflow.projectId}`];
      if (label) labels.push(label);
    }
    return labels;
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Income</CardTitle>
          <span className="text-sm font-semibold text-emerald-500">{currency.format(total)}</span>
        </CardHeader>
        <CardContent>
          {loading ? (
            <CenteredListMessage label="Loading income..." />
          ) : sorted.length === 0 ? (
            <CenteredListMessage label="No income recorded yet." />
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Description</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead className="text-right">Amount</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((inflow) => {
                  const assigned = assignmentLabels(inflow);
                  return (
                    <TableRow key={inflow.id}>
                      <TableCell className="font-medium">
                        {inflow.item}
                        {assigned.map((label) => (
                          <span
                            key={label}
                            className="ml-2 rounded bg-secondary px-1.5 py-0.5 text-xs text-muted-foreground"
                          >
                            {label}
                          </span>
                        ))}
                      </TableCell>
                      <TableCell className="text-muted-foreground">
                        {format(inflow.timestamp, "MMM d, yyyy")}
                      </TableCell>
                      <TableCell className="text-right font-semibold text-emerald-500">
                        +{currency.format(inflow.amount)}
                      </TableCell>
                      <TableCell>
                        <Button
                          size="icon"
                          variant="ghost"
                          disabled={deletingId === inflow.id}
                          onClick={() => void handleDelete(inflow.id)}
                        >
                          {deletingId === inflow.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <Trash2 className="h-4 w-4" />
                          )}
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function GoalsTab({
  goals,
  loading,
  onCreateGoal,
  onUpdateGoal,
  onDeleteGoal,
  onMoveGoal,
}: {
  goals: DashboardGoal[];
  loading: boolean;
  onCreateGoal: (payload: { name: string; targetAmount: number; emoji: string }) => Promise<void>;
  onUpdateGoal: (
    goalId: string,
    payload: { name?: string; targetAmount?: number; emoji?: string },
  ) => Promise<void>;
  onDeleteGoal: (goalId: string) => Promise<void>;
  onMoveGoal: (goalId: string, direction: -1 | 1) => Promise<void>;
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formEmoji, setFormEmoji] = useState("🎯");
  const [formTarget, setFormTarget] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function openAdd() {
    setEditingId(null);
    setFormName("");
    setFormEmoji("🎯");
    setFormTarget("");
    setFormError(null);
    setDialogOpen(true);
  }

  function openEdit(goal: DashboardGoal) {
    setEditingId(goal.id);
    setFormName(goal.name);
    setFormEmoji(goal.emoji);
    setFormTarget(String(goal.targetAmount));
    setFormError(null);
    setDialogOpen(true);
  }

  async function handleSubmit() {
    const name = formName.trim();
    const target = Number(formTarget);
    if (!name) {
      setFormError("Name is required.");
      return;
    }
    if (!Number.isFinite(target) || target <= 0) {
      setFormError("Target must be a positive number.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      if (editingId) {
        await onUpdateGoal(editingId, { name, targetAmount: target, emoji: formEmoji.trim() || "🎯" });
      } else {
        await onCreateGoal({ name, targetAmount: target, emoji: formEmoji.trim() || "🎯" });
      }
      setDialogOpen(false);
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Unable to save goal.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(goal: DashboardGoal) {
    if (!window.confirm(`Delete goal "${goal.name}"?`)) return;
    setBusyId(goal.id);
    try {
      await onDeleteGoal(goal.id);
    } catch {
      // next refresh reconciles
    } finally {
      setBusyId(null);
    }
  }

  async function handleMove(goal: DashboardGoal, direction: -1 | 1) {
    setBusyId(goal.id);
    try {
      await onMoveGoal(goal.id, direction);
    } catch {
      // next refresh reconciles
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-lg">Goals</CardTitle>
            <p className="text-xs text-muted-foreground">Monthly savings targets — progress resets each month.</p>
          </div>
          <Button size="sm" className="gap-1" onClick={openAdd}>
            <Plus className="h-4 w-4" />
            Add Goal
          </Button>
        </CardHeader>
        <CardContent className="space-y-5">
          {loading ? (
            <CenteredListMessage label="Loading goals..." />
          ) : goals.length === 0 ? (
            <CenteredListMessage label="No goals yet — add one to start tracking a monthly target." />
          ) : (
            goals.map((goal, index) => {
              const pct = goal.targetAmount > 0 ? (goal.accumulated / goal.targetAmount) * 100 : 0;
              const reached = goal.targetAmount > 0 && goal.accumulated >= goal.targetAmount;
              return (
                <div key={goal.id} className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="h-8 w-8 rounded-md bg-secondary flex items-center justify-center shrink-0 text-sm leading-none">
                        {goal.emoji}
                      </span>
                      <p className="font-medium text-sm">{goal.name}</p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <p className={`text-sm font-semibold ${reached ? "text-emerald-500" : "text-foreground"}`}>
                        {currency.format(goal.accumulated)}{" "}
                        <span className="text-muted-foreground font-normal">
                          / {currency.format(goal.targetAmount)} ({Math.round(pct)}%)
                        </span>
                      </p>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        disabled={busyId === goal.id || index === 0}
                        aria-label={`Move ${goal.name} up`}
                        onClick={() => void handleMove(goal, -1)}
                      >
                        <ChevronUp className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        disabled={busyId === goal.id || index === goals.length - 1}
                        aria-label={`Move ${goal.name} down`}
                        onClick={() => void handleMove(goal, 1)}
                      >
                        <ChevronDown className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        aria-label={`Edit ${goal.name}`}
                        onClick={() => openEdit(goal)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-destructive hover:text-destructive"
                        disabled={busyId === goal.id}
                        aria-label={`Delete ${goal.name}`}
                        onClick={() => void handleDelete(goal)}
                      >
                        {busyId === goal.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </div>
                  <Progress
                    value={Math.min(pct, 100)}
                    className={reached ? "[&>div]:bg-emerald-500" : "[&>div]:bg-accent"}
                  />
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={(open) => { if (!open && !saving) setDialogOpen(false); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingId ? "Edit Goal" : "Add Goal"}</DialogTitle>
            <DialogDescription>A monthly savings target funded by income you assign to it.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="goal-name">Name</Label>
              <Input id="goal-name" value={formName} onChange={(e) => setFormName(e.target.value)} disabled={saving} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="goal-emoji">Emoji</Label>
              <Input id="goal-emoji" value={formEmoji} onChange={(e) => setFormEmoji(e.target.value)} disabled={saving} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="goal-target">Monthly Target</Label>
              <Input
                id="goal-target"
                type="number"
                inputMode="decimal"
                min="0.01"
                step="0.01"
                value={formTarget}
                onChange={(e) => setFormTarget(e.target.value)}
                disabled={saving}
              />
            </div>
            {formError ? <p className="text-sm text-destructive">{formError}</p> : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={() => void handleSubmit()} disabled={saving}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {editingId ? "Save" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}


function ProjectsTab({
  projects,
  inflows,
  loading,
  onCreateProject,
  onUpdateProject,
  onDeleteProject,
  onMoveProject,
}: {
  projects: DashboardProject[];
  inflows: DashboardInflow[];
  loading: boolean;
  onCreateProject: (payload: {
    name: string;
    targetAmount: number;
    initialAmount: number;
    deadline: string;
    emoji: string;
  }) => Promise<void>;
  onUpdateProject: (
    projectId: string,
    payload: {
      name?: string;
      targetAmount?: number;
      initialAmount?: number;
      deadline?: string;
      emoji?: string;
    },
  ) => Promise<void>;
  onDeleteProject: (projectId: string) => Promise<void>;
  onMoveProject: (projectId: string, direction: -1 | 1) => Promise<void>;
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  // Track the id, not the object: the dialog then reflects live edits and closes
  // itself if the project disappears from a background refresh.
  const [detailId, setDetailId] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formEmoji, setFormEmoji] = useState("🚀");
  const [formTarget, setFormTarget] = useState("");
  const [formInitialAmount, setFormInitialAmount] = useState("");
  const [formDeadline, setFormDeadline] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const detailProject = useMemo(
    () => projects.find((project) => project.id === detailId) ?? null,
    [projects, detailId],
  );
  const detailInflows = useMemo(
    () =>
      detailId
        ? inflows
            .filter((inflow) => inflow.projectId === detailId)
            .sort((a, b) => b.timestamp.getTime() - a.timestamp.getTime())
        : [],
    [inflows, detailId],
  );
  const detailContributed = useMemo(
    () => detailInflows.reduce((sum, inflow) => sum + inflow.amount, 0),
    [detailInflows],
  );

  function openAdd() {
    setEditingId(null);
    setFormName("");
    setFormEmoji("🚀");
    setFormTarget("");
    setFormInitialAmount("");
    setFormDeadline("");
    setFormError(null);
    setDialogOpen(true);
  }

  function openEdit(project: DashboardProject) {
    setEditingId(project.id);
    setFormName(project.name);
    setFormEmoji(project.emoji);
    setFormTarget(String(project.targetAmount));
    setFormInitialAmount(project.initialAmount > 0 ? String(project.initialAmount) : "");
    setFormDeadline(project.deadline ? project.deadline.slice(0, 10) : "");
    setFormError(null);
    setDialogOpen(true);
  }

  async function handleSubmit() {
    const name = formName.trim();
    const target = Number(formTarget);
    const initialAmount = formInitialAmount.trim() ? Number(formInitialAmount) : 0;
    if (!name) {
      setFormError("Name is required.");
      return;
    }
    if (!Number.isFinite(target) || target <= 0) {
      setFormError("Target must be a positive number.");
      return;
    }
    if (!Number.isFinite(initialAmount) || initialAmount < 0) {
      setFormError("Current amount must be zero or more.");
      return;
    }
    if (!formDeadline || Number.isNaN(new Date(formDeadline).getTime())) {
      setFormError("A deadline date is required.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      if (editingId) {
        await onUpdateProject(editingId, {
          name,
          targetAmount: target,
          initialAmount,
          deadline: formDeadline,
          emoji: formEmoji.trim() || "🚀",
        });
      } else {
        await onCreateProject({
          name,
          targetAmount: target,
          initialAmount,
          deadline: formDeadline,
          emoji: formEmoji.trim() || "🚀",
        });
      }
      setDialogOpen(false);
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Unable to save project.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(project: DashboardProject) {
    if (!window.confirm(`Delete project "${project.name}"?`)) return;
    setBusyId(project.id);
    try {
      await onDeleteProject(project.id);
    } catch {
      // next refresh reconciles
    } finally {
      setBusyId(null);
    }
  }

  async function handleMove(project: DashboardProject, direction: -1 | 1) {
    setBusyId(project.id);
    try {
      await onMoveProject(project.id, direction);
    } catch {
      // next refresh reconciles
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle className="text-lg">Long-Term Projects</CardTitle>
            <p className="text-xs text-muted-foreground">Cumulative savings toward a deadline — progress never resets.</p>
          </div>
          <Button size="sm" className="gap-1" onClick={openAdd}>
            <Plus className="h-4 w-4" />
            Add Project
          </Button>
        </CardHeader>
        <CardContent className="space-y-5">
          {loading ? (
            <CenteredListMessage label="Loading projects..." />
          ) : projects.length === 0 ? (
            <CenteredListMessage label="No long-term projects yet — add one with a target and deadline." />
          ) : (
            projects.map((project, index) => {
              const pct = project.targetAmount > 0 ? (project.accumulated / project.targetAmount) * 100 : 0;
              const reached = project.targetAmount > 0 && project.accumulated >= project.targetAmount;
              const due = deadlineLabel(project.deadline);
              return (
                <div
                  key={project.id}
                  role="button"
                  tabIndex={0}
                  aria-label={`View ${project.name} contributions`}
                  className="space-y-2 -mx-2 rounded-md px-2 py-1 cursor-pointer transition-colors hover:bg-secondary/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onClick={() => setDetailId(project.id)}
                  onKeyDown={(event) => {
                    // Ignore keys bubbling up from the icon buttons inside this row.
                    if (event.target !== event.currentTarget) return;
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setDetailId(project.id);
                    }
                  }}
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="h-8 w-8 rounded-md bg-secondary flex items-center justify-center shrink-0 text-sm leading-none">
                        {project.emoji}
                      </span>
                      <div className="min-w-0">
                        <p className="font-medium text-sm">{project.name}</p>
                        {due.text ? (
                          <p className={`text-xs ${due.overdue ? "text-destructive" : "text-muted-foreground"}`}>{due.text}</p>
                        ) : null}
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <p className={`text-sm font-semibold ${reached ? "text-emerald-500" : "text-foreground"}`}>
                        {currency.format(project.accumulated)}{" "}
                        <span className="text-muted-foreground font-normal">
                          / {currency.format(project.targetAmount)} ({Math.round(pct)}%)
                        </span>
                      </p>
                      {/* Row-level click opens the detail dialog; these controls must not. */}
                      <div className="flex items-center gap-1" onClick={(event) => event.stopPropagation()}>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          disabled={busyId === project.id || index === 0}
                          aria-label={`Move ${project.name} up`}
                          onClick={() => void handleMove(project, -1)}
                        >
                          <ChevronUp className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          disabled={busyId === project.id || index === projects.length - 1}
                          aria-label={`Move ${project.name} down`}
                          onClick={() => void handleMove(project, 1)}
                        >
                          <ChevronDown className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7"
                          aria-label={`Edit ${project.name}`}
                          onClick={() => openEdit(project)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          size="icon"
                          variant="ghost"
                          className="h-7 w-7 text-destructive hover:text-destructive"
                          disabled={busyId === project.id}
                          aria-label={`Delete ${project.name}`}
                          onClick={() => void handleDelete(project)}
                        >
                          {busyId === project.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      </div>
                    </div>
                  </div>
                  <Progress
                    value={Math.min(pct, 100)}
                    className={reached ? "[&>div]:bg-emerald-500" : "[&>div]:bg-accent"}
                  />
                </div>
              );
            })
          )}
        </CardContent>
      </Card>

      <Dialog open={detailProject !== null} onOpenChange={(open) => { if (!open) setDetailId(null); }}>
        <DialogContent className="sm:max-w-2xl">
          {detailProject ? (
            <>
              <DialogHeader>
                <DialogTitle>
                  {detailProject.emoji} {detailProject.name}
                </DialogTitle>
                <DialogDescription>
                  {currency.format(detailProject.accumulated)} of {currency.format(detailProject.targetAmount)} saved
                  {deadlineLabel(detailProject.deadline).text
                    ? ` — ${deadlineLabel(detailProject.deadline).text}`
                    : ""}
                </DialogDescription>
              </DialogHeader>

              <Progress
                value={Math.min(
                  detailProject.targetAmount > 0
                    ? (detailProject.accumulated / detailProject.targetAmount) * 100
                    : 0,
                  100,
                )}
                className={
                  detailProject.targetAmount > 0 && detailProject.accumulated >= detailProject.targetAmount
                    ? "[&>div]:bg-emerald-500"
                    : "[&>div]:bg-accent"
                }
              />

              <div className="grid grid-cols-3 gap-3">
                <div>
                  <p className="text-xs text-muted-foreground">Starting amount</p>
                  <p className="text-sm font-semibold">{currency.format(detailProject.initialAmount)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Income assigned</p>
                  <p className="text-sm font-semibold text-emerald-500">
                    +{currency.format(detailContributed)}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Total saved</p>
                  <p className="text-sm font-semibold">{currency.format(detailProject.accumulated)}</p>
                </div>
              </div>

              <div className="space-y-2">
                <p className="text-sm font-medium">Contribution history</p>
                {detailInflows.length === 0 ? (
                  <CenteredListMessage label="No income assigned to this project yet." />
                ) : (
                  <div className="max-h-[45vh] overflow-y-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Description</TableHead>
                          <TableHead>Date</TableHead>
                          <TableHead className="text-right">Amount</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailInflows.map((inflow) => (
                          <TableRow key={inflow.id}>
                            <TableCell className="font-medium">{inflow.item}</TableCell>
                            <TableCell className="text-muted-foreground">
                              {format(inflow.timestamp, "MMM d, yyyy")}
                            </TableCell>
                            <TableCell className="text-right font-semibold text-emerald-500">
                              +{currency.format(inflow.amount)}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                )}
                <p className="text-xs text-muted-foreground">
                  The starting amount is seed capital entered on the project itself, so it has no income entry and is
                  not listed above.
                </p>
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => setDetailId(null)}>
                  Close
                </Button>
                <Button
                  onClick={() => {
                    const project = detailProject;
                    setDetailId(null);
                    openEdit(project);
                  }}
                >
                  Edit Project
                </Button>
              </DialogFooter>
            </>
          ) : null}
        </DialogContent>
      </Dialog>

      <Dialog open={dialogOpen} onOpenChange={(open) => { if (!open && !saving) setDialogOpen(false); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingId ? "Edit Project" : "Add Project"}</DialogTitle>
            <DialogDescription>A long-term savings target with a deadline, funded by assigned income.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="project-name">Name</Label>
              <Input id="project-name" value={formName} onChange={(e) => setFormName(e.target.value)} disabled={saving} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-emoji">Emoji</Label>
              <Input id="project-emoji" value={formEmoji} onChange={(e) => setFormEmoji(e.target.value)} disabled={saving} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-initial">Current Amount</Label>
              <Input
                id="project-initial"
                type="number"
                inputMode="decimal"
                min="0"
                step="0.01"
                value={formInitialAmount}
                onChange={(e) => setFormInitialAmount(e.target.value)}
                disabled={saving}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-target">Target Amount</Label>
              <Input
                id="project-target"
                type="number"
                inputMode="decimal"
                min="0.01"
                step="0.01"
                value={formTarget}
                onChange={(e) => setFormTarget(e.target.value)}
                disabled={saving}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="project-deadline">Deadline</Label>
              <Input
                id="project-deadline"
                type="date"
                value={formDeadline}
                onChange={(e) => setFormDeadline(e.target.value)}
                disabled={saving}
              />
            </div>
            {formError ? <p className="text-sm text-destructive">{formError}</p> : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={() => void handleSubmit()} disabled={saving}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {editingId ? "Save" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CategoriesTab({
  categories,
  loading,
  onCreateCategory,
  onUpdateCategory,
  onDeleteCategory,
  onMoveCategory,
}: {
  categories: DashboardCategory[];
  loading: boolean;
  onCreateCategory: (payload: { name: string; emoji: string }) => Promise<void>;
  onUpdateCategory: (categoryName: string, payload: { name: string; emoji: string }) => Promise<void>;
  onDeleteCategory: (categoryName: string) => Promise<void>;
  onMoveCategory: (categoryName: string, direction: -1 | 1) => Promise<void>;
}) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingName, setEditingName] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formEmoji, setFormEmoji] = useState("🏷️");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [busyName, setBusyName] = useState<string | null>(null);

  // "Other" is a protected fallback category — it cannot be renamed, removed, or reordered.
  const movable = categories.filter((category) => category.name !== "Other");

  function openAdd() {
    setEditingName(null);
    setFormName("");
    setFormEmoji("🏷️");
    setFormError(null);
    setDialogOpen(true);
  }

  function openEdit(category: DashboardCategory) {
    setEditingName(category.name);
    setFormName(category.name);
    setFormEmoji(category.emoji);
    setFormError(null);
    setDialogOpen(true);
  }

  async function handleSubmit() {
    const name = formName.trim();
    const emoji = formEmoji.trim() || "🏷️";
    if (!name) {
      setFormError("Name is required.");
      return;
    }
    setSaving(true);
    setFormError(null);
    try {
      if (editingName) {
        await onUpdateCategory(editingName, { name, emoji });
      } else {
        await onCreateCategory({ name, emoji });
      }
      setDialogOpen(false);
    } catch (caught) {
      setFormError(caught instanceof Error ? caught.message : "Unable to save category.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(category: DashboardCategory) {
    if (!window.confirm(`Delete category "${category.name}"? Its transactions move to "Other".`)) return;
    setBusyName(category.name);
    try {
      await onDeleteCategory(category.name);
    } catch {
      // next refresh reconciles
    } finally {
      setBusyName(null);
    }
  }

  async function handleMove(category: DashboardCategory, direction: -1 | 1) {
    setBusyName(category.name);
    try {
      await onMoveCategory(category.name, direction);
    } catch {
      // next refresh reconciles
    } finally {
      setBusyName(null);
    }
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Categories</CardTitle>
          <Button size="sm" className="gap-1" onClick={openAdd}>
            <Plus className="h-4 w-4" />
            Add Category
          </Button>
        </CardHeader>
        <CardContent>
          {loading ? (
            <CenteredListMessage label="Loading categories..." />
          ) : categories.length === 0 ? (
            <CenteredListMessage label="No categories found." />
          ) : (
            <div className="space-y-1">
              {categories.map((category) => {
                const isOther = category.name === "Other";
                const movableIndex = movable.findIndex((entry) => entry.name === category.name);
                return (
                  <div
                    key={category.name}
                    className="flex items-center justify-between gap-3 rounded-lg px-2 py-2 hover:bg-secondary/50"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <span className="h-8 w-8 rounded-md bg-secondary flex items-center justify-center shrink-0 text-sm leading-none">
                        {category.emoji}
                      </span>
                      <p className="font-medium text-sm">{category.name}</p>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        disabled={isOther || busyName === category.name || movableIndex <= 0}
                        aria-label={`Move ${category.name} up`}
                        onClick={() => void handleMove(category, -1)}
                      >
                        <ChevronUp className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        disabled={isOther || busyName === category.name || movableIndex === movable.length - 1}
                        aria-label={`Move ${category.name} down`}
                        onClick={() => void handleMove(category, 1)}
                      >
                        <ChevronDown className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7"
                        disabled={isOther}
                        aria-label={`Edit ${category.name}`}
                        onClick={() => openEdit(category)}
                      >
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        className="h-7 w-7 text-destructive hover:text-destructive"
                        disabled={isOther || busyName === category.name}
                        aria-label={`Delete ${category.name}`}
                        onClick={() => void handleDelete(category)}
                      >
                        {busyName === category.name ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <Trash2 className="h-3.5 w-3.5" />
                        )}
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onOpenChange={(open) => { if (!open && !saving) setDialogOpen(false); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingName ? "Edit Category" : "Add Category"}</DialogTitle>
            <DialogDescription>Categories organise your expenses and budgets.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="category-name">Name</Label>
              <Input id="category-name" value={formName} onChange={(e) => setFormName(e.target.value)} disabled={saving} />
            </div>
            <div className="space-y-2">
              <Label htmlFor="category-emoji">Emoji</Label>
              <Input id="category-emoji" value={formEmoji} onChange={(e) => setFormEmoji(e.target.value)} disabled={saving} />
            </div>
            {formError ? <p className="text-sm text-destructive">{formError}</p> : null}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>
              Cancel
            </Button>
            <Button onClick={() => void handleSubmit()} disabled={saving}>
              {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              {editingName ? "Save" : "Create"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
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
