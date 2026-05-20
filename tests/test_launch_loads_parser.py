"""Launch load file parser tests."""

from schemagraph.launch_compat.loads.parser import merge_psd, parse_load_file, psd_grms


def test_merge_upload_overrides_bundled():
    bundled = [{"freq_hz": 10, "asd_g2_hz": 0.001}]
    override = {"points": [{"freq_hz": 50, "asd_g2_hz": 0.1}]}
    pts, src = merge_psd(bundled, override)
    assert src == "upload"
    assert pts[0]["freq_hz"] == 50
