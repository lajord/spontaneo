'use client'

import { useEffect, useState, useCallback } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { useSession } from '@/lib/auth-client'

interface EmailStatus {
  connected: boolean
  provider?: 'gmail'
  oauthEmail?: string
}

const PROVIDER_LABELS: Record<string, string> = { gmail: 'Gmail' }

export default function SettingsPage() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const { data: session } = useSession()

  const [emailStatus, setEmailStatus] = useState<EmailStatus>({ connected: false })
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [disconnecting, setDisconnecting] = useState(false)

  // Profil
  const [name, setName] = useState('')
  const [savingName, setSavingName] = useState(false)

  // Mot de passe
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [savingPassword, setSavingPassword] = useState(false)

  // Suppression compte
  const [deleteConfirm, setDeleteConfirm] = useState('')
  const [deleting, setDeleting] = useState(false)

  useEffect(() => {
    if (session?.user?.name) setName(session.user.name)
  }, [session])

  const fetchEmailStatus = useCallback(async () => {
    const res = await fetch('/api/settings/email')
    if (res.ok) setEmailStatus(await res.json())
  }, [])

  useEffect(() => { fetchEmailStatus() }, [fetchEmailStatus])

  useEffect(() => {
    const connected = searchParams.get('connected')
    const error = searchParams.get('error')
    if (connected) {
      showToast(`${PROVIDER_LABELS[connected] ?? connected} connecté avec succès !`, 'success')
      fetchEmailStatus()
    } else if (error) {
      showToast(`Erreur : ${error}`, 'error')
    }
  }, [searchParams, fetchEmailStatus])

  function showToast(message: string, type: 'success' | 'error') {
    setToast({ message, type })
    setTimeout(() => setToast(null), 4000)
  }

  async function handleDisconnect() {
    setDisconnecting(true)
    const res = await fetch('/api/auth/connect/disconnect', { method: 'DELETE' })
    if (res.ok) {
      setEmailStatus({ connected: false })
      showToast('Compte email déconnecté.', 'success')
    } else {
      showToast('Erreur lors de la déconnexion.', 'error')
    }
    setDisconnecting(false)
  }

  async function handleSaveName(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim()) return
    setSavingName(true)
    const res = await fetch('/api/settings/profile', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: name.trim() }),
    })
    showToast(res.ok ? 'Nom mis à jour.' : 'Erreur lors de la mise à jour.', res.ok ? 'success' : 'error')
    setSavingName(false)
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault()
    if (newPassword !== confirmPassword) {
      showToast('Les mots de passe ne correspondent pas.', 'error')
      return
    }
    if (newPassword.length < 8) {
      showToast('Le mot de passe doit faire au moins 8 caractères.', 'error')
      return
    }
    setSavingPassword(true)
    const res = await fetch('/api/settings/password', {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ currentPassword, newPassword }),
    })
    if (res.ok) {
      showToast('Mot de passe mis à jour.', 'success')
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
    } else {
      const data = await res.json()
      showToast(data.error ?? 'Erreur lors du changement.', 'error')
    }
    setSavingPassword(false)
  }

  async function handleDeleteAccount() {
    if (deleteConfirm !== 'SUPPRIMER') return
    setDeleting(true)
    const res = await fetch('/api/settings/delete-account', { method: 'DELETE' })
    if (res.ok) {
      router.push('/login')
    } else {
      showToast('Erreur lors de la suppression.', 'error')
      setDeleting(false)
    }
  }

  return (
    <div className="p-8 max-w-2xl space-y-8">
      <div>
        <h1 className="text-xl font-bold text-slate-900">Paramètres</h1>
        <p className="text-sm text-slate-400 mt-0.5">Gérez votre compte et vos préférences</p>
      </div>

      {toast && (
        <div className={`text-sm rounded-lg px-4 py-3 ${
          toast.type === 'success'
            ? 'text-emerald-700 bg-emerald-50 border border-emerald-200'
            : 'text-red-700 bg-red-50 border border-red-200'
        }`}>
          {toast.message}
        </div>
      )}

      {/* ── Compte email d'envoi ── */}
      <Section title="Compte email d'envoi" desc="Vos candidatures seront envoyées directement depuis votre boîte mail.">
        {emailStatus.connected ? (
          <div className="flex items-center justify-between gap-4 p-4 bg-slate-50 rounded-lg border border-slate-200">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                <svg className="w-4 h-4 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <div>
                <p className="text-sm font-medium text-slate-800">
                  {PROVIDER_LABELS[emailStatus.provider ?? ''] ?? emailStatus.provider} connecté
                </p>
                {emailStatus.oauthEmail && (
                  <p className="text-xs text-slate-500 mt-0.5">{emailStatus.oauthEmail}</p>
                )}
              </div>
            </div>
            <button
              onClick={handleDisconnect}
              disabled={disconnecting}
              className="text-xs text-slate-500 hover:text-red-600 border border-slate-200 hover:border-red-200 rounded-lg px-3 py-1.5 transition-colors disabled:opacity-50"
            >
              {disconnecting ? 'Déconnexion...' : 'Déconnecter'}
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <a
              href="/api/auth/connect/gmail"
              className="flex items-center gap-3 w-full border border-slate-200 hover:border-slate-300 hover:bg-slate-50 rounded-lg px-4 py-3 transition-colors group"
            >
              <GmailIcon />
              <span className="text-sm font-medium text-slate-700">Connecter Gmail</span>
              <svg className="w-4 h-4 text-slate-400 group-hover:text-slate-600 ml-auto transition-colors" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </a>
            <p className="text-xs text-slate-400">
              Nous demandons uniquement la permission d&apos;envoyer des emails en votre nom. Vos messages ne sont jamais stockés.
            </p>
          </div>
        )}
      </Section>

      {/* ── Profil ── */}
      <Section title="Profil" desc="Modifiez vos informations personnelles.">
        <form onSubmit={handleSaveName} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Nom complet</label>
            <input
              type="text"
              value={name}
              onChange={e => setName(e.target.value)}
              className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Email</label>
            <input
              type="email"
              value={session?.user?.email ?? ''}
              disabled
              className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm text-slate-400 bg-slate-50 cursor-not-allowed"
            />
            <p className="text-xs text-slate-400 mt-1">L'email ne peut pas être modifié.</p>
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={savingName}
              className="px-4 py-2 bg-slate-900 hover:bg-slate-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {savingName ? 'Enregistrement...' : 'Enregistrer'}
            </button>
          </div>
        </form>
      </Section>

      {/* ── Mot de passe ── */}
      <Section title="Mot de passe" desc="Changez votre mot de passe de connexion.">
        <form onSubmit={handleChangePassword} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Mot de passe actuel</label>
            <input
              type="password"
              value={currentPassword}
              onChange={e => setCurrentPassword(e.target.value)}
              required
              placeholder="••••••••"
              className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Nouveau mot de passe</label>
            <input
              type="password"
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              required
              minLength={8}
              placeholder="8 caractères minimum"
              className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-600 mb-1.5">Confirmer le mot de passe</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
              placeholder="••••••••"
              className="w-full border border-slate-200 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition"
            />
          </div>
          <div className="flex justify-end">
            <button
              type="submit"
              disabled={savingPassword}
              className="px-4 py-2 bg-slate-900 hover:bg-slate-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              {savingPassword ? 'Mise à jour...' : 'Changer le mot de passe'}
            </button>
          </div>
        </form>
      </Section>

      {/* ── Zone danger ── */}
      <Section title="Zone de danger" desc="Actions irréversibles sur votre compte." danger>
        <div className="space-y-3">
          <p className="text-sm text-slate-600">
            La suppression de votre compte est <span className="font-medium text-slate-900">définitive et irréversible</span>. Toutes vos campagnes, emails et données seront supprimés.
          </p>
          <p className="text-xs text-slate-400">
            Tapez <span className="font-mono font-semibold text-slate-600">SUPPRIMER</span> pour confirmer.
          </p>
          <input
            type="text"
            value={deleteConfirm}
            onChange={e => setDeleteConfirm(e.target.value)}
            placeholder="SUPPRIMER"
            className="w-full border border-red-200 rounded-lg px-3.5 py-2.5 text-sm text-slate-900 focus:outline-none focus:ring-2 focus:ring-red-400 focus:border-transparent transition"
          />
          <button
            onClick={handleDeleteAccount}
            disabled={deleteConfirm !== 'SUPPRIMER' || deleting}
            className="px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-40 disabled:cursor-not-allowed text-white text-sm font-medium rounded-lg transition-colors"
          >
            {deleting ? 'Suppression...' : 'Supprimer mon compte'}
          </button>
        </div>
      </Section>
    </div>
  )
}

function Section({
  title, desc, children, danger,
}: {
  title: string
  desc: string
  children: React.ReactNode
  danger?: boolean
}) {
  return (
    <div className={`bg-white border rounded-xl p-6 space-y-5 ${danger ? 'border-red-200' : 'border-slate-100'}`}>
      <div className={`pb-4 border-b ${danger ? 'border-red-100' : 'border-slate-100'}`}>
        <h2 className={`text-sm font-semibold ${danger ? 'text-red-600' : 'text-slate-700'}`}>{title}</h2>
        <p className="text-xs text-slate-400 mt-0.5">{desc}</p>
      </div>
      {children}
    </div>
  )
}

function GmailIcon() {
  return (
    <svg className="w-5 h-5 flex-shrink-0" viewBox="0 0 48 48">
      <path fill="#EA4335" d="M7 40h34V20L24 32 7 20z" />
      <path fill="#FBBC05" d="M41 8H7L24 20z" />
      <path fill="#34A853" d="M41 8l6 6v26l-6-6z" />
      <path fill="#4285F4" d="M7 8L1 14v26l6-6z" />
      <path fill="#C5221F" d="M7 8v12l17 12 17-12V8L24 20z" />
    </svg>
  )
}
