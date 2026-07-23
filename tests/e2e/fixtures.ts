import { expect, test as base } from '@playwright/test'
import path from 'node:path'

type Fixtures = {
  apiBaseURL: string
  apiOrigin: string
  sample: (name: string) => string
}

export const test = base.extend<Fixtures>({
  apiBaseURL: [process.env.PLAYWRIGHT_API_URL ?? 'http://127.0.0.1:5173/api/v1', { option: true }],
  apiOrigin: [process.env.PLAYWRIGHT_API_ORIGIN ?? 'http://127.0.0.1:8000', { option: true }],
  sample: async ({}, use) => {
    await use((name) => path.resolve('sample-data', 'synthetic-pdfs', name))
  },
})

export { expect }
