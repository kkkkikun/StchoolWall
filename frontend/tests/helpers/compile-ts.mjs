import { readFile, writeFile } from 'node:fs/promises'
import ts from 'typescript'

// 测试用临时文件统一放在 tests/ 目录下，与各测试的 .temp-*.mjs 同级
const TESTS_DIR = new URL('../', import.meta.url)

/**
 * 把 src 下的 TS 模块转译成临时 .mjs，让测试以「真实源码」参与。
 *
 * 为什么需要：测试用 Node 直接加载 SFC / TS 源码，不经过 vite，
 * 所以源码里的 `@/xxx` 别名必须换成真实文件的相对路径才能被解析。
 *
 * @param relSrcPath 相对 tests/helpers/ 的源码路径，如 '../../src/utils/icons.ts'
 * @param outName    临时文件名（同一 tests 目录下须唯一，node --test 并行跑多个文件）
 * @returns 可用于 replaceAll 的导入说明符（相对 tests/ 目录）
 */
export async function compileTsModule(relSrcPath, outName) {
  const src = await readFile(new URL(relSrcPath, import.meta.url), 'utf8')
  const js = ts.transpileModule(src, {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText
  await writeFile(new URL(outName, TESTS_DIR), js)
  return `./${outName}`
}
