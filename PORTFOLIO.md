# Agentic Clinical Document Investigation Platform

## Overview

The Agentic Clinical Document Investigation Platform is an evidence-grounded AI system for investigating longitudinal clinical records.

Rather than asking an LLM to directly summarize a collection of documents, the platform separates the investigation process into structured stages:

**Evidence -> Claims -> Findings -> Validation -> Human Review -> Final Report**

The system analyzes clinical evidence across documents, reconstructs longitudinal timelines, evaluates medication information, identifies contradictions and missing follow-up, checks unsupported claims, and produces an auditable investigation report.

The project is designed as an engineering demonstration of reliable agentic AI for high-stakes document workflows rather than as a clinical diagnostic system.

---

## Problem

Clinical information is often distributed across admission notes, progress notes, laboratory reports, medication reconciliation records, discharge summaries, and follow-up documentation.

A conventional RAG pipeline can retrieve relevant text, but retrieval alone does not provide a structured mechanism for:

- reasoning across multiple documents;
- reconstructing longitudinal events;
- identifying conflicting medication information;
- distinguishing evidence from derived conclusions;
- detecting unsupported statements;
- validating findings before reporting them;
- escalating uncertain or high-risk findings for human review.

This project addresses those problems through a multi-stage investigation workflow.

---

## Architecture

The production workflow is implemented as an agentic state graph.

```text
Clinical Documents
       |
       v
Evidence Retrieval
       |
       v
Timeline Analysis
       |
       v
Medication Analysis
       |
       v
Contradiction Analysis
       |
       v
Missing Follow-Up Analysis
       |
       v
Unsupported Claim Analysis
       |
       v
Finding Synthesis
       |
       v
Validation
      / \
     /   \
 PASS   HUMAN REVIEW
     \   /
      \ /
       v
Final Investigation Report