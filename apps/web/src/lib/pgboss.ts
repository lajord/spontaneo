import PgBoss from 'pg-boss'

// Singleton pg-boss instance for the Next.js app (used only to enqueue jobs)
let _boss: PgBoss | null = null

export async function getBoss(): Promise<PgBoss> {
  if (!_boss) {
    const url = new URL(process.env.DATABASE_URL!)
    url.searchParams.delete('pgbouncer')
    url.searchParams.delete('sslmode')
    url.searchParams.delete('connection_limit')

    _boss = new PgBoss({
      connectionString: url.toString(),
      ssl: url.hostname.includes('supabase') ? { rejectUnauthorized: false } : false,
      // Limite le pool interne à 2 connexions (Supabase free tier = ~5 max)
      // Chaque hot-reload Next.js recréait un pool sans libérer le précédent
      max: 2,
      monitorStateIntervalSeconds: 0, // désactive le monitoring (connexions extra)
    })
    _boss.on('error', (err) => console.error('[pg-boss] Error:', err))
    await _boss.start()
  }
  return _boss
}
