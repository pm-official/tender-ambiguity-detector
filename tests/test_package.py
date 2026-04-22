from src.pipeline import _auto_document_type


def test_auto_document_type_heuristics():
    cases = {
        "GCC_CPWD_2020.pdf": "GCC",
        "NIT_no_42.pdf": "NIT",
        "BOQ_Schedule_A.pdf": "BOQ",
        "corrigendum_01.pdf": "Addendum",
        "drawing_arch_04.pdf": "Drawing",
        "technical_specifications.pdf": "Technical Specifications",
        "particular_specs.pdf": "Technical Specifications",
        "additional_conditions.pdf": "Additional Conditions",
        "conditions_of_contract.pdf": "Conditions of Contract",
        "photos_site.pdf": "Other",
    }
    for fname, expected in cases.items():
        assert _auto_document_type(fname) == expected, f"{fname} -> expected {expected}"


def test_tender_package_schema_roundtrip():
    from src.schemas import PackageDocument, TenderPackage

    d = PackageDocument(doc_id="d1", filename="GCC.pdf", document_type="GCC", num_pages=10)
    pkg = TenderPackage(package_id="pkg_abc", documents=[d])
    ser = pkg.model_dump()
    back = TenderPackage.model_validate(ser)
    assert back.package_id == "pkg_abc"
    assert back.documents[0].document_type == "GCC"
