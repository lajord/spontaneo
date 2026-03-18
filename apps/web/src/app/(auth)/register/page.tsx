'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { signUp, signIn } from '@/lib/auth-client'

export default function RegisterPage() {
  const router = useRouter()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [googleLoading, setGoogleLoading] = useState(false)

  async function handleGoogle() {
    setGoogleLoading(true)
    await signIn.social({ provider: 'google', callbackURL: '/dashboard' })
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const result = await signUp.email({ name, email, password })
    if (result.error) {
      setError(result.error.message ?? 'Erreur lors de la création du compte')
      setLoading(false)
      return
    }
    router.push('/dashboard')
  }

  return (
    <div className="min-h-screen relative flex items-center justify-center p-4 overflow-hidden">
      {/* Gradient background */}
      <div
        className="absolute inset-0"
        style={{
          background: 'linear-gradient(135deg, #fafaf5 0%, #d4e8cf 25%, #9ec49a 50%, #b8c9ba 75%, #d6d6d2 100%)',
        }}
      />
      <div className="absolute inset-0 backdrop-blur-[2px]" />

      {/* Logo */}
      <div className="absolute top-6 left-8 z-10">
        <span className="font-bold text-lg text-slate-800 tracking-tight">Spontaneo</span>
      </div>

      {/* Card */}
      <div className="relative z-10 w-full max-w-md bg-white rounded-2xl shadow-2xl shadow-black/10 p-8">
        <div className="mb-6">
          <h1 className="text-xl font-bold text-slate-900">Créez votre compte</h1>
          <p className="text-slate-500 text-sm mt-1">Gratuit, sans engagement</p>
        </div>

        {/* Google first (most prominent) */}
        <button
          type="button"
          onClick={handleGoogle}
          disabled={googleLoading}
          className="w-full flex items-center justify-center gap-2.5 border border-slate-200 rounded-lg py-2.5 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-60 transition-colors mb-5"
        >
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
            <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
            <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
            <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z"/>
            <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
          </svg>
          {googleLoading ? 'Redirection...' : "S'inscrire avec Google"}
        </button>

        {/* Divider */}
        <div className="mb-5 flex items-center gap-3">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="text-xs text-slate-400 font-medium">OU</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Nom complet</label>
            <input
              type="text"
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jean Dupont"
              className="w-full border border-slate-300 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">E-mail</label>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="vous@exemple.com"
              className="w-full border border-slate-300 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">Mot de passe</label>
            <input
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="8 caractères minimum"
              className="w-full border border-slate-300 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
          </div>

          {error && (
            <p className="text-red-600 text-sm bg-red-50 border border-red-100 rounded-lg px-3 py-2.5">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-semibold rounded-lg py-2.5 text-sm transition-colors"
          >
            {loading ? 'Création...' : 'Créer mon compte'}
          </button>
        </form>

        {/* Footer */}
        <div className="mt-6 pt-5 border-t border-slate-100 text-center text-sm text-slate-500">
          Déjà un compte ?{' '}
          <Link href="/login" className="text-blue-600 font-medium hover:underline">
            Se connecter
          </Link>
        </div>
      </div>

      {/* Bottom legal */}
      <div className="absolute bottom-5 left-8 z-10 flex items-center gap-4 text-xs text-slate-500">
        <span>© {new Date().getFullYear()} Spontaneo</span>
        <a href="#" className="hover:underline">Confidentialité et CGU</a>
      </div>
    </div>
  )
}
