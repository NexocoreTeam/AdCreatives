from strategy.product_dedup import find_near_duplicate


def test_misspelled_subset_matches():
    # The exact Zoka failure: operator typed "Palladino", site says "Espresso Paladino".
    assert find_near_duplicate("palladino", ["espresso-paladino"]) == "espresso-paladino"
    assert find_near_duplicate("espresso-paladino", ["palladino"]) == "palladino"


def test_display_names_work_too():
    assert find_near_duplicate("Palladino", ["Espresso Paladino"]) == "Espresso Paladino"


def test_distinct_products_do_not_match():
    assert find_near_duplicate("colombia-blend", ["colombia-decaf"]) is None
    assert find_near_duplicate("fitzroy", ["espresso-paladino", "tatoosh"]) is None


def test_exact_same_slug_is_not_reported():
    # Re-writing the same slug is the idempotent-update path, not a dup.
    assert find_near_duplicate("espresso-paladino", ["espresso-paladino"]) is None


def test_empty_inputs():
    assert find_near_duplicate("", ["espresso-paladino"]) is None
    assert find_near_duplicate("espresso-paladino", []) is None
