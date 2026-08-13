from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

MODUL_SOKVAG = Path(__file__).with_name("build.py")
SPEC = importlib.util.spec_from_file_location("pdf_bokhylla_build", MODUL_SOKVAG)
assert SPEC and SPEC.loader
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class PdfBokhyllaBuildTest(unittest.TestCase):
    def test_ref_maste_vara_fullstandig_sha(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "fullständig commit-SHA"):
            build._validera_ref({"bokhylla": {"ref": "main"}})

    def test_ovantat_saknat_dokument_stoppar_exporten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rot = Path(tmp)
            mal = rot / "ut"
            manifest = rot / "bokhylla/backend/pdfdata/test/manifest.json"
            (mal / "data").mkdir(parents=True)
            manifest.parent.mkdir(parents=True)
            (mal / "data/grupper.json").write_text(
                json.dumps({"grupper": [{"namn": "test", "antal": 2}]}),
                encoding="utf-8",
            )
            manifest.write_text(
                json.dumps({"saknade": ["ovantat-dokument"]}), encoding="utf-8"
            )
            config = {
                "grupper": [
                    {"namn": "test", "minst_antal": 2, "tillatet_saknade": []}
                ]
            }
            with self.assertRaisesRegex(RuntimeError, "oväntat saknade dokument"):
                build._validera_manifest(rot / "bokhylla", mal, config)

    def test_odata_nyckel_far_inte_finnas_i_artefakten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            mal = Path(tmp)
            (mal / "data.txt").write_text("hemlig-testnyckel", encoding="utf-8")
            with patch.dict(os.environ, {"SVK_ODATA_API_KEY": "hemlig-testnyckel"}):
                with self.assertRaisesRegex(RuntimeError, "OData-nyckeln"):
                    build._skanna_hemlighet(mal)

    def test_brett_exportmal_avvisas_fore_rensning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            rot = Path(tmp)
            (rot / "backend/app").mkdir(parents=True)
            (rot / "backend/app/pdfexport.py").touch()
            (rot / "poc").mkdir()
            with self.assertRaisesRegex(RuntimeError, "särskild katalog"):
                build.bygg(rot, rot / "ut", None)


if __name__ == "__main__":
    unittest.main()
