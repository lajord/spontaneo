'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { signIn } from '@/lib/auth-client'

export default function LoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    const result = await signIn.email({ email, password })
    if (result.error) {
      setError(result.error.message ?? 'Erreur de connexion')
      setLoading(false)
      return
    }
    router.push('/dashboard')
  }

  return (
    <div className="min-h-screen flex">
      {/* Left panel */}
      <div className="hidden lg:flex lg:w-2/5 bg-brand-500 flex-col justify-between p-10">
        <div>
          <span className="text-white font-bold text-xl tracking-tight">Spontaneo</span>
        </div>
        <div>
          <h2 className="text-white text-3xl font-bold leading-snug mb-4">
            Automatisez vos candidatures spontanées.
          </h2>
          <p className="text-brand-200 text-sm leading-relaxed">
            Trouvez des entreprises, générez des emails personnalisés et envoyez-les en quelques clics.
          </p>
        </div>
        <p className="text-brand-300 text-xs">© {new Date().getFullYear()} Spontaneo</p>
      </div>

      {/* Right panel */}
      <div className="flex-1 flex items-center justify-center bg-white p-6">
        <div className="w-full max-w-sm">
          <div className="mb-8">
            <h1 className="text-2xl font-bold text-slate-900">Connexion</h1>
            <p className="text-slate-500 text-sm mt-1">Accédez à votre espace</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="vous@exemple.com"
                className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Mot de passe</label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition"
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
              className="w-full bg-brand-500 hover:bg-brand-600 disabled:opacity-60 text-white font-semibold rounded-lg py-2.5 text-sm transition-colors mt-2"
            >
              {loading ? 'Connexion...' : 'Se connecter'}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-slate-500">
            Pas encore de compte ?{' '}
            <Link href="/register" className="text-brand-500 font-medium hover:underline">
              Créer un compte
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}
