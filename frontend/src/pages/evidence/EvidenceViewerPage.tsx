import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'
import { Download, ShieldCheck, ShieldOff } from 'lucide-react'
import apiClient from '@/services/api'
import type { EvidenceScreenshot, EvidenceVerifyResult } from '@/types'

export default function EvidenceViewerPage() {
  const { executionId } = useParams<{ executionId: string }>()
  const [lightboxIndex, setLightboxIndex] = useState<number | null>(null)
  const [verifyResult, setVerifyResult] = useState<EvidenceVerifyResult | null>(null)

  const { data: screenshots = [] } = useQuery<EvidenceScreenshot[]>({
    queryKey: ['evidence', executionId],
    queryFn: () =>
      apiClient.get(`/executions/${executionId}/evidence`).then((r) => r.data),
    enabled: !!executionId,
  })

  const verifyMutation = useMutation({
    mutationFn: () =>
      apiClient.post(`/executions/${executionId}/evidence/verify`).then((r) => r.data),
    onSuccess: (data) => setVerifyResult(data),
  })

  const downloadReport = () => {
    window.open(`/api/v1/executions/${executionId}/evidence/report`, '_blank')
  }

  return (
    <div className="p-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Evidence</h1>
        <div className="flex gap-3">
          <button
            onClick={() => verifyMutation.mutate()}
            disabled={verifyMutation.isPending}
            className="flex items-center gap-2 px-4 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50"
          >
            {verifyResult?.valid ? (
              <ShieldCheck size={16} className="text-green-500" />
            ) : (
              <ShieldOff size={16} className="text-gray-400" />
            )}
            Verify Integrity
          </button>
          <button
            onClick={downloadReport}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md text-sm font-medium hover:bg-blue-700"
          >
            <Download size={16} />
            Download PDF
          </button>
        </div>
      </div>

      {verifyResult && (
        <div className={`mb-4 p-3 rounded-md text-sm ${verifyResult.valid ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
          {verifyResult.valid
            ? 'All screenshots verified — integrity chain intact.'
            : `Integrity check failed on steps: ${verifyResult.failed_steps.join(', ')}`}
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        {screenshots.map((s, i) => (
          <div
            key={s.id}
            className="bg-white border border-gray-200 rounded-xl overflow-hidden cursor-pointer hover:shadow-md transition-shadow"
            onClick={() => setLightboxIndex(i)}
          >
            {s.sas_url && (
              <img
                src={s.sas_url}
                alt={`Step ${s.step_number}`}
                className="w-full h-40 object-cover"
              />
            )}
            <div className="p-3">
              <p className="text-xs font-medium text-gray-700">Step {s.step_number}</p>
              <p className="text-xs text-gray-400 font-mono truncate mt-0.5">{s.sha256.slice(0, 16)}…</p>
            </div>
          </div>
        ))}
        {screenshots.length === 0 && (
          <p className="col-span-4 text-sm text-gray-400 text-center py-8">
            No evidence screenshots found for this execution.
          </p>
        )}
      </div>
    </div>
  )
}
