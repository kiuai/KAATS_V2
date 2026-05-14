import { useCallback, useState } from 'react'
import { UploadCloud, X, FileText } from 'lucide-react'

interface Props {
  accept?: string
  maxSizeMb?: number
  onFile: (file: File) => void
  label?: string
}

export default function FileUploadZone({
  accept = '.txt,.csv,.json,.docx,.pdf',
  maxSizeMb = 20,
  onFile,
  label = 'Drop file here or click to browse',
}: Props) {
  const [dragOver, setDragOver] = useState(false)
  const [picked, setPicked] = useState<File | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleFile = useCallback(
    (file: File) => {
      setError(null)
      if (file.size > maxSizeMb * 1024 * 1024) {
        setError(`File exceeds ${maxSizeMb} MB limit`)
        return
      }
      setPicked(file)
      onFile(file)
    },
    [maxSizeMb, onFile],
  )

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files[0]
    if (file) handleFile(file)
  }

  const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  return (
    <div>
      <label
        className={`block border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors ${
          dragOver
            ? 'border-blue-400 bg-blue-50'
            : 'border-gray-300 hover:border-gray-400'
        }`}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
      >
        <input
          type="file"
          accept={accept}
          className="sr-only"
          onChange={onInputChange}
        />
        <UploadCloud size={32} className="mx-auto mb-3 text-gray-400" />
        <p className="text-sm text-gray-600">{label}</p>
        <p className="text-xs text-gray-400 mt-1">
          Supported: {accept} · Max {maxSizeMb} MB
        </p>
      </label>

      {error && (
        <p className="mt-2 text-sm text-red-600">{error}</p>
      )}

      {picked && !error && (
        <div className="mt-3 flex items-center gap-3 px-4 py-2.5 bg-gray-50 border border-gray-200 rounded-lg">
          <FileText size={16} className="text-gray-500 shrink-0" />
          <span className="text-sm text-gray-700 flex-1 truncate">{picked.name}</span>
          <span className="text-xs text-gray-400">
            {(picked.size / 1024).toFixed(1)} KB
          </span>
          <button
            type="button"
            onClick={() => { setPicked(null); setError(null) }}
            className="text-gray-400 hover:text-gray-600"
          >
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  )
}
