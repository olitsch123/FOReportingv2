# scripts/seed_field_library.py
# Generates Field Library bundle into app/pe_docs/mapping/ from "Field Library.xlsx".
import os, sys, json, re, csv
import pandas as pd
from pathlib import Path

SEED_DIR = os.getenv("FIELD_SEED_DIR", "app/pe_docs/seeds")
XLSX_NAME = os.getenv("FIELD_SEED_XLSX", "Field Library.xlsx")
OUT_DIR = "app/pe_docs/mapping"

Path(OUT_DIR).mkdir(parents=True, exist_ok=True)

def normalize_name(s: str) -> str:
    s = (s or "").strip()
    s = re.sub(r"\s+", " ", s)
    s = s.replace("/", " ").replace("-", " ")
    s = re.sub(r"[^\w\s]", "", s)
    s = s.strip().lower()
    return s.replace(" ", "_")

def seed_from_xlsx(path: str):
    xl = pd.ExcelFile(path)
    fields, column_map = [], []
    for sheet in xl.sheet_names:
        df = xl.parse(sheet).fillna("")
        cols = {c.lower(): c for c in df.columns}
        name_col = cols.get("field name") or cols.get("field") or list(df.columns)[0]
        type_col = cols.get("type")
        unit_col = cols.get("unit")
        syn_en  = cols.get("en synonyms") or cols.get("en")
        syn_de  = cols.get("de synonyms") or cols.get("de")
        patt_col= cols.get("patterns")
        group   = sheet.strip()
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
            for alias in f["synonyms"].get("en", []) + f["synonyms"].get("de", []):
                column_map.append({"alias": alias, "canonical": canonical, "locale_hint": ""})
    return fields, column_map

def write_bundle(fields, column_map):
    yaml = ["version: 1.0", "locales:", "  default_locale: en", "fields:"]
    for f in fields:
        yaml += [
            f"  - canonical: {f['canonical']}",
            f"    label: {json.dumps(f['label'])}",
            f"    type: {f['type']}",
            f"    unit: {f['unit']}",
            f"    group: {json.dumps(f['group'])}",
        ]
        if f["synonyms"]["en"] or f["synonyms"]["de"]:
            yaml.append("    synonyms:")
            if f["synonyms"]["en"]:
                yaml.append("      en: [" + ", ".join(json.dumps(s) for s in f["synonyms"]["en"]) + "]")
            if f["synonyms"]["de"]:
                yaml.append("      de: [" + ", ".join(json.dumps(s) for s in f["synonyms"]["de"]) + "]")
        if f["patterns"]:
            yaml.append("    patterns: [" + ", ".join(json.dumps(p) for p in f["patterns"]) + "]")
    Path(OUT_DIR, "field_library.yaml").write_text("\n".join(yaml) + "\n", encoding="utf-8")

    with open(Path(OUT_DIR, "column_map.csv"), "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["alias","canonical","locale_hint"])
        w.writeheader()
        seen = set()
        for r in column_map:
            key = (r["alias"], r["canonical"])
            if key in seen: 
                continue
            seen.add(key)
            w.writerow(r)

    Path(OUT_DIR, "regex_bank.yaml").write_text(
        "dates: ['(?i)\\b\\d{1,2}[./-]\\d{1,2}[./-]\\d{2,4}\\b']\n"
        "currency: ['€','\\$','£']\n"
        "neg_parentheses: ['^\\(\\s*\\d[\\d,\\.\\s]*\\)$']\n"
        "units: ['(?i)(k|thou|m|mn|bn)$']\n", encoding="utf-8"
    )
    Path(OUT_DIR, "phrase_bank.yaml").write_text(
        "QR:\n  anchors: ['(?i)nav reconciliation','(?i)statement of assets','(?i)portfolio holdings']\n"
        "CAS:\n  anchors: ['(?i)capital account statement','(?i)partner capital']\n", encoding="utf-8"
    )
    Path(OUT_DIR, "validation_rules.yaml").write_text(
        "rules:\n"
        "  - id: cas_equation\n"
        "    applies_to: CAS\n"
        "    expr: \"abs(ending - (opening + pic - dist - fees + pnl)) <= tolerance('nav_bridge')\"\n",
        encoding="utf-8"
    )
    Path(OUT_DIR, "units.yaml").write_text(
        "currency_symbols: {'€': EUR, '$': USD, '£': GBP}\n"
        "multipliers: {'k': 1000, 'm': 1000000, 'bn': 1000000000}\n"
        "decimal: {en: ['.',','], de: [',','.']}\n", encoding="utf-8"
    )

def main():
    xlsx_path = str(Path(SEED_DIR, XLSX_NAME))
    if not Path(xlsx_path).exists():
        print(f"Seed XLSX not found at {xlsx_path}. Place it and re-run.")
        sys.exit(1)
    fields, colmap = seed_from_xlsx(xlsx_path)
    write_bundle(fields, colmap)
    print(f"Generated Field Library bundle in {OUT_DIR}")

if __name__ == "__main__":
    main()
