"""Regression tests for independent semantic and rendered-figure failure gates."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def verifier():
    pytest.importorskip("PIL")
    script = (
        Path(__file__).resolve().parents[1]
        / "publication/options-risk-study/scripts/verify_pack.py"
    )
    spec = importlib.util.spec_from_file_location("options_publication_verifier", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_blank_same_size_image_fails_despite_matching_contract(verifier, monkeypatch, tmp_path):
    from PIL import Image

    def blank_figure(output_path, contract_path):
        contract = verifier.build_figures.build_render_contract()
        verifier.build_figures.write_render_contract(contract, contract_path)
        Image.new("RGB", (1650, 975), "white").save(output_path)
        return str(output_path)

    monkeypatch.setattr(verifier.build_figures, "build_figure", blank_figure)
    verifier.check_figure_reproducible(tmp_path)
    assert any("figure visual comparison differs" in failure for failure in verifier.FAILURES)


def test_changed_value_fails_even_when_image_bytes_match(verifier, monkeypatch, tmp_path):
    def changed_contract(output_path, contract_path):
        contract = verifier.build_figures.build_render_contract()
        contract["plotted_rows"][0]["mean_var_corrected"] += 1
        contract_path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
        output_path.write_bytes(
            (verifier.build_tables.FIGURES_DIR / verifier.FIGURE_NAME).read_bytes()
        )
        return str(output_path)

    monkeypatch.setattr(verifier.build_figures, "build_figure", changed_contract)
    verifier.check_figure_reproducible(tmp_path)
    assert any("freshly recomputed semantic" in failure for failure in verifier.FAILURES)
