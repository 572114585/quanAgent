import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


PPT_MASTER_REQUIREMENTS = {
    "PyYAML>=6.0": "yaml",
    "python-pptx>=0.6.21": "pptx",
    "XlsxWriter>=3.0.0": "xlsxwriter",
    "skia-pathops>=0.9.2": "pathops",
    "uharfbuzz>=0.50.0": "uharfbuzz",
    "edge-tts>=7.2.8": "edge_tts",
    "PyMuPDF>=1.23.0": "fitz",
    "mammoth>=1.6.0": "mammoth",
    "EbookLib>=0.18": "ebooklib",
    "nbconvert>=7.0.0": "nbconvert",
    "beautifulsoup4>=4.12.0": "bs4",
    "curl_cffi>=0.7.0": "curl_cffi",
    "google-genai>=1.0.0": "google.genai",
    "flask>=3.0.0": "flask",
}


def test_root_manifest_declares_ppt_master_dependencies() -> None:
    manifest = (ROOT / "requirement.txt").read_text(encoding="utf-8")
    for requirement in PPT_MASTER_REQUIREMENTS:
        assert requirement in manifest


def test_ppt_master_dependencies_are_importable_from_current_python() -> None:
    missing = [
        f"{requirement} ({module})"
        for requirement, module in PPT_MASTER_REQUIREMENTS.items()
        if importlib.util.find_spec(module) is None
    ]
    assert not missing, "Missing PPT Master dependencies: " + ", ".join(missing)
