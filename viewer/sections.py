# Field groupings for the viewer — shared by terminal and web interfaces.
# Note: technology_description_summary (10a) and technology_description_formatted (10b)
# are rendered by special template logic in dataset.html, not via the SECTIONS loop.

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
        "dataset_type", "process_type",
        "name_treatment_standards_routes", "name_mix_and_location_types",
    ]),
    ("Other", [
        "lci_method_principle", "lci_method_approaches",
        "time_description", "mathematical_relations",
        "deviations_from_lci_method", "modelling_constants",
        "data_cutoff_principles", "data_selection_principles",
        "supply_coverage_percent", "source_url", "databases",
    ]),
]

# MUST fields checked in terminal summary header (null audit).
MUST_FIELDS = [
    "uuid", "name_base", "synonyms", "general_comment", "location",
    "geographical_representativeness_description", "reference_year",
    "valid_until", "technology_description", "dataset_type", "process_type",
    "dqi_overall_quality", "classification",
]

# Sections open by default in web detail view
DEFAULT_OPEN = {"Identity", "Technology", "Time", "DQI", "Modelling"}
