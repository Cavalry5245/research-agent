"""
Diagnostic script to understand PDF structure and heading detection.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import fitz
from app.services.pdf_parser import parse_structured_elements, generate_pdf_profile


def main():
    pdf_path = "app/storage/papers/2203.16513v2.pdf"

    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF not found: {pdf_path}")
        return

    doc = fitz.open(pdf_path)
    paper_id = "diagnostic_001"

    try:
        profile = generate_pdf_profile(doc, paper_id)
        elements = parse_structured_elements(doc, paper_id, profile.layout_type)

        print("\n" + "=" * 80)
        print("PDF Structure Diagnostic")
        print("=" * 80)

        # Find elements with section keywords
        section_keywords = ['abstract', 'introduction', 'related work', 'method',
                          'experiment', 'results', 'conclusion', 'references']

        print("\nSearching for section keywords in elements...")
        print("-" * 80)

        found_count = 0
        for elem in elements:
            text_lower = elem.text.lower().strip()

            # Check if text matches any keyword
            for kw in section_keywords:
                if kw in text_lower and len(text_lower) < 100:  # Short text likely to be heading
                    found_count += 1
                    print(f"\nElement #{elem.order_index}")
                    print(f"  Type: {elem.type}")
                    print(f"  Page: {elem.page_number}")
                    print(f"  Text: '{elem.text[:80]}'")
                    print(f"  Text length: {len(elem.text)}")

                    # Check font info if available
                    if elem.bbox:
                        print(f"  BBox: {elem.bbox}")

                    break

        print(f"\n{'-' * 80}")
        print(f"Found {found_count} elements containing section keywords")

        # Show first 50 elements to understand structure
        print("\n" + "=" * 80)
        print("First 30 elements (structure overview):")
        print("=" * 80)

        for elem in elements[:30]:
            text_display = elem.text[:60].replace('\n', ' ')
            if len(elem.text) > 60:
                text_display += "..."
            print(f"\n[{elem.order_index:3d}] {elem.type:15s} (page {elem.page_number})")
            print(f"      {text_display}")

    finally:
        doc.close()


if __name__ == "__main__":
    main()
