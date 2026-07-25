"""Tests for object-sculptor package_html TS→JS stripping and packaging."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = (
    Path(__file__).resolve().parents[1]
    / "workspace"
    / "skills"
    / "object-sculptor"
    / "scripts"
)
sys.path.insert(0, str(SCRIPTS))

from package_html import build_html, main as package_main, strip_typescript  # noqa: E402


SAMPLE_TS = """
import * as THREE from 'three';

export type ProceduralModelOptions = {
  wireframe?: boolean;
};

export const SCULPT_FACTORY_CONTRACT = {
  factoryExport: "createSculptModel",
  expectedComponentIds: ["root"],
} as const;

type CaptureHost = typeof globalThis & {
  __THREEJS_SCULPT_CAPTURE_RUNTIME__?: () => unknown[];
};

function installCapture(): void {
  const host = globalThis as CaptureHost;
  host.__THREEJS_SCULPT_CAPTURE_RUNTIME__ = () => [];
}

const roots = new Set<THREE.Group>();

export function createDemoModel(options: ProceduralModelOptions = {}): THREE.Group {
  const root = new THREE.Group();
  root.name = 'demo';
  const mesh = new THREE.Mesh(
    new THREE.BoxGeometry(1, 1, 1),
    new THREE.MeshStandardMaterial({ color: 0x2563eb }),
  );
  root.add(mesh);
  roots.add(root);
  installCapture();
  root.userData.sculptRuntime = { dispose: () => undefined } satisfies { dispose: () => void };
  return root;
}

export const createSculptModel = createDemoModel;

export function frameDemoForReview(
  camera: THREE.PerspectiveCamera,
  model: THREE.Object3D,
  mode: 'neutral' | 'grazing' | 'reference' = 'neutral',
): void {
  const useMode = mode === 'grazing' ? 1 : 0;
  camera.position.set(2 + useMode, 2, 3);
  camera.lookAt(0, 0, 0);
}
"""


class StripTypescriptTests(unittest.TestCase):
    def test_strips_types_and_keeps_runtime(self) -> None:
        js = strip_typescript(SAMPLE_TS)
        self.assertIn("createSculptModel", js)
        self.assertIn('expectedComponentIds: ["root"]', js)
        self.assertNotIn("export type", js)
        self.assertNotIn("as const", js)
        self.assertNotIn("satisfies", js)
        self.assertNotIn("new Set<THREE.Group>", js)
        self.assertIn("new Set()", js)
        self.assertIn("function frameDemoForReview(", js)
        self.assertRegex(js, r"mode\s*=\s*'neutral'")
        self.assertNotIn("{ dispose: () => void }", js)

    def test_package_writes_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            factory = root / "Demo.generated.ts"
            factory.write_text(SAMPLE_TS, encoding="utf-8")
            out = root / "demo.html"
            code = package_main(
                [
                    "--factory",
                    str(factory),
                    "--out",
                    str(out),
                    "--title",
                    "Demo",
                    "--also-js",
                ]
            )
            self.assertEqual(code, 0)
            html = out.read_text(encoding="utf-8")
            self.assertIn("preserveDrawingBuffer: true", html)
            self.assertIn("three@0.160.0", html)
            self.assertIn("createSculptModel", html)
            self.assertIn("OrbitControls", html)
            self.assertTrue(out.with_suffix(".factory.js").is_file())

    def test_build_html_detects_helpers(self) -> None:
        js = strip_typescript(SAMPLE_TS)
        html = build_html(js, title="T")
        self.assertIn("frameDemoForReview(camera, model)", html)


if __name__ == "__main__":
    unittest.main()
