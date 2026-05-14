import Editor from '@monaco-editor/react'

const FORMAT_LANGUAGE: Record<string, string> = {
  playwright:  'typescript',
  selenium:    'python',
  pytest:      'python',
  robot:       'plaintext',  // Monaco has no robotframework built-in
  gherkin:     'gherkin',
  typescript:  'typescript',
  python:      'python',
}

interface Props {
  value: string
  format?: string
  readOnly?: boolean
  onChange?: (value: string) => void
  height?: string
}

export default function ScriptEditor({
  value,
  format = 'playwright',
  readOnly = false,
  onChange,
  height = '500px',
}: Props) {
  const language = FORMAT_LANGUAGE[format.toLowerCase()] ?? 'plaintext'

  return (
    <div className="rounded-xl overflow-hidden border border-gray-200">
      <Editor
        height={height}
        language={language}
        value={value}
        onChange={(v) => onChange?.(v ?? '')}
        options={{
          readOnly,
          minimap: { enabled: false },
          fontSize: 13,
          lineNumbers: 'on',
          scrollBeyondLastLine: false,
          wordWrap: 'on',
          theme: 'vs',
          automaticLayout: true,
          renderLineHighlight: readOnly ? 'none' : 'line',
          contextmenu: !readOnly,
        }}
      />
    </div>
  )
}
