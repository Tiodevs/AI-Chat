import { pt } from "@/i18n/pt.ts"
import { cn } from "cn"
import { Loader2Icon } from "lucide-react"

function Spinner({
  className,
  "aria-label": ariaLabel,
  "aria-hidden": ariaHidden,
  ...props
}: React.ComponentProps<"svg">) {
  const hidden = ariaHidden === true || ariaHidden === "true"
  return (
    <Loader2Icon
      data-slot="spinner"
      role={hidden ? undefined : "status"}
      aria-label={hidden ? undefined : (ariaLabel ?? pt.loading)}
      aria-hidden={ariaHidden}
      className={cn("size-4 animate-spin", className)}
      {...props}
    />
  )
}

export { Spinner }
