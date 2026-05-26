# GlobalTalent Concierge 🌍✈️

### Mastering International Onboarding with Agentic Case Orchestration

**Track:** Track 1: UiPath Maestro Case  
**Tagline:** An AI-powered "Command Center" for the modern global HR department.

---

## 📖 Project Overview
**GlobalTalent Concierge** is an agentic case management solution built on the **UiPath Platform**. It is designed to solve the high-friction, high-risk process of international employee relocation. By treating every hire as a dynamic "Case" rather than a linear task, we allow AI agents and humans to collaborate on complex, non-linear workflows.

### The Problem
* **Compliance Risks:** Manual checks of international visa rules often lead to errors.
* **Cost of Vacancy:** Every day a hire is delayed costs companies thousands in productivity.
* **Fragmented Experience:** Candidates feel lost in a sea of paperwork and outdated relocation guides.

### Our Solution
A multi-agent system orchestrated by **UiPath Maestro** that handles document ingestion, compliance reasoning, and personalized life-planning.

---

## 🤖 The Agent Squad
We have developed four specialized agents that work together:

1. **DocSentry (The Ingestion Agent)**
   * **Role:** OCR and Data Extraction.
   * **Tech:** UiPath Document Understanding.
   * **Action:** Converts raw photos of passports/visas into structured JSON data.

2. **ComplianceAgent (The Rule Checker)**
   * **Role:** Regulatory Reasoning.
   * **Tech:** **Gemma-4 (via Hugging Face)** + RAG (Retrieval-Augmented Generation).
   * **Action:** Cross-references hire data against a knowledge base of real-world immigration laws to provide a PASS/FAIL result.

3. **RelocationAgent (The Life Planner)**
   * **Role:** Personalized Onboarding.
   * **Tech:** Gemma-4 + **Tavily Live Search**.
   * **Action:** Generates a custom roadmap for the hire, including schools, housing, and local laws based on live web data.

4. **CaseOrchestrator (The Boss Agent)**
   * **Role:** Workflow Management.
   * **Tech:** **UiPath Maestro Case Management**.
   * **Action:** Manages the stages of the case, handles interruptions, and triggers Human-in-the-Loop checkpoints.

---

## 🛠️ Technical Architecture & Stack
* **Orchestration Layer:** UiPath Maestro (Case Management) used to handle long-running, non-linear stages.
* **Intelligence Layer:** Python scripts running **Gemma-4** for NLP reasoning and **Tavily API** for real-time web search.
* **Knowledge Base:** Vector database containing scraped government immigration rules.
* **Coding Agents:** Developed using **UiPath for Coding Agents** (Gemini/Claude) to build high-performance Python integrations.
* **Human-in-the-Loop:** UiPath Action Center for mandatory HR approvals with AI-generated **Confidence Scores**.

---

## ✨ Key Features
* **Agentic Reasoning:** Unlike simple bots, our agents "reason" through compliance rules and explain their logic to the human user.
* **Dynamic Staging:** Maestro allows the Relocation stage to proceed even if Document Verification is pending a human review.
* **Live Knowledge:** Agents pull current data from the web, ensuring relocation advice is never outdated.
* **Explainable AI:** Every decision comes with a reasoning summary and a confidence score to build trust with HR specialists.

---

## 👥 User Stories

### Persona: Sarah (The New Hire)
> "I want instant feedback on my document uploads so I don't lose time, and I want a relocation plan that actually knows where my kids can go to school."

### Persona: Marcus (The HR Specialist)
> "I want to spend my time on complex human issues, not checking passport expiry dates. I want the AI to flag the risks so I can make the final call."

---

## 🚀 How to Run the Project
1. **Clone the Repo:** `git clone https://github.com/yourusername/GlobalTalent-Concierge.git`
2. **Configure APIs:** Add your `HF_TOKEN` and `TAVILY_API_KEY` to the `.env` file.
3. **Open in UiPath:** Open `Main.xaml` in UiPath Studio (2024.10+).
4. **Deploy Maestro:** Import the provided JSON case template into your UiPath Automation Cloud tenant.
5. **Start Case:** Trigger a new case from the Orchestrator or the provided Web Form.

---

## 🏆 Hackathon Checklist
- [x] Built on **UiPath Maestro Case** (Track 1).
- [x] Uses **Coding Agents** for Python integration (Bonus Points).
- [x] Includes **Human-in-the-Loop** via Action Center.
- [x] Integrated **external LLMs** (Gemma-4 via Hugging Face).
- [x] Working prototype demo video included.

---

## 📜 License
This project is licensed under the **MIT License** - see the LICENSE file for details.

---
**Built for the UiPath AgentHack 2026**