import { describe, it, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import { register } from 'node:module'
import { pathToFileURL } from 'node:url'
import path from 'node:path'
import fs from 'node:fs'

// 解析 hook：支持 '@/...' 别名、相对路径自动补 .ts
const aliasLoader = `
import { pathToFileURL } from "node:url";
import path from "node:path";
import fs from "node:fs";

export async function resolve(specifier, context, nextResolve) {
  if (specifier.startsWith("@/")) {
    const resolved = path.resolve(process.cwd(), "src", specifier.slice(2));
    return nextResolve(pathToFileURL(withExt(resolved)).href, context);
  }
  if (specifier.startsWith(".") && !path.extname(specifier)) {
    const base = path.resolve(process.cwd(), path.dirname(context.parentURL.replace("file://", "")), specifier);
    return nextResolve(pathToFileURL(withExt(base)).href, context);
  }
  return nextResolve(specifier, context);
}

function withExt(target) {
  if (fs.existsSync(target)) return target;
  for (const ext of [".ts", ".js", ".mjs"]) {
    if (fs.existsSync(target + ext)) return target + ext;
  }
  if (fs.existsSync(path.join(target, "index.ts"))) return path.join(target, "index.ts");
  return target;
}
`
register('data:text/javascript,' + encodeURIComponent(aliasLoader), import.meta.url)

// 浏览器环境 mock：localStorage 与 cookie
const store = new Map()
globalThis.localStorage = {
  getItem: (key) => (store.has(key) ? store.get(key) : null),
  setItem: (key, value) => store.set(key, value),
  removeItem: (key) => store.delete(key),
}
globalThis.document = { cookie: '' }
globalThis.window = { isSecureContext: false, location: { href: 'http://localhost/' } }

const { http } = await import('../src/utils/http.ts')
const { mapVerificationRecord, mapBlockedUser, mapAppealRecord } = await import(
  '../src/api/mappers.ts'
)
const blocksApi = await import('../src/api/blocks.ts')
const appealsApi = await import('../src/api/appeals.ts')
const verificationApi = await import('../src/api/verification.ts')
const authApi = await import('../src/api/auth.ts')

describe('屏蔽管理的接口与映射', () => {
  let calls = []

  beforeEach(() => {
    calls = []
    store.clear()
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: { code: 0, data: { items: [], has_more: false, next_cursor: null } },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
  })

  it('屏蔽列表按游标分页并映射成前端类型', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: {
          code: 0,
          data: {
            items: [{ id: 'u-1', nickname: '小张' }],
            has_more: true,
            next_cursor: 'u-1',
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
    const page = await blocksApi.listBlockedUsers()
    assert.equal(calls[0].url, '/user/blocks')
    assert.equal(calls[0].params.limit, 20)
    assert.equal(page.items[0].id, 'u-1')
    assert.equal(page.items[0].nickname, '小张')
    assert.equal(page.hasMore, true)
    assert.equal(page.nextCursor, 'u-1')
  })

  it('带游标时把游标放进查询串', async () => {
    await blocksApi.listBlockedUsers('u-9')
    assert.equal(calls[0].params.cursor, 'u-9')
  })

  it('屏蔽与解除屏蔽走同一个用户路由的 POST / DELETE', async () => {
    await blocksApi.blockUser('u-2')
    assert.equal(calls[0].method, 'post')
    assert.equal(calls[0].url, '/users/u-2/block')

    await blocksApi.unblockUser('u-2')
    assert.equal(calls[1].method, 'delete')
    assert.equal(calls[1].url, '/users/u-2/block')
  })

  it('被屏蔽用户缺昵称时映射成 null，页面据此显示占位名', () => {
    assert.equal(mapBlockedUser({ id: 'u-3' }).nickname, null)
  })
})

describe('申诉的接口与映射', () => {
  let calls = []

  beforeEach(() => {
    calls = []
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: { code: 0, data: { items: [] } },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
  })

  it('我的申诉列表按页拉取并映射成 camelCase', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: {
          code: 0,
          data: {
            items: [
              {
                id: 'a-1',
                entity_type: 'post',
                entity_id: '42',
                reason: '内容误判',
                status: 'accepted',
                decision_reason: '已恢复',
                created_at: '2026-11-02T00:00:00Z',
              },
            ],
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
    const page = await appealsApi.getAppeals(2)
    assert.equal(calls[0].url, '/appeals')
    assert.equal(calls[0].params.page, 2)
    assert.equal(page.items[0].entityType, 'post')
    assert.equal(page.items[0].decisionReason, '已恢复')
    assert.equal(page.items[0].status, 'accepted')
  })

  it('发起申诉把对象类型与编号按后端字段名提交', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: {
          code: 0,
          data: {
            id: 'a-2',
            entity_type: 'verification',
            entity_id: 'v-1',
            reason: '认证被误拒',
            status: 'pending',
            decision_reason: null,
            created_at: '2026-11-02T00:00:00Z',
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
    const created = await appealsApi.submitAppeal('verification', 'v-1', '认证被误拒')
    assert.equal(calls[0].url, '/appeals')
    assert.equal(calls[0].method, 'post')
    assert.deepEqual(JSON.parse(calls[0].data), {
      entity_type: 'verification',
      entity_id: 'v-1',
      reason: '认证被误拒',
    })
    assert.equal(created.entityType, 'verification')
    assert.equal(created.decisionReason, null)
  })

  it('未知状态与类型退回到安全默认值，不会漏到视图层', () => {
    const mapped = mapAppealRecord({ entity_type: 'unknown', status: 'weird' })
    assert.equal(mapped.entityType, 'post')
    assert.equal(mapped.status, 'pending')
  })
})

describe('学生证认证的接口', () => {
  let calls = []

  beforeEach(() => {
    calls = []
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: { code: 0, data: {} },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
  })

  it('读取认证状态时返回是否开放与当前记录', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: {
          code: 0,
          data: {
            enabled: true,
            school_name: '鄂尔多斯应用技术学院',
            verification: {
              id: 'v-1',
              school_id: 's-1',
              status: 'pending',
              created_at: '2026-11-01T00:00:00Z',
              submitted_at: '2026-11-01T01:00:00Z',
              reviewed_at: null,
              review_reason: null,
              verified_until: null,
              evidence_delete_after: '2026-11-15T01:00:00Z',
            },
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
    const overview = await verificationApi.getVerification()
    assert.equal(calls[0].url, '/student-verifications/me')
    assert.equal(overview.enabled, true)
    assert.equal(overview.schoolName, '鄂尔多斯应用技术学院')
    assert.equal(overview.verification.status, 'pending')
    assert.equal(overview.verification.evidenceDeleteAfter, '2026-11-15T01:00:00Z')
  })

  it('尚未提交过认证时 verification 为 null', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: { code: 0, data: { enabled: true, school_name: '本校', verification: null } },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
    const overview = await verificationApi.getVerification()
    assert.equal(overview.verification, null)
  })

  it('拍摄码按 camelCase 返回，拍摄码本身原样透传', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: {
          code: 0,
          data: {
            verification_id: 'v-1',
            challenge_id: 'c-1',
            code: 'A1B2C3',
            expires_at: '2026-11-02T00:10:00Z',
            school_id: 's-1',
            school_name: '本校',
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
    const challenge = await verificationApi.createVerificationChallenge()
    assert.equal(calls[0].url, '/student-verifications/challenge')
    assert.equal(calls[0].method, 'post')
    assert.equal(challenge.verificationId, 'v-1')
    assert.equal(challenge.code, 'A1B2C3')
    assert.equal(challenge.schoolName, '本校')
  })

  it('提交学生证走 multipart，字段名与后端一致', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: {
          code: 0,
          data: {
            id: 'v-1',
            school_id: 's-1',
            status: 'pending',
            created_at: '2026-11-01T00:00:00Z',
            submitted_at: '2026-11-01T01:00:00Z',
            reviewed_at: null,
            review_reason: null,
            verified_until: null,
            evidence_delete_after: '2026-11-15T01:00:00Z',
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
    const file = new File(['fake'], 'card.jpg', { type: 'image/jpeg' })
    const record = await verificationApi.submitStudentCard(
      {
        verificationId: 'v-1',
        challengeId: 'c-1',
        code: 'A1B2C3',
        expiresAt: '2026-11-02T00:10:00Z',
        schoolId: 's-1',
        schoolName: '本校',
      },
      ' 20260001 ',
      file,
      '2027-06-30',
    )
    assert.equal(calls[0].url, '/student-verifications')
    assert.equal(calls[0].method, 'post')
    const form = calls[0].data
    assert.equal(form.get('verification_id'), 'v-1')
    assert.equal(form.get('challenge_code'), 'A1B2C3')
    assert.equal(form.get('student_id'), '20260001')
    assert.equal(form.get('consent_version'), 'student-card-v1')
    assert.equal(form.get('card_valid_until'), '2027-06-30')
    assert.ok(form.get('file'))
    assert.equal(record.status, 'pending')
  })

  it('未填证件有效期时不下发 card_valid_until，后端按可空处理', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return { data: { code: 0, data: null }, status: 200, statusText: 'OK', headers: {}, config }
    }
    await verificationApi.submitStudentCard(
      {
        verificationId: 'v-1',
        challengeId: 'c-1',
        code: 'A1B2C3',
        expiresAt: '2026-11-02T00:10:00Z',
        schoolId: 's-1',
        schoolName: '本校',
      },
      '20260001',
      new File(['fake'], 'card.jpg', { type: 'image/jpeg' }),
      '',
    )
    assert.equal(calls[0].data.get('card_valid_until'), null)
  })

  it('未知认证状态退回到草稿，不把异常值透到视图层', () => {
    assert.equal(mapVerificationRecord({ id: 'v-1', status: 'weird' }).status, 'draft')
  })
})

describe('账号与跨端配对的接口', () => {
  let calls = []

  beforeEach(() => {
    calls = []
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: { code: 0, data: {} },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
  })

  it('生成配对码走后端配对路由，并带回有效秒数', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: { code: 0, data: { code: 'ABC123DEF456', expires_in: 600 } },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
    const pairing = await authApi.createPairing()
    assert.equal(calls[0].url, '/auth/pairing')
    assert.equal(calls[0].method, 'post')
    assert.equal(pairing.code, 'ABC123DEF456')
    // 后端固定 10 分钟有效
    assert.equal(pairing.expires_in, 600)
  })

  it('绑定原账号时配对码去空格并转大写', async () => {
    http.defaults.adapter = async (config) => {
      calls.push(config)
      return {
        data: {
          code: 0,
          data: {
            access_token: 'token',
            session_id: 'sid',
            expires_in: 3600,
            role: 'student',
            user_info: { id: 'u-1', nickname: '小张', is_verified: true },
          },
        },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      }
    }
    const session = await authApi.claimPairing('  abc123def456 ')
    assert.equal(calls[0].url, '/auth/pairing/claim')
    assert.deepEqual(JSON.parse(calls[0].data), { code: 'ABC123DEF456' })
    assert.equal(session.user_info.nickname, '小张')
  })

  it('修改密码走 PUT /user/password 并带上原密码与新密码', async () => {
    await authApi.changePassword('old-pass-1', 'new-pass-123')
    assert.equal(calls[0].url, '/user/password')
    assert.equal(calls[0].method, 'put')
    assert.deepEqual(JSON.parse(calls[0].data), {
      old_password: 'old-pass-1',
      new_password: 'new-pass-123',
    })
  })

  it('设置登录密码走 POST /auth/password', async () => {
    await authApi.setLoginPassword('zhangsan', 'new-pass-123')
    assert.equal(calls[0].url, '/auth/password')
    assert.equal(calls[0].method, 'post')
    assert.deepEqual(JSON.parse(calls[0].data), { username: 'zhangsan', password: 'new-pass-123' })
  })

  it('注销账号走 POST /user/account/deactivate，未填密码时传 null', async () => {
    await authApi.deactivateAccount('')
    assert.equal(calls[0].url, '/user/account/deactivate')
    assert.equal(calls[0].method, 'post')
    assert.deepEqual(JSON.parse(calls[0].data), { password: null })
  })

  it('下线全部设备走 POST /auth/sessions/revoke-all', async () => {
    await authApi.revokeAllSessions()
    assert.equal(calls[0].url, '/auth/sessions/revoke-all')
    assert.equal(calls[0].method, 'post')
  })
})
