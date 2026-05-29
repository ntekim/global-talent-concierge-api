import json


def extraction_prompt(raw_text: str) -> str:
    return f"""Extract the following fields from the text below and return a JSON object.
Fields: full_name, document_type, document_number, issue_date, expiry_date, nationality, issuing_country.
If a field cannot be found, set it to null.

Document text:
{raw_text}"""


def compliance_system_prompt() -> str:
    return """You are a visa compliance expert. Given visa rules and a candidate's document data, determine if the document is compliant. Always output valid JSON matching the requested schema.

Scoring rubric for confidence_score:
- 90-100: All required documents present and valid. Clear PASS.
- 70-89: Most documents present with minor issues (e.g., formatting, name mismatch). Likely PASS after corrections.
- 50-69: Some required documents missing. Needs human review.
- 30-49: Significant gaps in documentation. Likely non-compliant.
- 0-29: Critical documents missing or all documents expired. Cannot proceed."""


def compliance_prompt(combined_context: str, context_note: str, document_data: dict) -> str:
    return f"""Based on the visa rules provided and the document data provided, determine if this person's document is compliant. Return a JSON object with these fields: status (PASS or FAIL), confidence_score (a number between 0 and 100), reasons (a list of strings explaining why it passed or failed), missing_documents (a list of any documents that are missing or expired), recommendation (a short string telling the HR specialist what to do next)

Visa rules context:
{combined_context or "No visa rules context available. Assess based on general knowledge."}
{context_note}

Document data:
{json.dumps(document_data, indent=2)}"""


def relocation_system_prompt() -> str:
    return "You are a relocation expert concierge. Generate warm, friendly, and detailed personalized relocation guides for new hires moving abroad."


def relocation_prompt(hire_profile: dict, combined_context: str, context_note: str) -> str:
    first_name = hire_profile.get("full_name", "there").split()[0]
    return f"""Based on the hire profile and the local information provided, generate a warm, friendly, and detailed personalized relocation guide. Include sections for: recommended neighbourhoods, schools near those neighbourhoods if the hire has children, estimated monthly living costs based on the budget, top 3 important local laws or cultural tips to know, and a 30 day settling in checklist. Address the guide directly to the hire by their first name.

Hire profile:
{json.dumps(hire_profile, indent=2)}

Local information:
{combined_context or "No local information available. Use your general knowledge to provide helpful advice."}
{context_note}"""
