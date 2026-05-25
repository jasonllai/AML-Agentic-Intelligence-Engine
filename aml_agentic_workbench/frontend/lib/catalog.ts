import type { AgentName, SupportedRole, TaskType } from "@/types/api";

export const roles: Record<SupportedRole, { label: string; focus: string; tasks: string[]; reportStyle: string }> = {
  data_scientist: {
    label: "Data Scientist",
    focus: "Feature behaviour, model drivers, anomaly patterns, and analytical next steps.",
    tasks: ["Model risk explanation", "Feature quality review", "Full intelligence report"],
    reportStyle: "Technical, feature-rich, and explicit about model limitations."
  },
  investigator: {
    label: "Investigator",
    focus: "Customer behaviour, evidence assembly, and careful case-oriented summaries.",
    tasks: ["Investigator summary", "Customer behaviour analysis", "Typology mapping"],
    reportStyle: "Plain AML language with evidence tables and review-ready findings."
  },
  model_validator: {
    label: "Model Validator",
    focus: "Auditability, uncertainty, feature governance, and validation concerns.",
    tasks: ["Model validation review", "Model risk explanation", "Feature quality review"],
    reportStyle: "Governance-forward with caveats, limitations, and validation tests."
  },
  compliance_strategy: {
    label: "Compliance Strategy",
    focus: "Typology coverage, policy alignment, and careful regulatory language.",
    tasks: ["Compliance typology review", "Typology mapping", "Full intelligence report"],
    reportStyle: "Concise policy alignment with citations and non-conclusive language."
  }
};

export const tasks: Record<TaskType, string> = {
  customer_behaviour_analysis: "Customer behaviour analysis",
  model_risk_explanation: "Model risk explanation",
  typology_mapping: "Typology mapping",
  feature_quality_review: "Feature quality review",
  full_intelligence_report: "Full intelligence report",
  investigator_summary: "Investigator summary",
  model_validation_review: "Model validation review",
  compliance_typology_review: "Compliance typology review"
};

export const agents: Record<AgentName, { label: string; why: string; sections: string[] }> = {
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
  evidence_assembly_agent: {
    label: "Evidence Assembly",
    why: "Builds the governed report from only the agents that actually ran.",
    sections: ["Executive Summary", "Limitations and Uncertainty", "Recommended Analytical Next Steps"]
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
  if (role === "model_validator" && task === "model_validation_review") {
    return ["model_explanation_agent", "feature_critic_agent", "evidence_assembly_agent", "judge_panel_agent", "guardrail_agent"];
  }
  if (role === "compliance_strategy" && task === "compliance_typology_review") {
    return ["typology_mapping_agent", "evidence_assembly_agent", "judge_panel_agent", "guardrail_agent"];
  }
  return ["evidence_assembly_agent", "judge_panel_agent", "guardrail_agent"];
}
