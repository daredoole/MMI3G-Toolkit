from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_BUILDER = REPO_ROOT / "docs" / "app" / "index.html"


class WebBuilderParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WEB_BUILDER.read_text(encoding="utf-8")

    def test_generate_run_sh_sources_platform_helper(self):
        for snippet in (
            "scripts/common/platform.sh",
            "platform.sh installed to ${EFSDIR}/scripts/common/",
        ):
            self.assertIn(snippet, self.source)

    def test_generate_run_sh_shows_running_and_done_status(self):
        for snippet in (
            "/tmp/showScreen",
            "SHOWSCREEN_PID=$!",
            "lib/running.png",
            "lib/done.png",
            "kill ${SHOWSCREEN_PID} 2>/dev/null",
        ):
            self.assertIn(snippet, self.source)

    def test_bundle_includes_platform_helper_and_module_artifacts(self):
        self.assertIn(
            'files.push({ path: "scripts/common/platform.sh", bytes: platformSh });',
            self.source,
        )
        self.assertIn(
            'if (meta.artifact && f.path === meta.artifact) return `modules/${modName}/${f.path}`;',
            self.source,
        )
        self.assertIn(
            'for (const payload of (meta.payload_dirs || [])) {',
            self.source,
        )
        self.assertIn(
            'return { path: moduleOutputPath(modName, meta, f), bytes };',
            self.source,
        )

    def test_web_release_zip_prefers_pages_url(self):
        self.assertIn('if (rz && rz.web_url) return rz.web_url;', self.source)
        self.assertIn('const zipFiles = await fetchReleaseZipFiles(rz);', self.source)

    def test_p0824_card_is_web_buildable_with_pages_payload_link(self):
        manifest = (REPO_ROOT / 'docs' / 'app' / 'manifest.json').read_text(encoding='utf-8')

        self.assertIn('payloadUrl: meta.release_zip?.web_url || meta.prebuilt_zip || null', self.source)
        self.assertIn('cliOnly: meta.web_build === false', self.source)
        self.assertIn(
            'https://dspl1236.github.io/MMI3G-Toolkit/payloads/gemmi_p0824_eu_vw.zip',
            manifest,
        )

    def test_module_cards_are_manifest_driven(self):
        self.assertNotIn('const MODULES_DISPLAY = [', self.source)
        self.assertIn('displayModulesFromManifest(manifest)', self.source)
        self.assertIn('runScriptOptions: meta.run_script_options || []', self.source)
        self.assertIn(
            '...m.runScriptOptions.map(opt => React.createElement("option"',
            self.source,
        )


if __name__ == "__main__":
    unittest.main()
