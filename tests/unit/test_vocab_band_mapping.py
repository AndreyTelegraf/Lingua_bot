from services.vocab_runtime.result_snapshot import map_range_to_product_band


def test_map_range_to_product_band():
    assert map_range_to_product_band(range_min=0, range_max=400) == "A0"
    assert map_range_to_product_band(range_min=500, range_max=1000) == "A1"
    assert map_range_to_product_band(range_min=1000, range_max=1500) == "A1+"
    assert map_range_to_product_band(range_min=1500, range_max=2500) == "A2"
    assert map_range_to_product_band(range_min=2500, range_max=4000) == "B1"
    assert map_range_to_product_band(range_min=4000, range_max=6500) == "B2"
    assert map_range_to_product_band(range_min=6500, range_max=8000) == "C1"
    assert map_range_to_product_band(range_min=8000, range_max=9000) == "C1+"
