import * as React from "react"
import { cn } from "cn"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-12 w-full min-w-0 rounded-sm border border-[#cccccc] bg-white px-4 py-1 text-base text-ink transition-colors outline-none file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-[#6b6b6b] focus-visible:border-2 focus-visible:border-primary focus-visible:ring-0 disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-[#f3f3f3] disabled:text-[#cccccc] aria-invalid:border-destructive aria-invalid:ring-0 md:text-base",
        className
      )}
      {...props}
    />
  )
}

export { Input }
