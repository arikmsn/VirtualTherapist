/**
 * AppLogo — renders the מטפל.אונליין brand image.
 *
 * variant="icon"  → Only-Sign (symbol only, square-ish)
 * variant="full"  → Clean-Logo (symbol + brand text, landscape)
 *
 * Images are served from /public/assets/logo/ and work in both
 * Vite dev server and the deployed build without any imports.
 */

interface AppLogoProps {
  variant: 'full' | 'icon'
  /** Controls the rendered height; width scales automatically. */
  size?: 'sm' | 'md' | 'lg'
  /**
   * fluid — width-driven sizing: image fills its container width, height is auto.
   * Use by wrapping in a div with responsive width classes.
   * When true, `size` is ignored.
   */
  fluid?: boolean
  className?: string
}

const heightMap: Record<string, string> = {
  sm: 'h-7',
  md: 'h-9',
  lg: 'h-16',
}

export default function AppLogo({ variant, size = 'md', fluid = false, className = '' }: AppLogoProps) {
  const src =
    variant === 'icon'
      ? '/assets/logo/only-sign.jpeg'
      : '/assets/logo/clean-logo.jpg'

  const imgClass = fluid
    ? `w-full h-auto object-contain select-none ${className}`
    : `${heightMap[size]} w-auto object-contain select-none ${className}`

  return (
    <img
      src={src}
      alt="מטפל.אונליין"
      className={imgClass}
      draggable={false}
    />
  )
}
