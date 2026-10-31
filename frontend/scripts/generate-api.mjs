import { readFile, writeFile, mkdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import openapiTS, { astToString } from 'openapi-typescript'
const input = new URL('../../release/openapi.json', import.meta.url)
const output = new URL('../src/types/generated-api.ts', import.meta.url)
const schema = JSON.parse(await readFile(input, 'utf8'))
const ast = await openapiTS(schema)
await mkdir(fileURLToPath(new URL('../src/types/', import.meta.url)), { recursive: true })
await writeFile(output, astToString(ast))
console.log('Generated src/types/generated-api.ts from release/openapi.json')
