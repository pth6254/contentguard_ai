import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

const KST = { timeZone: "Asia/Seoul" } as const

/** "2025-01-23" 형식 (KST) */
export function toKSTDate(utcStr: string): string {
  return new Date(utcStr.endsWith("Z") ? utcStr : utcStr + "Z")
    .toLocaleDateString("ko-KR", { ...KST, year: "numeric", month: "2-digit", day: "2-digit" })
    .replace(/\. /g, "-").replace(".", "")
}

/** "2025-01-23 14:05" 형식 (KST) */
export function toKSTDateTime(utcStr: string): string {
  return new Date(utcStr.endsWith("Z") ? utcStr : utcStr + "Z")
    .toLocaleString("ko-KR", { ...KST, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hour12: false })
    .replace(/\. /g, "-").replace(". ", " ").replace(".", "")
}
