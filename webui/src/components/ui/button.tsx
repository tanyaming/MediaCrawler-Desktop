import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-lg text-sm font-medium transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cyber-neon-cyan/40 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default:
          'bg-cyber-neon-cyan text-white shadow-sm hover:bg-cyber-neon-cyan-dim hover:shadow-md active:scale-[0.98]',
        destructive:
          'bg-cyber-neon-pink text-white shadow-sm hover:bg-cyber-neon-pink-dim hover:shadow-md active:scale-[0.98]',
        outline:
          'border border-cyber-border-DEFAULT bg-white text-cyber-text-secondary hover:bg-cyber-bg-secondary hover:border-cyber-neon-cyan/50 hover:text-cyber-neon-cyan',
        secondary:
          'bg-cyber-neon-green text-white shadow-sm hover:bg-cyber-neon-green-dim hover:shadow-md active:scale-[0.98]',
        ghost:
          'hover:bg-cyber-bg-secondary hover:text-cyber-neon-cyan',
        link:
          'text-cyber-neon-cyan underline-offset-4 hover:underline',
        glow:
          'bg-cyber-neon-cyan text-white shadow-sm hover:shadow-md hover:bg-cyber-neon-cyan-dim active:scale-[0.98]',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-md px-3',
        lg: 'h-12 rounded-lg px-8 text-base',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }
