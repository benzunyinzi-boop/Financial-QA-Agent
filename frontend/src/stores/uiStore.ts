import { create } from 'zustand'
import { persist } from 'zustand/middleware'

type UserRole = 'customer' | 'agent'

interface UIState {
  sidebarCollapsed: boolean
  sidebarMobileOpen: boolean
  searchQuery: string
  role: UserRole

  toggleSidebar: () => void
  setSidebarMobileOpen: (open: boolean) => void
  setSearchQuery: (q: string) => void
  setRole: (role: UserRole) => void
}

export const useUIStore = create<UIState>()(
  persist(
    (set) => ({
      sidebarCollapsed: false,
      sidebarMobileOpen: false,
      searchQuery: '',
      role: 'customer',

      toggleSidebar: () => set((s) => ({ sidebarCollapsed: !s.sidebarCollapsed })),
      setSidebarMobileOpen: (open) => set({ sidebarMobileOpen: open }),
      setSearchQuery: (q) => set({ searchQuery: q }),
      setRole: (role) => set({ role }),
    }),
    {
      name: 'ui-store',
      partialize: (state) => ({
        sidebarCollapsed: state.sidebarCollapsed,
        role: state.role,
      }),
    }
  )
)
