import * as React from "react"
import { cn } from "cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-11 w-full resize-none rounded-lg border border-input bg-transparent px-3 py-2 text-body text-foreground transition-colors outline-none placeholder:text-muted-foreground disabled:cursor-default disabled:opacity-50 aria-invalid:border-danger md:min-h-8",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
