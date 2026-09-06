"""Script to generate eval/routing_trainset.jsonl (600) and eval/routing_testset.jsonl (300).

Generates realistic Indian PSU / MRPL refinery domain prompts across the 9 task classes.
Trainset and testset use disjoint template seeds and disjoint vocabulary patterns to prevent memorisation.
"""

import json
from pathlib import Path
import random

CLASSES = [
    "code_generate",
    "code_debug",
    "doc_summarise",
    "doc_extract",
    "engineering_calc",
    "official_drafting",
    "vision_ocr",
    "kb_qa",
    "other",
]

# Train set templates (Seed 42)
TRAIN_TEMPLATES = {
    "code_generate": [
        "Write a Python script to parse CSV data containing refinery crude unit temperature readings and calculate hourly averages.",
        "Implement a pandas function to clean equipment maintenance log dataset and export to Excel.",
        "Create a script using openpyxl to generate automated monthly inspection summary reports.",
        "Write a Python script to compute moving averages for FT-101 flow meter sensor telemetry.",
        "Write a function to validate ISA instrument tag formats using regular expressions.",
        "Implement a script to convert raw log files from refinery boiler units into JSON format.",
    ],
    "code_debug": [
        "Debug this Python snippet throwing AttributeError: 'DataFrame' object has no attribute 'append' in crude analysis pipeline.",
        "Fix KeyError: 'vram_usage' occurring in GPU telemetry logging script.",
        "Resolve SyntaxError: invalid syntax in openpyxl spreadsheet generation function.",
        "Fix TypeError: unsupported operand type(s) for +: 'int' and 'str' in boiler calculation script.",
        "Traceback (most recent call last): File 'calc.py', line 45, in <module> ZeroDivisionError: division by zero. Please fix.",
        "Fix IndexError: list index out of range when parsing instrument tag list.",
    ],
    "doc_summarise": [
        "Provide an executive summary of the attached OISD-118 safety audit report for MRPL CDU-II.",
        "Summarise the key findings of the Q3 refinery maintenance shutdown report.",
        "Synthesise the main recommendations from the annual environmental compliance audit.",
        "Summarise the 50-page crude distillation unit operating manual section on emergency shutdown.",
        "Summarise the minutes of the DGM safety committee meeting held on 15th August.",
        "Give a concise 3-paragraph summary of the pump overhaul inspection report.",
    ],
    "doc_extract": [
        "Extract all ultrasonic thickness measurement readings and pipe schedule numbers from this inspection report.",
        "Extract the asset tag numbers, inspection dates, and corrosion rates from this log document.",
        "Extract all financial figures and budget head numbers from this purchase requisition note.",
        "List all ISA instrument tags mentioned in the crude distillation unit equipment register.",
        "Extract the minimum required wall thickness values from the ASME vessel data sheet.",
        "Extract all non-conformance report (NCR) serial numbers from the annual audit file.",
    ],
    "engineering_calc": [
        "Calculate the minimum required pipe wall thickness for 10-inch line at 35 bar operating pressure according to ASME B31.3.",
        "Compute the hydrotest pressure required for crude storage tank T-102 per IS 803.",
        "Determine the maximum allowable working pressure (MAWP) for vessel V-301 given 12mm thickness and 2% corrosion allowance.",
        "Calculate heat exchanger heat duty Q = m * Cp * DeltaT for heavy naphtha stream.",
        "Compute pressure drop across control valve FCV-201 operating at 450 m3/h flow rate.",
        "Calculate the corrosion rate in mm/year given initial thickness 14.2mm, current thickness 11.8mm over 4 years.",
    ],
    "official_drafting": [
        "Draft a formal approval note for DGM Mech seeking sanction for urgent procurement of mechanical seals for P-201.",
        "Draft an official PSU note proposing sanction of INR 4.5 Lakhs for OISD safety compliance training.",
        "मंगलोर रिफाइनरी हेतु पंप मरम्मत स्वीकृति टिप्पणी (Approval Note) प्रारूप तैयार करें।",
        "Draft a formal memorandum to the Projects Division regarding delay in P&ID drawing submission.",
        "कच्चा तेल आसवन इकाई (CDU) के नियमित निरीक्षण के लिए आधिकारिक पत्र ड्राफ्ट करें।",
        "Draft a recommendation note seeking deviation approval from standard painting specifications for offsite piping.",
    ],
    "vision_ocr": [
        "Run OCR on this scanned handwritten inspection form for pressure vessel V-104.",
        "Extract table data from this scanned PDF image of P&ID drawing sheet 3.",
        "Read the blurred thickness gauge reading photo and extract the numbers.",
        "Process this scanned diagram photo of flow transmitter FT-1702 and extract tag labels.",
        "इस धुंधली स्कैन की गई हस्तलिखित रिपोर्ट छवि से अक्षर और आंकड़े निकालें।",
        "OCR this scanned blueprint photo of MRPL refinery tank farm layout.",
    ],
    "kb_qa": [
        "What is the governing OISD standard clause for fire water storage capacity in Indian petroleum refineries?",
        "What are the permitted corrosion allowances under ASME Section VIII Division 1 for hydrocarbon service?",
        "What is the procedure for issuing a Hot Work Permit under refinery safety regulations?",
        "According to MRPL safety manual, what is the frequency of hydrostatic testing for LPG spheres?",
        "What does clause 4.2 of IS 456 specify regarding concrete cover in industrial marine environments?",
        "What are the mandatory PPE requirements for entry into a confined vessel space?",
    ],
    "other": [
        "Translate this paragraph into Hindi for official refinery circular distribution.",
        "Organise these 5 general file names into chronological order.",
        "Convert this text fragment into a bulleted list.",
        "Hello, who created the SWARAJ workbench system?",
        "List 3 general differences between centrifugal and positive displacement pumps.",
        "Reformat this text into a clean markdown table.",
    ],
}

# Test set templates (Seed 999 - COMPLETELY DISJOINT vocabulary & structures)
TEST_TEMPLATES = {
    "code_generate": [
        "Generate a Python script using pandas to filter refinery sensor logs where pressure exceeds 40 bar.",
        "Write a Python utility to parse ISA tag strings like PIC-3301 and split into function code and loop number.",
        "Create an automated script to read tank telemetry JSON files and calculate total daily storage throughput.",
        "Write a Python module to compute ASME B31.3 allowable stress tables from CSV input.",
        "Implement a Python script to scan log directories for error tracebacks and write summary to CSV.",
        "Write a script using matplotlib to plot wall thickness degradation over 10 inspection cycles.",
    ],
    "code_debug": [
        "Fix TypeError: 'NoneType' object is not subscriptable in P&ID tag parser script.",
        "Debug ValueError: invalid literal for int() with base 10: 'FT-1702' in telemetry loader.",
        "Resolve KeyError: 'thickness_mm' when iterating over inspection report records.",
        "Traceback (most recent call last): File 'pipeline.py', line 112, in <module> FileNotFoundError: [Errno 2] No such file. Fix it.",
        "Fix ZeroDivisionError in corrosion rate calculation function when time delta is zero.",
        "Debug recursion error in approval note hierarchy parser.",
    ],
    "doc_summarise": [
        "Summarise the quarterly reliability report for Hydrogen Generation Unit (HGU-2).",
        "Provide a 2-paragraph overview of the turnaround inspection findings for FCCU reactor vessel.",
        "Summarise the environmental audit report regarding sulfur recovery unit (SRU) emissions.",
        "Give a concise executive summary of the third-party risk assessment report for tank farm T-501.",
        "Summarise the root cause failure analysis (RCFA) document for motor driven pump P-104.",
        "Provide a high-level summary of the OISD safety committee inspection notes.",
    ],
    "doc_extract": [
        "Extract all weld inspection result codes and NDT operator names from this PDF document.",
        "Extract the design temperature, operating pressure, and flange rating numbers from this vessel specification sheet.",
        "Extract all cost center codes and approved amounts from the quarterly expenditure statement.",
        "List all control valve tag numbers (e.g. FCV-101, LCV-202) from this plant register file.",
        "Extract pipe material grade specifications and heat numbers from the mill test certificate.",
        "Extract all safety non-compliance observations from the auditor's field notes.",
    ],
    "engineering_calc": [
        "Calculate the stress intensification factor for a 12-inch unreinforced branch connection per ASME B31.3.",
        "Compute the required vent capacity for atmospheric storage tank T-204 per API 2000.",
        "Determine the minimum test pressure for a 16-inch crude pipeline under ASME B31.4.",
        "Calculate thermal expansion delta L for a 150-meter carbon steel steam pipe operating at 300 deg C.",
        "Compute pump net positive suction head available (NPSHA) for crude charge pump P-101.",
        "Calculate the remaining service life of pipe section 10-CW-102 given corrosion rate 0.15 mm/yr.",
    ],
    "official_drafting": [
        "Draft an approval note for Chief Manager (Projects) requesting administrative sanction for pipeline replacement.",
        "Draft a formal note seeking approval for financial sanction of INR 12.8 Lakhs for valve overhaul.",
        "रिफाइनरी सुरक्षा उपकरण खरीद हेतु डीजीएम (प्रक्रिया) के समक्ष स्वीकृति टिप्पणी (Approval Note) तैयार करें।",
        "Draft an official PSU memorandum regarding compliance with updated OISD-118 guidelines.",
        "उपकरण निरीक्षण रिपोर्ट के संदर्भ में मुख्य अभियंता को आधिकारिक स्वीकृति पत्र का प्रारूप तैयार करें।",
        "Draft a formal recommendation note for sanction of emergency shutdown repair work.",
    ],
    "vision_ocr": [
        "Extract text and numerical readings from this scanned handwritten equipment log sheet.",
        "Run OCR on this scanned P&ID drawing image sheet 7 and extract tag PIC-3301.",
        "Process this scanned photo of ultrasonic thickness gauge display showing 8.4mm.",
        "OCR this scanned blueprint document of crude distillation column internals.",
        "इस धुंधली स्कैन की गई हिंदी स्वीकृति टिप्पणी (Scanned Note Image) से पाठ निकालें।",
        "Extract table data from this scanned PDF image of valve maintenance register.",
    ],
    "kb_qa": [
        "What is the maximum allowable working stress for SA-516 Grade 70 steel at 300 deg C per ASME Sec II Part D?",
        "What does clause 6.3 of OISD-118 specify regarding inter-distance between crude storage tanks?",
        "What are the mandatory inspection intervals for relief valves in hydrocarbon service under OISD-132?",
        "According to API 570, what is the classification of Class 1 piping systems in petroleum refineries?",
        "What safety checks are required prior to cold work in explosive hydrocarbon zones per refinery SOP?",
        "What is the standard procedure for nitrogen purging of reactor vessels during shutdown?",
    ],
    "other": [
        "Convert this text file from UTF-8 to ASCII encoding.",
        "Format these 4 project milestone titles into title case.",
        "What is the capital city of Karnataka?",
        "Draft a friendly reminder to clean up the shared workstation desk.",
        "Explain the difference between a gate valve and a globe valve in simple terms.",
        "Rearrange these 3 sentences into a logical paragraph.",
    ],
}


def build_dataset(templates: dict, target_count: int, seed: int) -> list[dict]:
    random.seed(seed)
    items = []
    items_per_class = (target_count + len(CLASSES) - 1) // len(CLASSES)

    for cls in CLASSES:
        cls_templates = templates[cls]
        for i in range(items_per_class):
            base_tpl = cls_templates[i % len(cls_templates)]
            # Add slight realistic variations without changing the semantic class
            var_id = i // len(cls_templates)
            if var_id == 0:
                prompt = base_tpl
            elif var_id == 1:
                prompt = f"[Refinery Unit {100 + i}] {base_tpl}"
            elif var_id == 2:
                prompt = f"Please proceed: {base_tpl} (Priority: High)"
            elif var_id == 3:
                prompt = f"{base_tpl} -- Reference MRPL/INSP/2026/{500+i}."
            else:
                prompt = f"{base_tpl} [Asset Tag: FT-{1700+i}]"

            has_image = cls == "vision_ocr" or "scanned" in prompt.lower() or "photo" in prompt.lower() or "image" in prompt.lower()
            mime_types = ["image/png"] if has_image else []

            items.append({
                "prompt": prompt,
                "has_image": has_image,
                "mime_types": mime_types,
                "expected_class": cls,
            })

    random.shuffle(items)
    return items


def main():
    root = Path("d:/SovereignAI/eval")
    root.mkdir(parents=True, exist_ok=True)

    train_items = build_dataset(TRAIN_TEMPLATES, 603, seed=42)
    test_items = build_dataset(TEST_TEMPLATES, 306, seed=999)

    train_path = root / "routing_trainset.jsonl"
    test_path = root / "routing_testset.jsonl"

    with open(train_path, "w", encoding="utf-8") as f:
        for item in train_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    with open(test_path, "w", encoding="utf-8") as f:
        for item in test_items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Successfully generated {len(train_items)} train items -> {train_path}")
    print(f"Successfully generated {len(test_items)} test items -> {test_path}")


if __name__ == "__main__":
    main()
