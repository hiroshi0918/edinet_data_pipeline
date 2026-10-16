import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

const buttonVariants = cva(
  "group/button inline-flex shrink-0 items-center justify-center rounded-[2px] border border-chrome text-[11px] font-bold tracking-wide whitespace-nowrap outline-none select-none disabled:pointer-events-none disabled:opacity-50 aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "press border-transparent bg-signal text-carbon",
        outline: "press bg-surface text-ink aria-expanded:bg-platinum",
        secondary: "press border-transparent bg-amber text-carbon",
        ghost:
          "border-transparent hover:bg-canvas-soft aria-expanded:bg-canvas-soft",
        destructive: "press border-transparent bg-brand text-surface",
        link: "h-auto border-transparent px-0 text-sm font-bold tracking-normal text-chrome underline decoration-chrome/40 underline-offset-4 hover:decoration-signal",
      },
      size: {
        default: "h-11 gap-1.5 px-4",
        xs: "h-8 gap-1 px-2.5 text-[10px] [&_svg:not([class*='size-'])]:size-3",
        sm: "h-10 gap-1 px-3 text-[11px] [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-12 gap-2 px-5 text-sm",
        icon: "size-11",
        "icon-xs": "size-8 [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-10",
        "icon-lg": "size-12",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
