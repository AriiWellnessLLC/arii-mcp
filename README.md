# Arii MCP Specification

Source of truth for the Arii Health Platform API schema, published as a Model Context Protocol tool surface for AI agents via the Airia Platform gateway.

## Overview

This repository maintains `arii.yaml`, an OpenAPI 3.0.3 specification for the Arii Health Platform API. The specification is ingested by the Airia Platform, which exposes each operation as a Model Context Protocol (MCP) tool under the `Arii_MCP` prefix.

The specification is authored by hand rather than generated, but it is not authored freely: every operation, parameter, and documented behaviour is derived from merged `arii-api` `main` and verified against it. Nothing is exposed that is not merged. Where the API's own XML documentation disagrees with its runtime behaviour, the behaviour is what this file records.

The surface is **read-only**. No `create_*` or other write operation is exposed: the client writes records when a person approves them, so an agent writing directly would create a row nobody approved and the approval would then save a duplicate.

Descriptions are written for agent consumption and define the supported workflows for identity resolution, biomarker retrieval, observation queries, medication adherence, and clinical notes.

The specification currently defines **29 operations** across **29 paths** and **11 component schemas**, organised into the following domains:

| Tag | Scope |
| --- | --- |
| `Users` | Caller identity and Arii user ID resolution |
| `Journal` | Patient wellness journal entries |
| `Meals` | Meal and nutrition tracking |
| `Medications` | Medication prescriptions and adherence history |
| `Notes` | Clinical and provider notes, including patient-shared notes |
| `Observations` | Labs, activities, assessments, appointments, and summaries |
| `Documents` | Health documents with AI-assisted feature extraction |
| `Symptoms` | Symptom tracking and reporting |
| `Markers` | Marker summaries (full and compact), averages, and raw samples |
| `MarkerTypes` | Biomarker and metric definitions and lookup |
| `DataDictionary` | Per-user inventory of marker types with recorded data |

## Authentication

Two schemes are declared, and the choice materially affects how user identifiers are handled.

- **`bearerAuth`** — JWT Bearer, including Airia Platform passthrough. All user-scoped parameters require Arii user IDs. No Airia profile to Arii user translation is performed.
- **`apiKeyAuth`** — API key supplied via the `X-API-Key` header. Some older endpoints auto-translate Airia profile IDs to Arii user IDs under this scheme only. Several newer endpoints do not accept API key authentication.

Three distinct identifiers appear across the platform and must not be interchanged: the Arii user ID (`UserDto.id`), the Airia profile ID (`airiaProfileId`, correlation only), and the Keycloak subject claim.

`get_current_user` returns the requester, never the subject of the question. Under Bearer/passthrough the caller is resolved from the session, so no read here needs `requestingUserId` and `get_current_user` is not a step before a patient read — the patient's Arii user ID comes from the execution context. Under API key, `requestingUserId` is the only identity the API has and the reads that accept it refuse the call without one.

## Environments

The declared server is the Arii development environment:

```
https://dev.api.arii.com
```

`dev.api.arii.com` and `dev.api.nicoya.health` are both live and serve the same API. The declared value is a default only.

Environment targeting is handled at the gateway. Override the target per environment using the `?u=` query parameter on the gateway URL rather than editing the server block.

## Authoring conventions

Changes to the specification are derived from the `arii-api` implementation — controllers for routes, versioning, and authentication behaviour, and DTOs for field definitions. Read the controller action, not just its XML documentation: several parameters are declared optional in C# and rejected at runtime, and some XML comments are stale. When adding or amending an operation, follow the conventions already established in the file:

- `operationId` values are snake_case and become the MCP tool name.
- Every operation declares `x-mcp-annotations` with the applicable hints (`readOnlyHint`, `idempotentHint`).
- Descriptions are written as agent guidance, stating the workflow an operation belongs to and the tools that should precede or follow it.
- Response schemas are declared under `components/schemas` and referenced, never inlined. Coverage is partial: the entity reads (users, journals, meals, notes, observations, compact marker summary) declare a response schema and the remaining operations document their response in prose. Extending coverage is welcome; adding a schema that has not been checked against the merged DTO is not.
- Enumerated values are serialised by the API as integers with camelCase property names, and must be declared accordingly.

The `get_user` operation is the reference implementation for block structure and description style.

## Validation

Validate the specification before opening a pull request:

```bash
npx @redocly/cli lint arii.yaml
```

Confirm every declared route still exists on the API before merging. A route that answers `401` exists and requires authentication; a `404` means the operation is not there:

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://dev.api.arii.com/api/v2/MarkerType
```
