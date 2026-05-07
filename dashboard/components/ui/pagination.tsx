interface PaginationProps {
  page: number
  totalPages: number
  onPageChange: (page: number) => void
}

export function Pagination({ page, totalPages, onPageChange }: PaginationProps) {
  if (totalPages <= 1) return null

  const pages: (number | "...")[] = []

  if (totalPages <= 7) {
    for (let i = 0; i < totalPages; i++) pages.push(i)
  } else {
    const winStart = Math.max(1, page - 2)
    const winEnd   = Math.min(totalPages - 2, page + 2)
    pages.push(0)
    if (winStart > 1) pages.push("...")
    for (let i = winStart; i <= winEnd; i++) pages.push(i)
    if (winEnd < totalPages - 2) pages.push("...")
    pages.push(totalPages - 1)
  }

  const btnBase = "min-w-[2rem] px-2 py-1.5 rounded-md text-sm transition-colors"
  const btnIdle = `${btnBase} bg-slate-800 text-slate-400 hover:text-slate-100`
  const btnActive = `${btnBase} bg-indigo-600 text-white font-medium`
  const btnDisabled = `${btnBase} bg-slate-800 text-slate-600 cursor-not-allowed`

  return (
    <div className="flex items-center justify-end gap-1">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page === 0}
        className={page === 0 ? btnDisabled : btnIdle}
      >
        &lt;
      </button>

      {pages.map((p, i) =>
        p === "..." ? (
          <span key={`e${i}`} className="px-1 text-slate-600 text-sm select-none">…</span>
        ) : (
          <button
            key={p}
            onClick={() => onPageChange(p)}
            className={p === page ? btnActive : btnIdle}
          >
            {p + 1}
          </button>
        )
      )}

      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages - 1}
        className={page >= totalPages - 1 ? btnDisabled : btnIdle}
      >
        &gt;
      </button>
    </div>
  )
}
