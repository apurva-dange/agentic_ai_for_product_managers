# Agentic AI for Product Managers: My Toolkit

> This repository contains my personal frameworks, guides, and resources for Product Managers on how to effectively build, manage, and scale products using Agentic AI.

As a Product Manager / Founder / Technologist, I'm focused on bridging the gap between complex AI capabilities and real-world user value. This repo is where I document and share my methodologies for a new generation of AI-native products.


## 💡 My Product Philosophy for Agentic AI

I believe successful Agentic AI products are built on three pillars:

* **Precise Job-to-be-Done (JTBD):** Agents must be designed to accomplish a specific, high-value user goal, not just be a "wrapper" for an LLM.
* **Trust Through Reliability:** User adoption is 100% dependent on the agent's reliability. This means focusing on guardrails, validation, and clear error handling from day one.
* **Rapid, Data-Driven Iteration:** Building an agent is a process of discovery. My approach centers on launching a minimal viable agent (MVA), defining the right success KPIs, and iterating relentlessly.

## 🧩 Portfolio Projects

Hands-on projects that put the philosophy above into practice:

* **[Product Discovery Agent](product-discovery-agent/)** - A local, explainable AI agent that evaluates a feature idea (e.g. "Should we build dark mode?") by planning what evidence it needs, calling tools to gather customer feedback, usage analytics, competitor research, engineering effort, and risk data, and only then producing a structured recommendation. Built to demonstrate the full agentic tool-use loop (`tool_use` → execute → observe → continue → `end_turn`), including deliberate bug-mode demonstrations of what goes wrong when message history or stopping conditions are implemented incorrectly. Runs with no API key required. See its [README](product-discovery-agent/README.md) for details.

## 🗓️ What's Coming Next

This repository is actively maintained. Here is a preview of topics I'll be adding soon:

* How to use Agentic AI in your day-to-day Product Manager career.
* Frameworks on using agents to effectively save time and automate PM tasks.
* Awesome code-free n8n projects for easy workflow automation.
