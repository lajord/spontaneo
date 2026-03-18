'use client'

import { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { signOut } from '@/lib/auth-client'

interface TopbarProps {
  credits: number
  initials: string
}

export default function Topbar({ credits, initials }: TopbarProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  const router = useRouter()

  // Ferme le dropdown si clic extérieur
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [])

  async function handleSignOut() {
    setOpen(false)
    await signOut()
    router.push('/login')
  }

  return (
    <header className="h-14 bg-white border-b border-slate-200 flex items-center justify-end px-6 gap-3 shrink-0">
      {/* Credits */}
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-50 border border-slate-200 text-sm text-slate-600 font-medium">
        <svg className="w-4 h-4 text-slate-400" viewBox="0 0 24 24" fill="currentColor">
          <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8zm.31-8.86c-1.77-.45-2.34-.94-2.34-1.67 0-.84.79-1.43 2.1-1.43 1.38 0 1.9.66 1.94 1.64h1.71c-.05-1.34-.87-2.57-2.49-2.97V5H10.9v1.69c-1.51.32-2.72 1.3-2.72 2.81 0 1.79 1.49 2.69 3.66 3.21 1.95.46 2.34 1.15 2.34 1.87 0 .53-.39 1.39-2.1 1.39-1.6 0-2.23-.72-2.32-1.64H8.04c.1 1.7 1.36 2.66 2.86 2.97V19h2.34v-1.67c1.52-.29 2.72-1.16 2.73-2.77-.01-2.2-1.9-2.96-3.66-3.42z" />
        </svg>
        {credits} Crédit{credits !== 1 ? 's' : ''}
      </div>

      {/* Offres */}
      <Link
        href="/pricing"
        className="px-3 py-1.5 rounded-lg bg-slate-900 text-white text-sm font-medium hover:bg-slate-700 transition-colors"
      >
        Offres
      </Link>

      {/* Avatar + Dropdown */}
      <div ref={ref} className="relative">
        <button
          onClick={() => setOpen(prev => !prev)}
          className="w-9 h-9 rounded-full bg-brand-500 flex items-center justify-center shrink-0 hover:bg-brand-600 transition-colors shadow-sm"
        >
          <span className="text-white text-xs font-semibold">{initials}</span>
        </button>

        {open && (
          <div className="absolute right-0 top-11 w-48 bg-white rounded-xl border border-slate-200 shadow-lg shadow-black/5 py-1.5 z-50">
            {/* Settings */}
            <Link
              href="/settings"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-3.5 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
              Paramètres
            </Link>

            {/* Payment History */}
            <Link
              href="/billing"
              onClick={() => setOpen(false)}
              className="flex items-center gap-2.5 px-3.5 py-2 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
            >
              <svg className="w-4 h-4 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Historique paiements
            </Link>

            <div className="my-1.5 border-t border-slate-100" />

            {/* Sign Out */}
            <button
              onClick={handleSignOut}
              className="w-full flex items-center gap-2.5 px-3.5 py-2 text-sm text-red-500 hover:bg-red-50 transition-colors"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
              Se déconnecter
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
