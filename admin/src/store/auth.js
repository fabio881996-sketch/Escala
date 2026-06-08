import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export const useAuth = create(
  persist(
    (set) => ({
      token: null,
      user: null,
      setAuth: (token, user) => set({ token, user }),
      logout: () => {
        localStorage.removeItem('gnr_admin_token')
        set({ token: null, user: null })
      },
    }),
    {
      name: 'gnr-admin-auth',
      onRehydrateStorage: () => (state) => {
        if (state?.token) localStorage.setItem('gnr_admin_token', state.token)
      },
    }
  )
)
