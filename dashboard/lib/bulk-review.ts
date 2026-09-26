import type { Content, ReviewAction } from "@/lib/api"

export async function runBulkReview(
  items: Content[], action: ReviewAction,
  review: (item: Content, action: ReviewAction) => Promise<unknown>,
) {
  const outcomes = await Promise.allSettled(items.map(item => review(item, action)))
  const failures = outcomes.flatMap((outcome, index) => outcome.status === "rejected"
    ? [{ item: items[index], reason: outcome.reason }] : [])
  const conflicts = failures.filter(({ reason }) => typeof reason?.message === "string" && reason.message.includes("409")).length
  return { succeeded: items.length - failures.length, failures, conflicts }
}
