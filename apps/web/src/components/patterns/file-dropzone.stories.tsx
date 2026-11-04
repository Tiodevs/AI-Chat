import type { Meta, StoryObj } from "@storybook/react-vite"
import { useState } from "react"

import { FileDropzone } from "@/components/patterns/file-dropzone.tsx"
import { pt } from "@/i18n/pt.ts"

const meta = {
  title: "Patterns/FileDropzone",
  component: FileDropzone,
  args: { file: null, onFileChange: () => undefined },
} satisfies Meta<typeof FileDropzone>

export default meta

type Story = StoryObj<typeof meta>

const sample = new File(["# Estacionamento\n\nSubsolo."], "04-parking.md", {
  type: "text/markdown",
})

function Interactive() {
  const [file, setFile] = useState<File | null>(null)
  return <FileDropzone file={file} onFileChange={setFile} accept=".md,.txt,.pdf" />
}

export const Estados: Story = {
  render: () => (
    <div className="flex max-w-md flex-col gap-8">
      <Interactive />
      <FileDropzone id="dropzone-selected" file={sample} onFileChange={() => undefined} />
      <FileDropzone
        id="dropzone-invalid"
        file={null}
        onFileChange={() => undefined}
        error={pt.documents.dropzone.wrongType}
      />
      <FileDropzone id="dropzone-disabled" file={sample} onFileChange={() => undefined} disabled />
    </div>
  ),
}
