import { auth } from '@/lib/auth'
import { prisma } from '@/lib/prisma'
import { headers } from 'next/headers'
import { redirect } from 'next/navigation'
import AdminConfigForm from './AdminConfigForm'

export default async function AdminPage() {
  const session = await auth.api.getSession({ headers: await headers() })
  if (!session || (session.user as any).role !== 'admin') redirect('/dashboard')

  // Upsert singleton config
  const config = await prisma.appConfig.upsert({
    where: { id: 'singleton' },
    update: {},
    create: { id: 'singleton' },
  })

  return (
    <div className="p-8 max-w-3xl">
      <div className="mb-8">
        <h1 className="text-xl font-bold text-slate-900">Administration</h1>
        <p className="text-sm text-slate-400 mt-0.5">
          Configuration des hyperparametres du worker
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-xl p-6">
        <AdminConfigForm
          defaultValues={{
            maxConcurrent: config.maxConcurrent,
            batchSize: config.batchSize,
            pollIntervalMs: config.pollIntervalMs,
            modelEnrichissement: config.modelEnrichissement,
            modelEnrichissement2: config.modelEnrichissement2,
            modelCreationMail: config.modelCreationMail,
            modelCreationLm: config.modelCreationLm,
            modelKeywords: config.modelKeywords,
            modelCvReader: config.modelCvReader,
            modelRanking: config.modelRanking,
          }}
        />
      </div>
    </div>
  )
}
