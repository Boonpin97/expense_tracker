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
