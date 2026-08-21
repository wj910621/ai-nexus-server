import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { User } from '@/types'
import { tokenStorage } from '@/utils/token'

interface AuthState {
  user: User | null
  isAuthenticated: boolean
  setUser: (user: User | null) => void
  logout: () => void
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      isAuthenticated: false,
      setUser: (user) =>
        set({
          user,
          isAuthenticated: !!user,
        }),
      logout: () => {
        tokenStorage.clear()
        set({ user: null, isAuthenticated: false })
      },
    }),
    {
      name: 'comic-auth',
      partialize: (state) => ({ user: state.user, isAuthenticated: state.isAuthenticated }),
    }
  )
)
