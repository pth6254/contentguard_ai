"use client"
import { useCallback, useRef, useState } from "react"
import { Upload, FileText, X, CheckCircle, AlertCircle } from "lucide-react"
import { Button } from "@/components/ui/button"
import { api, type UploadResult } from "@/lib/api"

interface PreviewRow {
  content_id: string
  text: string
}

function parseCsvLine(line: string): string[] {
  const result: string[] = []
  let current = ""
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') { current += '"'; i++ }
      else inQuotes = !inQuotes
    } else if (ch === ',' && !inQuotes) {
      result.push(current); current = ""
    } else {
      current += ch
    }
  }
  result.push(current)
  return result
}

function parseCsv(text: string): { rows: PreviewRow[]; error: string | null } {
  const lines = text.split(/\r?\n/).filter(Boolean)
  if (lines.length < 2) return { rows: [], error: null }
  const headers = parseCsvLine(lines[0]).map(h => h.trim())
  const cidIdx = headers.indexOf("content_id")
  const txtIdx = headers.indexOf("text")
  if (cidIdx === -1 || txtIdx === -1)
    return { rows: [], error: "'content_id'와 'text' 컬럼이 없습니다." }
  const rows = lines.slice(1).map(line => {
    const cols = parseCsvLine(line)
    return { content_id: (cols[cidIdx] ?? "").trim(), text: (cols[txtIdx] ?? "").trim() }
  })
  return { rows, error: null }
}

export default function UploadPage() {
  const [file, setFile]         = useState<File | null>(null)
  const [preview, setPreview]   = useState<PreviewRow[]>([])
  const [parseError, setParseError] = useState<string | null>(null)
  const [uploading, setUploading]   = useState(false)
  const [result, setResult]     = useState<UploadResult | null>(null)
  const [uploadError, setUploadError] = useState<string | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleFile = (f: File) => {
    setFile(f); setResult(null); setUploadError(null)
    const reader = new FileReader()
    reader.onload = e => {
      const { rows, error } = parseCsv(e.target?.result as string)
      setPreview(rows); setParseError(error)
    }
    reader.readAsText(f, "utf-8")
  }

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    const f = e.dataTransfer.files[0]
    if (f?.name.endsWith(".csv")) handleFile(f)
  }, [])

  const handleUpload = async () => {
    if (!file) return
    setUploading(true); setUploadError(null)
    try {
      setResult(await api.uploadFile(file))
    } catch (e: unknown) {
      setUploadError(e instanceof Error ? e.message : String(e))
    } finally {
      setUploading(false)
    }
  }

  const reset = () => { setFile(null); setPreview([]); setParseError(null); setResult(null); setUploadError(null) }

  return (
    <div className="space-y-6 max-w-3xl">
      <h1 className="text-2xl font-bold text-slate-100">CSV 일괄 업로드</h1>
      <p className="text-sm text-slate-400">
        <code className="bg-slate-800 px-1 rounded text-slate-300">content_id</code>,{" "}
        <code className="bg-slate-800 px-1 rounded text-slate-300">text</code> 컬럼을 포함한 CSV 파일을 업로드하세요.
        최대 1,000건 · UTF-8 인코딩 · LLM 설명 생략
      </p>

      {/* 드롭존 */}
      {!file && (
        <div
          onDrop={handleDrop}
          onDragOver={e => e.preventDefault()}
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-slate-600 bg-slate-800/40 p-12 cursor-pointer hover:border-indigo-500 hover:bg-slate-800/60 transition-colors"
        >
          <Upload className="h-8 w-8 text-slate-500" />
          <p className="text-slate-400 text-sm">클릭하거나 CSV 파일을 드래그하세요</p>
          <input
            ref={inputRef} type="file" accept=".csv" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) handleFile(f) }}
          />
        </div>
      )}

      {/* 파일 선택됨 */}
      {file && !result && (
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-slate-300">
              <FileText className="h-4 w-4 text-indigo-400" />
              <span className="text-sm font-medium">{file.name}</span>
              <span className="text-xs text-slate-500">{preview.length}건</span>
            </div>
            <button onClick={reset} className="text-slate-500 hover:text-slate-300">
              <X className="h-4 w-4" />
            </button>
          </div>

          {parseError && (
            <p className="text-xs text-red-400 flex items-center gap-1">
              <AlertCircle className="h-3.5 w-3.5" /> {parseError}
            </p>
          )}

          {preview.length > 0 && (
            <div className="overflow-x-auto rounded-md border border-slate-700">
              <table className="w-full text-xs">
                <thead>
                  <tr className="bg-slate-900 border-b border-slate-700">
                    <th className="text-left px-3 py-2 text-slate-500 font-medium w-32">content_id</th>
                    <th className="text-left px-3 py-2 text-slate-500 font-medium">text</th>
                  </tr>
                </thead>
                <tbody>
                  {preview.slice(0, 5).map((row, i) => (
                    <tr key={i} className="border-b border-slate-700/50 last:border-0">
                      <td className="px-3 py-2 font-mono text-slate-400 whitespace-nowrap">{row.content_id}</td>
                      <td className="px-3 py-2 text-slate-300 truncate max-w-xs">{row.text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {preview.length > 5 && (
                <p className="text-xs text-slate-500 px-3 py-2 border-t border-slate-700">... 외 {preview.length - 5}건</p>
              )}
            </div>
          )}

          {uploadError && (
            <p className="text-xs text-red-400 flex items-center gap-1">
              <AlertCircle className="h-3.5 w-3.5" /> {uploadError}
            </p>
          )}

          <div className="flex gap-2">
            <Button onClick={handleUpload} disabled={uploading || preview.length === 0 || !!parseError}>
              {uploading ? "분석 중..." : `${preview.length}건 분석 시작`}
            </Button>
            <Button variant="ghost" onClick={reset} disabled={uploading}>취소</Button>
          </div>
        </div>
      )}

      {/* 결과 */}
      {result && (
        <div className="rounded-lg border border-slate-700 bg-slate-800 p-6 space-y-5">
          <div className="flex items-center gap-2">
            <CheckCircle className="h-5 w-5 text-emerald-400" />
            <span className="text-slate-100 font-medium">업로드 완료</span>
          </div>

          <div className="grid grid-cols-3 gap-3">
            {[
              { label: "전체", value: result.total, color: "text-slate-100" },
              { label: "저장됨", value: result.saved, color: "text-emerald-400" },
              { label: "중복 건너뜀", value: result.skipped, color: "text-slate-400" },
            ].map(({ label, value, color }) => (
              <div key={label} className="rounded-md bg-slate-900 p-4 text-center">
                <p className={`text-2xl font-bold ${color}`}>{value}</p>
                <p className="text-xs text-slate-500 mt-1">{label}</p>
              </div>
            ))}
          </div>

          {result.errors.length > 0 && (
            <div className="rounded-md bg-slate-900 p-3 space-y-1.5">
              <div className="flex items-center gap-1.5 text-amber-400 text-xs font-medium">
                <AlertCircle className="h-3.5 w-3.5" />
                오류 {result.errors.length}건
              </div>
              {result.errors.slice(0, 5).map((e, i) => (
                <p key={i} className="text-xs text-slate-400 pl-5">
                  Row {e.row} · <span className="font-mono">{e.content_id || "(없음)"}</span> · {e.reason}
                </p>
              ))}
              {result.errors.length > 5 && (
                <p className="text-xs text-slate-500 pl-5">... 외 {result.errors.length - 5}건</p>
              )}
            </div>
          )}

          <Button variant="ghost" onClick={reset} className="text-sm">다른 파일 업로드</Button>
        </div>
      )}
    </div>
  )
}
