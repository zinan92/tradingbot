import * as React from "react"
import { cn } from "@/lib/utils"
import { ChevronDown } from "lucide-react"

interface SelectProps {
  value: string
  onValueChange: (value: string) => void
  children: React.ReactNode
  className?: string
}

export function Select({ value, onValueChange, children, className }: SelectProps) {
  const [isOpen, setIsOpen] = React.useState(false)
  
  return (
    <div className={cn("relative", className)}>
      {React.Children.map(children, child => {
        if (React.isValidElement(child)) {
          return React.cloneElement(child as React.ReactElement<any>, {
            value,
            onValueChange,
            isOpen,
            setIsOpen
          })
        }
        return child
      })}
    </div>
  )
}

interface SelectTriggerProps extends React.HTMLAttributes<HTMLButtonElement> {
  value?: string
  isOpen?: boolean
  setIsOpen?: (open: boolean) => void
}

export const SelectTrigger = React.forwardRef<HTMLButtonElement, SelectTriggerProps>(
  ({ className, children, isOpen, setIsOpen, ...props }, ref) => (
    <button
      ref={ref}
      type="button"
      className={cn(
        "flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      onClick={() => setIsOpen?.(!isOpen)}
      {...props}
    >
      {children}
      <ChevronDown className="h-4 w-4 opacity-50" />
    </button>
  )
)
SelectTrigger.displayName = "SelectTrigger"

export function SelectValue({ placeholder }: { placeholder?: string }) {
  const context = React.useContext(SelectValueContext)
  return <span>{context?.label || placeholder}</span>
}

const SelectValueContext = React.createContext<{ label: string } | null>(null)

interface SelectContentProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: string
  onValueChange?: (value: string) => void
  isOpen?: boolean
  setIsOpen?: (open: boolean) => void
}

export function SelectContent({ className, children, value, onValueChange, isOpen, setIsOpen, ...props }: SelectContentProps) {
  if (!isOpen) return null
  
  return (
    <SelectValueContext.Provider value={{ label: value || "" }}>
      <div
        className={cn(
          "absolute z-50 mt-1 max-h-60 w-full overflow-auto rounded-md border bg-popover p-1 text-popover-foreground shadow-md",
          className
        )}
        {...props}
      >
        {React.Children.map(children, child => {
          if (React.isValidElement(child)) {
            return React.cloneElement(child as React.ReactElement<any>, {
              onValueChange,
              setIsOpen,
              currentValue: value
            })
          }
          return child
        })}
      </div>
    </SelectValueContext.Provider>
  )
}

interface SelectItemProps extends React.HTMLAttributes<HTMLDivElement> {
  value: string
  onValueChange?: (value: string) => void
  setIsOpen?: (open: boolean) => void
  currentValue?: string
}

export function SelectItem({ className, children, value, onValueChange, setIsOpen, currentValue, ...props }: SelectItemProps) {
  const isSelected = currentValue === value
  
  return (
    <div
      className={cn(
        "relative flex w-full cursor-pointer select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none hover:bg-accent hover:text-accent-foreground",
        isSelected && "bg-accent text-accent-foreground",
        className
      )}
      onClick={() => {
        onValueChange?.(value)
        setIsOpen?.(false)
      }}
      {...props}
    >
      {children}
    </div>
  )
}