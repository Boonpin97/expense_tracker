/**
 * Pure formatting helpers shared by the desktop and mobile dashboard trees.
 * Kept dependency-free so either presentation layer can import them without
 * pulling in the other.
 */

export const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 2,
});

/** Golden-angle hue walk so adjacent categories stay visually distinct. */
export function colorForCategory(index: number) {
  const hue = (index * 137.508) % 360;
  const lightness = [0.6, 0.68, 0.74][index % 3];
  const chroma = [0.2, 0.16, 0.13][index % 3];
  return `oklch(${lightness} ${chroma} ${hue})`;
}

/** Local-time value for an <input type="datetime-local">. */
export function formatDateTimeInputValue(value: Date) {
  const year = value.getFullYear();
  const month = String(value.getMonth() + 1).padStart(2, "0");
  const day = String(value.getDate()).padStart(2, "0");
  const hours = String(value.getHours()).padStart(2, "0");
  const minutes = String(value.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

export function deadlineLabel(deadline: string): { text: string; overdue: boolean } {
  const due = new Date(deadline);
  if (Number.isNaN(due.getTime())) return { text: "", overdue: false };
  const today = new Date();
  const startOfToday = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const startOfDue = new Date(due.getFullYear(), due.getMonth(), due.getDate());
  const days = Math.round((startOfDue.getTime() - startOfToday.getTime()) / 86400000);
  if (days < 0)
    return {
      text: `Overdue by ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"}`,
      overdue: true,
    };
  if (days === 0) return { text: "Due today", overdue: false };
  return { text: `${days} day${days === 1 ? "" : "s"} left`, overdue: false };
}

/** Whole-dollar formatter for derived figures — projected rates read cleaner without cents. */
export const currencyWhole = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const DAYS_PER_MONTH = 30.44;

export type ProjectStatusKey = "complete" | "review" | "on-track" | "behind" | "new";

export type ProjectSummary = {
  pct: number;
  reached: boolean;
  remaining: number;
  /** Days until the deadline; negative once it has passed, null when unparseable. */
  daysLeft: number | null;
  /** Amount per month still needed to land on the target; null once the deadline has passed. */
  monthlyNeeded: number | null;
  status: { key: ProjectStatusKey; label: string };
  /** "Target Jun 16, 2029", "14d left · Sep 16, 2026", "Target date passed · Jun 16, 2026". */
  targetText: string;
  overdue: boolean;
  subtitle: string;
};

/**
 * Everything a project card shows beyond its raw fields.
 *
 * The status badge is pace-based: a project is on track when the average
 * monthly contribution since its first assigned income already covers the
 * monthly amount still needed. Projects with no contributions yet have no pace
 * to judge, so they read as "New" rather than "Behind".
 */
export function projectSummary(
  project: { targetAmount: number; accumulated: number; deadline: string },
  contributions: { amount: number; timestamp: Date }[],
): ProjectSummary {
  const pct = project.targetAmount > 0 ? (project.accumulated / project.targetAmount) * 100 : 0;
  const reached = project.targetAmount > 0 && project.accumulated >= project.targetAmount;
  const remaining = Math.max(project.targetAmount - project.accumulated, 0);

  const due = new Date(project.deadline);
  const hasDeadline = !Number.isNaN(due.getTime());
  const now = new Date();
  const startOfToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const daysLeft = hasDeadline
    ? Math.round(
        (new Date(due.getFullYear(), due.getMonth(), due.getDate()).getTime() -
          startOfToday.getTime()) /
          86400000,
      )
    : null;

  const monthsLeft = daysLeft !== null && daysLeft > 0 ? daysLeft / DAYS_PER_MONTH : null;
  const monthlyNeeded = monthsLeft !== null && remaining > 0 ? remaining / monthsLeft : null;

  let targetText = "";
  if (hasDeadline && daysLeft !== null) {
    const date = due.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
    if (daysLeft < 0) targetText = `Target date passed · ${date}`;
    else if (daysLeft === 0) targetText = `Due today · ${date}`;
    else if (daysLeft <= 30) targetText = `${daysLeft}d left · ${date}`;
    else targetText = `Target ${date}`;
  }

  let status: ProjectSummary["status"];
  if (reached) {
    status = { key: "complete", label: "Complete" };
  } else if (daysLeft !== null && daysLeft < 0) {
    status = { key: "review", label: "Review" };
  } else if (contributions.length === 0) {
    status = { key: "new", label: "New" };
  } else {
    const contributed = contributions.reduce((sum, entry) => sum + entry.amount, 0);
    const firstAt = contributions.reduce(
      (earliest, entry) => Math.min(earliest, entry.timestamp.getTime()),
      contributions[0].timestamp.getTime(),
    );
    // Floor the window at one month so a single fresh contribution cannot imply
    // an implausibly high monthly pace.
    const monthsElapsed = Math.max((now.getTime() - firstAt) / (DAYS_PER_MONTH * 86400000), 1);
    const pace = contributed / monthsElapsed;
    status =
      monthlyNeeded === null || pace >= monthlyNeeded
        ? { key: "on-track", label: "On track" }
        : { key: "behind", label: "Behind" };
  }

  const subtitle =
    contributions.length === 0
      ? "Long-term · no contributions yet"
      : `Long-term · ${contributions.length} contribution${contributions.length === 1 ? "" : "s"}`;

  return {
    pct,
    reached,
    remaining,
    daysLeft,
    monthlyNeeded,
    status,
    targetText,
    overdue: daysLeft !== null && daysLeft < 0,
    subtitle,
  };
}
