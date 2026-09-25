const { test } = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const React = require('react')
const { renderToStaticMarkup } = require('react-dom/server')

function load(file, overrides = {}) {
  const source = fs.readFileSync(path.join(__dirname, '..', file), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: {
    module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020, jsx: ts.JsxEmit.ReactJSX,
  }}).outputText
  const module = { exports: {} }
  vm.runInNewContext(code, { module, exports: module.exports, require, TextDecoder, Uint8Array, atob, Date, ...overrides })
  return module.exports
}

function authContext(fetch = async () => ({ status: 200 })) {
  const storage = new Map()
  const redirects = []
  const localStorage = { getItem: k => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) }
  const window = { location: { pathname: '/queue', assign: path => redirects.push(path) } }
  return { auth: load('lib/auth.ts', { window, localStorage, fetch }), storage, redirects }
}

function token(payload) {
  return 'header.' + Buffer.from(JSON.stringify(payload)).toString('base64url') + '.signature'
}

test('expired tokens are removed and Korean names survive base64url decoding', () => {
  const { auth, storage } = authContext()
  auth.setToken(token({ role: 'operator', name: '운영자😀', exp: Math.floor(Date.now() / 1000) + 60 }))
  assert.equal(auth.getUserName(), '운영자😀')
  assert.equal(auth.getRole(), 'operator')
  auth.setToken(token({ role: 'client', exp: 1 }))
  assert.equal(auth.isLoggedIn(), false)
  assert.equal(storage.size, 0)
})

test('401 clears the session and sends the user to login', async () => {
  const { auth, storage, redirects } = authContext(async () => ({ status: 401 }))
  storage.set('cg_token', 'stale')
  await auth.authenticatedFetch('/api/contents')
  assert.equal(storage.size, 0)
  assert.deepEqual(redirects, ['/login'])
})

test('login uses the selected account type', async () => {
  const urls = []
  const fetch = async url => { urls.push(url); return { ok: true, json: async () => ({ access_token: 'test' }) } }
  const { auth } = authContext(fetch)
  const { api } = load('lib/api.ts', { fetch, URLSearchParams, require: name => name === '@/lib/auth' ? auth : require(name) })
  await api.login('client@example.com', 'password', 'client')
  await api.login('operator@example.com', 'password', 'operator')
  assert.deepEqual(urls, ['/auth/login', '/auth/operator/login'])
})

test('evidence indices count Unicode code points including emoji', () => {
  const { HighlightedText } = load('components/highlighted-text.tsx')
  const text = '😀 [전화번호] 죽이겠다'
  const start = Array.from(text).length - Array.from('죽이겠다').length
  const html = renderToStaticMarkup(React.createElement(HighlightedText, { text, spans: [
    { text: '죽이겠다', category: 'threat', severity: 'high', start_index: start, end_index: start + 4 },
  ] }))
  assert.ok(html.includes('title="threat">죽이겠다</span>'))
})

test('old mismatched evidence does not highlight unrelated text', () => {
  const { HighlightedText } = load('components/highlighted-text.tsx')
  const html = renderToStaticMarkup(React.createElement(HighlightedText, { text: '010-1234-5678 죽이겠다', spans: [
    { text: '죽이겠다', category: 'threat', severity: 'high', start_index: 7, end_index: 11 },
  ] }))
  assert.ok(!html.includes('title="threat"'))
})
