import {
  endOfDay,
  startOfDay,
  startOfMonth,
  startOfYear,
  subDays,
} from "date-fns";

import type {
  DashboardCategory,
  DashboardTransaction,
} from "@/lib/dashboard-api";

export type AnalyticsRangePreset =
  | "current-month"
  | "last-30-days"
  | "last-90-days"
  | "year-to-date"
  | "custom";

export type DateRangeValue = {
  from: Date;
  to: Date;
};

export type TrendPoint = {
  date: Date;
  total: number;
};

export type CategorySummary = {
  name: string;
  label: string;
  total: number;
};

export function analyticsRangePresetLabel(preset: AnalyticsRangePreset) {
  switch (preset) {
    case "current-month":
      return "Current month";
    case "last-30-days":
      return "Last 30 days";
    case "last-90-days":
      return "Last 90 days";
    case "year-to-date":
      return "Year to date";
    case "custom":
      return "Custom";
  }
}

export function analyticsRangeForPreset(
  preset: AnalyticsRangePreset,
  now = new Date(),
): DateRangeValue {
  switch (preset) {
    case "current-month":
      return { from: startOfMonth(now), to: endOfDay(now) };
    case "last-30-days":
      return { from: startOfDay(subDays(now, 29)), to: endOfDay(now) };
    case "last-90-days":
      return { from: startOfDay(subDays(now, 89)), to: endOfDay(now) };
    case "year-to-date":
      return { from: startOfYear(now), to: endOfDay(now) };
    case "custom":
      return { from: startOfMonth(now), to: endOfDay(now) };
  }
}

export function endExclusive(date: Date) {
  const result = startOfDay(date);
  result.setDate(result.getDate() + 1);
  return result;
}

export function analyticsCategorySelectionLabel(
  selectedCategories: Set<string>,
  categories: DashboardCategory[],
) {
  if (categories.length === 0) {
    return "All categories";
  }

  const orderedNames = categories.map((category) => category.name);
  if (
    selectedCategories.size >= orderedNames.length &&
    orderedNames.every((name) => selectedCategories.has(name))
  ) {
    return "All categories";
  }

  if (selectedCategories.size === 1) {
    return [...selectedCategories][0] ?? "All categories";
  }

  return `${selectedCategories.size} categories`;
}

export function filterTransactionsBySelectedCategories(
  transactions: DashboardTransaction[],
  selectedCategories: Set<string>,
) {
  if (selectedCategories.size === 0) {
    return transactions;
  }
  return transactions.filter((transaction) => selectedCategories.has(transaction.category));
}

export function buildCategorySummaries(
  transactions: DashboardTransaction[],
  categories: DashboardCategory[],
) {
  const emojiByCategory = new Map(categories.map((category) => [category.name, category.emoji]));
  const totals = new Map<string, number>();

  for (const transaction of transactions) {
    totals.set(transaction.category, (totals.get(transaction.category) ?? 0) + transaction.amount);
  }

  return [...totals.entries()]
    .map(([name, total]) => ({
      name,
      label: `${emojiByCategory.get(name) ?? "*"} ${name}`,
      total,
    }))
    .sort((a, b) => b.total - a.total);
}

export function buildTrendSeries(transactions: DashboardTransaction[]) {
  const totalsByDay = new Map<string, number>();

  for (const transaction of transactions) {
    const dayKey = startOfDay(transaction.timestamp).toISOString();
    totalsByDay.set(dayKey, (totalsByDay.get(dayKey) ?? 0) + transaction.amount);
  }

  return [...totalsByDay.entries()]
    .map(([key, total]) => ({ date: new Date(key), total }))
    .sort((a, b) => a.date.getTime() - b.date.getTime());
}

export type TransactionSortKey =
  | "date-desc"
  | "date-asc"
  | "category-asc"
  | "category-desc"
  | "amount-desc"
  | "amount-asc";

/** Sort options in menu order, shared by the desktop and mobile expense tabs. */
export const TRANSACTION_SORT_OPTIONS: { key: TransactionSortKey; label: string }[] = [
  { key: "date-desc", label: "Date (Newest)" },
  { key: "date-asc", label: "Date (Oldest)" },
  { key: "category-asc", label: "Category (A-Z)" },
  { key: "category-desc", label: "Category (Z-A)" },
  { key: "amount-desc", label: "Amount (High-Low)" },
  { key: "amount-asc", label: "Amount (Low-High)" },
];

export function sortTransactions(
  transactions: DashboardTransaction[],
  sortKey: TransactionSortKey,
) {
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
