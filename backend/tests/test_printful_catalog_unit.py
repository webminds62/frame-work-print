import asyncio
import os

import pytest
from pydantic import ValidationError

os.environ["PRINTFUL_CATALOG_MODE"] = "snapshot"

from printful_catalog import find_selection, find_variant, get_catalog, snapshot_variants
from server import PaymentCreateIn, resolve_printful_variant, validated_printful_variant


def test_verified_snapshot_has_unique_exact_fulfillment_variants():
    variants = snapshot_variants(1.6)
    assert len(variants) == 51
    assert len({variant.id for variant in variants}) == len(variants)
    assert len({(variant.product_id, variant.size_key, variant.finish_key) for variant in variants}) == len(variants)
    assert all(variant.image.startswith("https://files.cdn.printful.com/") for variant in variants)


def test_known_official_variants_keep_product_finish_size_and_price():
    variants = snapshot_variants(1.6)
    canvas_brown = find_variant(variants, 16044)
    poster_oak = find_variant(variants, 15031)
    assert (canvas_brown.product_id, canvas_brown.material, canvas_brown.size_key, canvas_brown.finish_label) == (614, "canvas", "18x24", "Brown")
    assert (poster_oak.product_id, poster_oak.material, poster_oak.size_key, poster_oak.finish_label) == (2, "poster", "18x24", "Red Oak")
    assert canvas_brown.retail_price == 114.24
    assert poster_oak.retail_price == 72.62


def test_snapshot_offers_multiple_real_wall_art_product_types():
    variants = snapshot_variants(1.6)
    product_ids = {variant.product_id for variant in variants}
    assert {1, 2, 3, 614}.issubset(product_ids)
    assert {171, 172, 588, 616, 795}.issubset(product_ids)

    metal = find_variant(variants, 15139)
    assert metal is not None
    assert (metal.product_id, metal.material, metal.size_key, metal.finish_label) == (
        588, "metal", "24x36", "Glossy metal"
    )


def test_unavailable_framed_size_is_not_silently_substituted():
    variants = snapshot_variants(1.6)
    assert find_selection(variants, "canvas", "30x40", "brown") is None
    assert resolve_printful_variant("canvas", "30x40", "wood") == (None, False)
    unframed = find_selection(variants, "canvas", "30x40", "none")
    assert unframed and unframed.id == 19323


def test_snapshot_mode_is_deterministic_without_account_credentials():
    variants, source, synced_at = asyncio.run(get_catalog(1.6))
    assert source == "verified_snapshot"
    assert synced_at.endswith("Z")
    assert find_variant(variants, 16038).name == "Framed Canvas (Black / 18″×24″)"


def test_server_rejects_variant_that_does_not_match_selection():
    with pytest.raises(Exception) as exc:
        asyncio.run(validated_printful_variant(16038, "canvas", "18x24", "white"))
    assert getattr(exc.value, "status_code", None) == 422


def test_payment_contract_requires_exact_variant_id():
    with pytest.raises(ValidationError):
        PaymentCreateIn(
            project_id="project-1",
            material="canvas",
            size="18x24",
            frame="brown",
            panels=1,
            recipient={
                "name": "Test User",
                "address1": "123 Main St",
                "city": "Austin",
                "state_code": "TX",
                "country_code": "US",
                "zip": "78701",
            },
        )
