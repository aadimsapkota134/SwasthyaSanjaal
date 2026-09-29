# SwasthyaSanjaal
# Nepali Clinical Language Layer

A clinical NLP system for converting messy Nepali health information into structured, reviewable, and interoperable clinical data.

A prescription may arrive as a handwritten photograph. A laboratory report may be a Devanagari PDF. A community-health assessment may exist only as spoken Nepali. The problem is not simply storing these records. The problem is converting them into reliable clinical information that a digital health system can actually use.

This project builds the language layer between those real-world inputs and a structured health record.

---

## The Problem

Nepal does not have a shortage of health records. It has a problem with what those records contain and how they move.

Health information commonly begins as:

* handwritten prescriptions
* scanned or photographed reports
* Devanagari documents
* paper notes
* Romanized Nepali
* code-mixed Nepali-English
* spoken assessments

These formats may contain clinically useful information, but the information is rarely structured enough to be searched, connected with previous visits, validated, or reused across health systems.

The difficult part begins before an electronic health record exists.

A sentence such as:

> `हिजोबाट तातो छ जस्तो छ, आज झन् बढेको।`

may need to become something like:

```json
{
  "symptom": "fever",
  "duration": "2 days",
  "severity": "increasing"
}
```

The conversion becomes more difficult when the same concept appears through different forms:

```text
ज्वरो
ज्वरो छ
मियादी जोरो
miyadi joro
typhoid
ज्वरो छैन
Glycomet
```

These are not merely spelling differences. A system may need to recognize colloquial language, Romanized text, negation, medicine brands, OCR errors, and conversational descriptions while preserving the original meaning.

A single missed negation or incorrectly normalized medicine can produce a structurally valid record containing the wrong clinical concept.

---

## What This Project Does

This project provides a **Nepali Clinical Language Layer** between unstructured health inputs and structured clinical records.

```text
                 REAL-WORLD INPUT
                        |
       +----------------+----------------+
       |                |                |
   Photograph         Document         Speech
       |                |                |
       +----------------+----------------+
                        |
                  AI / NLP Layer
                        |
              Transcription / ASR
                        |
                 Clinical Lexicon
                        |
          Exact → Fuzzy → AI Matching
                        |
              Clinical Extraction
                        |
              Field-level Uncertainty
                        |
                  Confirmation
                        |
               Structured Record
                        |
          +-------------+-------------+
          |                           |
       Patient                   Community
     Health Record                Health Use
```

The core transformation is:

**messy Nepali clinical language in → structured and reviewable health information out**

---

## Core Components

### 1. Nepali Clinical Lexicon

The foundation of the system is a controlled clinical lexicon.

Each concept contains the different ways it may appear in real-world Nepali health communication:

```text
Concept ID
├── Devanagari forms
├── Romanized forms
├── Colloquial forms
├── Code-mixed forms
├── Brand → generic medicine mappings
├── Negation markers
└── Clinical metadata
```

Example:

```json
{
  "concept_id": "SYM_FEVER",
  "canonical": "Fever",
  "nepali": ["ज्वरो", "ज्वरो आउनु", "तातो हुनु"],
  "romanized": ["jvaro", "jwaro", "tato hunu"]
}
```

The first version intentionally contains a limited number of clinician-reviewed concepts rather than attempting to cover all of medicine.

The lexicon acts as a boundary for the AI system: models can select an approved concept or return `UNKNOWN`, but they cannot silently invent new clinical terminology.

---

### 2. Multi-stage Concept Matching

Incoming clinical language is resolved using three stages.

#### Exact matching

Known forms are matched directly against the lexicon.

```text
"ज्वरो" → SYM_FEVER
```

#### Fuzzy matching

Spelling variation, OCR errors, and minor typos are handled without requiring an LLM.

```text
"जवरो" → SYM_FEVER
"jwaro" → SYM_FEVER
```

#### Constrained AI matching

When deterministic methods fail, an open-source language model receives:

1. the unresolved term
2. candidate concepts from the lexicon
3. the allowed output format

It must return:

```text
EXISTING_CONCEPT_ID
```

or:

```text
UNKNOWN
```

The model is therefore performing constrained normalization rather than open-ended medical generation.

---

### 3. Clinical Information Extraction

Normalized concepts are converted into a fixed clinical schema.

Example:

```text
दुई दिनदेखि ज्वरो छ, हिजोदेखि धेरै बढेको
```

may become:

```json
{
  "symptom": {
    "value": "fever",
    "confidence": 0.96
  },
  "duration": {
    "value": "2 days",
    "confidence": 0.91
  },
  "severity": {
    "value": "increasing",
    "confidence": 0.78
  }
}
```

The system separates uncertainty by field.

A record can therefore be:

```text
Symptom     → certain
Duration    → certain
Severity    → uncertain
```

rather than assigning one confidence score to the entire document.

---

### 4. Negation Handling

Clinical negation is treated as structured information rather than ordinary text.

For example:

```text
ज्वरो छैन
```

must represent:

```json
{
  "concept": "fever",
  "negated": true
}
```

rather than:

```json
{
  "concept": "fever",
  "negated": false
}
```

Preserving negation is essential because losing a single word can invert the meaning of the clinical statement.

---

### 5. Medicine Normalization

Patients and documents may refer to medicines by different names.

```text
Glycomet → Metformin
Ecosprin → Aspirin
```

The system maintains controlled brand-to-generic mappings rather than allowing an LLM to freely infer medication identities.

The original text remains available alongside the normalized concept.

---

### 6. Document Understanding

A photograph or scan of a prescription or laboratory report is processed by an open-source vision-language model.

The model is instructed to transcribe what is visibly present.

Unreadable text must be represented as:

```text
[?]
```

rather than guessed.

The system intentionally separates:

```text
What does the document say?
```

from:

```text
What does the document mean clinically?
```

This reduces the risk of an AI model silently converting uncertain handwriting into a confident clinical fact.

---

### 7. Nepali Speech Pipeline

For community-health use, spoken Nepali can enter the same downstream pipeline.

```text
FCHV speech
    ↓
Nepali ASR
    ↓
Transcript
    ↓
Clinical normalization
    ↓
Structured fields
    ↓
Uncertainty detection
    ↓
Confirmation
```

The project treats clinical speech as a separate evaluation problem because general Nepali ASR may not adequately represent:

* medicine names
* local pronunciation
* code-switching
* conversational speech
* background noise
* community-health terminology

A poor transcription should therefore surface as uncertainty instead of becoming a hidden record error.

---

## Confirmation Layer

Uncertainty is not discarded.

When the system is unsure about a field, it asks for confirmation.

Example:

> `मैले दुई दिनदेखि ज्वरो आएको भनेर बुझेँ। हो?`

Only the confirmed interpretation is passed to the next stage.

This creates a human-in-the-loop workflow:

```text
AI extraction
      ↓
Confidence assessment
      ↓
      ├── High confidence → accepted
      |
      └── Uncertain → human confirmation
                           ↓
                       confirmed value
```

The goal is not to make the model appear certain.

The goal is to make uncertainty visible before it becomes part of the health record.

---

## Two Intended Use Paths

### Patient Path

A patient can provide a photograph or scan of a health document.

```text
Prescription / Lab Report
          ↓
Document Understanding
          ↓
Clinical Normalization
          ↓
Structured Fields
          ↓
Confirmation
          ↓
Portable Health Record
```

The patient-facing interface also provides:

* plain-Nepali explanations
* read-aloud output
* original-source visibility
* structured clinical fields
* uncertainty and confirmation status

The explanation is grounded in the extracted record rather than generated as a new medical opinion.

---

### FCHV Path

A Female Community Health Volunteer can provide a spoken Nepali assessment.

```text
Spoken assessment
        ↓
       ASR
        ↓
Clinical normalization
        ↓
Structured protocol fields
        ↓
Confirmation
        ↓
Assessment / protocol output
        ↓
Nepali voice response
```

The written/document pipeline is the first implementation target because it is easier to collect, test, and evaluate within the project timeline.

Speech uses the same downstream normalization and safety architecture.

---

## AI Architecture

AI is used for specific conversion tasks rather than unrestricted medical decision-making.

| Component              | AI Role                                       | Output Boundary                 |
| ---------------------- | --------------------------------------------- | ------------------------------- |
| Document understanding | Read photographed/scanned text                | Transcription                   |
| Clinical matching      | Resolve unfamiliar expressions                | Existing concept ID / `UNKNOWN` |
| Information extraction | Fill fixed clinical fields                    | Predefined schema               |
| ASR                    | Convert Nepali speech to text                 | Transcript                      |
| Explanation            | Express extracted information in plain Nepali | Source-grounded explanation     |

The system does **not** ask a general model to:

* invent diagnoses
* create new clinical concepts
* determine treatment independently
* silently correct uncertain source text
* replace clinician review for ambiguous information

---

## Safety and Reliability Principles

### Controlled vocabulary

AI outputs are constrained by the clinical lexicon.

### Source preservation

Original text and normalized concepts are stored separately.

```text
Original:
"मियादी जोरो"

Normalized:
Concept ID → ...
```

### Explicit uncertainty

Every extracted field can carry its own uncertainty state.

### `UNKNOWN` is valid

When the system cannot resolve a term safely, it returns:

```text
UNKNOWN
```

instead of forcing a prediction.

### Human confirmation

Uncertain information can require confirmation before becoming part of the structured record.

### Provenance

Each normalized value records how it was obtained:

```text
LEXICON
FUZZY_MATCH
LLM
OCR / VLM
ASR
HUMAN_CONFIRMED
```

This makes downstream auditing possible.

---

## Example

Input:

```text
दुई दिनदेखि ज्वरो छ।
ज्वरो हिजोभन्दा धेरै बढेको छ।
```

Possible structured output:

```json
{
  "findings": [
    {
      "concept_id": "SYM_FEVER",
      "label": "Fever",
      "negated": false,
      "duration": "2 days",
      "severity": "increasing",
      "source": "patient_text",
      "resolution_method": "LEXICON",
      "confirmation_required": false
    }
  ]
}
```

Negated input:

```text
ज्वरो छैन।
```

becomes:

```json
{
  "concept_id": "SYM_FEVER",
  "negated": true
}
```

Uncertain input may become:

```json
{
  "concept_id": "UNKNOWN",
  "source_text": "मियादी जोरो",
  "resolution_method": "LLM",
  "confirmation_required": true
}
```

The system does not hide the uncertainty.

---

## Why a Clinical Lexicon?

General Nepali NLP resources are useful for language understanding, but clinical normalization requires a more specific vocabulary.

Existing resources can provide:

* general Nepali language data
* news and web text
* pretrained Nepali language models
* medical terminology references

But a clinical system additionally needs mappings between:

```text
Devanagari
      ↕
Romanized Nepali
      ↕
Colloquial expressions
      ↕
Code-mixed language
      ↕
Brand names
      ↕
Clinical concepts
      ↕
Structured fields
```

A dictionary tells a person what a term means.

A machine-readable clinical lexicon tells a system which approved concept a real-world expression refers to and how that concept should be represented downstream.

---

## Research Questions

The project can be evaluated around several concrete questions:

1. How accurately can Nepali clinical expressions be normalized into a controlled clinical vocabulary?

2. How much do exact matching, fuzzy matching, and constrained LLM matching contribute individually?

3. How reliably can the system preserve clinical negation?

4. How accurately can medicine brands and common Nepali expressions be mapped to generic concepts?

5. How well can an open-source vision-language model transcribe handwritten or scanned Nepali clinical documents without introducing unsupported text?

6. How well does Nepali clinical speech recognition perform compared with general-domain Nepali ASR?

7. Does field-level uncertainty and confirmation reduce downstream extraction errors?

8. How does performance change across Devanagari, Romanized Nepali, code-mixed Nepali-English, and noisy inputs?

---

## Evaluation

The system can be evaluated at multiple stages rather than using only end-to-end accuracy.

### Lexicon matching

```text
Exact Match Accuracy
Fuzzy Match Accuracy
Unknown Detection
Brand → Generic Accuracy
```

### Clinical extraction

```text
Precision
Recall
F1
Negation Accuracy
Duration Extraction Accuracy
Severity Extraction Accuracy
```

### Document understanding

```text
Character Error Rate
Word Error Rate
Clinical Field Accuracy
Unsupported Text Rate
```

### Speech

```text
Word Error Rate
Clinical Term Error Rate
Concept Normalization Accuracy
```

### Safety / uncertainty

```text
False Acceptance Rate
Unknown Rate
Confirmation Rate
Post-confirmation Accuracy
```

The most important measurement is not simply whether the model generated a plausible answer.

It is whether the final confirmed structured record represents the original source correctly.

---

## Initial Scope

The first version is intentionally narrow.

### Included

* a clinician-reviewed clinical lexicon
* a few hundred high-value concepts
* Nepali Devanagari text
* Romanized Nepali
* selected colloquial expressions
* selected code-mixed forms
* medicine normalization
* negation handling
* basic clinical field extraction
* document transcription
* field-level uncertainty
* human confirmation
* structured JSON output

### Planned extensions

* Nepali speech input
* broader clinical terminology
* additional medicine mappings
* FHIR-compatible health-record representation
* longitudinal patient records
* FCHV-specific protocols
* larger evaluation datasets

The project does not attempt to build a complete hospital information system.

Its primary research and engineering problem is the language conversion layer.

---

## Example End-to-End Flow

```text
                 ┌──────────────────────┐
                 │  Prescription Image  │
                 └──────────┬───────────┘
                            ↓
                 ┌──────────────────────┐
                 │ Document Transcriber │
                 └──────────┬───────────┘
                            ↓
                 ┌──────────────────────┐
                 │   Raw Nepali Text    │
                 └──────────┬───────────┘
                            ↓
                 ┌──────────────────────┐
                 │ Clinical Lexicon     │
                 │ Exact Match          │
                 └──────────┬───────────┘
                            ↓
                    not resolved?
                            ↓
                 ┌──────────────────────┐
                 │   Fuzzy Matching     │
                 └──────────┬───────────┘
                            ↓
                    not resolved?
                            ↓
                 ┌──────────────────────┐
                 │ Constrained LLM      │
                 │ ID / UNKNOWN         │
                 └──────────┬───────────┘
                            ↓
                 ┌──────────────────────┐
                 │ Clinical Extraction  │
                 └──────────┬───────────┘
                            ↓
                 ┌──────────────────────┐
                 │ Field-Level          │
                 │ Uncertainty          │
                 └──────────┬───────────┘
                            ↓
                    needs confirmation?
                      /             \
                    yes             no
                    ↓                ↓
            Human confirmation      Accept
                    \                /
                     \              /
                      ↓            ↓
                 ┌──────────────────────┐
                 │ Structured Record    │
                 └──────────────────────┘
```

---
---

## Intended Output

The end product is not simply an OCR tool, chatbot, or medical-record database.

It is a **clinical language conversion layer** that transforms:

```text
Photographs
Scans
Handwritten notes
Nepali text
Romanized Nepali
Code-mixed language
Speech
```

into:

```text
Normalized clinical concepts
Structured fields
Negation-aware findings
Medicine mappings
Field-level confidence
Source provenance
Human-confirmed health information
```

The central deliverable is therefore:

**unstructured Nepali clinical input → structured, reviewable, reusable health information**
