# Sphera LCA Dataset — JSON Field Mapping (Draft)

> Status: Draft — under review, last updated 2026-03-20. Field table updated with live XML findings.

## Field Priority Tiers

| Symbol | Tier | Purpose |
|---|---|---|
| ✅ | **MUST** | Core fields — exported in JSON, used by LLM in Module 2, short view in Module 3 |
| 🔵 | **NICE TO HAVE** | Useful for humans — long view in Module 3, exported in JSON |
| ❌ | **EXCLUDE** | Not exported |

> **Note:** The MUST / NICE TO HAVE distinction applies beyond the listed modules —
> it also governs how datasets are used in downstream applications (e.g. LLM pipelines,
> reporting tools, integrations built on top of this project). MUST fields form the
> stable core contract; NICE TO HAVE fields are extended context.

> **TODO (future version):** Allow a user-supplied config file (e.g., CSV or JSON table) as input
> to define which fields are included or excluded at runtime, instead of hardcoding the field list.
> This enables different export profiles without changing the code.

---

## Field Table

> XML structure for data quality indicators: `<dataQualityIndicator name="Overall quality" value="good"/>`
> Each indicator is a separate element with `name` and `value` attributes.

| # | ILCD Section | XML Field Name | JSON Key | Priority | Example (first ~10 words) | Notes |
|---|---|---|---|---|---|---|
| 1 | Key data set info | `common:UUID` | `uuid` | ✅ | `9f2f5c2f-f304-4de0-8988-b0eaccdf7dff` | |
| 2 | Key data set info | `baseName` | `name_base` | ✅ | `Capacitor Al-capacitor SMD (2.54g) D12.5x13.5` | Confirmed from live XML |
| 3 | Key data set info | `treatmentStandardsRoutes` | `name_treatment_standards_routes` | 🔵 | `technology mix` | Confirmed from live XML |
| 4 | Key data set info | `mixAndLocationTypes` | `name_mix_and_location_types` | 🔵 | `production mix, at plant` | Confirmed from live XML |
| 5 | Key data set info | `functionalUnitFlowProperties` | `name_functional_unit` | 🔵 | `(2.54g) D12.5x13.5` | Confirmed from live XML |
| 6 | Key data set info | `synonyms` | `synonyms` | ✅ | `electrolytic capacitor, SMD cap...` | Field name and attribute name both `synonyms`; confirmed |
| 7 | Key data set info | `classificationInformation` | `classification` | ✅ | `Electronics / Passive components` | |
| 8 | Key data set info | `common:generalComment` | `general_comment` | ✅ | `This dataset represents a cradle-to-gate...` | |
| 9 | Key data set info | `useAdviceForDataSet` | `use_advice` | 🔵 | `This dataset should be used for...` | Field name and attribute name both `useAdviceForDataSet`; free text |
| 10 | Key data set info | `referenceToReferenceFlow` | `reference_flows` | 🔵 | `1 piece Al-capacitor SMD 10µF...` | "Reference flow(s)" |
| 11 | Time | `common:referenceYear` | `reference_year` | ✅ | `2025` | |
| 12 | Time | `common:dataSetValidUntil` | `valid_until` | ✅ | `2028` | |
| 13 | Time | `common:timeRepresentativenessDescription` | `time_description` | 🔵 | `annual average` | |
| 14 | Location | `locationOfOperationSupplyOrProduction` | `location` | ✅ | `GLO` | Attribute on element, e.g. location="GLO" |
| 15 | Location | `descriptionOfRestrictions` | `geographical_representativeness_description` | ✅ | `Global dataset; production data primarily from China...` | Confirmed from live XML |
| 16 | Technology | `technologyDescriptionAndIncludedProcesses` | `technology_description` | ✅ | `The manufacturing of aluminum capacitors involves...` | Main long text field |
| 17 | Technology | `technologicalApplicability` | `technological_applicability` | 🔵 | `Used in consumer electronics, automotive, industrial...` | Field name and attribute name both `technologicalApplicability`; free text; "Technical purpose of product or process" |
| 18 | Technology | `mathematicalRelations` | `mathematical_relations` | 🔵 | `Mass balance applied across all unit processes...` | |
| 19 | Modelling | `typeOfDataSet` | `dataset_type` | ✅ | `LCI result` | |
| 20 | Modelling | `LCIMethodPrinciple` | `lci_method_principle` | ✅ | `Attributional` | |
| 21 | Modelling | `LCIMethodApproaches` | `lci_method_approaches` | ✅ | `["market value", "calorific value", ...]` | |
| 22 | Modelling | `deviationsFromLCIMethodApproaches` | `deviations_from_lci_method` | 🔵 | `No deviations from standard allocation...` | |
| 23 | Modelling | `modellingConstants` | `modelling_constants` | 🔵 | `GHG emission factors based on IPCC 2021...` | |
| 24 | Data sources | `dataCutOffAndCompletenessPrinciples` | `data_cutoff_principles` | 🔵 | `Coverage of at least 99% of mass and energy...` | |
| 25 | Data sources | `dataSelectionAndCombinationPrinciples` | `data_selection_principles` | 🔵 | `Primary data collected from industry surveys...` | |
| 26 | Data sources | `percentageSupplyOrProductionCovered` | `supply_coverage_percent` | 🔵 | `99.0` | |
| 27 | Validation | `dataQualityIndicator` name=`Overall quality` | `dqi_overall_quality` | ✅ | `good` | Must have |
| 28 | Validation | `dataQualityIndicator` name=`Technological representativeness` | `dqi_technological_representativeness` | 🔵 | `very good` | |
| 29 | Validation | `dataQualityIndicator` name=`Time representativeness` | `dqi_time_representativeness` | 🔵 | `good` | |
| 30 | Validation | `dataQualityIndicator` name=`Geographical representativeness` | `dqi_geographical_representativeness` | 🔵 | `fair` | |
| 31 | Validation | `dataQualityIndicator` name=`Completeness` | `dqi_completeness` | 🔵 | `very good` | |
| 32 | Validation | `dataQualityIndicator` name=`Precision` | `dqi_precision` | 🔵 | `good` | |
| 33 | Validation | `dataQualityIndicator` name=`Methodological appropriateness and consistency` | `dqi_methodological_appropriateness` | 🔵 | `very good` | |
| 34 | Flows | `exchanges` | `inputs` / `outputs` | ❌ | — | **Not available** — XMLs are `metaDataOnly="true"`; exchange data not present |
| 35 | Completeness | *(all fields)* | — | ❌ | — | |
| 36 | Compliance | *(all fields)* | — | ❌ | — | |
| 37 | Admin info | *(all fields)* | — | ❌ | — | |

---

## Official ILCD References

| Resource | URL |
|---|---|
| ILCD ProcessDataSet Format 1.1 Documentation | https://eplca.jrc.ec.europa.eu/LCDN/downloads/ILCD_Format_1.1_Documentation/ILCD_ProcessDataSet.html |
| ILCD Developer Data Format Overview | https://eplca.jrc.ec.europa.eu/LCDN/developerILCDDataFormat.html |
| European Platform on LCA (EPLCA) — ILCD Home | https://eplca.jrc.ec.europa.eu/ilcd.html |
| ILCD Guidance Document (PDF, v1.1 beta) | https://eplca.jrc.ec.europa.eu/uploads/QMS_H08_ENSURE_ILCD_GuidanceDocumentationLCADataSets_Version1-1Beta_2011_ISBN_clean.pdf |

> Standard maintained by the Joint Research Centre (JRC), European Commission.
> Sphera datasets follow ILCD Format 1.1.

---

## Open Questions

*All field names confirmed — no open questions remaining. Table ready for user review.*

---

## Viewer Design Note

> **Module 3 viewer** should support two modes:
> - **Short / Overview** — MUST fields only
> - **Long / Full** — MUST + NICE TO HAVE fields
>
> This distinction applies beyond the viewer — it also governs downstream use of the datasets
> (LLM pipelines, reporting tools, integrations). MUST fields form the stable core contract;
> NICE TO HAVE fields are extended context for human review.
>
> Tree hierarchy labels (e.g., `Location | geographical_representativeness_description`) useful
> for orientation — consider for a later viewer version.
