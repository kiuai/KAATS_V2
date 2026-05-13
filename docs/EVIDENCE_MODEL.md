# KAATS — Evidence Model

Version: 1.0 | Status: Authoritative

---

## 1. Overview

When the `ExecutionAgent` runs a test script, it captures a screenshot after every step. These screenshots are the primary evidence record. Each screenshot is:

1. Captured by Playwright as a raw PNG
2. Annotated using Pillow (step number, description, pass/fail badge)
3. Uploaded to Azure Blob Storage
4. Linked to a `TestStepResult` record in Azure SQL
5. Bundled at run completion into a SHA-256 integrity-chained PDF report

---

## 2. Blob Storage Layout

```
kaats-evidence/
└── tenant-{company_id}/
    └── evidence/
        └── {execution_id}/
            ├── step-001-navigate.png         ← raw capture (optional, not exposed)
            ├── step-001-navigate-annotated.png  ← annotated screenshot
            ├── step-002-fill-annotated.png
            ├── ...
            ├── manifest.json                 ← evidence manifest
            └── report.pdf                    ← final PDF evidence report
```

Only annotated PNGs and the PDF are exposed to users. Raw captures are retained for 7 days and then deleted by a Blob lifecycle policy.

---

## 3. Screenshot Capture

The `ExecutionAgent` calls `take_screenshot` after every step action:

```
1. Playwright: page.screenshot(full_page=False) → raw bytes
2. Upload raw bytes to Blob: step-{NNN}-{action}-raw.png
3. Download raw bytes from Blob (or use in-memory buffer)
4. Pillow: annotate image → annotated bytes
5. Upload annotated bytes: step-{NNN}-{action}-annotated.png
6. Compute SHA-256(annotated bytes)
7. INSERT evidence_screenshots record (blob_path, sha256, step_number)
```

---

## 4. Pillow Annotation Specification

Every annotated screenshot receives three overlays:

### 4.1 Step Badge (top-left)
- **Background**: semi-transparent black rectangle (80% opacity)
- **Text**: `STEP {step_number}` in white, bold, 18pt
- **Size**: auto-fitted to text width + 20px padding

### 4.2 Description Banner (bottom)
- **Background**: full-width semi-transparent band (75% opacity)
  - Colour: green (`#22c55e`) if passed, red (`#ef4444`) if failed, yellow (`#f59e0b`) if skipped
- **Text**: step description (truncated at 120 chars), white, 14pt

### 4.3 Status Icon (top-right)
- **Passed**: green circle with white ✓
- **Failed**: red circle with white ✕
- **Skipped**: grey circle with white —

### Reference Geometry (1920×1080 viewport)

| Element | Position | Size |
|---|---|---|
| Step badge background | (10, 10) | auto |
| Step badge text | (20, 15) | — |
| Status icon | (width-50, 10) | 40×40 |
| Bottom banner | (0, height-50) | width×50 |
| Description text | (10, height-38) | — |

For viewports with different resolutions, all dimensions are scaled proportionally by `min(width/1920, height/1080)`.

---

## 5. Manifest JSON

A `manifest.json` file is written to the execution's Blob directory at run completion.

```json
{
  "schema_version": "1.0",
  "execution_id": "uuid",
  "system_id": "uuid",
  "company_id": "uuid",
  "script_title": "Login Flow — Happy Path",
  "started_at": "2026-05-13T10:00:00Z",
  "completed_at": "2026-05-13T10:12:34Z",
  "duration_seconds": 754,
  "status": "failed",
  "passed_count": 8,
  "failed_count": 1,
  "skipped_count": 0,
  "steps": [
    {
      "step_number": 1,
      "action": "navigate",
      "description": "Navigate to the application login page",
      "status": "passed",
      "annotated_blob": "step-001-navigate-annotated.png",
      "sha256": "a3f1c2...",
      "captured_at": "2026-05-13T10:00:05Z",
      "duration_ms": 823
    },
    {
      "step_number": 2,
      "action": "fill",
      "description": "Enter username in the username field",
      "status": "passed",
      "annotated_blob": "step-002-fill-annotated.png",
      "sha256": "b7e3d4...",
      "captured_at": "2026-05-13T10:00:09Z",
      "duration_ms": 312
    }
  ],
  "integrity": {
    "manifest_sha256": "c9f2a1...",
    "chain": [
      { "step": 1, "sha256": "a3f1c2..." },
      { "step": 2, "sha256": "b7e3d4..." }
    ]
  }
}
```

---

## 6. SHA-256 Integrity Chain

The integrity chain provides tamper-evidence for the screenshot record.

### Chain Construction

```
H(step_1) = SHA-256(annotated_step_1.png)
H(step_2) = SHA-256(annotated_step_2.png)
...
H(step_n) = SHA-256(annotated_step_n.png)

chain_hash = SHA-256(H(step_1) || H(step_2) || ... || H(step_n))
manifest_sha256 = SHA-256(manifest_json_bytes_with_chain_hash)
```

The `chain_hash` is embedded in `manifest.integrity.chain`. The final `manifest_sha256` is stored in `agent_runs.evidence_integrity_hash`.

### Verification

`POST /api/v1/executions/{execution_id}/evidence/verify` performs:
1. Download all annotated screenshots from Blob Storage.
2. Recompute SHA-256 for each.
3. Compare against `manifest.integrity.chain[step].sha256`.
4. Recompute `chain_hash` and compare against stored value.
5. Return `{"valid": true}` or `{"valid": false, "failed_steps": [3, 7]}`.

---

## 7. PDF Evidence Report

The PDF is generated by `reportlab` at run completion.

### Structure

| Section | Content |
|---|---|
| Cover page | Company name, system name, script title, run date, overall status, pass/fail counts |
| Table of contents | Auto-generated from step list |
| Step pages | One page per step: annotated screenshot (full width), step description, expected vs actual outcome, status |
| Summary page | Execution timeline, duration, agent run ID, integrity hash |

### Cover Page Fields

```
KAATS — Test Execution Evidence Report
System:   {system.name}
Script:   {script.title}
Run date: {execution.started_at} UTC
Status:   PASSED / FAILED
Steps:    {passed_count} passed, {failed_count} failed, {skipped_count} skipped
Run ID:   {execution_id}
```

### Page Layout (A4 Portrait)

- Margin: 20mm on all sides
- Screenshot: scaled to fit page width (max 170mm wide); maintain aspect ratio
- Caption: 9pt text below screenshot
- Page footer: `KAATS Execution Evidence | Page {n} of {total} | Run ID: {id}`

---

## 8. Storage Lifecycle Policy

| Object | Retention | Policy |
|---|---|---|
| Raw PNG captures | 7 days | Blob lifecycle rule: delete after 7 days |
| Annotated PNGs | `evidence_retention_days` (default: 365) | Blob lifecycle rule |
| `manifest.json` | Same as annotated PNGs | — |
| `report.pdf` | Same as annotated PNGs | — |

When evidence is deleted (by policy or by user), the corresponding `evidence_screenshots` SQL records are soft-deleted (`deleted_at` set). The `agent_runs.evidence_pdf_url` is set to null.

---

## 9. Access Control

Evidence artifacts are stored in Azure Blob Storage. Users never access Blob Storage directly. The API generates ephemeral **SAS (Shared Access Signature) URLs** with a 1-hour TTL on every evidence request.

```
GET /api/v1/evidence/{screenshot_id}
→ 200 { "data": { "blob_path": "...", "sas_url": "https://...?sv=...&sig=...", "expires_at": "..." }}
```

```
GET /api/v1/executions/{execution_id}/evidence/report
→ 302 redirect to SAS URL for report.pdf
```

SAS URLs are scoped to the specific blob (not the container). The API validates company ownership before generating the SAS.

---

## 10. Evidence in Cosmos DB

The Cosmos `agent_run` document also carries a lightweight evidence summary for quick lookup without SQL joins:

```json
{
  "evidence_summary": {
    "total_screenshots": 9,
    "pdf_blob_path": "tenant-uuid/evidence/exec-uuid/report.pdf",
    "integrity_hash": "c9f2a1...",
    "steps": [
      { "step": 1, "status": "passed", "blob": "step-001-navigate-annotated.png" },
      { "step": 2, "status": "passed", "blob": "step-002-fill-annotated.png" }
    ]
  }
}
```
