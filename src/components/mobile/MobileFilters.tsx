import { useCallback, useEffect, useState } from "react";
import { endOfDay, startOfDay, startOfMonth, startOfYear, subDays } from "date-fns";
import { Check, ChevronDown, ListFilter } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  TRANSACTION_SORT_OPTIONS,
  type TransactionSortKey,
} from "@/lib/dashboard-analytics";
import type { DashboardCategory } from "@/lib/dashboard-api";

/** Same preset keys and labels as the desktop RangeSelector. */
export type MobileRangeKey =
  | "today"
  | "yesterday"
  | "weekly"
  | "current-month"
  | "30d"
  | "ytd";

export const MOBILE_RANGES: { key: MobileRangeKey; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "yesterday", label: "Yesterday" },
  { key: "weekly", label: "Weekly" },
  { key: "current-month", label: "Current Month" },
  { key: "30d", label: "Last 30 Days" },
  { key: "ytd", label: "Year to Date" },
];

export function mobileRange(key: MobileRangeKey): { from: Date; to: Date } {
  const today = new Date();
  switch (key) {
    case "today":
      return { from: startOfDay(today), to: endOfDay(today) };
    case "yesterday": {
      const yesterday = subDays(today, 1);
      return { from: startOfDay(yesterday), to: endOfDay(yesterday) };
    }
    case "weekly":
      return { from: startOfDay(subDays(today, 6)), to: endOfDay(today) };
    case "30d":
      return { from: startOfDay(subDays(today, 29)), to: endOfDay(today) };
    case "ytd":
      return { from: startOfYear(today), to: endOfDay(today) };
    case "current-month":
    default:
      return { from: startOfMonth(today), to: endOfDay(today) };
  }
}

export function MobileRangeSelect({
  value,
  onChange,
}: {
  value: MobileRangeKey;
  onChange: (key: MobileRangeKey) => void;
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as MobileRangeKey)}>
      <SelectTrigger className="h-10 flex-1">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {MOBILE_RANGES.map((r) => (
          <SelectItem key={r.key} value={r.key}>
            {r.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/**
 * Multi-select category filter, mirroring the desktop CategoryFilterPopover
 * (including its "Categories (n/m)" trigger label and All toggle).
 */
export function MobileCategoryFilter({
  categories,
  selected,
  isAllMode,
  onToggleAll,
  onToggleOne,
}: {
  categories: DashboardCategory[];
  selected: string[];
  isAllMode: boolean;
  onToggleAll: (all: boolean) => void;
  onToggleOne: (name: string, checked: boolean) => void;
}) {
  const shown = isAllMode ? categories.length : selected.length;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="outline" className="h-10 flex-1 justify-between gap-1 px-3">
          <span className="truncate text-sm">
            Categories ({shown}/{categories.length})
          </span>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-64 p-0">
        <div className="max-h-72 overflow-y-auto p-1">
          <label className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-3 text-sm font-medium">
            <Checkbox checked={isAllMode} onCheckedChange={(c) => onToggleAll(!!c)} />
            <span className="flex-1">All</span>
            {isAllMode ? <Check className="h-4 w-4 opacity-60" /> : null}
          </label>
          <div className="my-1 border-t" />
          {categories.map((category) => {
            const checked = isAllMode || selected.includes(category.name);
            return (
              <label
                key={category.name}
                className="flex min-h-11 cursor-pointer items-center gap-3 rounded-md px-3 text-sm"
              >
                <Checkbox
                  checked={checked}
                  onCheckedChange={(c) => onToggleOne(category.name, !!c)}
                />
                <span className="shrink-0">{category.emoji}</span>
                <span className="min-w-0 flex-1 truncate">{category.name}</span>
              </label>
            );
          })}
        </div>
      </PopoverContent>
    </Popover>
  );
}

/**
 * Shared category-selection state, matching the desktop CategoryFilterPopover:
 * "all mode" tracks every category (including ones added later), and unchecking
 * one drops out of all-mode into an explicit list.
 */
export function useCategorySelection(categories: DashboardCategory[]) {
  const [selected, setSelected] = useState<string[]>([]);
  const [isAllMode, setIsAllMode] = useState(true);

  useEffect(() => {
    if (isAllMode) setSelected(categories.map((c) => c.name));
  }, [categories, isAllMode]);

  // All three callbacks are stable so a caller can depend on them in an effect
  // without re-running it every render (the Expenses tab jump does exactly
  // that). They lean on the effect above rather than reading `categories`:
  // while in all-mode `selected` already holds every category name.
  const toggleAll = useCallback((all: boolean) => {
    setIsAllMode(all);
    if (!all) setSelected([]);
  }, []);

  const toggleOne = useCallback((name: string, checked: boolean) => {
    setIsAllMode(false);
    setSelected((current) =>
      checked ? [...new Set([...current, name])] : current.filter((n) => n !== name),
    );
  }, []);

  /** Used by the budget-tab jump to preselect exactly one category. */
  const selectOnly = useCallback((name: string) => {
    setIsAllMode(false);
    setSelected([name]);
  }, []);

  return { selected, isAllMode, toggleAll, toggleOne, selectOnly };
}

/** Sort trigger mirroring the desktop one: icon plus a static "Sort" label. */
export function MobileSortSelect({
  value,
  onChange,
}: {
  value: TransactionSortKey;
  onChange: (key: TransactionSortKey) => void;
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v as TransactionSortKey)}>
      <SelectTrigger className="h-10 flex-1" aria-label="Sort expenses">
        <div className="flex items-center gap-2">
          <ListFilter className="h-4 w-4 shrink-0 opacity-70" />
          <span className="truncate text-sm">Sort</span>
        </div>
      </SelectTrigger>
      <SelectContent>
        {TRANSACTION_SORT_OPTIONS.map((option) => (
          <SelectItem key={option.key} value={option.key}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

/**
 * Request from another tab to open Expenses with a filter already applied,
 * mirroring the desktop TxnJump. `version` re-triggers a repeat jump to the
 * same category.
 */
export type MobileTxnJump = {
  category: string | null;
  rangeKey: MobileRangeKey;
  version: number;
};
