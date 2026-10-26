export type Verdict = "meets" | "violates" | "unclear" | "not_applicable";

export interface Finding {
  ref: string;
  citation: string;
  regulation: string;
  agency: string;
  heading: string;
  kind: string;
  url: string;
  as_of: string;
  provision_text: string;
  ancestor_context: string;
  applies: boolean;
  verdict: Verdict;
  reason: string;
  ad_evidence: string;
  caveat: string;
  is_supporting_context: boolean;
  retrieval_score: number;
  why_retrieved: string[];
}

export interface CheckResponse {
  mode: "verdicts" | "retrieval_only";
  findings: Finding[];
  overall_note: string;
  notices: string[];
  dropped_findings: { ref?: string; citation?: string; reason: string }[];
  gate: {
    parts_in_scope: string[];
    included: string[];
    excluded: string[];
    failed_open: boolean;
  };
  topic_flags: Record<string, boolean>;
  candidate_count: number;
  collapsed_ancestors: string[];
}

export interface Health {
  status: string;
  provisions: number;
  verdicts_enabled: boolean;
  model: string | null;
  regulations: {
    regulation: string;
    agency: string;
    part: string;
    nodes: number;
    as_of: string | null;
  }[];
}

export interface SampleAd {
  id: string;
  advertiser: { name: string; type: string; fdic_insured?: boolean; ncua_insured?: boolean };
  channel: string;
  text: string;
  context?: string;
}
