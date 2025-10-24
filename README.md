# MBSE Maturity Evaluation Platform - Project Overview

> **Problem Statement:** The US government and civilian companies are using Model Based Systems Engineering (MBSE) to deliver digital products based on contract requirements and needs. These MBSE models range from very primitive to highly complex. Predictive AI can be trained to analyze existing MBSE models and determine the readiness levels of each model for operational use and applicability for test, simulation, technology transfers, etc.

> **Sponsor Suggestion:** Provide an LLM-driven analysis of MBSE models and report model “readiness” across usability dimensions (requirements traceability, SSOT, simulation, what-if, tech change, ops degradation, cyber, etc.), plus an MBSE-specific readiness ladder and recommendations per model.

## 1) Purpose

Build a backend + UI that ingests MBSE model exports, evaluates maturity across multiple criteria, and returns structured results for decision support.

## 2) What the sponsor asked for (scope)

- LLM-assisted analysis of MBSE models supplied by SME.
- Assess: technical fidelity vs real system, requirements/use as SSOT, simulation/what-if, technology updates, design/architecture changes, ops degradation realism, cyber risks.
- Output: recommendations per model and a defined MBSE Readiness Ladder (similar to TRL) specific to models.
- Deliverables: IMS with milestones, PDR/CDR, MVP, mid-term report, final demo, lessons learned.

## 3) Our approach (minimum to full)

**MVP path**

1. **Input adapters**: parse Sparx/Cameo XML to a neutral Graph-IR.
2. **Criteria engine**: run maturity criteria per ladder rung; produce counts, pass/fail, and explanations.
3. **Evidence pack**: structured JSON used by both UI and LLM.
4. **RAG/LLM**: retrieve evidence and references, generate validated summaries and recommendations as strict JSON.
5. **REST API**: TBD.

**Architecture, simplified**

- Frontend: React + TypeScript.
- Backend: Python REST.
- Storage: per-run temporary store.
- LLM: retrieval-augmented explanations; validator enforces IDs/citations before UI display.

## 4) Readiness Ladder (draft)

- **MML-1 Foundation**: model loads; unique IDs; basic structure.
- **MML-2 Structure**: typed elements; relation integrity; basic coverage.
- **MML-3 Traceability**: requirements links; transitive traces; gap analysis.
- **MML-4 Analysis**: parameters/constraints; simulation hooks; change impacts; basic cyber findings.  
  (Names and gates will finalize after sponsor reviews.)

## 5) Milestones (aligning to sponsor deliverables)

- **Kickoff + IMS** with POAM and budget checkpoints.
- **PDR**: working ingest + first criteria + sample reports.
- **CDR**: validated ladder, expanded criteria, RAG in place.
- **MVP**: end-to-end demo on sponsor model(s).
- **Final**: full report, recommendations per model, lessons learned.
