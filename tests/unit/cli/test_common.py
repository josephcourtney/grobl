from grobl.cli.common import (
    _default_confirm,
    _detect_heavy_dirs,
    _execute_with_handling,
    _maybe_offer_legacy_migration,
    _maybe_warn_on_common_heavy_dirs,
    _scan_for_legacy_references,
    iter_legacy_references,
    print_interrupt_diagnostics,
)

# TODO: write real unit tests


def test__default_confirm():
    assert _default_confirm


def test__detect_heavy_dirs():
    assert _detect_heavy_dirs


def test__maybe_warn_on_common_heavy_dirs():
    assert _maybe_warn_on_common_heavy_dirs


def test_iter_legacy_references():
    assert iter_legacy_references


def test__scan_for_legacy_references():
    assert _scan_for_legacy_references


def test__maybe_offer_legacy_migration():
    assert _maybe_offer_legacy_migration


def test_print_interrupt_diagnostics():
    assert print_interrupt_diagnostics


def test__execute_with_handling():
    assert _execute_with_handling
