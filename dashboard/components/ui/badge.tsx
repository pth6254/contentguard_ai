import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors",
  {
    variants: {
      variant: {
        LOW: "bg-emerald-900/50 text-emerald-400 border border-emerald-800",
        MEDIUM: "bg-yellow-900/50 text-yellow-400 border border-yellow-800",
        HIGH: "bg-orange-900/50 text-orange-400 border border-orange-800",
        CRITICAL: "bg-red-900/50 text-red-400 border border-red-800",
        PENDING: "bg-slate-700 text-slate-300 border border-slate-600",
        APPROVED: "bg-emerald-900/50 text-emerald-400 border border-emerald-800",
        REMOVED: "bg-red-900/50 text-red-400 border border-red-800",
        HELD: "bg-yellow-900/50 text-yellow-400 border border-yellow-800",
        MONITORED: "bg-blue-900/50 text-blue-400 border border-blue-800",
      },
    },
    defaultVariants: { variant: "PENDING" },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
