# Student 2 project — Native Windows PostgreSQL

Start with `README_VI.md`. This version uses PostgreSQL installed directly on Windows and Python in VS Code; it does not require Docker. Vault is a separate local service for the encryption part.

A fallback Docker stack lives at the repository root (`docker-compose.yml`) for team testing while the production-like Vault + TLS infrastructure is being built. It is documented in `docs/infra/local-stack.md`; it does not replace the native Windows instructions.
