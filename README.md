# Arii MCP Specification

Source of truth for the Arii Health Platform API schema, published as a Model Context Protocol tool surface for AI agents via the Airia Platform gateway.

## Overview

This repository maintains `arii.yaml`, an OpenAPI 3.0.3 specification for the Arii Health Platform API. The specification is ingested by the Airia Platform, which exposes each operation as a Model Context Protocol (MCP) tool under the `Arii_MCP` prefix.

The specification is authored contract-first and maintained by hand. It is not generated from the API implementation. Operation, parameter, and schema descriptions are written for agent consumption and define the supported workflows for identity resolution, biomarker retrieval, observation queries, and patient data entry.

The specification currently defines **30 operations** across **27 paths** and **23 component schemas**, organised into the following domains:

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
| `Markers` | Marker summaries, averages, and raw samples |
| `MarkerTypes` | Biomarker and metric definitions and lookup |
| `DataDictionary` | Per-user inventory of marker types with recorded data |

## Authentication

Two schemes are declared, and the choice materially affects how user identifiers are handled.

- **`bearerAuth`** — JWT Bearer, including Airia Platform passthrough. All user-scoped parameters require Arii user IDs. No Airia profile to Arii user translation is performed.
- **`apiKeyAuth`** — API key supplied via the `X-API-Key` header. Some older endpoints auto-translate Airia profile IDs to Arii user IDs under this scheme only. Several newer endpoints do not accept API key authentication.

Three distinct identifiers appear across the platform and must not be interchanged: the Arii user ID (`UserDto.id`), the Airia profile ID (`airiaProfileId`, correlation only), and the Keycloak subject claim. Agents resolve the Arii user ID by calling `get_current_user` and reusing the returned `id`.

## Environments

The declared server is the Nicoya development environment:

```
https://dev.api.nicoya.health
```

Environment targeting is handled at the gateway. Override the target per environment using the `?u=` query parameter on the gateway URL rather than editing the server block.

## Authoring conventions

Changes to the specification are derived from the `arii-api` implementation — controllers for routes, versioning, and authentication behaviour, and DTOs for field definitions. When adding or amending an operation, follow the conventions already established in the file:

- `operationId` values are snake_case and become the MCP tool name.
- Every operation declares `x-mcp-annotations` with the applicable hints (`readOnlyHint`, `idempotentHint`).
- Descriptions are written as agent guidance, stating the workflow an operation belongs to and the tools that should precede or follow it.
- Request and response bodies reference shared definitions under `components/schemas` rather than inlining structures.
- Enumerated values are serialised by the API as integers with camelCase property names, and must be declared accordingly.

The `get_user` operation is the reference implementation for block structure and description style.

## Validation

Validate the specification before opening a pull request:

```bash
npx @redocly/cli lint arii.yaml
```
