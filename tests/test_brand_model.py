from models.brand import Brand, VisualIdentity


def test_visual_identity_mood_string_coerced_to_list():
    """The Zoka onboard crash: LLM returned mood as prose, schema wants list.
    A type wobble here must not brick load_brand()."""
    vi = VisualIdentity(mood="Warm, trustworthy, craft-forward.")
    assert vi.mood == ["Warm, trustworthy, craft-forward."]


def test_visual_identity_list_fields_pass_through():
    vi = VisualIdentity(mood=["warm", "trustworthy"], visual_references="PROBAT roaster")
    assert vi.mood == ["warm", "trustworthy"]
    assert vi.visual_references == ["PROBAT roaster"]


def test_visual_identity_str_fields_coerce_lists():
    vi = VisualIdentity(aesthetic=["craft", "heritage"], color_mood=["warm", "earthy"])
    assert vi.aesthetic == "craft, heritage"
    assert vi.color_mood == "warm, earthy"


def test_audience_interests_string_coerced():
    brand = Brand(name="Zoka Coffee", audience={"age_range": "35-60", "interests": "specialty coffee"})
    assert brand.audience.interests == ["specialty coffee"]


def test_full_zoka_shape_loads():
    """Regression: the exact brand.yaml shape research wrote for Zoka."""
    brand = Brand(
        name="Zoka Coffee",
        visual_identity={
            "aesthetic": "Pacific Northwest craft heritage",
            "mood": "Warm, trustworthy, craft-forward. Feels like a place that "
                    "has been here for decades and will be here for decades more.",
            "visual_references": ["1963 German PROBAT roaster imagery"],
        },
        tone="Confident and grounded",
        audience={"age_range": "35-60", "gender": "mixed", "interests": ["Home espresso"]},
    )
    assert brand.visual_identity.mood[0].startswith("Warm, trustworthy")
