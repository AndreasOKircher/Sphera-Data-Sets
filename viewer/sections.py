# Field groupings for the viewer — shared by terminal and web interfaces.
# Dropped fields (not shown): time_description, mathematical_relations,
# lci_method_principle, lci_method_approaches, deviations_from_lci_method,
# modelling_constants

SECTIONS = [
    ("Identity", [
        "uuid", "name_base", "name_functional_unit", "general_comment", "synonyms", "classification",
    ]),
    ("Technology", [
        "technology_description", "technological_applicability",
    ]),
    ("Time", [
        "reference_year", "valid_until",
    ]),
    ("DQI", [
        "dqi_overall_quality", "dqi_technological_representativeness",
        "dqi_time_representativeness", "dqi_geographical_representativeness",
        "dqi_completeness", "dqi_precision",
        "dqi_methodological_appropriateness",
    ]),
    ("Notes", [
        "use_advice", "reference_flows",
    ]),
    ("Location", [
        "location", "geographical_representativeness_description",
    ]),
    ("Modelling", [
        "dataset_type",
    ]),
    ("Data Sources", [
        "data_cutoff_principles", "data_selection_principles",
        "supply_coverage_percent",
    ]),
    ("Name Details", [
        "name_treatment_standards_routes", "name_mix_and_location_types",
    ]),
    ("Catalogue", [
        "source_url", "xls_dataset_type", "databases",
    ]),
]

# MUST fields checked in terminal summary header (null audit).
# Subset of core/parser.py MUST_FIELDS — excludes lci_method_principle
# and lci_method_approaches (dropped from viewer as low value for inspection).
MUST_FIELDS = [
    "uuid", "name_base", "synonyms", "general_comment", "location",
    "geographical_representativeness_description", "reference_year",
    "valid_until", "technology_description", "dataset_type",
    "dqi_overall_quality", "classification",
]

# Sections open by default in web detail view
DEFAULT_OPEN = {"Identity", "Technology", "Time", "DQI"}
