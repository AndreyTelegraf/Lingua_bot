from services.vocab_runtime.result_snapshot import map_band_to_prior_theta_hint


def test_map_band_to_prior_theta_hint():
    assert map_band_to_prior_theta_hint("A0") == -2.0
    assert map_band_to_prior_theta_hint("A1") == -1.4
    assert map_band_to_prior_theta_hint("A1+") == -1.0
    assert map_band_to_prior_theta_hint("A2") == -0.4
    assert map_band_to_prior_theta_hint("B1") == 0.2
    assert map_band_to_prior_theta_hint("B2") == 0.9
    assert map_band_to_prior_theta_hint("C1") == 1.5
    assert map_band_to_prior_theta_hint("C1+") == 2.0
