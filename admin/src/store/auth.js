import { create } from 'zustand'

const TOKEN_KEY = 'gnr_admin_token'

export const useAuth = create((set) => ({
  token: localStorage.getItem(TOKEN_KEY),
  user: null,

  setToken: (token) => {
    localStorage.setItem(TOKEN_KEY, token)
    set({ token })
  },
  setUser: (user) => set({ user }),
  logout: () => {
    localStorage.removeItem(TOKEN_KEY)
    set({ token: null, user: null })
  },
}))
