# ResearchVault MVP

A working early-stage academic discovery prototype. It searches OpenAlex, Crossref and Europe PMC, deduplicates records, offers DOI metadata lookup, discovers some open-access locations via OpenAlex, and saves papers to a local SQLite library.

## Important scope and limitations

This is an MVP prototype, not the complete commercial product described in the product blueprint.
- No user accounts or multi-user access controls yet.
- Saved papers are stored in one SQLite database. Do not expose this version publicly for multiple users until authentication and per-user authorisation are implemented.
- No paid subscriptions or payment processing.
- No AI literature synthesis / PDF RAG yet.
- DOI lookup checks Crossref metadata only. It does not establish scientific quality or prove a paper is not retracted.
- Search results depend on the external scholarly APIs and their coverage.
- Full-text links are surfaced where a source provides them; the app does not bypass paywalls or download restricted content.

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

API health: http://127.0.0.1:8000/api/health

## Deploy

1. Create a GitHub repository and push this project.
2. Create a Render account.
3. Create a new Blueprint and connect the repository containing `render.yaml`.
4. Review the plan and persistent disk costs before confirming deployment.
5. After deployment, test `/api/health` and perform several known-publication searches.
6. Do not enable public multi-user use until authentication, per-user database isolation, rate limiting, privacy policy, terms, backups and security review are implemented.

The included Render configuration uses a persistent disk for SQLite. For a commercial multi-user product, migrate to managed PostgreSQL before launch.

## Before accepting payments

Create and verify a merchant account in your own business name, confirm supported Zimbabwean payout and settlement arrangements, and integrate a payment provider using server-side webhooks. Never put payment secrets in frontend code. Do not advertise a paid plan until payment, cancellation, refunds, tax and customer support flows have been tested.

## Suggested next engineering milestones

1. Supabase Auth or equivalent authentication.
2. PostgreSQL schema with per-user row-level security.
3. Persistent scholarly search cache and source provenance.
4. More robust DOI and metadata reconciliation.
5. Retraction/correction status checks from reliable sources.
6. Full-text rights and licence handling.
7. Citation formatting and RIS/BibTeX exports.
8. Secure PDF ingestion and evidence-grounded RAG.
9. Subscription billing and usage metering.
10. Security, privacy and load testing.
