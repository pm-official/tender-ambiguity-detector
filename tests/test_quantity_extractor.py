from src.quantity_extractor import extract


def test_concrete_grade():
    q = extract("Reinforced concrete of grade M25 shall be used throughout.")
    assert any(m.name == "concrete_grade" and m.value == "M25" for m in q)


def test_steel_grade():
    q = extract("Use Fe500 steel reinforcement bars conforming to IS 1786.")
    assert any(m.name == "steel_grade" and m.value == "FE500" for m in q)


def test_crore_amount():
    q = extract("Estimated cost Rs. 4.50 crore.")
    assert any(m.name == "amount_crore_rs" and float(m.value) == 4.5 for m in q)


def test_volume_quantity_with_hint():
    q = extract("Total concrete quantity for the overhead reservoir is 1500 cu.m.")
    names = {m.name for m in q}
    assert any("concrete_volume" in n for n in names)


def test_tolerance_mm():
    q = extract("Tolerance on dimension shall be +/- 5 mm.")
    assert any(m.name == "tolerance_mm" and float(m.value) == 5 for m in q)


def test_days_and_strength():
    q = extract("28 days cube strength shall be at least 25 MPa.")
    assert any(m.name == "age_days" and int(m.value) == 28 for m in q)
    assert any(m.name == "strength_MPa" and float(m.value) == 25 for m in q)
