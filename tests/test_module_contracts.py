import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / 'builder' / 'build_sd.py'
GENERATE_MANIFEST = REPO_ROOT / 'builder' / 'generate_manifest.py'
WEB_BUILDER = REPO_ROOT / 'docs' / 'app' / 'index.html'
README = REPO_ROOT / 'README.md'


def load_module(module_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ModuleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = load_module('mmi3g_build_sd_contracts', BUILD_SCRIPT)
        cls.manifest_generator = load_module('mmi3g_generate_manifest_contracts', GENERATE_MANIFEST)
        cls.modules = cls.builder.find_modules()
        cls.manifest = cls.manifest_generator.build_manifest()
        cls.web_source = WEB_BUILDER.read_text(encoding='utf-8')

    def test_all_module_manifests_are_valid_and_discovered(self):
        module_dirs = {
            path.parent.name
            for path in (REPO_ROOT / 'modules').glob('*/module.json')
        }

        self.assertEqual(set(self.modules), module_dirs)
        for name, meta in self.modules.items():
            with self.subTest(module=name):
                self.assertEqual(meta['name'], name)
                self.assertIn(meta['status'], {'alpha', 'design', 'planned', 'ready', 'tested'})
                self.assertTrue(set(meta['compatible']).issubset(self.builder.SUPPORTED_PLATFORMS))

    def test_prerequisite_graph_resolves_for_every_real_module(self):
        for name, meta in self.modules.items():
            with self.subTest(module=name):
                resolved, _ = self.builder.resolve_selected_modules([name], self.modules)
                self.assertEqual(resolved[-1], name)
                prereq = meta.get('prereq')
                if prereq:
                    self.assertIn(prereq, resolved)
                    self.assertLess(resolved.index(prereq), resolved.index(name))

    def test_web_display_metadata_is_manifest_driven(self):
        self.assertNotIn('const MODULES_DISPLAY = [', self.web_source)
        self.assertIn('displayModulesFromManifest(appManifest)', self.web_source)

        explicitly_hidden = {
            'can-diag',
            'persistence-dump',
            'region-audit',
        }

        self.assertEqual(
            {
                name
                for name, meta in self.manifest['modules'].items()
                if meta.get('display') is False
            },
            explicitly_hidden,
        )

        orders = []
        for name, meta in self.manifest['modules'].items():
            if meta.get('display') is False:
                continue
            with self.subTest(module=name):
                self.assertTrue(meta.get('display_name'))
                self.assertIn(meta.get('category'), {'system', 'gem', 'visual', 'nav', 'diag', 'net'})
                self.assertTrue(meta.get('detail'))
                self.assertIn(meta.get('status'), {'alpha', 'design', 'planned', 'ready', 'tested'})
                self.assertTrue(meta.get('compatible'))
                self.assertIsInstance(meta.get('display_order'), int)
                orders.append(meta['display_order'])

        self.assertEqual(len(orders), len(set(orders)))

    def test_readme_module_count_matches_discovered_modules(self):
        readme = README.read_text(encoding='utf-8')
        match = re.search(r'collection of (\d+) modules', readme)
        self.assertIsNotNone(match)
        self.assertEqual(int(match.group(1)), len(self.modules))

    def test_declared_run_scripts_are_copied_for_runnable_modules(self):
        for name, meta in self.modules.items():
            if not meta.get('run_script'):
                continue
            if meta.get('release_assets') or meta.get('release_zip'):
                continue

            with self.subTest(module=name):
                with tempfile.TemporaryDirectory() as tmpdir:
                    output_dir = Path(tmpdir) / 'sdcard'
                    self.builder.build_sd([name], self.modules, str(output_dir))

                    run_script = meta['run_script']
                    self.assertTrue((output_dir / 'scripts' / run_script).is_file())
                    run_sh = (output_dir / 'run.sh').read_text(encoding='utf-8')
                    self.assertIn(f'ksh "${{SDPATH}}/scripts/{run_script}" "${{SDPATH}}"', run_sh)

    def test_no_unexpected_large_tracked_binary_payloads(self):
        allowed_large_files = {
            'binaries/gemmi/libembeddedearth_oncar.so',
        }
        binary_suffixes = {'.bin', '.jar', '.so', '.zip'}
        max_unlisted_size = 5 * 1024 * 1024
        tracked = subprocess.check_output(
            ['git', 'ls-files', '-z'],
            cwd=str(REPO_ROOT),
        ).decode('utf-8').split('\0')

        offenders = []
        for rel in filter(None, tracked):
            path = REPO_ROOT / rel
            if path.suffix not in binary_suffixes:
                continue
            if path.stat().st_size <= max_unlisted_size:
                continue
            if rel not in allowed_large_files:
                offenders.append(rel)

        self.assertEqual(offenders, [])
        self.assertNotIn('docs/payloads/gemmi_p0824_eu_vw.zip', tracked)


if __name__ == '__main__':
    unittest.main()
