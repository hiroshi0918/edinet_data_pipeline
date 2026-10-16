import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "cn"
import { Slot } from "radix-ui"

const buttonVariants = cva(
  "group/button press inline-flex shrink-0 items-center justify-center rounded-full border border-transparent text-sm font-bold tracking-[0.02em] whitespace-nowrap outline-none select-none disabled:pointer-events-none disabled:bg-[#f3f3f3] disabled:text-[#cccccc] aria-invalid:border-destructive [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-4",
  {
    variants: {
      variant: {
        default: "bg-primary text-white active:bg-[#0064b7]",
        outline: "border-[#cccccc] bg-transparent text-ink aria-expanded:bg-[#f3f3f3]",
        secondary: "bg-black text-white",
        ghost:
          "border-transparent hover:bg-[#f3f3f3] aria-expanded:bg-[#f3f3f3]",
        destructive: "bg-destructive text-white",
        link: "h-auto border-transparent px-0 font-normal tracking-normal text-link underline decoration-link/30 underline-offset-4 hover:decoration-link",
      },
      size: {
        default: "h-12 gap-2 px-7",
        xs: "h-8 gap-1 px-3 text-xs [&_svg:not([class*='size-'])]:size-3",
        sm: "h-10 gap-1.5 px-4 text-sm [&_svg:not([class*='size-'])]:size-3.5",
        lg: "h-12 gap-2 px-7 text-sm",
        icon: "size-12",
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
