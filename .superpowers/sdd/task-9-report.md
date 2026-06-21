# Task 9 Report: Add Zotero Source Adapter

## Status: DONE

## Summary

Successfully implemented the Zotero source adapter that integrates with the existing `ZoteroLocalHttpClient` to provide collection listing and paper candidate retrieval for the research pipeline.

## Changes Made

### Files Created

1. **app/research_pipeline/sources/zotero.py**
   - `ZoteroSourceAdapter` class with two main methods:
     - `list_collections(limit=100)`: Returns list of Zotero collections
     - `get_candidates(collection_key)`: Retrieves papers from a collection as `PaperCandidate` objects
   - `_normalize_zotero_item_to_candidate()`: Converts `ZoteroCollectionItem` to `PaperCandidate`
   - `_resolve_pdf_path_from_attachments()`: Extracts first PDF path from attachments (does not check file existence)

2. **tests/research_pipeline/test_zotero_source.py**
   - 11 comprehensive tests covering:
     - Collection listing (success, empty, HTTP errors)
     - Candidate retrieval (with/without PDF, multiple papers, empty collection, HTTP errors)
     - PDF path resolution
     - Router endpoint integration

### Files Modified

1. **app/research_pipeline/router.py**
   - Added import for `ZoteroSourceAdapter`
   - Added `GET /research-pipeline/sources/zotero/collections` endpoint
   - Returns 503 with clear error message when Zotero API is unavailable

## Key Implementation Details

### Design Decisions

1. **PDF Path Handling**: Unlike the research_workflow's `resolve_first_existing_pdf()` which checks file existence, the pipeline adapter returns PDF paths even if files don't exist yet. This supports future scenarios where PDFs might be referenced but not yet downloaded.

2. **Error Handling**: Zotero API failures (HTTPStatusError, ConnectError) are propagated to the router, which returns 503 Service Unavailable with descriptive error messages. This ensures the caller knows the failure is external.

3. **No PDF = Still Valid Candidate**: Papers without local PDFs still generate valid `PaperCandidate` objects with `local_pdf_path=None`, allowing the pipeline to track papers that may need PDF acquisition later.

4. **Metadata Extraction**: The normalizer extracts:
   - arXiv ID from Zotero's `extra` field
   - Venue from `publicationTitle`
   - Abstract from `abstractNote`
   - All raw Zotero data stored in `metadata.zotero_raw`

## Test Results

```powershell
& "D:\Hcworkspace\Anoconda3\envs\research_agent\python.exe" -m pytest tests/research_pipeline/test_zotero_source.py -q
```

**Result**: 11 passed, 1 warning (httpx deprecation in testclient - not blocking)

### Test Coverage

- ✅ List collections: success, empty, HTTP error
- ✅ Get candidates: with PDF, without PDF, multiple papers, empty collection, HTTP error
- ✅ Resolve local PDF path from attachments
- ✅ Router endpoint: success, Zotero unavailable

## Commits

- `e665431`: feat(pipeline): add Zotero source adapter (Task 9)

## Verification

All acceptance criteria met:

- ✅ Calls `ZoteroLocalHttpClient.list_collections()` for collection list
- ✅ Calls `ZoteroLocalHttpClient.list_collection_items()` for items
- ✅ Maps local PDF attachments to `local_pdf_path`
- ✅ Generates candidates even without PDFs (`local_pdf_path=None`)
- ✅ Zotero API failures return clear errors (503 with descriptive message)

## Integration Notes

The adapter is now ready for use in the pipeline:

```python
from app.research_pipeline.sources.zotero import ZoteroSourceAdapter

# List collections
adapter = ZoteroSourceAdapter()
collections = adapter.list_collections()  # Returns list of dicts

# Get candidates from a collection
candidates = adapter.get_candidates("COLLECTION_KEY")  # Returns list[PaperCandidate]
```

The router endpoint is available at:
```
GET /research-pipeline/sources/zotero/collections?limit=100
```

## No Concerns

Implementation is complete, tested, and follows all requirements. The adapter correctly reuses the existing `ZoteroLocalHttpClient` without modifying any `app/research_workflow/` files.
