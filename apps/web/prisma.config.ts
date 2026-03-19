/// <reference types="node" />
import path from 'node:path'
import { readFileSync } from 'node:fs'
import { defineConfig } from 'prisma/config'

// Prisma CLI ne charge pas .env/.env.local quand un config file est détecté — on le fait manuellement
for (const file of ['.env', '.env.local']) {
  try {
    const content = readFileSync(path.join(process.cwd(), file), 'utf-8')
    for (const line of content.split('\n')) {
      const m = line.match(/^([A-Z_][A-Z0-9_]*)="?([^"#]*)"?\s*$/)
      if (m && !process.env[m[1]]) process.env[m[1]] = m[2].trim()
    }
  } catch {}
}

export default defineConfig({
  schema: path.join('prisma', 'schema.prisma'),
  datasource: {
    url: process.env.DATABASE_URL as string,
  },
})
