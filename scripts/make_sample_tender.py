"""Generate a synthetic demo tender PDF containing known ambiguities of all 8 categories.

This is pure demo material — not a real tender. It gives a determinate ground-truth for
showcasing the pipeline when a real Indian government tender PDF is not on hand.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import fitz  # pymupdf

SAMPLE_TEXT = r"""TENDER DOCUMENT
Construction of Overhead Reservoir and Allied Works
Tender No. CPWD/OHSR/2026/001
Estimated Cost: Rs. 4.5 crore
Issued by: Central Public Works Department (synthetic sample for TAD demo)

SECTION 1 — GENERAL

1.1 Scope of Work
The Contractor shall execute the construction of an overhead storage reservoir of suitable
capacity with good quality concrete and standard finishing as per the relevant IS code.
The works shall be carried out in accordance with the attached drawing.

1.2 Priority of Documents
In case of conflict between the documents, the Bill of Quantities (BOQ) shall prevail over
the Drawings and Specifications.

SECTION 2 — MATERIALS

2.1 Concrete
The Contractor shall use suitable aggregate for the subbase and approved make cement
for all reinforced concrete work. The concrete quantity for the overhead reservoir shall
be 1200 cu.m as per the BOQ.

2.2 Reinforcement
Reinforcement steel shall be of standard quality conforming to the requirements specified
elsewhere. The total quantity of steel reinforcement shall be 180 tonnes.

2.3 Primer and Sealant
Apply primer coat on the cleaned surface prior to painting. Seal all construction joints
with sealant of approved type.

SECTION 3 — EXECUTION

3.1 Drainage and Earthworks
The Contractor shall provide adequate drainage around the foundation and maintain
reasonable tolerance on all excavation dimensions.

3.2 Access and Coordination
The Contractor shall have access to site during daylight hours. The Contractor shall
coordinate with the supplier. They shall provide all materials required for the works.

3.3 Finishing
Provide fair finish on all exposed concrete surfaces. The surface shall be level to
satisfactory standards.

SECTION 4 — QUANTITIES SUMMARY

4.1 The total estimated cost of the project is Rs. 4.8 crore.
4.2 The concrete quantity for the overhead reservoir in the Specifications is 1500 cu.m.
4.3 All works shall conform to the particular specifications issued with this tender.

SECTION 5 — TESTING AND ACCEPTANCE

5.1 The Engineer shall confirm with the Contractor. He shall approve the design drawings
before the commencement of any casting work.

5.2 Any works found unsatisfactory shall be rejected. Reasonable care shall be taken in
stacking and storage of materials.

5.3 The block work shall be of fair quality and level throughout.
"""


def write_pdf(path: Path, text: str) -> None:
    doc = fitz.open()
    # Two-page layout
    parts = text.split("SECTION 3")
    for chunk in [parts[0], "SECTION 3" + parts[1]] if len(parts) == 2 else [text]:
        page = doc.new_page(width=595, height=842)  # A4
        rect = fitz.Rect(50, 50, 545, 790)
        page.insert_textbox(rect, chunk, fontsize=10, fontname="helv")
    doc.save(str(path))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="data/sample_tenders/synthetic_ohsr_tender.pdf")
    a = p.parse_args()
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    write_pdf(out, SAMPLE_TEXT)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
