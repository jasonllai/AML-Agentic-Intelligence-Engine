"""Investigator-facing definitions for engineered AML model features."""

# ruff: noqa: E501

from dataclasses import dataclass


@dataclass(frozen=True)
class FeatureDefinition:
    """Human-readable metadata for one engineered model feature."""

    display_name: str
    definition: str
    engineering_formula: str
    investigator_interpretation: str
    suggested_evidence_to_review: str


def _transaction_amount_feature(display_name: str, definition: str, formula: str) -> FeatureDefinition:
    return FeatureDefinition(
        display_name=display_name,
        definition=definition,
        engineering_formula=formula,
        investigator_interpretation=(
            "A high value can indicate concentration of transaction value that may warrant comparison with the "
            "customer profile, expected activity, source of funds, and transaction purpose."
        ),
        suggested_evidence_to_review=(
            "Review the largest source transactions, direction, counterparties, channels, dates, and KYC profile "
            "supporting the aggregate value."
        ),
    )


def _channel_feature(channel_label: str, *, ratio: bool) -> FeatureDefinition:
    metric = "ratio" if ratio else "count"
    return FeatureDefinition(
        display_name=f"{channel_label} channel {metric}",
        definition=f"Customer-level {metric} of transactions through the {channel_label} channel.",
        engineering_formula=(
            f"number of {channel_label} transactions / total transaction count"
            if ratio
            else f"count of transactions where channel = {channel_label}"
        ),
        investigator_interpretation=(
            f"An unusual {channel_label} channel pattern may indicate that activity is concentrated in a delivery "
            "channel that should be reviewed against expected customer behaviour."
        ),
        suggested_evidence_to_review=(
            f"Review {channel_label} transactions, counterparties, transaction purpose, recurrence, and whether the "
            "channel use aligns with the customer profile."
        ),
    )


FEATURE_DEFINITIONS: dict[str, FeatureDefinition] = {
    "txn_count_total": FeatureDefinition(
        "Total transaction count",
        "Total number of transactions observed for the customer in the modeled period.",
        "group transactions by customer_id and count rows",
        "A high count can indicate unusual activity volume; a low count with high value can indicate concentrated movement.",
        "Review the transaction timeline, frequency changes, and whether activity volume matches expected customer usage.",
    ),
    "amount_sum_total": _transaction_amount_feature(
        "Total transaction amount",
        "Sum of all transaction amounts in CAD for the customer in the modeled period.",
        "sum(amount_cad) grouped by customer_id",
    ),
    "amount_mean_total": _transaction_amount_feature(
        "Average transaction amount",
        "Average CAD amount across the customer's transactions.",
        "mean(amount_cad) grouped by customer_id",
    ),
    "amount_max_total": _transaction_amount_feature(
        "Maximum transaction amount",
        "Largest single CAD transaction amount observed for the customer.",
        "max(amount_cad) grouped by customer_id",
    ),
    "amount_std_total": FeatureDefinition(
        "Transaction amount variability",
        "Standard deviation of the customer's CAD transaction amounts.",
        "standard_deviation(amount_cad) grouped by customer_id; missing standard deviation is filled with 0",
        "High variability means the customer has a wider spread of transaction sizes, which can help investigators find spikes or irregular bursts.",
        "Review whether high-value transactions are isolated spikes, recurring behaviour, or aligned with documented customer activity.",
    ),
    "debit_amount_sum": _transaction_amount_feature(
        "Total debit amount",
        "Sum of outgoing/debit transaction amounts in CAD.",
        "sum(amount_cad where direction = debit) grouped by customer_id",
    ),
    "credit_amount_sum": _transaction_amount_feature(
        "Total credit amount",
        "Sum of incoming/credit transaction amounts in CAD.",
        "sum(amount_cad where direction = credit) grouped by customer_id",
    ),
    "debit_credit_amount_ratio": FeatureDefinition(
        "Debit-to-credit amount ratio",
        "Ratio of outgoing debit value to incoming credit value.",
        "debit_amount_sum / (credit_amount_sum + 1.0)",
        "An unusual imbalance can indicate that incoming and outgoing value patterns differ from the modeled population.",
        "Review source and use of funds, linked debit/credit transactions, and whether flows are economically coherent.",
    ),
    "high_value_txn_count": FeatureDefinition(
        "High-value transaction count",
        "Count of transactions with CAD amount greater than or equal to 10,000.",
        "count(transactions where amount_cad >= 10000) grouped by customer_id",
        "A high count points investigators to repeated high-value activity that should be checked against expected profile and purpose.",
        "Review each high-value transaction, counterparties, timing, supporting rationale, and customer profile fit.",
    ),
    "cash_txn_ratio": FeatureDefinition(
        "Cash transaction ratio",
        "Share of the customer's transactions identified as cash transactions.",
        "mean(is_cash) grouped by customer_id",
        "A high ratio can indicate reliance on cash activity and should be compared with occupation, business type, and expected cash usage.",
        "Review cash transaction dates, amounts, branch/channel context, and KYC information about expected cash activity.",
    ),
    "cross_border_txn_ratio": FeatureDefinition(
        "Cross-border transaction ratio",
        "Share of the customer's transactions identified as cross-border.",
        "mean(is_cross_border) grouped by customer_id",
        "A high ratio can indicate international movement that should be checked against expected geography and customer profile.",
        "Review destination/source jurisdictions, counterparties, customer profile, and documented international activity rationale.",
    ),
    "channel_diversity": FeatureDefinition(
        "Channel diversity",
        "Number of distinct transaction channels used by the customer.",
        "nunique(channel) grouped by customer_id",
        "High diversity may indicate broader channel usage; low diversity with high value may indicate concentration in one channel.",
        "Review whether channel usage patterns are expected for the customer type and whether any channel concentration needs explanation.",
    ),
    "active_days_span": FeatureDefinition(
        "Active transaction date span",
        "Number of days between the customer's first and last observed transaction.",
        "max(transaction_datetime) - min(transaction_datetime), in days, grouped by customer_id",
        "A short span with high value can indicate compressed activity; a long span gives context for whether volume is sustained.",
        "Review transaction timing, bursts, dormancy, and whether activity changed after onboarding or other events.",
    ),
    "days_since_last_txn": FeatureDefinition(
        "Days since last transaction",
        "Days between the global latest transaction date and the customer's latest observed transaction.",
        "global_max(transaction_datetime) - customer_max(transaction_datetime), in days",
        "A large value may indicate dormancy; a small value means activity is recent and may need timely review if other signals are high.",
        "Review recent transactions, dormant-to-active changes, and whether recent activity aligns with expected customer behaviour.",
    ),
    "channel_count_abm": _channel_feature("ABM", ratio=False),
    "channel_ratio_abm": _channel_feature("ABM", ratio=True),
    "channel_count_card": _channel_feature("card", ratio=False),
    "channel_ratio_card": _channel_feature("card", ratio=True),
    "channel_count_cheque": _channel_feature("cheque", ratio=False),
    "channel_ratio_cheque": _channel_feature("cheque", ratio=True),
    "channel_count_eft": _channel_feature("EFT", ratio=False),
    "channel_ratio_eft": _channel_feature("EFT", ratio=True),
    "channel_count_emt": _channel_feature("EMT", ratio=False),
    "channel_ratio_emt": _channel_feature("EMT", ratio=True),
    "channel_count_westernunion": _channel_feature("Western Union", ratio=False),
    "channel_ratio_westernunion": _channel_feature("Western Union", ratio=True),
    "channel_count_wire": _channel_feature("wire", ratio=False),
    "channel_ratio_wire": _channel_feature("wire", ratio=True),
    "kyc_customer_type_individual": FeatureDefinition(
        "Individual customer flag",
        "Indicator that the modeled customer is an individual customer.",
        "1 when customer appears in individual KYC records, otherwise 0",
        "Customer type affects expected behaviour and should shape how investigators interpret transaction activity.",
        "Review individual KYC profile, occupation, income, onboarding date, and expected account activity.",
    ),
    "kyc_customer_type_smallbusiness": FeatureDefinition(
        "Small-business customer flag",
        "Indicator that the modeled customer is a small-business customer.",
        "1 when customer appears in small-business KYC records, otherwise 0",
        "Customer type affects expected activity scale, channels, and counterparties.",
        "Review business type, sales, employee count, onboarding date, and expected transaction pattern.",
    ),
    "kyc_income": FeatureDefinition(
        "Individual KYC income",
        "Reported income for individual customers.",
        "income from individual KYC records; 0 for non-individual records or missing values",
        "Transaction value that is high relative to income can warrant profile comparison.",
        "Review income, occupation, source of funds, and whether transaction value aligns with the KYC profile.",
    ),
    "kyc_sales": FeatureDefinition(
        "Small-business KYC sales",
        "Reported sales for small-business customers.",
        "sales from small-business KYC records; 0 for non-small-business records or missing values",
        "Transaction value should be interpreted against the expected business scale.",
        "Review sales, business activity, counterparties, and whether transaction volume aligns with business operations.",
    ),
    "kyc_employee_count": FeatureDefinition(
        "Small-business employee count",
        "Reported employee count for small-business customers.",
        "employee_count from small-business KYC records; 0 for non-small-business records or missing values",
        "Employee count can contextualize expected business transaction scale and payroll-like activity.",
        "Review business profile, payroll/vendor activity, transaction volume, and consistency with stated operations.",
    ),
    "kyc_onboard_age_days": FeatureDefinition(
        "Customer onboarding age",
        "Number of days between onboarding and the reference date used by feature engineering.",
        "reference date - onboard_date, in days",
        "Newer relationships with high or rapidly changing activity may require closer profile validation.",
        "Review onboarding information, expected activity, early account behaviour, and any changes since onboarding.",
    ),
}


def get_feature_definition(feature_name: str) -> FeatureDefinition:
    """Return a known feature definition or a safe explicit fallback."""
    if feature_name in FEATURE_DEFINITIONS:
        return FEATURE_DEFINITIONS[feature_name]
    return FeatureDefinition(
        display_name=feature_name.replace("_", " ").title(),
        definition=f"Engineered model feature named {feature_name}.",
        engineering_formula="Feature formula is not documented in the local feature dictionary.",
        investigator_interpretation=(
            "The feature was selected by the model explanation layer, but its business meaning needs data science review."
        ),
        suggested_evidence_to_review=(
            "Review the source feature engineering code and supporting transactions before using this driver in a case review."
        ),
    )
