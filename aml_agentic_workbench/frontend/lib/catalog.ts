import type { AgentName, SupportedRole, TaskType } from "@/types/api";

export const primaryRoles: SupportedRole[] = ["data_scientist", "investigator"];

export const roles: Record<
  SupportedRole,
  {
    label: string;
    focus: string;
    tasks: string[];
    reportStyle: string;
    defaultTask: TaskType;
    defaultCustomerId: string;
    defaultQuery: string;
    actions: TaskType[];
  }
> = {
  data_scientist: {
    label: "Data Scientist",
    focus: "Model-driven AML detection, population scoring, threshold rationale, and investigator handoff.",
    tasks: ["Generate model-driven investigation candidates"],
    reportStyle: "Model run summary, ranked candidates, feature drivers, limitations, and handoff package.",
    defaultTask: "generate_model_driven_candidates",
    defaultCustomerId: "",
    defaultQuery: "Generate ranked model-driven AML investigation candidates for investigator handoff.",
    actions: ["generate_model_driven_candidates"]
  },
  investigator: {
    label: "Investigator",
    focus: "Case-level review of model-prioritized candidates, typology indicators, disposition, and feedback.",
    tasks: ["Investigate model-prioritized candidate"],
    reportStyle: "Evidence review, careful typology mapping, disposition, and model feedback.",
    defaultTask: "investigate_model_prioritized_candidate",
    defaultCustomerId: "SYNID0100000167",
    defaultQuery: "Investigate this model-prioritized candidate and return case feedback.",
    actions: ["investigate_model_prioritized_candidate"]
  }
};

export const tasks: Record<TaskType, string> = {
  generate_model_driven_candidates: "Generate model-driven investigation candidates",
  investigate_model_prioritized_candidate: "Investigate model-prioritized candidate",
  customer_behaviour_analysis: "Customer behaviour analysis",
  model_risk_explanation: "Model risk explanation",
  typology_mapping: "Typology mapping",
  feature_quality_review: "Feature quality review",
  full_intelligence_report: "Full intelligence report",
  investigator_summary: "Investigator summary"
};

export const agents: Record<AgentName, { label: string; why: string; sections: string[] }> = {
  candidate_ranking_agent: {
    label: "Candidate Ranking",
    why: "Scores the modeled population with four anomaly models and produces guarded candidate explanations.",
    sections: ["Four-Model Candidate Ranking", "Guarded Candidate Explanations"]
  },
  case_investigation_agent: {
    label: "Case Investigation",
    why: "Turns candidate context into disposition, missing evidence, and model feedback.",
    sections: ["Investigator Case Review", "Model Feedback"]
  },
  transaction_behaviour_agent: {
    label: "Transaction Behaviour",
    why: "Profiles velocity, counterparties, cross-border exposure, and baseline deviations.",
    sections: ["Customer Behaviour Overview", "Evidence Table"]
  },
  model_explanation_agent: {
    label: "Model Explanation",
    why: "Explains model-driven risk signals while stating model score is not proof of suspicious activity.",
    sections: ["Model Risk Explanation"]
  },
  typology_mapping_agent: {
    label: "Typology Mapping",
    why: "Maps evidence to AML typology indicators with careful, citation-backed language.",
    sections: ["Typology Mapping"]
  },
  feature_critic_agent: {
    label: "Feature Critic",
    why: "Critiques feature quality, leakage risk, and PySpark feature opportunities.",
    sections: ["Feature Quality Review"]
  },
  supervisor_planner_agent: {
    label: "Supervisor Planner",
    why: "Chooses the next bounded investigation action based on gathered and missing evidence.",
    sections: ["Planner Decisions", "Missing Evidence"]
  },
  evidence_assembly_agent: {
    label: "Evidence Assembly",
    why: "Builds the governed report from only the agents that actually ran.",
    sections: ["Executive Summary", "Limitations and Uncertainty", "Recommended Analytical Next Steps"]
  },
  report_critic_agent: {
    label: "Report Critic",
    why: "Reviews the draft report once and requests refinement only when it improves auditability.",
    sections: ["Critic Review", "Refinement Instruction"]
  },
  judge_panel_agent: {
    label: "Judge Panel",
    why: "Scores faithfulness, citations, compliance, typology, data science quality, and usefulness.",
    sections: ["Judge Score Cards"]
  },
  guardrail_agent: {
    label: "Guardrail Review",
    why: "Applies compliance safety checks before final response delivery.",
    sections: ["Guardrail Status", "Audit Metadata"]
  }
};

export function defaultRoute(role: SupportedRole, task: TaskType): AgentName[] {
  if (role === "data_scientist" && task === "generate_model_driven_candidates") {
    return ["candidate_ranking_agent", "guardrail_agent"];
  }
  if (role === "investigator" && task === "investigate_model_prioritized_candidate") {
    return [
      "supervisor_planner_agent",
      "transaction_behaviour_agent",
      "typology_mapping_agent",
      "case_investigation_agent",
      "evidence_assembly_agent",
      "report_critic_agent",
      "judge_panel_agent",
      "guardrail_agent"
    ];
  }
  if (task === "full_intelligence_report") {
    return [
      "transaction_behaviour_agent",
      "model_explanation_agent",
      "typology_mapping_agent",
      "feature_critic_agent",
      "evidence_assembly_agent",
      "judge_panel_agent",
      "guardrail_agent"
    ];
  }
  if (role === "data_scientist" && task === "model_risk_explanation") {
    return [
      "transaction_behaviour_agent",
      "model_explanation_agent",
      "feature_critic_agent",
      "evidence_assembly_agent",
      "judge_panel_agent",
      "guardrail_agent"
    ];
  }
  if (role === "investigator" && task === "investigator_summary") {
    return [
      "transaction_behaviour_agent",
      "typology_mapping_agent",
      "evidence_assembly_agent",
      "judge_panel_agent",
      "guardrail_agent"
    ];
  }
  return ["evidence_assembly_agent", "judge_panel_agent", "guardrail_agent"];
}
