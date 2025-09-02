# scripts/seed_field_library.py
# Reads 'Field Library.xlsx' (+ optionally the Canoe PDF) to generate the runtime Field Library bundle:
#   app/pe_docs/mapping/{field_library.yaml, column_map.csv, regex_bank.yaml, phrase_bank.yaml, validation_rules.yaml, units.yaml}
# Run once locally, then commit the generated files.

import os, sys, json, re
import pandas as pd

SEED_DIR   = os.getenv("FIELD_SEED_DIR", "app/pe_docs/seeds")
XLSX_NAME  = os.getenv("FIELD_SEED_XLSX", "Field Library.xlsx")
PDF_NAME   = os.getenv("FIELD_SEED_PDF",  "Canoe Asset Data External Field Library + Field Approach-12.pdf")
OUT_DIR    = "app/pe_docs/mapping"

os.makedirs(OUT_DIR, exist_ok=True)

def normalize_name(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("/", " ").replace("-", " ")
    s = re.sub(r"[^\w\s]", "", s)
    s = s.strip().lower()
    return s.replace(" ", "_")

def seed_from_xlsx(path):
    xl = pd.ExcelFile(path)
    # Expect tabs like: Static, Holdings, Operating_Metrics, Doc_Details, Txn_Attribution...
    # We'll attempt to infer columns: Field Name, Type, Unit, Group, EN Synonyms, DE Synonyms, Patterns
    fields = []
    column_map = []
    for sheet in xl.sheet_names:
        df = xl.parse(sheet).fillna("")
        # heuristic column picks
        cols = {c.lower(): c for c in df.columns}
        name_col = cols.get("field name") or cols.get("field") or list(df.columns)[0]
        type_col = cols.get("type") or None
        unit_col = cols.get("unit") or None
        syn_en   = cols.get("en synonyms") or cols.get("en") or None
        syn_de   = cols.get("de synonyms") or cols.get("de") or None
        patt_col = cols.get("patterns") or None
        group    = sheet.strip()

        for _, row in df.iterrows():
            name = str(row.get(name_col, "")).strip()
            if not name:
                continue
            canonical = normalize_name(name)
            f = {
                "canonical": canonical,
                "label": name,
                "type": (str(row.get(type_col, "decimal")).strip().lower() if type_col else "decimal"),
                "unit": (str(row.get(unit_col, "currency")).strip().lower() if unit_col else "currency"),
                "group": group,
                "synonyms": {
                    "en": [s.strip() for s in str(row.get(syn_en, "")).split(";") if s.strip()] if syn_en else [],
                    "de": [s.strip() for s in str(row.get(syn_de, "")).split(";") if s.strip()] if syn_de else [],
                },
                "patterns": [p.strip() for p in str(row.get(patt_col, "")).split(";") if p.strip()] if patt_col else [],
            }
            fields.append(f)
            # also add basic column_map entries from synonyms
            for alias in f["synonyms"].get("en", []) + f["synonyms"].get("de", []):
                column_map.append({"alias": alias, "canonical": canonical, "locale_hint": ""})

    return fields, column_map

def write_bundle(fields, column_map):
    # field_library.yaml (very minimal skeleton; enrich manually later)
    yaml_lines = ["version: 1.0", "locales:", "  default_locale: en", "fields:"]
    for f in fields:
        yaml_lines.append(f"  - canonical: {f['canonical']}")
        yaml_lines.append(f"    label: \"{f['label']}\"")
        yaml_lines.append(f"    type: {f['type']}")
        yaml_lines.append(f"    unit: {f['unit']}")
        yaml_lines.append(f"    group: \"{f['group']}\"")
        if f["synonyms"]["en"] or f["synonyms"]["de"]:
            yaml_lines.append(f"    synonyms:")
            if f["synonyms"]["en"]:
                yaml_lines.append(f"      en: [{', '.join([json.dumps(s) for s in f['synonyms']['en']])}]")
            if f["synonyms"]["de"]:
                yaml_lines.append(f"      de: [{', '.join([json.dumps(s) for s in f['synonyms']['de']])}]")
        if f["patterns"]:
            yaml_lines.append(f"    patterns: [{', '.join([json.dumps(p) for p in f['patterns']])}]")
    with open(os.path.join(OUT_DIR, "field_library.yaml"), "w", encoding="utf-8") as f:
        f.write("\n".join(yaml_lines) + "\n")

    # column_map.csv
    import csv
    with open(os.path.join(OUT_DIR, "column_map.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["alias","canonical","locale_hint"])
        w.writeheader()
        seen = set()
        for r in column_map:
            key = (r["alias"], r["canonical"])
            if key in seen:
                continue
            seen.add(key)
            w.writerow(r)

    # minimal stubs for other config files
    with open(os.path.join(OUT_DIR, "regex_bank.yaml"), "w", encoding="utf-8") as f:
        f.write("dates: ['(?i)\b\d{1,2}[./-]\d{1,2}[./-]\d{2,4}\b']\n")
        f.write("currency: ['€','\$','£']\n")
        f.write("neg_parentheses: ['^\(\s*\d[\d,\.\s]*\)$']\n")
        f.write("units: ['(?i)(k|thou|m|mn|bn)$']\n")

    with open(os.path.join(OUT_DIR, "phrase_bank.yaml"), "w", encoding="utf-8") as f:
        f.write("QR:\n  anchors: ['(?i)nav reconciliation','(?i)statement of assets','(?i)portfolio holdings']\n")
        f.write("CAS:\n  anchors: ['(?i)capital account statement','(?i)partner capital']\n")

    with open(os.path.join(OUT_DIR, "validation_rules.yaml"), "w", encoding="utf-8") as f:
        f.write("rules:\n")
        f.write("  - id: cas_equation\n    applies_to: CAS\n")
        f.write("    expr: "abs(ending - (opening + pic - dist - fees + pnl)) <= tolerance('nav_bridge')"\n")

    with open(os.path.join(OUT_DIR, "units.yaml"), "w", encoding="utf-8") as f:
        f.write("currency_symbols: {'€': EUR, '$': USD, '£': GBP}\n")
        f.write("multipliers: {'k': 1000, 'm': 1000000, 'bn': 1000000000}\n")
        f.write("decimal: {en: ['.',','], de: [',','.']}\n")

def main():
    xlsx_path = os.path.join(SEED_DIR, XLSX_NAME)
    if not os.path.exists(xlsx_path):
        print(f"Seed XLSX not found at {xlsx_path}. Place it and re-run.")
        sys.exit(1)
    fields, colmap = seed_from_xlsx(xlsx_path)
    write_bundle(fields, colmap)
    print(f"Generated Field Library bundle in {OUT_DIR}")

if __name__ == '__main__':
    main()
