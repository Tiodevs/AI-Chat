import * as React from "react"
import { cn } from "cn"
import { ToggleGroup as ToggleGroupPrimitive } from "radix-ui"

function ToggleGroup({
  className,
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Root>) {
  return (
    <ToggleGroupPrimitive.Root
      data-slot="toggle-group"
      className={cn("flex flex-wrap items-center gap-2", className)}
      {...props}
    />
  )
}

function ToggleGroupItem({
  className,
  ...props
}: React.ComponentProps<typeof ToggleGroupPrimitive.Item>) {
  return (
    <ToggleGroupPrimitive.Item
      data-slot="toggle-group-item"
      className={cn(
        "inline-flex min-h-11 items-center justify-center rounded-full border border-border-strong bg-card px-4 text-body text-foreground hover:bg-muted focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring disabled:cursor-default disabled:opacity-50 data-[state=on]:bg-primary data-[state=on]:text-primary-foreground md:min-h-8",
        className
      )}
      {...props}
    />
  )
}

export { ToggleGroup, ToggleGroupItem }
