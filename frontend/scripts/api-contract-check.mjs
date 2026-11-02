#!/usr/bin/env node
/**
 * 前后端 API 契约漂移守卫。
 *
 * 断言三件事，任一不满足即非零退出：
 * 1. 入库的生成类型 frontend/src/types/generated-api.ts 与后端契约 release/openapi.json
 *    重新生成的结果一致（后端改了接口却没重新生成类型 = 漂移）；
 * 2. 学生端与管理台 API 模块里出现的 API 路径字面量都存在于后端契约中
 *    （前端调了后端没有的接口 = 漂移）；
 * 3. 契约里的路径都是版本化的 /api/v1/**。
 *
 * 用法：node frontend/scripts/api-contract-check.mjs
 * 前置：frontend/ 下已 npm ci（脚本用 openapi-typescript 重新生成类型做比对），
 *      release/openapi.json 存在（CI 由 scripts/check_api_contract.py 导出）。
 */
import { readFileSync, readdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'
import openapiTS, { astToString } from 'openapi-typescript'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const API_PREFIX = '/api/v1'
const CONTRACT_PATH = path.join(ROOT, 'release/openapi.json')
const GENERATED_TYPES_PATH = path.join(ROOT, 'frontend/src/types/generated-api.ts')
const API_MODULE_DIRS = [
  path.join(ROOT, 'frontend/src/api'),
  path.join(ROOT, 'admin-frontend/src/api'),
]

const LITERAL_PATTERN = /(['"`])(\/[^'"`\s]*)/g

/** 契约路径形状：{param} 记作一段占位。 */
function contractShape(apiPath) {
  return apiPath.replace(/\{[^}]*\}/g, '*')
}

/** 字面量形状：${...} 与 {param} 都记作一段占位；未闭合的 ${ 之后按查询串丢弃。 */
function literalShape(literal) {
  const withoutQuery = literal.split('?', 1)[0]
  const withPrefix = withoutQuery.startsWith(API_PREFIX) ? withoutQuery : API_PREFIX + withoutQuery
  let shape = ''
  let index = 0
  while (index < withPrefix.length) {
    if (withPrefix[index] === '$' && withPrefix[index + 1] === '{') {
      const end = withPrefix.indexOf('}', index + 2)
      if (end === -1) break
      shape += '*'
      index = end + 1
      continue
    }
    if (withPrefix[index] === '{') break
    shape += withPrefix[index]
    index += 1
  }
  return shape
}

function collectLiterals(directory) {
  const literals = []
  for (const name of readdirSync(directory).filter((file) => file.endsWith('.ts')).sort()) {
    const file = path.join(directory, name)
    for (const match of readFileSync(file, 'utf8').matchAll(LITERAL_PATTERN)) {
      literals.push({ file: path.relative(ROOT, file), literal: match[2] })
    }
  }
  return literals
}

async function main() {
  const contract = JSON.parse(readFileSync(CONTRACT_PATH, 'utf8'))
  const contractPaths = Object.keys(contract.paths ?? {})
  const problems = []

  for (const apiPath of contractPaths) {
    // 与 scripts/check_api_contract.py 同一把尺子：/api/** 必须版本化，健康检查等非业务路径不受限
    if (apiPath.startsWith('/api/') && !apiPath.startsWith(API_PREFIX)) {
      problems.push(`契约存在未版本化的业务路径：${apiPath}`)
    }
  }

  const generated = await openapiTS(contract)
  const expected = astToString(generated)
  const committed = readFileSync(GENERATED_TYPES_PATH, 'utf8')
  if (committed !== expected) {
    problems.push(
      `生成类型与契约不一致：${path.relative(ROOT, GENERATED_TYPES_PATH)}。` +
        '请先重新导出契约（backend/ 下 `python ../scripts/check_api_contract.py --output ../release/openapi.json`），' +
        '再在 frontend/ 下执行 `npm run generate:api`，两者一起提交。',
    )
  }

  const contractShapes = new Set(contractPaths.map(contractShape))
  const literals = API_MODULE_DIRS.flatMap(collectLiterals)
  for (const { file, literal } of literals) {
    const shape = literalShape(literal)
    if (!contractShapes.has(shape)) {
      problems.push(`前端调用的接口不在后端契约中：${file} → ${literal}（归一化为 ${shape}）`)
    }
  }

  if (problems.length > 0) {
    console.error('[失败] 前后端 API 契约漂移：')
    for (const problem of problems) console.error(`  - ${problem}`)
    process.exit(1)
  }
  console.log(
    `[通过] 契约与生成类型一致（${contractPaths.length} 条路径），` +
      `学生端与管理台 API 模块 ${literals.length} 处路径字面量均存在于后端契约中`,
  )
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
