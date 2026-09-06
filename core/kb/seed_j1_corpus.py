"""Seed Journey J1 demo corpus with API 570 and ASME Sec VIII Div 1 clause texts."""

from typing import Any


J1_DEMO_CLAUSES: list[dict[str, Any]] = [
    {
        "doc_id": "API-570",
        "title": "API 570 Piping Inspection Code",
        "dept": "INSPECTION",
        "classification": "CONFIDENTIAL",
        "effective_date": "2024-01-01",
        "heading_path": "API 570 › Section 7 › 7.1.1 Remaining Life Calculation",
        "body_text": (
            "API 570 Piping Inspection Code — Section 7.1.1 Remaining Life Calculation: "
            "The remaining life of a piping system shall be calculated as: "
            "Remaining Life (years) = (t_actual - t_minimum) / C_rate, where t_actual is the "
            "measured wall thickness in mm, t_minimum is the minimum required wall thickness "
            "in mm per ASME design code, and C_rate is the corrosion rate in mm/year. "
            "If remaining life is less than 2.0 years, inspection frequency shall be doubled "
            "or replacement scheduled immediately."
        ),
    },
    {
        "doc_id": "ASME-SEC-VIII",
        "title": "ASME Boiler & Pressure Vessel Code Sec VIII Div 1",
        "dept": "ENGINEERING",
        "classification": "CONFIDENTIAL",
        "effective_date": "2023-07-01",
        "heading_path": "ASME Sec VIII Div 1 › Part UG › UG-27 Thickness of Cylindrical Shells",
        "body_text": (
            "ASME Boiler and Pressure Vessel Code Section VIII Division 1 — UG-27: "
            "The minimum required thickness of cylindrical shells under internal pressure "
            "shall be calculated as t_min = (P * R) / (S * E - 0.6 * P), where P is internal "
            "design pressure in MPa, R is inside radius in mm, S is allowable stress value "
            "of material in MPa, and E is joint efficiency factor."
        ),
    },
]

J1_DEMO_EQUIPMENT_REGISTER: list[dict[str, Any]] = [
    {
        "tag_id": "C-101",
        "unit_id": "UNIT-01",
        "equipment_name": "Crude Distillation Column",
        "service_description": "Crude Oil Fractionation",
        "design_pressure_mpa": 2.4,
        "design_temp_c": 350.0,
    },
    {
        "tag_id": "PT-101",
        "unit_id": "UNIT-01",
        "equipment_name": "Column Top Pressure Transmitter",
        "service_description": "Vapor Pressure Monitoring",
        "design_pressure_mpa": 2.4,
        "design_temp_c": 120.0,
    },
    {
        "tag_id": "TI-202",
        "unit_id": "UNIT-01",
        "equipment_name": "Reflux Temperature Indicator",
        "service_description": "Reflux Stream Temperature",
        "design_pressure_mpa": 1.6,
        "design_temp_c": 180.0,
    },
    {
        "tag_id": "FIC-204A",
        "unit_id": "UNIT-01",
        "equipment_name": "Crude Feed Flow Indicator Controller",
        "service_description": "Raw Crude Feed Rate",
        "design_pressure_mpa": 4.0,
        "design_temp_c": 210.0,
    },
    # Note: PI-108 is intentionally omitted from the master register to serve as the planted demo discrepancy!
]


async def seed_equipment_register(db_path: Any) -> None:
    """Seed the SQLite equipment_register table with J1 plant tags."""
    from storage.equipment_store import EquipmentRegisterEntry, EquipmentRegisterStore

    store = EquipmentRegisterStore(db_path)
    for entry in J1_DEMO_EQUIPMENT_REGISTER:
        await store.add_equipment_entry(
            EquipmentRegisterEntry(
                tag_id=entry["tag_id"],
                unit_id=entry["unit_id"],
                equipment_name=entry["equipment_name"],
                service_description=entry["service_description"],
                design_pressure_mpa=entry["design_pressure_mpa"],
                design_temp_c=entry["design_temp_c"],
                is_active=True,
            )
        )

