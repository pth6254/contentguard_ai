import type { EvidenceSpan } from "@/lib/api"

const SEVERITY_STYLE: Record<EvidenceSpan["severity"], string> = {
  critical: "bg-red-500/25 text-red-300 rounded px-0.5",
  high:     "bg-orange-500/25 text-orange-300 rounded px-0.5",
  medium:   "bg-yellow-500/25 text-yellow-300 rounded px-0.5",
  low:      "bg-slate-600/40 text-slate-300 rounded px-0.5",
}

interface Props {
  text: string
  spans: EvidenceSpan[]
}

/**
 * evidence_spans의 start/end index를 이용해 위험 문구를 인라인 하이라이트로 렌더링한다.
 * 겹치는 스팬은 앞의 것을 우선하고 뒤의 것은 건너뛴다.
 */
export function HighlightedText({ text, spans }: Props) {
  if (!spans || spans.length === 0) {
    return <span className="text-sm text-slate-200">{text}</span>
  }

  // 겹침 제거: start_index 오름차순 정렬 후 끝점 기준 겹침 필터링
  const sorted = [...spans]
    .sort((a, b) => a.start_index - b.start_index)
    .filter((s) => s.start_index >= 0 && s.end_index <= text.length && s.start_index < s.end_index)

  const deduped: EvidenceSpan[] = []
  let cursor = 0
  for (const span of sorted) {
    if (span.start_index >= cursor) {
      deduped.push(span)
      cursor = span.end_index
    }
  }

  const parts: React.ReactNode[] = []
  let pos = 0
  for (const span of deduped) {
    if (span.start_index > pos) {
      parts.push(
        <span key={`pre-${pos}`} className="text-slate-200">
          {text.slice(pos, span.start_index)}
        </span>
      )
    }
    parts.push(
      <span
        key={`span-${span.start_index}`}
        className={SEVERITY_STYLE[span.severity] ?? SEVERITY_STYLE.low}
        title={span.category}
      >
        {text.slice(span.start_index, span.end_index)}
      </span>
    )
    pos = span.end_index
  }
  if (pos < text.length) {
    parts.push(
      <span key="tail" className="text-slate-200">
        {text.slice(pos)}
      </span>
    )
  }

  return <p className="text-sm leading-relaxed">{parts}</p>
}
