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
};

export type DashboardCategory = {
  name: string;
  emoji: string;
  order: number;
};

export class DashboardApiError extends Error {
  constructor(message: string, readonly status?: number) {
    super(message);
    this.name = "DashboardApiError";
  }
}

const PROD_API_BASE_URL = "https://finance-bot-jrpmzkxwoa-eu.a.run.app";
const DEV_API_BASE_URL = "https://finance-bot-dev-jrpmzkxwoa-eu.a.run.app";
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
    if (host === "budget-bot-123-dev.web.app" || host === "budget-bot-123-dev.firebaseapp.com") {
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
  };
}

function parseCategory(data: Record<string, unknown>): DashboardCategory {
  return {
    name: String(data.name ?? ""),
    emoji: String(data.emoji ?? "Tag"),
    order: typeof data.order === "number" ? data.order : 9998,
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

export async function fetchDashboardCategories() {
  const data = await requestJson<{ categories?: Record<string, unknown>[] }>(
    "GET",
    "/dashboard/categories",
  );

  return (data.categories ?? []).map(parseCategory).sort((a, b) => a.order - b.order);
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
