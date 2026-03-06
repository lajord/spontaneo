import path from 'node:path'
import { readFileSync } from 'node:fs'
import { defineConfig } from 'prisma/config'

// Prisma CLI ne charge pas .env.local — on le charge manuellement
try {
  const content = readFileSync(path.join(process.cwd(), '.env.local'), 'utf-8')
  for (const line of content.split('\n')) {
    const m = line.match(/^([A-Z_][A-Z0-9_]*)="?([^"#]*)"?\s*$/)
    if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim()
  }
} catch {}

export default defineConfig({
  schema: path.join('prisma', 'schema.prisma'),
  datasource: {
    url: process.env.DATABASE_URL as string,
  },
  migrate: {
    async adapter() {
      const { PrismaPg } = await import('@prisma/adapter-pg')
      return new PrismaPg({ connectionString: process.env.DATABASE_URL as string })
    },
  },
})
