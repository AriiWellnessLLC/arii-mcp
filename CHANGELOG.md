# Changelog

Each entry is one weekly release of `arii.yaml`, newest first. One Arii MCP catalog serves dev, staging and prod, so an upload changes the tools in every environment at once.

Releases before 3.1.0 were not run as weekly releases. Their entries group the changes merged to `main` in each week, under the spec version `main` held at the end of that week. Some versions were raised more than once in a week, and one week changed the spec without raising it. Both are noted where they happen.

Write the entry in the same PR that raises the version. List the tools added, changed and removed, and any breaking changes. A breaking change is anything that makes a tool call that worked before fail: a removed tool, a removed parameter, a parameter that becomes required, or a narrower limit.

## 3.1.0 — week of Oct 5–11, 2026 (released Oct 8)

Jira: AIP-381.

### Added

- `get_out_of_range_results` lists a patient's lab results that fall outside their normal range. Each result carries a Low or High flag. The server works the flag out from the range bounds, not from the band's label. Results with no range to judge against come back separately, under `noRange`. The response schemas are new: `OutOfRangeLabResults`, `OutOfRangeLabResult`, `UnjudgedLabResult`, `LabNormalRange` and `AlternateLabRange`. (AIP-331, #14)

### Changed

- `get_dose_history` is paged. New parameters: `pageSize` (1–100; the description says to send 50) and `pageNumber` (0-based). The response carries `hasNextPage`, doses come newest first, and a bad page returns 400. The description now points counts and adherence rates at `get_adherence_stats`. (AIP-396, #19)
- `get_user_symptom_details` returns each symptom's end date. For a record that has only a duration, the end date is the start date plus the duration. The read is paged with `pageNumber`, at most 100 entries per page, newest first. The description no longer says that a missing end date means the symptom is still active. (AIP-334, #20)
- `get_observation_samples`: `pageSize` is now declared as 1–100 (it was 1–1000). The API still accepts up to 1000, but agents keep to 100 so one result stays small. (#19)
- `get_marker_summary_compact`: the description now says `rangeStatus` is the same judgement `get_out_of_range_results` makes. It points to that tool for the range's source and the draw date. In the response schema, `rangeStatus` is declared as `L`, `H` or `InRange`, and null now explicitly means "not judged", never "normal". (#14)
- The top-level guidance sends "flag anything out of range" questions to `get_out_of_range_results`. It also says band labels on `get_observation_samples` are alert levels, not directions. (#14)

### Removed

- None.

### Breaking changes

These affect agents calling the tools. They do not affect the arii-api endpoints.

- `get_dose_history` now declares `startDate` and `pageSize` as required. A tool call that sends neither is not valid against the new schema. The API itself still accepts a call without them.
- `get_observation_samples` declares `pageSize` up to 100. A tool call with a larger page is not valid against the new schema.

### arii-api changes this version relies on

These are merged to arii-api `main`, and every one is on dev.

- The out-of-range read and the bounds-based flag: arii-api #2836, #2837.
- Dose history paging: arii-api #2905.
- Symptom end dates and paging: arii-api #2940.

## 3.0.0 — week of Sep 28 – Oct 4, 2026

`main` moved from 2.0.0 through 2.1.0, 2.2.0 and 2.2.1 to 3.0.0 this week. The 2.1.0 raise (#11) changed nothing but the version number.

### Added

- `get_marker_data_sources` lists, for each of a patient's marker types, every source that holds readings and which one is preferred. (AIP-350, #12)
- `get_marker_averages_compact` and `get_marker_samples_compact` read averages and individual readings from every source, one row per marker and source. (AIP-350, #18)

### Changed

- `get_marker_summary_compact` returns one row per marker and source, from every source. New parameters: `dataSources` and `staleDays`. It is no longer paged, and `pageNumber`, `pageSize`, `requestingUserId` and `skipFallbackData` are gone. An unscoped call is refused with 400. (AIP-350, #18)
- `get_user_journals` and `get_user_symptom_details` take `recordStartDate` and `recordEndDate`: the patient's own calendar days. A plain `startDate`/`endDate` on those reads is a UTC day, so it can miss or add entries near midnight. The older pair stays declared. (AIP-277, #7)
- `get_marker_averages` says what date a weekly chart point carries: the first and last day of its week, not the day of a reading. (AIP-343, #8)
- The marker reads say which source each row came from. A compact summary row no longer claims to carry `availableSources`; the description points to `get_marker_data_sources` instead. (AIP-350, #12, #16)

### Removed

- `get_marker_summary`, `get_marker_averages` and `get_marker_samples`. Each read one source per marker and dropped the rest, so an agent said a marker was not recorded when another device held it. The compact tools replace them. (AIP-350, #18)

### Breaking changes

- The three removed marker tools: an agent that still calls them gets no tool.
- `get_marker_summary_compact` no longer accepts `pageNumber`, `pageSize`, `requestingUserId` or `skipFallbackData`, and an unscoped call is refused.

## 2.0.0 (version not raised) — week of Sep 21–27, 2026

The spec changed this week, but `info.version` stayed at 2.0.0.

### Added

- None.

### Changed

- `get_user_meals` and `get_meal` name the nutrients a meal returns. The new `MealNutritionSample` schema carries `quantityTypeName`, which names each nutrient, so an agent no longer has to guess what a numeric code like 7 or 4 means. (AIP-236, #4)
- `get_user_journals`, `get_dose_history` and `get_user_symptom_details` say a plain `2026-08-28` date works. The old wording told agents a bare date returns 400. (AIP-234, #5)
- `get_observation_samples` declares its response: `PagedObservationSamples`, `ObservationSample`, `AppliedReferenceRange` and `ReferenceRangeSegment`. `appliedReferenceRange.source` is a name (`Platform`, `Org`, `Cohort`, `Patient`), not a number. (AIP-264, #6)

### Removed

- None.

### Breaking changes

- None.

## 2.0.0 — week of Sep 14–20, 2026

The catalog was brought up to what the gateway was already built from (catalog `e77a3c24`), and checked against arii-api `main`. (AIP-236, AIP-297, #2, #3)

### Added

- `get_active_medications_and_supplements`, `get_all_medications_and_supplements`, `get_dose_history` and `get_adherence_stats`: the medication and supplement reads.
- `get_observation_samples`: individual readings for an observation.
- `get_marker_summary_compact`: one row per marker with its current value.

### Changed

- `get_user_marker_types_with_data` becomes the first call for any marker question. It no longer tells agents to avoid reading another person's record, because the API decides access from who is asking. It gains `excludeSkipDailyAggregations`.
- Current-value questions are routed to `get_marker_summary_compact` everywhere, including the closing line of `get_user_marker_types_with_data`. (#3)
- `bulk_search_marker_types` becomes the fallback when the patient's own markers do not match what they asked about.
- `requestingUserId` is no longer required on any read: the API takes the caller from the session.
- `list_observations` gains `MarkerTypeIds`, `RecordStartDate` and `RecordEndDate`. `list_notes` gains `isPrivate`. `get_marker_averages` gains `skipFallbackData`, and `get_marker_samples` gains `filterRawSamples`.
- `get_user_preferences` no longer takes the `X-Access-Context` header.
- Most tool descriptions were rewritten as guidance for agents.

### Removed

- `create_journal`, `create_meal`, `create_medication`, `create_observation` and `create_user_symptom_details`. The catalog is read-only: the app saves a record when a person approves it, so an agent writing directly would create a row nobody approved.
- `get_medication_history`: replaced by `get_dose_history`.
- `lookup_marker_types`: the whole-catalog dump.

### Breaking changes

- The seven removed tools.
- `get_user_preferences` no longer accepts `X-Access-Context`.

## 1.0.0 — Sep 14, 2026

The first Arii MCP spec: 30 tools under the `Arii_MCP` prefix, pointed at `https://dev.api.nicoya.health`. (#1)

- Users: `get_current_user`, `get_user`, `get_user_preferences`.
- Journal: `get_user_journals`, `get_journal`, `create_journal`.
- Meals: `get_user_meals`, `get_meal`, `create_meal`.
- Medications: `get_medication_history`, `create_medication`.
- Notes: `list_notes`, `get_note`, `get_shared_notes`, `list_note_categories`.
- Observations: `list_observations`, `get_observation`, `create_observation`.
- Documents: `get_user_documents`.
- Symptoms: `list_symptoms`, `get_user_symptom_details`, `create_user_symptom_details`.
- Markers: `get_marker_summary`, `get_marker_averages`, `get_marker_samples`.
- Marker types: `list_marker_types`, `get_marker_type`, `lookup_marker_types`, `bulk_search_marker_types`, `get_user_marker_types_with_data`.
