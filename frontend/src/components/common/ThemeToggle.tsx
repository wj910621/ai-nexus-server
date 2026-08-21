import { Sun, Moon } from 'lucide-react'
import { useThemeStore } from '@/stores/themeStore'
import styles from './ThemeToggle.module.css'

export default function ThemeToggle() {
  const theme = useThemeStore((s) => s.theme)
  const toggleTheme = useThemeStore((s) => s.toggleTheme)

  return (
    <button
      className={styles.toggle}
      onClick={toggleTheme}
      title={theme === 'light' ? '切换到暗色' : '切换到浅色'}
      aria-label="切换主题"
    >
      {theme === 'light' ? <Moon size={16} /> : <Sun size={16} />}
    </button>
  )
}
