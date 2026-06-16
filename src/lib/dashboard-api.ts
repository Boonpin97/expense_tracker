export type DashboardSession = {
  username: string;
  chatId: number;
};

export type DashboardTransaction = {
  id: string;
  item: string;
  amount: number;
  category: string;
  timestamp: Date;
  chatId: number;
  sourceType: string;
  sourcePlanId: string | null;
};

export type DashboardInflow = {
  id: string;
  item: string;
  amount: number;
  timestamp: Date;
  chatId: number;
  goalId: string | null;
  projectId: string | null;
};

export type DashboardGoal = {
  id: string;
  name: string;
  emoji: string;
  targetAmount: number;
  accumulated: number;
  order: number;
};

export type DashboardProject = {
  id: string;
  name: string;
  emoji: string;
  targetAmount: number;
  accumulated: number;
  deadline: string;
  order: number;
};

export type DashboardCategory = {
  name: string;
  emoji: string;
  order: number;
};

export type DashboardPlan = {
  id: string;
  planType: "recurring" | "split_payment";
  item: string;
  category: string;
  dayOfMonth: number;
  status: "active" | "cancelled" | "completed";
  nextDueDate: string | null;
  startYear: number;
  startMonth: number;
  // recurring only
  amount: number;
  // split only
  totalAmount: number;
  installmentCount: number;
  currentInstallmentNumber: number;
  baseInstallmentAmount: number;
  finalInstallmentAmount: number;
};

export type DashboardPaymentType = "one_time" | "split_payment" | "recurring";

export type DashboardPreferences = {
  overviewVisibleCards: string[];
};

export class DashboardApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "DashboardApiError";
  }
}

const PROD_API_BASE_URL = "https://finance-bot-318969558548.asia-southeast3.run.app";
const DEV_API_BASE_URL = "https://finance-bot-dev-318969558548.asia-southeast3.run.app";
const SESSION_STORAGE_KEY = "dashboard_session_token";

function readStoredSessionToken() {
  if (typeof window === "undefined") {
    return null;
  }
  return window.localStorage.getItem(SESSION_STORAGE_KEY);
}

function writeStoredSessionToken(token: string | null) {
  if (typeof window === "undefined") {
    return;
  }
  if (token) {
    window.localStorage.setItem(SESSION_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(SESSION_STORAGE_KEY);
  }
}

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, "");
}

export function getDashboardApiBaseUrl() {
  const configured = import.meta.env.VITE_DASHBOARD_API_BASE_URL;
  if (configured) {
    return trimTrailingSlash(configured);
  }

  if (typeof window !== "undefined") {
    const host = window.location.host.toLowerCase();
    if (
      host === "budget-bot-123-dev.web.app" ||
      host === "budget-bot-123-dev.firebaseapp.com" ||
      host === "budget-flow-123-dev.web.app" ||
      host === "budget-flow-123-dev.firebaseapp.com" ||
      host.startsWith("localhost") ||
      host.startsWith("127.0.0.1")
    ) {
      return DEV_API_BASE_URL;
    }
  }

  return PROD_API_BASE_URL;
}

function buildUrl(path: string, query: Record<string, string | undefined> = {}) {
  const url = new URL(`${getDashboardApiBaseUrl()}${path}`);
  for (const [key, value] of Object.entries(query)) {
    if (value) {
      url.searchParams.set(key, value);
    }
  }
  return url.toString();
}

async function decodeResponse(response: Response) {
  const text = await response.text();
  if (!text) {
    return null;
  }
  return JSON.parse(text) as unknown;
}

async function requestJson<T>(
  method: "GET" | "POST" | "PATCH" | "DELETE",
  path: string,
  options: {
    query?: Record<string, string | undefined>;
    body?: unknown;
  } = {},
) {
  const response = await fetch(buildUrl(path, options.query), {
    method,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(readStoredSessionToken() ? { "X-Dashboard-Session": readStoredSessionToken()! } : {}),
    },
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });

  const decoded = await decodeResponse(response);
  if (response.ok) {
    return decoded as T;
  }

  const message =
    decoded && typeof decoded === "object"
      ? String(
          (decoded as Record<string, unknown>).detail ??
            (decoded as Record<string, unknown>).message ??
            "Request failed.",
        )
      : "Request failed.";
  throw new DashboardApiError(message, response.status);
}

function parseSession(data: Record<string, unknown>): DashboardSession {
  return {
    username: String(data.username ?? ""),
    chatId: typeof data.chat_id === "number" ? data.chat_id : 0,
  };
}

function parseTransaction(data: Record<string, unknown>): DashboardTransaction {
  return {
    id: String(data._doc_id ?? data.id ?? ""),
    item: String(data.item ?? ""),
    amount: typeof data.amount === "number" ? data.amount : 0,
    category: String(data.category ?? "Other"),
    timestamp: new Date(String(data.timestamp ?? "")),
    chatId: typeof data.chat_id === "number" ? data.chat_id : 0,
    sourceType: String(data.source_type ?? "manual"),
    sourcePlanId: data.source_plan_id ? String(data.source_plan_id) : null,
  };
}

function parseInflow(data: Record<string, unknown>): DashboardInflow {
  return {
    id: String(data._doc_id ?? data.id ?? ""),
    item: String(data.item ?? ""),
    amount: typeof data.amount === "number" ? data.amount : 0,
    timestamp: new Date(String(data.timestamp ?? "")),
    chatId: typeof data.chat_id === "number" ? data.chat_id : 0,
    goalId: data.goal_id ? String(data.goal_id) : null,
    projectId: data.project_id ? String(data.project_id) : null,
  };
}

function parseGoal(data: Record<string, unknown>): DashboardGoal {
  return {
    id: String(data.id ?? ""),
    name: String(data.name ?? ""),
    emoji: String(data.emoji ?? "🎯"),
    targetAmount: typeof data.target_amount === "number" ? data.target_amount : 0,
    accumulated: typeof data.accumulated === "number" ? data.accumulated : 0,
    order: typeof data.order === "number" ? data.order : 0,
  };
}

function parseProject(data: Record<string, unknown>): DashboardProject {
  return {
    id: String(data.id ?? ""),
    name: String(data.name ?? ""),
    emoji: String(data.emoji ?? "🚀"),
    targetAmount: typeof data.target_amount === "number" ? data.target_amount : 0,
    accumulated: typeof data.accumulated === "number" ? data.accumulated : 0,
    deadline: String(data.deadline ?? ""),
    order: typeof data.order === "number" ? data.order : 0,
  };
}

function parseCategory(data: Record<string, unknown>): DashboardCategory {
  return {
    name: String(data.name ?? ""),
    emoji: String(data.emoji ?? "Tag"),
    order: typeof data.order === "number" ? data.order : 9998,
  };
}

function parsePreferences(data: Record<string, unknown> | undefined): DashboardPreferences {
  const rawCards = data?.overview_visible_cards;
  return {
    overviewVisibleCards:
      rawCards === undefined
        ? ["today", "week", "month", "budget"]
        : Array.isArray(rawCards)
          ? rawCards.filter((value): value is string => typeof value === "string")
          : ["today", "week", "month", "budget"],
  };
}

export async function fetchDashboardSession() {
  const data = await requestJson<Record<string, unknown>>("GET", "/dashboard/auth/session");
  if (!data || data.authenticated !== true) {
    writeStoredSessionToken(null);
    return null;
  }
  return parseSession(data);
}

export async function loginToDashboard(username: string, password: string) {
  const data = await requestJson<Record<string, unknown>>("POST", "/dashboard/auth/login", {
    body: {
      username: username.trim(),
      password,
    },
  });

  if (!data || data.authenticated !== true) {
    throw new DashboardApiError("Login did not return an authenticated session.");
  }

  const token = typeof data.session_token === "string" ? data.session_token : "";
  if (token) {
    writeStoredSessionToken(token);
  }

  return parseSession(data);
}

export async function logoutFromDashboard() {
  await requestJson("POST", "/dashboard/auth/logout");
  writeStoredSessionToken(null);
}

export async function fetchDashboardTransactions(options: {
  start: Date;
  end: Date;
  category?: string;
}) {
  const data = await requestJson<{ transactions?: Record<string, unknown>[] }>(
    "GET",
    "/dashboard/transactions",
    {
      query: {
        start: options.start.toISOString(),
        end: options.end.toISOString(),
        category: options.category,
      },
    },
  );

  return (data.transactions ?? []).map(parseTransaction);
}

export async function updateDashboardTransaction(
  transactionId: string,
  payload: {
    item: string;
    amount: number;
    category: string;
    timestamp: Date;
  },
) {
  await requestJson("PATCH", `/dashboard/transactions/${transactionId}`, {
    body: {
      item: payload.item,
      amount: payload.amount,
      category: payload.category,
      timestamp: payload.timestamp.toISOString(),
    },
  });
}

export async function deleteDashboardTransaction(transactionId: string) {
  await requestJson("DELETE", `/dashboard/transactions/${transactionId}`);
}

export async function fetchDashboardInflows(options: { start: Date; end: Date }) {
  const data = await requestJson<{ inflows?: Record<string, unknown>[] }>(
    "GET",
    "/dashboard/inflows",
    {
      query: {
        start: options.start.toISOString(),
        end: options.end.toISOString(),
      },
    },
  );

  return (data.inflows ?? []).map(parseInflow);
}

export async function createDashboardInflow(payload: {
  item: string;
  amount: number;
  timestamp: Date;
  goalId?: string | null;
  projectId?: string | null;
}) {
  await requestJson("POST", "/dashboard/inflows", {
    body: {
      item: payload.item,
      amount: payload.amount,
      timestamp: payload.timestamp.toISOString(),
      ...(payload.goalId ? { goal_id: payload.goalId } : {}),
      ...(payload.projectId ? { project_id: payload.projectId } : {}),
    },
  });
}

export async function deleteDashboardInflow(inflowId: string) {
  await requestJson("DELETE", `/dashboard/inflows/${inflowId}`);
}

export async function fetchDashboardCategories() {
  const data = await requestJson<{ categories?: Record<string, unknown>[] }>(
    "GET",
    "/dashboard/categories",
  );

  return (data.categories ?? []).map(parseCategory).sort((a, b) => a.order - b.order);
}

export async function createDashboardCategory(payload: { name: string; emoji: string }) {
  await requestJson("POST", "/dashboard/categories", {
    body: { name: payload.name, emoji: payload.emoji },
  });
}

export async function updateDashboardCategory(
  categoryName: string,
  payload: { name: string; emoji: string },
) {
  await requestJson("PATCH", `/dashboard/categories/${encodeURIComponent(categoryName)}`, {
    body: { name: payload.name, emoji: payload.emoji },
  });
}

export async function deleteDashboardCategory(categoryName: string) {
  await requestJson("DELETE", `/dashboard/categories/${encodeURIComponent(categoryName)}`);
}

export async function moveDashboardCategory(categoryName: string, direction: -1 | 1) {
  await requestJson("POST", `/dashboard/categories/${encodeURIComponent(categoryName)}/move`, {
    body: { direction },
  });
}

export async function fetchDashboardGoals() {
  const data = await requestJson<{ goals?: Record<string, unknown>[] }>(
    "GET",
    "/dashboard/goals",
  );

  return (data.goals ?? []).map(parseGoal);
}

export async function createDashboardGoal(payload: {
  name: string;
  targetAmount: number;
  emoji: string;
}) {
  await requestJson("POST", "/dashboard/goals", {
    body: { name: payload.name, target_amount: payload.targetAmount, emoji: payload.emoji },
  });
}

export async function updateDashboardGoal(
  goalId: string,
  payload: { name?: string; targetAmount?: number; emoji?: string },
) {
  await requestJson("PATCH", `/dashboard/goals/${goalId}`, {
    body: {
      ...(payload.name !== undefined ? { name: payload.name } : {}),
      ...(payload.targetAmount !== undefined ? { target_amount: payload.targetAmount } : {}),
      ...(payload.emoji !== undefined ? { emoji: payload.emoji } : {}),
    },
  });
}

export async function deleteDashboardGoal(goalId: string) {
  await requestJson("DELETE", `/dashboard/goals/${goalId}`);
}

export async function moveDashboardGoal(goalId: string, direction: -1 | 1) {
  await requestJson("POST", `/dashboard/goals/${goalId}/move`, {
    body: { direction },
  });
}

export async function fetchDashboardProjects() {
  const data = await requestJson<{ projects?: Record<string, unknown>[] }>(
    "GET",
    "/dashboard/projects",
  );

  return (data.projects ?? []).map(parseProject);
}

export async function createDashboardProject(payload: {
  name: string;
  targetAmount: number;
  deadline: string;
  emoji: string;
}) {
  await requestJson("POST", "/dashboard/projects", {
    body: {
      name: payload.name,
      target_amount: payload.targetAmount,
      deadline: payload.deadline,
      emoji: payload.emoji,
    },
  });
}

export async function updateDashboardProject(
  projectId: string,
  payload: { name?: string; targetAmount?: number; deadline?: string; emoji?: string },
) {
  await requestJson("PATCH", `/dashboard/projects/${projectId}`, {
    body: {
      ...(payload.name !== undefined ? { name: payload.name } : {}),
      ...(payload.targetAmount !== undefined ? { target_amount: payload.targetAmount } : {}),
      ...(payload.deadline !== undefined ? { deadline: payload.deadline } : {}),
      ...(payload.emoji !== undefined ? { emoji: payload.emoji } : {}),
    },
  });
}

export async function deleteDashboardProject(projectId: string) {
  await requestJson("DELETE", `/dashboard/projects/${projectId}`);
}

export async function moveDashboardProject(projectId: string, direction: -1 | 1) {
  await requestJson("POST", `/dashboard/projects/${projectId}/move`, {
    body: { direction },
  });
}

export async function fetchDashboardBudgets() {
  const data = await requestJson<{ budgets?: Record<string, unknown> }>(
    "GET",
    "/dashboard/budgets",
  );

  const budgets: Record<string, number> = {};
  for (const [key, value] of Object.entries(data.budgets ?? {})) {
    if (typeof value === "number") {
      budgets[key] = value;
    }
  }
  return budgets;
}

export async function updateDashboardBudget(categoryName: string, amount: number): Promise<void> {
  await requestJson("PATCH", `/dashboard/budgets/${encodeURIComponent(categoryName)}`, {
    body: { amount },
  });
}

export async function deleteDashboardBudget(categoryName: string): Promise<void> {
  await requestJson("DELETE", `/dashboard/budgets/${encodeURIComponent(categoryName)}`);
}

function parsePlan(data: Record<string, unknown>): DashboardPlan {
  return {
    id: String(data.id ?? data._doc_id ?? ""),
    planType: data.plan_type === "split_payment" ? "split_payment" : "recurring",
    item: String(data.item ?? ""),
    category: String(data.category ?? ""),
    dayOfMonth: typeof data.day_of_month === "number" ? data.day_of_month : 1,
    status: (data.status as DashboardPlan["status"]) ?? "active",
    nextDueDate: data.next_due_date ? String(data.next_due_date) : null,
    startYear: typeof data.start_year === "number" ? data.start_year : 0,
    startMonth: typeof data.start_month === "number" ? data.start_month : 0,
    amount: typeof data.amount === "number" ? data.amount : 0,
    totalAmount: typeof data.total_amount === "number" ? data.total_amount : 0,
    installmentCount: typeof data.installment_count === "number" ? data.installment_count : 0,
    currentInstallmentNumber:
      typeof data.current_installment_number === "number" ? data.current_installment_number : 0,
    baseInstallmentAmount:
      typeof data.base_installment_amount === "number" ? data.base_installment_amount : 0,
    finalInstallmentAmount:
      typeof data.final_installment_amount === "number" ? data.final_installment_amount : 0,
  };
}

export async function fetchDashboardPlans(): Promise<DashboardPlan[]> {
  const data = await requestJson<{ plans?: Record<string, unknown>[] }>("GET", "/dashboard/plans");
  return (data.plans ?? []).map(parsePlan);
}

export async function updateDashboardPlan(
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
): Promise<void> {
  await requestJson("PATCH", `/dashboard/plans/${planId}`, {
    body: {
      ...(payload.item !== undefined ? { item: payload.item } : {}),
      ...(payload.category !== undefined ? { category: payload.category } : {}),
      ...(payload.dayOfMonth !== undefined ? { day_of_month: payload.dayOfMonth } : {}),
      ...(payload.startDate !== undefined ? { start_date: payload.startDate } : {}),
      ...(payload.amount !== undefined ? { amount: payload.amount } : {}),
      ...(payload.totalAmount !== undefined ? { total_amount: payload.totalAmount } : {}),
      ...(payload.installmentCount !== undefined
        ? { installment_count: payload.installmentCount }
        : {}),
    },
  });
}

export async function fetchDashboardPreferences(): Promise<DashboardPreferences> {
  const data = await requestJson<{ preferences?: Record<string, unknown> }>(
    "GET",
    "/dashboard/preferences",
  );
  return parsePreferences(data.preferences);
}

export async function updateDashboardPreferences(payload: {
  overviewVisibleCards: string[];
}): Promise<void> {
  await requestJson("PATCH", "/dashboard/preferences", {
    body: {
      overview_visible_cards: payload.overviewVisibleCards,
    },
  });
}

export async function createDashboardTransaction(payload: {
  item: string;
  amount: number;
  category: string;
  timestamp: Date;
  paymentType: DashboardPaymentType;
  dayOfMonth?: number;
  startDate?: string; // split: ISO date the plan starts
  numberOfMonths?: number; // split: months to spread across
  createFirstTransactionNow?: boolean;
}) {
  await requestJson("POST", "/dashboard/transactions", {
    body: {
      item: payload.item,
      amount: payload.amount,
      category: payload.category,
      timestamp: payload.timestamp.toISOString(),
      payment_type: payload.paymentType,
      ...(payload.dayOfMonth !== undefined ? { day_of_month: payload.dayOfMonth } : {}),
      ...(payload.startDate !== undefined ? { start_date: payload.startDate } : {}),
      ...(payload.numberOfMonths !== undefined
        ? { number_of_months: payload.numberOfMonths }
        : {}),
      ...(payload.createFirstTransactionNow !== undefined
        ? { create_first_transaction_now: payload.createFirstTransactionNow }
        : {}),
    },
  });
}

export async function deleteDashboardPlan(
  planId: string,
  mode: "future" | "all",
): Promise<void> {
  await requestJson("DELETE", `/dashboard/plans/${planId}`, {
    query: { mode },
  });
}
