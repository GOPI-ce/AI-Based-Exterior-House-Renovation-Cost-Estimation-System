const inr = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const num = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 });

export const formatINR = (value: number) => inr.format(Number.isFinite(value) ? value : 0);

export const formatNumber = (value: number) => num.format(Number.isFinite(value) ? value : 0);

/** ₹3,17,947 -> "₹3.18 lakh" for headline figures. */
export function formatINRShort(value: number): string {
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(2)} crore`;
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(2)} lakh`;
  return formatINR(value);
}

export function timeAgo(iso: string): string {
  const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
  if (seconds < 60) return "just now";
  if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)} h ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
}

export const uid = (prefix: string) => `${prefix}-${Math.random().toString(36).slice(2, 8)}`;
