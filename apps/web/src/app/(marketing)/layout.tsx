import Link from 'next/link'
import { ArrowRight } from 'lucide-react'

export default function MarketingLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-white font-sans text-gray-900">

      {/* Header */}
      <header
        className="fixed top-0 left-0 right-0 z-50 border-b border-gray-100 bg-white"
      >
        <nav className="max-w-5xl mx-auto px-6 flex items-center justify-between" style={{ height: '64px' }}>

          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div
              className="h-7 w-7 rounded-lg flex items-center justify-center text-white font-bold text-sm transition-all duration-200 group-hover:scale-105"
              style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                boxShadow: '0 0 14px rgba(16,185,129,0.3)',
              }}
            >
              S
            </div>
            <span className="text-[15px] font-semibold tracking-tight text-gray-900">
              Spontaneo
            </span>
          </Link>

          {/* Nav */}
          <div className="flex items-center gap-2">
            <Link
              href="/login"
              className="text-sm font-medium text-gray-500 hover:text-gray-900 transition-colors px-3 py-1.5"
            >
              Se connecter
            </Link>
            <Link
              href="/register"
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg text-sm font-semibold text-white transition-all duration-200 hover:scale-[1.02] group"
              style={{
                background: 'linear-gradient(135deg, #10b981 0%, #059669 100%)',
                boxShadow: '0 2px 12px rgba(16,185,129,0.25)',
              }}
            >
              Commencer
              <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-0.5 transition-transform" />
            </Link>
          </div>
        </nav>
      </header>

      {/* Main */}
      <main style={{ paddingTop: '64px' }}>{children}</main>

      {/* Footer — dark pour s'enchaîner avec le CTA final */}
      <footer style={{ background: '#0d1117' }} className="border-t border-white/[0.05]">
        <div className="max-w-5xl mx-auto px-6 py-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <Link href="/" className="flex items-center gap-2 group">
            <div
              className="h-5 w-5 rounded flex items-center justify-center text-white font-bold text-[10px]"
              style={{ background: 'linear-gradient(135deg, #10b981, #059669)' }}
            >
              S
            </div>
            <span className="text-sm font-semibold text-white/30 group-hover:text-white/60 transition-colors">Spontaneo</span>
          </Link>
          <p className="text-xs text-white/20">© 2026 Spontaneo. Tous droits réservés.</p>
          <div className="flex items-center gap-5 text-xs text-white/25">
            <a href="#" className="hover:text-white/60 transition-colors">CGU</a>
            <a href="#" className="hover:text-white/60 transition-colors">Confidentialité</a>
            <a href="#" className="hover:text-white/60 transition-colors">Contact</a>
          </div>
        </div>
      </footer>
    </div>
  )
}
