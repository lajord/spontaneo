'use client'

import { useRouter } from 'next/navigation'
import { signOut } from '@/lib/auth-client'

export default function SignOutButton() {
  const router = useRouter()

  async function handleSignOut() {
    await signOut()
    router.push('/login')
  }

  return (
    <button
      onClick={handleSignOut}
      className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-600 hover:bg-slate-50 transition-colors"
    >
      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
      </svg>
      Déconnexion
    </button>
  )
}
