"""
Manual test script for section tree building with real PDF (Task 2.3).
Run this directly to test with available PDFs.
"""

import os
import sys

import fitz

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.pdf_parser import (
    build_section_tree,
    generate_pdf_profile,
    parse_structured_elements,
)


def run_with_pdf(pdf_path: str):
    """Test section tree building with a specific PDF."""
    print(f"\n{'='*80}")
    print(f"Testing with PDF: {pdf_path}")
    print(f"{'='*80}\n")

    paper_id = "test_manual_001"

    try:
        doc = fitz.open(pdf_path)
        print(f"[OK] PDF opened successfully ({doc.page_count} pages)")

        # Step 1: Generate PDF profile
        try:
            profile = generate_pdf_profile(doc, paper_id)
            print(f"\n[OK] PDF Profile Generated:")
            print(f"  - Layout type: {profile.layout_type}")
            print(f"  - Text density: {profile.text_density:.2f} chars/page")
            print(f"  - Has tables: {profile.has_tables}")
            print(f"  - Has figures: {profile.has_figures}")
            print(f"  - References start page: {profile.reference_page_start}")
        except ValueError as e:
            print(f"\n[SKIP] PDF Profile Failed: {e}")
            print("  This is likely a scanned/image PDF. Trying next PDF...")
            doc.close()
            return False

        # Step 2: Parse structured elements
        elements = parse_structured_elements(doc, paper_id, profile.layout_type)
        print(f"\n[OK] Parsed {len(elements)} structured elements")

        # Element type distribution
        type_counts = {}
        for elem in elements:
            type_counts[elem.type] = type_counts.get(elem.type, 0) + 1

        print(f"\n  Element type distribution:")
        for elem_type, count in sorted(type_counts.items()):
            print(f"    - {elem_type}: {count}")

        # Step 3: Build section tree
        elements = build_section_tree(elements)
        print(f"\n[OK] Section tree built successfully")

        # Section statistics
        section_paths = set()
        sections_by_level = {1: set(), 2: set(), 3: set()}
        in_references_count = 0

        for elem in elements:
            if elem.section_path:
                section_paths.add(elem.section_path)

                # Determine level by counting '/'
                level = elem.section_path.count("/") + 1
                if elem.type in ["heading", "title"] and level <= 3:
                    sections_by_level[level].add(elem.section_path)

            if elem.metadata.get("in_references"):
                in_references_count += 1

        print(f"\n  Section tree statistics:")
        print(f"    - Total unique sections: {len(section_paths)}")
        print(f"    - Level 1 sections: {len(sections_by_level[1])}")
        print(f"    - Level 2 sections: {len(sections_by_level[2])}")
        print(f"    - Level 3 sections: {len(sections_by_level[3])}")
        print(f"    - Elements in References: {in_references_count}")

        # Section coverage
        elements_with_section = [e for e in elements if e.section_path is not None]
        coverage = len(elements_with_section) / len(elements) if elements else 0
        print(f"    - Section path coverage: {coverage:.1%}")

        # Print all identified sections
        print(f"\n  Identified sections:")
        for level in [1, 2, 3]:
            if sections_by_level[level]:
                print(f"\n    Level {level}:")
                for section in sorted(sections_by_level[level])[:10]:
                    print(f"      - {section}")
                if len(sections_by_level[level]) > 10:
                    print(f"      ... and {len(sections_by_level[level]) - 10} more")

        # Print sample elements with their section paths
        print(f"\n  Sample elements with section paths:")
        sample_count = 0
        for elem in elements:
            if elem.type in ["heading", "paragraph"] and sample_count < 15:
                section_display = elem.section_path or "(none)"
                text_preview = elem.text[:60] + "..." if len(elem.text) > 60 else elem.text
                print(f"    [{elem.type:10s}] {section_display}")
                print(f"                    → {text_preview}")
                sample_count += 1

        doc.close()
        print(f"\n{'='*80}")
        print("[OK] Test completed successfully!")
        print(f"{'='*80}\n")
        return True

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Find and test available PDFs."""
    print("\nSection Tree Building Test (Task 2.3)")
    print("=" * 80)

    # Try to find test PDFs
    test_locations = [
        "tests/data/sample.pdf",
        "app/storage/papers",
    ]

    pdfs_to_test = []

    for location in test_locations:
        if os.path.isfile(location):
            pdfs_to_test.append(location)
        elif os.path.isdir(location):
            files = [f for f in os.listdir(location) if f.lower().endswith(".pdf")]
            pdfs_to_test.extend([os.path.join(location, f) for f in files[:5]])

    if not pdfs_to_test:
        print("\n[ERROR] No PDF files found for testing")
        print("  Please place a sample PDF in tests/data/sample.pdf")
        print("  or in app/storage/papers/")
        return

    print(f"\nFound {len(pdfs_to_test)} PDF(s) to test")

    success_count = 0
    for pdf_path in pdfs_to_test:
        if run_with_pdf(pdf_path):
            success_count += 1
            break  # Stop after first successful test

    if success_count == 0:
        print("\n[ERROR] No PDFs could be successfully processed")
        print("  All PDFs appear to be scanned/image PDFs without text content")
    else:
        print(f"\n[OK] Successfully tested with {success_count} PDF(s)")


if __name__ == "__main__":
    main()
