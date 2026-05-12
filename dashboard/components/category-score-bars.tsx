import type { CategoryScores } from "@/lib/api"

const CAT_KO: Record<keyof CategoryScores, string> = {
  threat:           "협박/폭력",
  profanity:        "욕설/비방",
  self_harm:        "자해/자살",
  sexual:           "성적 표현",
  privacy:          "개인정보",
  policy_violation: "정책 위반",
  spam:             "스팸/도배",
}

// 점수에 따른 바 색상
function barColor(score: number): string {
  if (score >= 80) return "bg-red-500"
  if (score >= 60) return "bg-orange-500"
  if (score >= 40) return "bg-yellow-500"
  return "bg-emerald-500"
}

interface Props {
  scores: CategoryScores
}

export function CategoryScoreBars({ scores }: Props) {
  const nonZero = (Object.entries(scores) as [keyof CategoryScores, number][])
    .filter(([, v]) => v > 0)
    .sort(([, a], [, b]) => b - a)

  if (nonZero.length === 0) return null

  return (
    <div className="space-y-1">
      {nonZero.map(([cat, score]) => (
        <div key={cat} className="flex items-center gap-2">
          <span className="text-[10px] text-slate-500 w-20 shrink-0 text-right">
            {CAT_KO[cat]}
          </span>
          <div className="flex-1 h-1.5 bg-slate-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${barColor(score)}`}
              style={{ width: `${score}%` }}
            />
          </div>
          <span className="text-[10px] font-mono text-slate-400 w-6 text-right">{score}</span>
        </div>
      ))}
    </div>
  )
}
