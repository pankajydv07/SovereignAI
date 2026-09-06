---
name: swaraj-domain
description: Industrial and PSU domain knowledge for SWARAJ - refinery inspection reports, approval notes, P&IDs, engineering calculations, maker-checker workflow, and Indian public-sector document conventions. Use whenever generating, parsing or reasoning about refinery or government office documents, or when deciding how a deliverable should be structured.
---

# SWARAJ domain knowledge

You are building software for **Mangalore Refinery and Petrochemicals Limited (MRPL)** and similar Indian PSUs, refineries and defence-linked manufacturing units. You do not natively know this domain, and plausible-sounding invention here is worse than useless — it produces documents that look right to you and are obviously wrong to an engineer.

**When you are unsure about a domain convention, ask. Do not guess.**

## Who uses this

- **Inspection Engineer** — reads scanned inspection reports, records findings
- **Deputy Manager / DGM (Mech or Process)** — prepares approval notes, checks subordinates' work
- **Design / Projects Engineer** — engineering calculations, P&ID review
- **IT / Security Officer** — owns the air gap, asks who accessed what

These are careful, accountable professionals. Their documents carry signatures and consequences.

## Key documents

### Approval note
The core PSU artefact. A formal internal document seeking sanction from a competent authority. Typical structure:

1. **Subject** — one line
2. **Reference** — prior correspondence, file numbers, previous approvals
3. **Background** — why this is being raised
4. **Observations / findings** — each traceable to a source
5. **Financial implication** — cost, budget head, whether provisioned
6. **Deviation** — any departure from standard practice, flagged explicitly
7. **Recommendation** — the specific sanction sought
8. **Approval ladder** — who prepares, who checks, who approves

Every organisation mandates its own format. **Load the org template; never invent the layout.**

### Inspection report
Field record of equipment condition. Contains asset tag, inspection date and method, thickness readings, observed defects, photographs, and non-conformances (NCRs). Frequently a **scan of a handwritten or printed form**, often poor quality.

### P&ID (Piping and Instrumentation Diagram)
Schematic showing equipment, piping, valves, and instrumentation with tag numbers. Highly confidential — it reveals plant configuration.

Instrument tags follow ISA-style patterns: letters for function, digits for loop. `FT-1702` is a flow transmitter on loop 1702; `PIC-3301` is a pressure indicating controller. Regex validation against the plant's own convention catches most OCR errors.

**What software can honestly do:** detect symbols, extract tags, inventory equipment, reconcile against a register, flag unreadable regions.
**What it cannot do:** determine which line connects to which valve, or whether a control loop is complete and safe. Never imply otherwise.

### Equipment register
The authoritative list of plant assets with tag numbers, specifications and inspection history. Used to reconcile what a drawing shows against what is recorded.

### SOP / manual
Standard Operating Procedure. Revision-controlled. **A superseded revision is dangerous to cite** — always check `effective_date` and `superseded_by`, and label any historical citation clearly.

## Maker–checker

Nothing is issued on one person's authority. A **maker** prepares; a **checker** verifies and signs. This is not bureaucracy to be optimised away — it is the accountability model, and software that ignores it will not be adopted.

Implications for the product:
- Every deliverable pauses for a named human approver
- The reviewer's identity, timestamp and any edits are part of the record
- Rejection requires a stated reason
- Approval is **blocked** while any low-confidence extracted value is unverified

## Engineering calculations

Must show their work: given values with sources, the governing standard clause, the formula, substitution, intermediate results, and the final answer with units.

Common references: IS codes (Indian Standards), ASME (pressure vessels and piping), API (petroleum industry), OISD (oil industry safety). **Cite the clause from the knowledge base; never recall a clause number from memory** — a wrong clause number in an engineering note is a serious error.

Never generate a number as text. Compute it as executed code with assertions, and render the derivation.

## Language

Internal correspondence is frequently Hindi or bilingual, especially older SOPs and letters. Handle Devanagari and mixed-script documents. Government correspondence has its own formal register in both languages.

## Confidentiality classification

Documents carry levels — Public, Internal, Confidential, Restricted. Retrieval must be filtered by the requesting user's role **before** results reach the model. Getting this wrong is a serious incident, not a bug.

## Tone for generated documents

Formal, impersonal, precise. Third person. No marketing language, no enthusiasm, no first-person narration. "It is recommended that…" not "I think we should…".

Every generated file carries a provenance footer naming the models used, the sources cited, the extraction confidence, and that it requires approval by a competent authority. A document that cannot be distinguished from a human-signed note is a compliance problem, not a feature.
