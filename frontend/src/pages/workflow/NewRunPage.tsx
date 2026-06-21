import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  createResearchRun,
  listZoteroCollections,
  type ResearchRunCreateRequest,
  type SourceMode,
} from "../../api/researchPipeline";

interface FormData {
  question: string;
  source_mode: SourceMode;
  zotero_collection_key: string;
  manual_collection_key: string;
  max_reader_papers: string;
  reader_concurrency: string;
  year_start: string;
  year_end: string;
  venue_filter: string;
  keywords: string;
}

interface FormErrors {
  question?: string;
  max_reader_papers?: string;
  reader_concurrency?: string;
  submit?: string;
}

const DEFAULT_FORM_DATA: FormData = {
  question: "",
  source_mode: "web_search",
  zotero_collection_key: "",
  manual_collection_key: "",
  max_reader_papers: "8",
  reader_concurrency: "3",
  year_start: "",
  year_end: "",
  venue_filter: "",
  keywords: "",
};

export function NewRunPage() {
  const navigate = useNavigate();
  const [formData, setFormData] = useState<FormData>(DEFAULT_FORM_DATA);
  const [errors, setErrors] = useState<FormErrors>({});

  // Load Zotero collections
  const {
    data: zoteroData,
    isLoading: zoteroLoading,
    error: zoteroError,
  } = useQuery({
    queryKey: ["zoteroCollections"],
    queryFn: () => listZoteroCollections(100),
    staleTime: 5 * 60 * 1000, // Cache for 5 minutes
  });

  // Create run mutation
  const createMutation = useMutation({
    mutationFn: createResearchRun,
    onSuccess: (data) => {
      navigate(`/workflow/${data.run_id}`);
    },
    onError: (error) => {
      setErrors({
        submit: error instanceof Error ? error.message : "Failed to create research run",
      });
    },
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    // Clear error for this field
    if (errors[name as keyof FormErrors]) {
      setErrors((prev) => ({ ...prev, [name]: undefined }));
    }
  };

  const validateForm = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.question.trim()) {
      newErrors.question = "Research question is required";
    }

    const maxReaderPapers = parseInt(formData.max_reader_papers, 10);
    if (isNaN(maxReaderPapers) || maxReaderPapers < 3 || maxReaderPapers > 15) {
      newErrors.max_reader_papers = "Must be between 3 and 15";
    }

    const readerConcurrency = parseInt(formData.reader_concurrency, 10);
    if (isNaN(readerConcurrency) || readerConcurrency < 1) {
      newErrors.reader_concurrency = "Must be at least 1";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    // Build request
    const request: ResearchRunCreateRequest = {
      question: formData.question.trim(),
      source_mode: formData.source_mode,
      max_reader_papers: parseInt(formData.max_reader_papers, 10),
      reader_concurrency: parseInt(formData.reader_concurrency, 10),
      year_start: formData.year_start ? parseInt(formData.year_start, 10) : null,
      year_end: formData.year_end ? parseInt(formData.year_end, 10) : null,
      venue_filter: formData.venue_filter
        ? formData.venue_filter.split(",").map((v) => v.trim()).filter(Boolean)
        : [],
      keywords: formData.keywords
        ? formData.keywords.split(",").map((k) => k.trim()).filter(Boolean)
        : [],
    };

    // Handle Zotero collection key
    if (formData.source_mode === "zotero_only" || formData.source_mode === "hybrid") {
      if (zoteroError) {
        // Use manual key when Zotero unavailable
        request.zotero_collection_key = formData.manual_collection_key.trim() || null;
      } else {
        // Use selected collection from dropdown
        request.zotero_collection_key = formData.zotero_collection_key || null;
      }
    } else {
      request.zotero_collection_key = null;
    }

    createMutation.mutate(request);
  };

  const showZoteroField =
    formData.source_mode === "zotero_only" || formData.source_mode === "hybrid";

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-ink">Create Research Run</h1>
        <p className="mt-2 text-sm text-muted">
          Start a new research pipeline run to explore academic papers and generate a report.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="max-w-2xl">
        {/* Research Question */}
        <div className="mb-6">
          <label htmlFor="question" className="block text-sm font-medium text-ink mb-2">
            Research Question *
          </label>
          <textarea
            id="question"
            name="question"
            value={formData.question}
            onChange={handleChange}
            rows={3}
            className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
            placeholder="What are the latest advances in large language model reasoning?"
          />
          {errors.question && (
            <p className="mt-1 text-xs text-red-600">{errors.question}</p>
          )}
        </div>

        {/* Source Mode */}
        <div className="mb-6">
          <label htmlFor="source_mode" className="block text-sm font-medium text-ink mb-2">
            Source Mode *
          </label>
          <select
            id="source_mode"
            name="source_mode"
            value={formData.source_mode}
            onChange={handleChange}
            className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          >
            <option value="web_search">Web Search</option>
            <option value="zotero_only">Zotero Only</option>
            <option value="hybrid">Hybrid</option>
          </select>
          <p className="mt-1 text-xs text-muted">
            Web Search: Semantic Scholar + arXiv | Zotero Only: Local library | Hybrid: Both
          </p>
        </div>

        {/* Zotero Collection (conditional) */}
        {showZoteroField && (
          <div className="mb-6">
            {zoteroError ? (
              // Manual fallback when Zotero unavailable
              <>
                <label
                  htmlFor="manual_collection_key"
                  className="block text-sm font-medium text-ink mb-2"
                >
                  Collection Key (Manual)
                </label>
                <input
                  type="text"
                  id="manual_collection_key"
                  name="manual_collection_key"
                  value={formData.manual_collection_key}
                  onChange={handleChange}
                  className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  placeholder="Enter Zotero collection key"
                />
                <p className="mt-1 text-xs text-amber-600">
                  Zotero collections unavailable. Enter collection key manually.
                </p>
              </>
            ) : (
              // Collection selector when Zotero available
              <>
                <label
                  htmlFor="zotero_collection_key"
                  className="block text-sm font-medium text-ink mb-2"
                >
                  Zotero Collection
                </label>
                {zoteroLoading ? (
                  <p className="text-sm text-muted">Loading collections...</p>
                ) : (
                  <select
                    id="zotero_collection_key"
                    name="zotero_collection_key"
                    value={formData.zotero_collection_key}
                    onChange={handleChange}
                    className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
                  >
                    <option value="">None (search all)</option>
                    {zoteroData?.collections.map((collection) => (
                      <option key={collection.key} value={collection.key}>
                        {collection.name}
                      </option>
                    ))}
                  </select>
                )}
              </>
            )}
          </div>
        )}

        {/* Max Reader Papers */}
        <div className="mb-6">
          <label htmlFor="max_reader_papers" className="block text-sm font-medium text-ink mb-2">
            Max Reader Papers
          </label>
          <input
            type="number"
            id="max_reader_papers"
            name="max_reader_papers"
            value={formData.max_reader_papers}
            onChange={handleChange}
            min={3}
            max={15}
            className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <p className="mt-1 text-xs text-muted">
            Maximum papers to read in detail (3-15, default 8)
          </p>
          {errors.max_reader_papers && (
            <p className="mt-1 text-xs text-red-600">{errors.max_reader_papers}</p>
          )}
        </div>

        {/* Reader Concurrency */}
        <div className="mb-6">
          <label
            htmlFor="reader_concurrency"
            className="block text-sm font-medium text-ink mb-2"
          >
            Reader Concurrency
          </label>
          <input
            type="number"
            id="reader_concurrency"
            name="reader_concurrency"
            value={formData.reader_concurrency}
            onChange={handleChange}
            min={1}
            className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <p className="mt-1 text-xs text-muted">
            Parallel readers (default 3)
          </p>
          {errors.reader_concurrency && (
            <p className="mt-1 text-xs text-red-600">{errors.reader_concurrency}</p>
          )}
        </div>

        {/* Year Range */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-ink mb-2">Year Range</label>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <input
                type="number"
                id="year_start"
                name="year_start"
                value={formData.year_start}
                onChange={handleChange}
                placeholder="Start year"
                className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
            <div>
              <input
                type="number"
                id="year_end"
                name="year_end"
                value={formData.year_end}
                onChange={handleChange}
                placeholder="End year"
                className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
          </div>
          <p className="mt-1 text-xs text-muted">Optional: filter papers by publication year</p>
        </div>

        {/* Venue Filter */}
        <div className="mb-6">
          <label htmlFor="venue_filter" className="block text-sm font-medium text-ink mb-2">
            Venue Filter
          </label>
          <input
            type="text"
            id="venue_filter"
            name="venue_filter"
            value={formData.venue_filter}
            onChange={handleChange}
            placeholder="NeurIPS, ICML, ICLR"
            className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <p className="mt-1 text-xs text-muted">
            Optional: comma-separated venue names (e.g., NeurIPS, ICML)
          </p>
        </div>

        {/* Keywords */}
        <div className="mb-6">
          <label htmlFor="keywords" className="block text-sm font-medium text-ink mb-2">
            Keywords
          </label>
          <input
            type="text"
            id="keywords"
            name="keywords"
            value={formData.keywords}
            onChange={handleChange}
            placeholder="transformer, attention, reasoning"
            className="w-full rounded-md border border-line bg-panel px-3 py-2 text-sm text-ink placeholder:text-muted focus:border-accent focus:outline-none focus:ring-1 focus:ring-accent"
          />
          <p className="mt-1 text-xs text-muted">
            Optional: comma-separated keywords for filtering
          </p>
        </div>

        {/* Submit Error */}
        {errors.submit && (
          <div className="mb-6 rounded-md border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm text-red-600">{errors.submit}</p>
          </div>
        )}

        {/* Submit Button */}
        <div className="flex items-center gap-4">
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="inline-flex items-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {createMutation.isPending ? "Creating..." : "Create Run"}
          </button>
          <button
            type="button"
            onClick={() => navigate("/workflow")}
            className="text-sm text-muted hover:text-ink"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
