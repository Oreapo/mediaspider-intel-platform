import { readFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const scriptDir = dirname(fileURLToPath(import.meta.url))
const frontendRoot = resolve(scriptDir, '..')
const messagesPath = resolve(frontendRoot, 'src/i18n/messages.ts')

const source = await readFile(messagesPath, 'utf8')
const transpiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.ES2020,
    target: ts.ScriptTarget.ES2020,
  },
  fileName: messagesPath,
})

const encoded = Buffer.from(transpiled.outputText, 'utf8').toString('base64')
const { messages } = await import(`data:text/javascript;base64,${encoded}`)

const locales = Object.keys(messages)
const [baseLocale] = locales
const baseKeys = Object.keys(messages[baseLocale]).sort()
const failures = []

function placeholders(value) {
  return [...String(value).matchAll(/\{([a-zA-Z0-9_]+)\}/g)].map((match) => match[1]).sort()
}

for (const locale of locales) {
  const localeKeys = Object.keys(messages[locale]).sort()
  const missing = baseKeys.filter((key) => !localeKeys.includes(key))
  const extra = localeKeys.filter((key) => !baseKeys.includes(key))

  if (missing.length) failures.push(`${locale} missing keys: ${missing.join(', ')}`)
  if (extra.length) failures.push(`${locale} extra keys: ${extra.join(', ')}`)

  for (const key of baseKeys) {
    if (!(key in messages[locale])) continue
    const expected = placeholders(messages[baseLocale][key])
    const actual = placeholders(messages[locale][key])
    if (expected.join('|') !== actual.join('|')) {
      failures.push(
        `${locale}.${key} placeholder mismatch: expected {${expected.join(', ')}}, got {${actual.join(', ')}}`,
      )
    }
  }
}

if (failures.length) {
  console.error(`i18n check failed with ${failures.length} issue(s):`)
  for (const failure of failures) console.error(`- ${failure}`)
  process.exit(1)
}

console.log(`i18n check passed for ${locales.length} locales and ${baseKeys.length} keys.`)
