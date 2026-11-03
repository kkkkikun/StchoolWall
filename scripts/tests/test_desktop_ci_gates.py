"""电脑端三道门禁脚本的单元测试。

覆盖：
- `desktop-frontend/scripts/bundle-budget-check.py`：体积测量与基线比对（人为把基线调小 30% 必须判失败）；
- `desktop-frontend/scripts/ui-contrast-audit.py`：令牌读取、令牌级对比度判定与未定义令牌检查；
- `desktop-frontend/scripts/walkthrough_server.py`：`/pc/` 前缀剥离与页面地址拼接；
- `desktop-frontend/scripts/desktop_mock_api.py`：接口夹具与信封格式。

脚本本身不依赖 playwright（浏览器部分在 main() 里才导入），因此这组用例可以在
没有浏览器的环境里跑（CI 的运维脚本回归步骤早于浏览器走查步骤）。
"""

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DESKTOP = ROOT / 'desktop-frontend'
SCRIPTS = DESKTOP / 'scripts'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class BundleBudgetTests(unittest.TestCase):
    """体积预算守卫。"""

    def setUp(self):
        self.mod = load('desktop_bundle_budget', SCRIPTS / 'bundle-budget-check.py')
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dist = Path(temp.name) / 'dist'
        (self.dist / 'assets').mkdir(parents=True)
        (self.dist / 'assets' / 'index-abc.js').write_bytes(b'console.log(1)' * 100)
        (self.dist / 'assets' / 'index-abc.css').write_bytes(b'body{}' * 50)
        (self.dist / 'assets' / 'chunk-1.js').write_bytes(b'x' * 200)
        (self.dist / 'index.html').write_text(
            '<html><script src="/pc/assets/index-abc.js"></script>'
            '<link href="/pc/assets/index-abc.css"></html>',
            encoding='utf-8',
        )
        self.mod.DIST_DIR = str(self.dist)
        self.mod.ASSETS_DIR = str(self.dist / 'assets')

    def test_measure_separates_entry_chunk_and_total(self):
        measured = self.mod.measure()
        self.assertEqual(measured['main_chunk_js_raw'], 1400)
        self.assertEqual(measured['main_chunk_css_raw'], 300)
        self.assertEqual(measured['js_count'], 2)
        self.assertEqual(measured['css_count'], 1)
        self.assertGreater(measured['total_js_raw'], measured['main_chunk_js_raw'])
        self.assertGreater(measured['main_chunk_js_gzip'], 0)

    def test_baseline_shrunk_by_thirty_percent_is_rejected(self):
        measured = self.mod.measure()
        shrunk = {k: v * 0.7 for k, v in measured.items() if k not in ('js_count', 'css_count')}
        findings = self.mod.compare(measured, shrunk, 0.10)
        self.assertTrue(findings, '基线调小 30% 必须被判失败')
        self.assertTrue(any('main_chunk_js_raw' in item for item in findings))
        self.assertTrue(any('main_chunk_js_gzip' in item for item in findings))

    def test_baseline_within_tolerance_passes(self):
        measured = self.mod.measure()
        self.assertEqual(self.mod.compare(measured, measured, 0.10), [])

    def test_committed_baseline_covers_every_measured_metric(self):
        baseline = json.loads((DESKTOP / 'bundle-baseline.json').read_text(encoding='utf-8'))
        measured = self.mod.measure()
        self.assertEqual(set(baseline['bundle']), set(measured),
                         '体积基线必须覆盖测量脚本的全部指标')
        self.assertGreater(baseline['tolerance'], 0)


class ContrastAuditTests(unittest.TestCase):
    """对比度扫描的令牌层判定。"""

    def setUp(self):
        self.mod = load('desktop_contrast_audit', SCRIPTS / 'ui-contrast-audit.py')
        self.tokens = self.mod.read_tokens(self.mod.TOKENS_CSS)

    def test_reads_light_and_dark_tokens(self):
        self.assertEqual(self.tokens['light']['--sw-primary'], '#c2455c')
        self.assertNotEqual(self.tokens['dark']['--sw-bg'], self.tokens['light']['--sw-bg'])
        self.assertIn('--sw-text', self.tokens['dark'])

    def test_resolve_follows_var_chain(self):
        light = self.tokens['light']
        self.assertEqual(self.mod.resolve(light, '--el-color-primary'), '#c2455c')

    def test_contrast_matches_wcag_reference(self):
        self.assertAlmostEqual(self.mod.contrast('#000000', '#ffffff'), 21.0, places=4)
        self.assertAlmostEqual(self.mod.contrast('#ffffff', '#ffffff'), 1.0, places=4)

    def test_repository_palette_passes_token_level_gate(self):
        self.assertEqual(self.mod.token_level_findings(self.tokens), [])

    def test_no_undefined_token_reference_in_sources(self):
        self.assertEqual(self.mod.undefined_token_references(self.mod.SRC_DIR, self.tokens), [])

    def test_body_token_below_threshold_is_blocked(self):
        broken = {'light': dict(self.tokens['light']), 'dark': dict(self.tokens['dark'])}
        broken['light']['--sw-text'] = '#bbbbbb'
        broken['dark']['--sw-text'] = '#bbbbbb'
        findings = self.mod.token_level_findings(broken)
        self.assertTrue(findings)
        self.assertTrue(any('--sw-text' in item['issue'] for item in findings))

    def test_color_is_resolved_back_to_token_name(self):
        index = self.mod.token_value_index(self.tokens['light'])
        name, role = self.mod.classify('#c2455c', self.tokens['light'], index)
        self.assertEqual(name, '--sw-primary')
        self.assertEqual(role, '品牌色文字')
        name, role = self.mod.classify('#1f2328', self.tokens['light'], index)
        self.assertEqual(name, '--sw-text')
        self.assertEqual(role, '正文')


class WalkthroughServerTests(unittest.TestCase):
    """走查静态服务的部署前缀处理。"""

    def setUp(self):
        self.mod = load('desktop_walkthrough_server', SCRIPTS / 'walkthrough_server.py')

    def test_strips_pc_prefix(self):
        self.assertEqual(self.mod.SPAHandler._strip_prefix('/pc/assets/a.js'), '/assets/a.js')
        self.assertEqual(self.mod.SPAHandler._strip_prefix('/assets/a.js'), '/assets/a.js')

    def test_route_url_keeps_prefix(self):
        self.assertEqual(self.mod.route_url('http://127.0.0.1:8000', '/post/1'),
                         'http://127.0.0.1:8000/pc/post/1')
        self.assertEqual(self.mod.route_url('http://127.0.0.1:8000', 'post/1'),
                         'http://127.0.0.1:8000/pc/post/1')

    def test_server_origin_extracts_host(self):
        self.assertEqual(self.mod.server_origin('http://127.0.0.1:8000'), '127.0.0.1:8000')


class MockApiTests(unittest.TestCase):
    """接口夹具。"""

    def setUp(self):
        self.mod = load('desktop_mock_api', SCRIPTS / 'desktop_mock_api.py')
        self.mod.SESSION_STATE['logged_in'] = False

    def test_recognises_backend_requests_only(self):
        self.assertTrue(self.mod.is_api_url('http://127.0.0.1:8000/api/v1/posts'))
        self.assertTrue(self.mod.is_api_url('https://api.example.com/api/v1/posts?cursor=1'))
        self.assertFalse(self.mod.is_api_url('http://127.0.0.1:8000/pc/assets/index.js'))

    def test_cross_origin_requests_are_mocked_too(self):
        # CI 里 VITE_API_BASE_URL 可能指向绝对地址，走查不能真的打到线上接口
        self.assertTrue(self.mod.is_api_url('https://api.example.com/posts', '127.0.0.1:8000'))
        self.assertFalse(self.mod.is_api_url('http://127.0.0.1:8000/pc/assets/index.js', '127.0.0.1:8000'))

    def test_posts_page_has_content(self):
        page = self.mod.dispatch('GET', '/posts')
        self.assertTrue(page['items'])
        self.assertFalse(page['has_more'])

    def test_login_returns_session_with_role(self):
        session = self.mod.dispatch('POST', '/auth/web-login')
        self.assertEqual(session['role'], 'student')
        self.assertTrue(session['access_token'])
        self.assertNotIn('real_name', session['user_info'])
        self.assertNotIn('student_number', session['user_info'])

    def test_refresh_is_empty_until_login(self):
        self.assertEqual(self.mod.dispatch('POST', '/auth/refresh'), {})
        self.mod.dispatch('POST', '/auth/web-login')
        self.assertEqual(self.mod.dispatch('POST', '/auth/refresh')['user_info']['nickname'],
                         '走查测试员')

    def test_publish_returns_new_post_id(self):
        self.assertEqual(self.mod.dispatch('POST', '/posts')['post_id'], 101)


if __name__ == '__main__':
    unittest.main()
