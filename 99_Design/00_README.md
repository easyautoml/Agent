# Documentation Guide

This set covers everything from product intent to implementation detail.
Read in order for a full mental model, or jump to the file you need.

---

## Reading Order

| File | What it answers | Best for |
|---|---|---|
| [01_product_overview.md](01_product_overview.md) | What is this, who is it for, what is V1 scope | New team members, stakeholders |
| [02_solution_overview.md](02_solution_overview.md) | Overall architecture, layers, how they fit | Anyone joining the project |
| [03_runtime_flows.md](03_runtime_flows.md) | What happens at runtime for each user action | Engineers, QA |
| [04_source_code_structure.md](04_source_code_structure.md) | Folder tree and what lives where | Engineers |
| [05_components.md](05_components.md) | Responsibility, inputs, outputs for each layer | Engineers building or extending |
| [06_data_and_storage.md](06_data_and_storage.md) | DB schema, vector store, filesystem, file lifecycle | Engineers, DBAs |
| [07_operations.md](07_operations.md) | Config, commands, error handling, NFRs | Operators, DevOps |
| [08_open_questions.md](08_open_questions.md) | Unresolved decisions | Tech leads, product owners |

---

## Source Documents

This set was derived from two source documents:

- `REQ.md` — original requirements specification (v1.2)
- `Final_Design.md` — current source code structure and design

Where they conflict, `Final_Design.md` wins — it reflects the current codebase (PostgreSQL, multi-channel, CrewAI).
