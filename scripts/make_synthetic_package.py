"""Generate a synthetic multi-document tender package for the Prompt-5 demo.

Emits six PDFs under tenders/real/sample_01_synthetic_cpwd/raw/ plus a manifest.yaml.
Labelled synthetic: true — not to be used for empirical results.

This mirrors the shape of a real CPWD tender package: NIT, GCC excerpts, Additional Conditions,
Technical Specifications, BOQ, and an Addendum. Known ambiguities across each of the 8 categories
are seeded so Stage-1 detection has real targets.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import fitz  # pymupdf
import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tenders" / "real" / "sample_01_synthetic_cpwd"

DOCS = {
    "NIT_OHSR_2026.pdf": {
        "role": "NIT",
        "title": "Notice Inviting e-Tender",
        "body": """
NOTICE INVITING e-TENDER
(Synthetic sample prepared for TAD demo — not a real CPWD notice)

Tender No. CPWD/Demo/OHSR/2026/001
Name of work: Construction of Overhead Storage Reservoir and allied civil works for a
government residential colony (synthetic demonstration tender).

Estimated cost: Rs. 4.50 crore (tentative — refer to BOQ).
Period of completion: 12 months from date of start.
Earnest money: Rs. 9,00,000 (deposited electronically as per standard procedure).

Eligibility: The Contractor shall have completed at least three similar works of suitable
magnitude during the last seven years. Details to be furnished on the latest schedule of rates.

Submission: online on the e-procurement portal as per the relevant guidelines in force.
""",
    },
    "GCC_Excerpt.pdf": {
        "role": "GCC",
        "title": "General Conditions of Contract — Excerpts",
        "body": """
GENERAL CONDITIONS OF CONTRACT (Excerpts)
(Synthetic sample prepared for TAD demo)

1. PRIORITY OF DOCUMENTS
In case of conflict between the documents forming part of the contract, the Bill of
Quantities (BOQ) shall prevail over the Drawings and the Specifications.
In case of any ambiguity in documents, the decision of the Engineer-in-Charge shall be
final and binding on both parties.

2. SCOPE OF WORK
The Contractor shall execute and complete the works as described in the Specifications and
shown on the attached drawings.

3. MATERIALS AND WORKMANSHIP
All materials shall conform to the applicable IS standards. The works shall be executed in a
workmanlike manner and to the satisfaction of the Engineer.

4. DEFECT LIABILITY
The Contractor shall be responsible for defects discovered within the defect liability
period, being such period as specified elsewhere in the contract.
""",
    },
    "Additional_Conditions.pdf": {
        "role": "Additional Conditions",
        "title": "Additional Conditions of Contract",
        "body": """
ADDITIONAL CONDITIONS OF CONTRACT
(Synthetic sample prepared for TAD demo)

1. SITE ACCESS
The Contractor shall have access to site during working hours. The Contractor shall
coordinate with the supplier. They shall provide all materials required for the works.

2. DRAINAGE
Adequate drainage shall be provided around all foundations. Reasonable tolerance shall be
maintained on excavation dimensions.

3. QUALITY
Contractor shall use suitable aggregate for the subbase and approved make cement for all
reinforced concrete work. The finishing shall be of fair quality and level throughout.

4. ESTIMATED COST CLAUSE
Notwithstanding any other provision, the estimated cost is Rs. 4.80 crore as per these
Additional Conditions (subject to BOQ rates actually applied).
""",
    },
    "Technical_Specifications.pdf": {
        "role": "Technical Specifications",
        "title": "Particular Technical Specifications",
        "body": """
PARTICULAR TECHNICAL SPECIFICATIONS
(Synthetic sample prepared for TAD demo)

1. CONCRETE
All reinforced concrete shall be of grade M25 conforming to IS 456:2000. Cement content and
water-cement ratio shall be as per IS 10262. Coarse aggregate shall conform to IS 383.

2. STEEL REINFORCEMENT
High strength deformed bars conforming to IS 1786:2008 (Fe 500 grade). Total quantity of
steel reinforcement: 180 tonnes.

3. PRIMER AND PAINTING
Apply primer coat on the cleaned surface prior to painting. Seal all construction joints
with sealant of approved type.

4. WATERPROOFING
Provide waterproofing on the roof slab as per the relevant IS code. Refer to the attached
drawing for details.

5. CONCRETE QUANTITY
Total concrete quantity for the overhead reservoir shall be 1500 cu.m as per these
Specifications. (Note: BOQ indicates 1200 cu.m — to be reconciled.)

6. FINISH
All exposed concrete surfaces shall be given a fair finish.
""",
    },
    "BOQ_Schedule_A.pdf": {
        "role": "BOQ",
        "title": "Bill of Quantities — Schedule A",
        "body": """
BILL OF QUANTITIES — SCHEDULE A
(Synthetic sample prepared for TAD demo)

Item  Description                                     Unit    Qty       Rate (Rs.)
----  ----------------------------------------------  ------  --------  ----------
1     Excavation in ordinary soil                     cu.m    820       550
2     PCC 1:4:8 for foundation                        cu.m    145       5800
3     Reinforced cement concrete M25                  cu.m    1200      9500
4     Steel reinforcement Fe500 (IS 1786)             tonne   180       78000
5     Brickwork in CM 1:6                             cu.m    260       8600
6     Plastering and finishing                        sq.m    5100      320
7     Primer and painting (as per Specifications)     sq.m    5100      210

TOTAL (tentative)                                                       Rs. 4,48,00,000

Note: All quantities are approximate and to be measured on actuals. Total estimated cost
declared at NIT stage: Rs. 4.50 crore. See also the Summary in the Technical Specifications
which states the cost as Rs. 4.80 crore.
""",
    },
    "Addendum_01.pdf": {
        "role": "Addendum",
        "title": "Corrigendum No. 1",
        "body": """
CORRIGENDUM No. 1
(Synthetic sample prepared for TAD demo)

In reference to Tender No. CPWD/Demo/OHSR/2026/001:

1. Clause on site access in the Additional Conditions is clarified: physical access to the
site shall be between 06:00 and 18:00 hours on working days only.

2. Cement grade: The cement shall be Ordinary Portland Cement, 43 Grade or 53 Grade
conforming to IS 269:2015 or IS 12269:2013. (This supersedes any ambiguous earlier mention.)

3. All other terms and conditions of the original tender remain unchanged.
""",
    },
}


def write_pdf(path: Path, title: str, body: str) -> int:
    doc = fitz.open()
    text = f"{title}\n\n{body.strip()}\n"
    # split into pages of ~1800 chars each so we get multi-page docs
    chunk = 1800
    for i in range(0, len(text), chunk):
        page = doc.new_page(width=595, height=842)
        rect = fitz.Rect(50, 50, 545, 790)
        page.insert_textbox(rect, text[i : i + chunk], fontsize=10, fontname="helv")
    n = len(doc)
    doc.save(str(path))
    doc.close()
    return n


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(OUT))
    args = p.parse_args()
    pkg = Path(args.out)
    (pkg / "raw").mkdir(parents=True, exist_ok=True)

    docs_meta = []
    for fname, spec in DOCS.items():
        pages = write_pdf(pkg / "raw" / fname, spec["title"], spec["body"])
        docs_meta.append({
            "filename": fname,
            "doc_role": spec["role"],
            "pages": pages,
            "page_range": None,
            "analyse": True,
        })
        print(f"wrote {fname} ({pages} pages)")

    manifest = {
        "package_id": "sample_01_synthetic_cpwd",
        "short_name": "sample_01_synthetic_cpwd",
        "source_portal": "SYNTHETIC",
        "source_url": None,
        "title": "Construction of Overhead Storage Reservoir (synthetic demo)",
        "value_crore": 4.5,
        "opened_on": "2026-03-01",
        "synthetic": True,
        "note": "Prepared for TAD demo. Not real CPWD content. Do not use for empirical results.",
        "documents": docs_meta,
    }
    (pkg / "manifest.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    print(f"wrote {pkg / 'manifest.yaml'}")


if __name__ == "__main__":
    main()
