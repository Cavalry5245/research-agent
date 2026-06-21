## Task 12: Implement Retriever Agent - DONE

### Status: DONE

All acceptance criteria met. The Retriever Agent successfully orchestrates paper retrieval across sources with proper routing, deduplication, and degraded mode handling.

### Commits

```
commit 5c518f8
feat(research-pipeline): implement Retriever Agent (Task 12)

- Add RetrieverAgent that orchestrates paper retrieval across sources
- Implement source_mode routing: web_search, zotero_only, hybrid
- Add candidate CRUD operations to store.py (create_candidate, get_candidates)
- Update get_run_detail to include candidates in response
- Integrate RetrieverAgent into runner via create_default_agent factory
- Handle source failures gracefully with degraded mode
- Implement deduplication before persistence
- Add comprehensive tests for all source modes and failure scenarios
```

### Test Results

```
$ python -m pytest tests/research_pipeline/test_retriever_agent.py tests/research_pipeline/test_retriever_integration.py -v

tests/research_pipeline/test_retriever_agent.py::test_web_search_mode_calls_both_sources PASSED
tests/research_pipeline/test_retriever_agent.py::test_zotero_only_mode_calls_zotero_only PASSED
tests/research_pipeline/test_retriever_agent.py::test_hybrid_mode_preserves_zotero_seed_and_merges_web_search PASSED
tests/research_pipeline/test_retriever_agent.py::test_source_failure_writes_event_and_allows_degraded PASSED
tests/research_pipeline/test_retriever_agent.py::test_all_sources_fail_marks_stage_as_failed PASSED
tests/research_pipeline/test_retriever_agent.py::test_candidates_visible_via_get_run_detail PASSED
tests/research_pipeline/test_retriever_agent.py::test_deduplication_happens_before_persistence PASSED
tests/research_pipeline/test_retriever_integration.py::test_runner_creates_retriever_agent PASSED
tests/research_pipeline/test_retriever_integration.py::test_default_agent_factory_creates_retriever_agent PASSED

============================== 9 passed in 1.72s ==============================
```

### Files Modified

**Created:**
- `app/research_pipeline/agents/retriever.py` (365 lines) - RetrieverAgent implementation
- `tests/research_pipeline/test_retriever_agent.py` (374 lines) - Comprehensive unit tests
- `tests/research_pipeline/test_retriever_integration.py` (133 lines) - Integration tests

**Modified:**
- `app/research_pipeline/store.py` (+129 lines) - Added candidate CRUD methods:
  - `create_candidate()` - Persist PaperCandidate to database
  - `get_candidates()` - Retrieve all candidates for a run
  - Updated `get_run_detail()` to include candidates in response
  
- `app/research_pipeline/runner.py` (+33 lines) - Integration:
  - Added imports for RetrieverAgent and source adapters
  - Implemented `create_default_agent()` factory function
  - Wired up RetrieverAgent for "retriever" stage

### Implementation Details

**RetrieverAgent Architecture:**

1. **Source Mode Routing:**
   - `web_search`: Calls Semantic Scholar + arXiv
   - `zotero_only`: Calls Zotero only
   - `hybrid`: Zotero seed → Web Search merge

2. **Deduplication:**
   - Uses `deduplicate_candidates()` from normalizer
   - Happens before persistence
   - Preserves Zotero source priority

3. **Degraded Mode:**
   - Partial source failures write error events
   - Stage marked as "degraded" but continues
   - All sources fail → stage marked as "failed" + exception raised

4. **Event Logging:**
   - Stage start/complete events
   - Per-source search progress events
   - Error events for source failures
   - Deduplication progress events

### Acceptance Criteria Verification

✅ **web_search calls Semantic Scholar and arXiv**
- Verified by `test_web_search_mode_calls_both_sources`
- Both sources called, candidates from both persisted

✅ **zotero_only calls Zotero only**
- Verified by `test_zotero_only_mode_calls_zotero_only`
- Only Zotero candidates present, no web search

✅ **hybrid preserves Zotero seed and merges Web Search**
- Verified by `test_hybrid_mode_preserves_zotero_seed_and_merges_web_search`
- Zotero candidates fetched first
- Web search candidates merged
- Deduplication preserves Zotero priority (source="zotero" retained)

✅ **Source failures write events and allow run degraded**
- Verified by `test_source_failure_writes_event_and_allows_degraded`
- Error events written for failed sources
- Stage marked as "degraded"
- Successful sources still provide candidates

✅ **Candidates visible via GET /research-pipeline/runs/{run_id}**
- Verified by `test_candidates_visible_via_get_run_detail`
- `get_run_detail()` includes "candidates" field
- Full candidate structure returned

### Concerns

None. All acceptance criteria met, all tests pass, integration with runner verified.

### Next Steps

Task 12 completes Slice 2 (Source Integration). The retriever stage is now fully functional with:
- Multi-source routing
- Deduplication
- Graceful degradation
- Database persistence

Ready to proceed to Slice 3: Planner, Reader, and PaperCard implementation.
