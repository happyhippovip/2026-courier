"""Host Guardian soak must not pass when an envelope sample is missing."""

from scripts.soak.envelope import envelope_pass


def test_missing_envelope_sample_is_not_a_pass():
    assert envelope_pass({
        "obj_within_envelope": True,
        "fd_within_envelope": True,
        "probes_within_envelope": True,
    }) is True
    assert envelope_pass({
        "fd_within_envelope": True,
        "probes_within_envelope": True,
    }) is False
    assert envelope_pass({
        "obj_within_envelope": True,
        "probes_within_envelope": True,
    }) is False
    assert envelope_pass({
        "obj_within_envelope": True,
        "fd_within_envelope": True,
    }) is False
    assert envelope_pass({
        "obj_within_envelope": 1,
        "fd_within_envelope": True,
        "probes_within_envelope": True,
    }) is False
