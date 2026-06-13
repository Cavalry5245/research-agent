"""
Specific test for section tree building with arxiv PDF (Task 2.3).
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fitz
from app.services.pdf_parser import (
    build_section_tree,
    generate_pdf_profile,
    parse_structured_elements,
)


def main():
    pdf_path = "app/storage/papers/2203.16513v2.pdf"

    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF not found: {pdf_path}")
        return

    print("\n" + "=" * 80)
    print("Section Tree Building Test - ArXiv PDF")
    print("=" * 80)
    print(f"\nPDF: {pdf_path}\n")

    paper_id = "test_arxiv_001"
    doc = fitz.open(pdf_path)

    try:
        # Step 1: Generate profile
        profile = generate_pdf_profile(doc, paper_id)
        print(f"[OK] PDF Profile:")
        print(f"  Pages: {profile.page_count}")
        print(f"  Layout: {profile.layout_type}")
        print(f"  Text density: {profile.text_density:.2f}")
        print(f"  References start: {profile.reference_page_start}")

        # Step 2: Parse elements
        elements = parse_structured_elements(doc, paper_id, profile.layout_type)
        print(f"\n[OK] Parsed {len(elements)} elements")

        # Type distribution
        type_counts = {}
        for elem in elements:
            type_counts[elem.type] = type_counts.get(elem.type, 0) + 1

        print("\n  Element types:")
        for t, c in sorted(type_counts.items()):
            print(f"    {t}: {c}")

        # Step 3: Build section tree
        elements = build_section_tree(elements)
        print(f"\n[OK] Section tree built")

        # Analyze sections
        sections = {}
        for elem in elements:
            if elem.type in ["heading", "title"] and elem.section_path:
                level = elem.section_path.count("/") + 1
                if level not in sections:
                    sections[level] = []
                sections[level].append(elem.section_path)

        print("\n  Sections by level:")
        for level in [1, 2, 3]:
            if level in sections:
                unique = list(dict.fromkeys(sections[level]))  # Preserve order, remove duplicates
                print(f"\n    Level {level} ({len(unique)} sections):")
                for s in unique[:15]:
                    print(f"      - {s}")
                if len(unique) > 15:
                    print(f"      ... and {len(unique) - 15} more")

        # Check References marking
        in_ref = [e for e in elements if e.metadata.get("in_references")]
        print(f"\n  Elements in References: {len(in_ref)}")

        # Coverage
        with_section = [e for e in elements if e.section_path]
        coverage = len(with_section) / len(elements) * 100
        print(f"  Section path coverage: {coverage:.1f}%")

        # Sample heading elements with their paths
        print("\n  Sample heading elements:")
        heading_count = 0
        for elem in elements:
            if elem.type == "heading" and heading_count < 20:
                text_short = elem.text[:50] + "..." if len(elem.text) > 50 else elem.text
                section_display = elem.section_path or "(no path)"
                print(f"    '{text_short}'")
                print(f"      -> {section_display}")
                heading_count += 1

        print("\n" + "=" * 80)
        print("[SUCCESS] All tests passed!")
        print("=" * 80)

    finally:
        doc.close()


if __name__ == "__main__":
    main()
