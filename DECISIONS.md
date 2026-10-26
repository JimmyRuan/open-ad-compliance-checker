# DECISIONS

## 1. Unit of Retrieval

**Decision:** Use a *provision node* representing a single labeled paragraph at its deepest citation level.

The eCFR provides paragraphs as flat text, with labels such as `(d)(2)(iii)` embedded inline rather than represented as a hierarchy.

To reconstruct the hierarchy, `app/labels.py` uses a backtracking stack machine that interprets the CFR labeling conventions. This handles ambiguous labels such as `(i)`, which can represent either the ninth letter or the first lowercase Roman numeral. Lookahead helps resolve these ambiguities.

Each provision node stores two distinct forms of information:

-   **Precise citation:** The deepest paragraph label, which identifies the specific provision a reviewer can act on.
-   **Searchable context:** The paragraph text combined with its ancestor introductions and descendant content, providing enough context for meaningful retrieval.

For example, `1026.24(d)(2)(iii)` begins:

> "The 'annual percentage rate,' using that term…"

On its own, this text provides insufficient context for reliable retrieval. Including the parent provision `(d)(2)` makes the paragraph more discoverable without sacrificing citation precision.

**Tradeoff:** Indexing additional context increases the text associated with each node, but substantially improves retrieval quality for short or context-dependent provisions.

## 2. Selecting Relevant Provisions

**Decision:** Use three sequential filtering and ranking stages, each designed to be explainable and auditable.

### Stage 1 — Deterministic Applicability Gate

An applicability gate determines which regulations are relevant to the advertiser before retrieval begins.

The gate is implemented directly as a SQL search predicate rather than a post-processing filter.

Examples:

-   **Credit unions:** Exclude Regulation DD because `12 CFR 1030.1(c)` excludes credit unions from its scope.
-   **Nonbank advertisers:** Exclude FDIC Part 328.
-   **Unknown advertiser types:** Disable restrictive filtering rather than guessing.

Every applicability rule references the regulatory provision establishing its scope.

The gate deliberately **fails open** when the advertiser type is unrecognized.

This prioritizes recall: an irrelevant retrieved provision can be dismissed by a reviewer, whereas a relevant provision excluded by the gate cannot be recovered downstream.

### Stage 2 — Multi-Query Hybrid Retrieval

Advertisement wording often differs substantially from regulatory terminology.

For example, advertisement `a2` contains the phrase "No strings attached!", which has little lexical overlap with the regulation governing misleading claims about free accounts.

To address this, each detected topic contributes an additional search query expressed in regulatory terminology.

Retrieval combines:

-   **Lexical search:** Finds provisions containing relevant terminology.
-   **Vector search:** Finds provisions with similar semantic meaning.
-   **Reciprocal Rank Fusion (RRF):** Combines results from both approaches into a unified ranking.

This improves the likelihood of finding relevant provisions even when advertisements use informal or promotional language.

### Stage 3 — Candidate Limiting and Hierarchy Collapse

The final candidate set is limited to **24 provisions**.

When both an ancestor and its descendant appear in the results, the ancestor is removed in favor of the more specific provision.

The LLM evaluates the remaining candidates in a single assessment call and identifies which provisions it rules out.

**Tradeoff:** Limiting candidates reduces assessment cost and latency, while hierarchy collapse removes redundant citations. However, relevant provisions may still be missed if they fall outside the candidate limit.

The system exposes its filtering decisions so reviewers can understand why particular regulations were included or excluded.

## 3. Improvements With One Additional Day

**Priority 1 — Build a Labeled Evaluation Set**

Create a dataset of advertisements with expected regulatory citations.

Measure:

-   **Recall:** How many expected provisions were successfully retrieved?
-   **Precision:** How many retrieved provisions were actually relevant?

The current implementation was tuned against seven sample advertisements. This is insufficient to establish general retrieval quality or demonstrate that the system generalizes to unseen advertisements.

**Priority 2 — Add Cross-Reference Traversal**

Regulatory provisions frequently reference other sections.

For example, `1026.24(f)(2)(i)(C)` references `1026.17`.

The parser already extracts these references. The next step would be to represent them as a graph and use that graph to retrieve related provisions when appropriate.

**Priority 3 — Expand Regulatory Coverage**

Add **NCUA Part 707**, which is absent from the supplied regulatory corpus.

Its absence explains why advertisement `a3`, involving a credit union, produces no APY-disclosure finding.

This is a corpus coverage limitation rather than a retrieval failure.

## 4. Scaling to 300 Regulations With Weekly Updates

**Decision:** Introduce incremental ingestion, version tracking, and regulation-specific vector indexes.

### Applicability Filtering Becomes Essential

At the current scale, the applicability gate primarily improves relevance and efficiency.

At approximately 300 regulations, it becomes a critical scalability mechanism.

The intended reduction is from searching approximately **1,000,000 provision nodes** to a relevant subset of approximately **10,000 nodes**.

### Incremental Ingestion

The current implementation replaces the entire corpus during ingestion.

At a larger scale, each provision would receive a content hash, allowing the ingestion pipeline to identify changed provisions and regenerate embeddings only when necessary.

Assuming fewer than 1% of sections change each week, this could substantially reduce ingestion work.

### Regulatory Version History

Add `valid_from` and `valid_to` fields to preserve historical versions.

This enables the system to answer:

> Which version of the regulation was used when this advertisement was reviewed?

Version history would improve auditability and support retrospective compliance reviews.

### Partitioned Vector Search

Introduce partial HNSW indexes for individual regulatory parts.

HNSW approximate nearest-neighbor search can select its nearest candidates before applying restrictive filters. Consequently, highly selective applicability filtering may return too few results even when relevant provisions exist.

Part-specific indexes would allow searches to operate within the relevant subset more effectively.

**Tradeoff:** These changes increase database and ingestion complexity, but become worthwhile as corpus size and update frequency grow.