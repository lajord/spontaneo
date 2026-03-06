import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Spontaneo',
  description: "Candidatures spontanées automatiques, propulsées par l'IA.",
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body className="bg-gray-50 text-gray-900 antialiased">{children}</body>
    </html>
  )
}
