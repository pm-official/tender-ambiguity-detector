# Licensing and attribution

This project ingests publicly hosted copies of Indian Standards (IS codes) and CPWD publications for academic research. The authors do not redistribute the source PDFs; the corpus at `standards/raw/` is gitignored and must be re-downloaded per environment.

## Indian Standards (BIS)

**Copyright.** Bureau of Indian Standards (BIS) retains copyright on all Indian Standards.

**Source we use.** Carl Malamud's `public.resource.org` project (mirror: `https://law.resource.org/pub/in/bis/`) publishes IS codes under a public-interest, research-access interpretation. When a document is unavailable from that mirror, we fall back to the Internet Archive (`archive.org`) mirror of the same file.

**Our use.** TAD reads the IS-code text at retrieval time to ground rewrites. No IS-code text is republished in the repository, the Streamlit app, the thesis, or any paper draft beyond short quotations for identification and citation. Every citation in a suggested rewrite points to a clause number that a user of the IS code can verify independently.

**Attribution.** Full attribution to:

- Carl Malamud / Public.Resource.Org — the mirror under which we access the codes.
- Bureau of Indian Standards — the issuing authority and copyright holder.

## CPWD publications

**Copyright.** Central Public Works Department, Government of India.

**Source we use.** `cpwd.gov.in/Publication/` for the Specifications 2019 volumes and the 2019 GCC; `ndmc.gov.in` mirror for the Works Manual 2019.

**Our use.** Same rules as IS codes — read at retrieval time, no republication, short quotations only for citation.

## Public-procurement tenders

Tender documents on `eprocure.gov.in` and `etender.cpwd.gov.in` are published by the issuing authority as part of a public procurement process and are public records by statute. When ingested into TAD, bidder-confidential content is never fetched (we only read the tender documents themselves, not submitted bids). Any personally identifying information in a downloaded tender is redacted before ingestion via a PyMuPDF blackout step; each redaction is logged to the tender's `manifest.yaml`.

## Fair-use statement

The use of IS-code and CPWD text in TAD is limited to (a) reading at retrieval time, (b) identifying the clause in a suggested rewrite by its number and a short quoted span, and (c) ingesting embeddings for similarity search. No derivative work reproduces the source documents in whole. This is consistent with Indian copyright law's research and educational exceptions (Copyright Act, 1957, §52(1)(a)).

## Contact

Research lead: Prakhar — M.Tech student, Civil Engineering, IIT Bombay. <sanjukharat90@gmail.com>.
