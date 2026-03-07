import { auth } from '@/lib/auth'
import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import Link from 'next/link'
import SignOutButton from '@/components/SignOutButton'

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session) redirect('/login')

  const initials = session.user.name
    ? session.user.name.split(' ').map((n: string) => n[0]).join('').toUpperCase().slice(0, 2)
    : session.user.email.slice(0, 2).toUpperCase()

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Sidebar */}
      <aside className="w-48 border-r border-slate-200 flex flex-col shrink-0" style={{ backgroundColor: '#E5E7DF' }}>
        {/* Logo */}
        <div className="px-5 py-5 border-b border-slate-100">
          <span className="font-bold text-lg text-brand-500 tracking-tight">Spontaneo</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-0.5">
          <Link
            href="/dashboard"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-900 hover:bg-black/5 transition-colors group"
          >
            <svg className="w-4 h-4 text-slate-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            Campagnes
          </Link>
          <Link
            href="/settings"
            className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-900 hover:bg-black/5 transition-colors group"
          >
            <svg className="w-4 h-4 text-slate-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            Paramètres
          </Link>
          {(session.user as any).role === 'admin' && (
            <Link
              href="/admin"
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-slate-900 hover:bg-black/5 transition-colors group"
            >
              <svg className="w-4 h-4 text-slate-900" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.75} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
              </svg>
              Admin
            </Link>
          )}
        </nav>

        {/* User footer */}
        <div className="px-4 py-4 border-t border-slate-100">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 rounded-full bg-brand-500 flex items-center justify-center shrink-0">
              <span className="text-white text-xs font-semibold">{initials}</span>
            </div>
            <p className="text-xs text-slate-500 truncate">{session.user.email}</p>
          </div>
          <SignOutButton />
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  )
}
