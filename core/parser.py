from lxml import etree

NS = {
    "ilcd": "http://lca.jrc.it/ILCD/Process",
    "common": "http://lca.jrc.it/ILCD/Common",
}

MUST_FIELDS = {
    "uuid", "name_base", "synonyms", "general_comment", "location",
    "geographical_representativeness_description", "reference_year",
    "valid_until", "technology_description", "dataset_type",
    "dqi_overall_quality", "classification",
}

NICE_FIELDS = {
    "name_treatment_standards_routes", "name_mix_and_location_types",
    "name_functional_unit", "use_advice", "reference_flows",
    "time_description", "technological_applicability", "mathematical_relations",
    "lci_method_principle", "lci_method_approaches",
    "deviations_from_lci_method", "modelling_constants", "data_cutoff_principles",
    "data_selection_principles", "supply_coverage_percent",
    "dqi_technological_representativeness", "dqi_time_representativeness",
    "dqi_geographical_representativeness", "dqi_completeness",
    "dqi_precision", "dqi_methodological_appropriateness",
}


def _text(root, xpath: str) -> str | None:
    """Extract text from first matching element, preferring lang=en."""
    elements = root.xpath(xpath, namespaces=NS)
    if not elements:
        return None
    en = [e for e in elements if e.get("{http://www.w3.org/XML/1998/namespace}lang") == "en"]
    el = en[0] if en else elements[0]
    return (el.text or "").strip() or None


def _attr(root, xpath: str, attr: str) -> str | None:
    """Extract attribute value from first matching element."""
    elements = root.xpath(xpath, namespaces=NS)
    return elements[0].get(attr) if elements else None


def _supply_percent(root) -> float | None:
    val = _text(root, ".//ilcd:percentageSupplyOrProductionCovered")
    try:
        return float(val) if val else None
    except ValueError:
        return None


def parse_dataset(xml_bytes: bytes) -> dict:
    """Parse ILCD XML bytes into a flat dict. Missing fields return None."""
    root = etree.fromstring(xml_bytes)

    # DQI indicators — keyed by name attribute
    dqi = {}
    for el in root.xpath(".//common:dataQualityIndicator", namespaces=NS):
        name = el.get("name")
        value = el.get("value")
        if name:
            dqi[name] = value

    # LCI method approaches — may be multiple elements
    approaches = [
        el.text.strip()
        for el in root.xpath(".//ilcd:LCIMethodApproaches", namespaces=NS)
        if el.text
    ]

    # Classification — concatenate hierarchy levels
    class_parts = [
        el.text.strip()
        for el in root.xpath(".//common:class", namespaces=NS)
        if el.text
    ]
    classification = " / ".join(class_parts) if class_parts else None

    # Reference year and valid until — integers
    ref_year_str = _text(root, ".//common:referenceYear")
    valid_until_str = _text(root, ".//common:dataSetValidUntil")

    # mathematical_relations lives in a child modelDescription element
    math_el = root.xpath(".//ilcd:mathematicalRelations/ilcd:modelDescription", namespaces=NS)
    if not math_el:
        # fallback: try direct text on the mathematicalRelations element
        math_el = root.xpath(".//ilcd:mathematicalRelations", namespaces=NS)
    mathematical_relations = None
    if math_el:
        en = [e for e in math_el if e.get("{http://www.w3.org/XML/1998/namespace}lang") == "en"]
        el = en[0] if en else math_el[0]
        mathematical_relations = (el.text or "").strip() or None

    return {
        # Key data set info
        "uuid": _text(root, ".//common:UUID"),
        "name_base": _text(root, ".//ilcd:baseName"),
        "name_treatment_standards_routes": _text(root, ".//ilcd:treatmentStandardsRoutes"),
        "name_mix_and_location_types": _text(root, ".//ilcd:mixAndLocationTypes"),
        "name_functional_unit": _text(root, ".//ilcd:functionalUnitFlowProperties"),
        "synonyms": _text(root, ".//common:synonyms"),
        "classification": classification,
        "general_comment": _text(root, ".//common:generalComment"),
        "use_advice": _text(root, ".//ilcd:useAdviceForDataSet"),
        "reference_flows": _text(root, ".//ilcd:referenceToReferenceFlow"),
        # Time
        "reference_year": int(ref_year_str) if ref_year_str else None,
        "valid_until": int(valid_until_str) if valid_until_str else None,
        "time_description": _text(root, ".//common:timeRepresentativenessDescription"),
        # Location
        "location": _attr(root, ".//ilcd:locationOfOperationSupplyOrProduction", "location"),
        "geographical_representativeness_description": _text(root, ".//ilcd:descriptionOfRestrictions"),
        # Technology
        "technology_description": _text(root, ".//ilcd:technologyDescriptionAndIncludedProcesses"),
        "technological_applicability": _text(root, ".//ilcd:technologicalApplicability"),
        "mathematical_relations": mathematical_relations,
        # Modelling
        "dataset_type": _text(root, ".//ilcd:typeOfDataSet"),
        "lci_method_principle": _text(root, ".//ilcd:LCIMethodPrinciple"),
        "lci_method_approaches": approaches if approaches else None,
        "deviations_from_lci_method": _text(root, ".//ilcd:deviationsFromLCIMethodApproaches"),
        "modelling_constants": _text(root, ".//ilcd:modellingConstants"),
        # Data sources
        "data_cutoff_principles": _text(root, ".//ilcd:dataCutOffAndCompletenessPrinciples"),
        "data_selection_principles": _text(root, ".//ilcd:dataSelectionAndCombinationPrinciples"),
        "supply_coverage_percent": _supply_percent(root),
        # Validation — DQI
        "dqi_overall_quality": dqi.get("Overall quality"),
        "dqi_technological_representativeness": dqi.get("Technological representativeness"),
        "dqi_time_representativeness": dqi.get("Time representativeness"),
        "dqi_geographical_representativeness": dqi.get("Geographical representativeness"),
        "dqi_completeness": dqi.get("Completeness"),
        "dqi_precision": dqi.get("Precision"),
        "dqi_methodological_appropriateness": dqi.get("Methodological appropriateness and consistency"),
    }
