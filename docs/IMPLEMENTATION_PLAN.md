# MarketMinder AI: Implementation Plan

A fully automated company run by orchestrated AI agents and controlled from a mission control interface.

## 0. Assumptions (swap these freely)

| # | Assumption | Effect if changed |
|---|-----------|-------------------|
| A1 | Operator is a South African sole proprietor or (Pty) Ltd. Currency is ZAR. | Thresholds in section 7 are stated in ZAR; change the figures, not the logic. |
| A2 | Starting capital is **R25,000** and one human operator working about 5 hours/week (approvals and escalations only). | A smaller budget lengthens the runway-based kill trigger; a larger one raises paid-acquisition limits. |
| A3 | Primary market is South African and African SMBs (1-50 staff) in retail, hospitality, professional services and e-commerce. Secondary market is global English-speaking SMBs. | Source lists and pricing move; the architecture does not. |
| A4 | Card payments are taken through a processor that supports South African merchants (Paystack or PayFast). Stripe's direct merchant onboarding is not available in South Africa, so the current Stripe code needs an adapter or a Stripe-supported entity (see section 8). | Payment adapter only. |
| A5 | LLM spend is capped at R3,000/month; hosting (Vercel + Supabase free/low tiers) at under R500/month. | Hard budget limits in section 6. |
| A6 | All customer data is personal information under POPIA, and outreach falls under the CPA, ECTA and POPIA direct-marketing rules. | Section 9. |

## 1. The business

**MarketMinder AI sells subscription market-intelligence to small businesses**: a monthly competitor and market brief, on-demand analysis questions, and trend alerts, delivered by dashboard and email.

Why it suits full automation:
- **The product is information, not goods.** There is no inventory, shipping or on-site service. Marginal cost per customer is a few rand of LLM and data fees.
- **Production, delivery and billing are fully digital**, so every step can be an API call.
- **Quality is checkable.** Reports can be generated, fact-checked against cited sources by a second agent, and scored before delivery.
- **Demand is repeatable.** SMBs have a standing need ("what are competitors charging, what's changing?") that suits a recurring subscription.

Pricing (monthly, ZAR, adjustable): Starter R299 (1 brief + 5 questions), Professional R899 (4 briefs + 30 questions + alerts), Enterprise R2,999 (custom segments, API access). Break-even is about 12 Starter customers against fixed costs.

## 2. Agent architecture

One orchestrator (**Mission Control**, `core/mission_control.py`) and six specialists (`agents/`), all inheriting from `BaseAgent`. Agents never talk to each other directly; every task passes through Mission Control, which routes it, tracks health and enforces limits.

| Agent | Responsibility | Representative tasks |
|-------|---------------|----------------------|
| **Market Scout** | Collects trends, competitor pricing and news from permitted public sources. | `scrape_trends`, `analyze_competitor`, `check_pricing`, `generate_market_report` |
| **Product Builder** | Turns research into the deliverables customers pay for. | `generate_report`, `answer_query`, `extract_insight`, `summarize_data` |
| **Marketing Engine** | Produces content, builds the audience, and generates inbound leads. | `create_content`, `segment_audience`, `run_campaign`, `analyze_performance` |
| **Sales Closer** | Qualifies leads, handles objections, books demos, sends proposals, and follows up. | `qualify_lead`, `handle_objection`, `create_proposal`, `analyze_pipeline` |
| **Customer Success** | Answers support tickets, detects churn risk and runs retention outreach. | `categorize_ticket`, `generate_response`, `detect_churn_risk`, `resolve_ticket` |
| **Finance Controller** | Subscriptions, invoices, payment webhooks, cash and unit-economics reporting. | `create_invoice`, `billing_check`, `calculate_metrics` |

**Orchestration rules**
1. **Routing:** a fixed task-type to agent table in Mission Control. Unknown task types are rejected, not guessed.
2. **Execution:** every task has a priority (1-10), a timeout (default 300 s) and a result or error recorded on the task.
3. **Health:** each agent reports status (`idle`, `processing`, `error`, `offline`, `needs_attention`), completed and failed counts and queue length. A worker mirrors this into Supabase every 30 s (`scripts/worker.py`).
4. **Shared state:** Supabase Postgres is the single source of truth. Agents read and write tables; the dashboard reads the same tables.
5. **Scheduling:** a Vercel cron every 10 minutes processes queued analysis requests and recomputes health. The long-running worker runs the agents' own loops.
6. **Human gates** (section 4) sit between agents and any irreversible or external action.

## 3. Mission control UI

**What the operator sees** (the `/dashboard` page)
- **Health score (0-100)** with label: Optimal (80+), Yellow (60-79), Red (40-59), Critical (below 40).
- **Headline metrics:** MRR, churn rate, cash runway (days), active agents.
- **Agent panel:** each agent's status, tasks completed and errors.
- **Billing:** subscription tier, status and renewal date.
- **Analysis history:** requests, status and results.

**Controls the operator has**

Built:
- Sign in/out; submit analyses; subscribe (checkout).
- Agent state changes through the authenticated API only.

Required for the plan (not built yet, see section 10):
- **Pause/resume per agent** and a global **pause all**.
- **Approval queue** for gated actions (section 4), with approve, edit and reject.
- **Kill switch:** wind-down button and automatic triggers.
- **Budget panel:** spend vs. cap per agent, with an editable cap.
- **Audit log:** every external action (email sent, payment, refund) with the agent, input and output.
- **Review-point panel:** pass/fail status for each checkpoint in section 7.

## 4. Operating model

### Finance
- **Revenue:** subscriptions only. Processor webhooks create the customer, record each payment as a transaction, and recompute MRR (`/api/billing/webhook`).
- **Cash:** Finance Controller tracks balance, burn (LLM + hosting + processor fees) and runway = cash / daily burn.
- **Controls:** refunds over R500 and any new payee need human approval. Agents have no payout or transfer capability. Monthly reconciliation of processor payouts against the transactions table.
- **Tax and compliance:** VAT registration once turnover passes R1m in 12 months (voluntary earlier if useful); keep invoices that meet SARS requirements. The operator files returns; the system supplies the reports.

### Sales
- **Motion:** self-serve first (landing page to checkout). Sales Closer handles inbound leads only: qualifies, answers objections, offers a demo or trial, and sends a proposal for Enterprise.
- **Pipeline:** `leads` table stages: prospect, qualified, demo, proposal, closed won/lost.
- **Gates:** discounts above 20% and any custom contract need approval.

### Marketing
- **Channels:** SEO content, LinkedIn and X posts, a free sample brief as a lead magnet, and partnerships with accountants and business associations.
- **Cold outreach is limited by law (section 9):** opt-in lists, B2B contacts with a legitimate-interest basis, a working opt-out on every message, and a daily send cap.
- **Gates:** the first post of each new campaign type is approved by the operator; after 10 approved without edits, that type can auto-publish with sampling.
- **Paid ads:** off until MRR passes the Week 6 gate; then at most 15% of MRR.

### Product
- **Pipeline:** Market Scout collects, Product Builder drafts, a verification pass checks every claim against a stored source, and the report is scored before delivery.
- **Quality bar:** reports with uncited numerical claims or a verification score below threshold are blocked and queued for review.
- **Honesty:** each report states its sources, date and limits. It never presents generated content as human-written research or fabricates data, quotes or testimonials.

### Customer support
- **Flow:** ticket in, categorized, answered by Customer Success from the knowledge base, closed on customer confirmation.
- **Escalate to the human:** billing disputes, legal or complaint language, data-deletion requests, anything the agent rates below 0.7 confidence, and any second contact on the same issue.
- **Proactive:** churn-risk detection (usage drop, failed payment, negative sentiment) triggers a retention message.
- **SLA:** first response within 1 hour for automated replies; human escalations within 1 business day.

## 5. Autonomy levels

| Level | Actions | Rule |
|-------|---------|------|
| 0: free | Research, drafting, analysis, internal reports | Fully automatic |
| 1: sampled | Support replies, content posts, report delivery | Auto, with 10% human sampling and an audit log |
| 2: approval | Outbound sales email, refunds over R500, pricing changes, new vendors, legal/complaint replies | Operator approves first |
| 3: forbidden | Moving money out, signing contracts, changing bank details, deleting customer data without request, any action outside Section 9 | Not possible for agents |

## 6. Budget caps

| Item | Monthly cap |
|------|------------|
| LLM API | R3,000 (alert at 70%, hard stop at 100%) |
| Hosting and data | R500 |
| Paid ads | 0 until Week 6 gate, then 15% of MRR |
| Everything else | Needs approval |

A hard stop pauses the affected agent and raises an alert instead of overspending.

## 7. Metrics, thresholds and review points

**Daily health score** (weights in `calculate_health_score`): MRR vs. target 20%, churn 15%, CAC 10%, LTV:CAC 15%, cash runway 15%, conversion 15%, billing errors 10%.

**Targets:** MRR R5,000 by day 90 (target, then growth), churn below 5% monthly, LTV:CAC of at least 3, CAC under R250, runway of at least 90 days.

### Review points and go thresholds

| Review | Day | GO if | If not |
|--------|-----|-------|--------|
| **Week 2** | 14 | System live; at least 100 qualified leads or 500 site visitors; 3 free sample briefs delivered; no agent failure rate above 10% | Fix and re-run for 7 days. Failing twice means pivot the niche. |
| **Month 1** | 30 | At least 3 paying customers; MRR of at least R1,000; refund rate under 10%; support resolved without escalation on 70% or more | Narrow the segment or price and re-run for 30 days. |
| **Month 2** | 60 | MRR of at least R2,500; churn under 10%; CAC under R400; runway above 60 days | Cut paid spend to zero; focus on retention. If MRR is below R1,500: kill. |
| **Month 3** | 90 | **MRR of at least R5,000 and health score of at least 50** | **Wind down** (below). |

### Failure conditions (kill triggers, any time)
- MRR below R1,500 after day 60 (`mrr_crash`).
- Cash runway under 30 days (`cash_runway_critical`).
- Health score below 40 for 7 consecutive days (`health_score_crash`).
- Churn above 10% monthly (`churn_spike`).
- A legal or compliance breach, or a data breach: **immediate stop** regardless of metrics.

### What "deleted if you fail" means in practice
The stakes device is implemented as a **wind-down protocol**, not a threat: on a kill trigger the system (1) stops all outbound messaging, (2) stops new billing and cancels or refunds subscriptions according to the terms, (3) delivers or refunds any paid work in progress, (4) exports customer data to each customer on request and deletes the rest per POPIA, (5) shuts down hosting, and (6) writes a post-mortem to the operator. The operator confirms the final shutdown.

## 8. Technology map (as built)

| Layer | Implementation |
|-------|---------------|
| Dashboard and API | Next.js on Vercel (`app/`): `/dashboard`, `/login`, `/api/metrics`, `/api/agents`, `/api/analyze`, `/api/analyses`, `/api/billing/*`, `/api/cron/orchestrate` |
| Database and auth | Supabase Postgres with Row Level Security and Supabase Auth (`supabase/migrations/`) |
| Agents | Python (`agents/`, `core/mission_control.py`), run by `scripts/worker.py` on any always-on host (Docker compose service provided) |
| Sync | `core/supabase_sync.py` mirrors agent health and metrics to Supabase |
| Payments | Stripe code in `lib/stripe.ts` and the webhook. **Needs a processor supported for South African merchants (A4)**; the webhook and checkout are the only places that change. |
| LLM | OpenAI via `lib/analysis.ts`, model set by `OPENAI_MODEL` |

## 9. Legal and ethical constraints

- **POPIA:** a lawful basis for processing; privacy notice; data-subject access, correction and deletion; breach notification to the Information Regulator and affected people; no use of personal data beyond its stated purpose. Customer data is not used to train models.
- **Direct marketing:** unsolicited electronic marketing needs opt-in, or an existing customer relationship, and every message needs an opt-out. No purchased lists. Cap daily sends.
- **CPA and ECTA:** clear pricing, cooling-off and cancellation rights for online purchases, and plain terms. No dark patterns, fake urgency or fake scarcity.
- **Data collection:** read public pages only where the site's terms and `robots.txt` allow it; no logins, paywall bypass or personal-data scraping. Prefer licensed APIs and RSS.
- **Truthfulness:** no fabricated statistics, testimonials, customer logos or reviews. Disclose that reports are AI-assisted. Marketing claims must be provable.
- **Advice limits:** reports are information, not financial, legal or investment advice, and say so.
- **Impersonation:** agents identify as MarketMinder AI and never pose as a named human.
- **Financial:** no handling of third-party funds; the human operator is the legal and tax-responsible party.

These are hard limits. The plan does not trade them for growth.

## 10. Build status against this plan

Done:
- Dashboard, auth and RLS, analysis processing, cron, Stripe checkout and webhook, agent health sync, and migrations applied to the Supabase project.

Not yet built (in suggested order):
1. **Task routing to the Python agents.** The worker reports health, but nothing sends it tasks, so the agents are idle.
2. **Approval queue and audit log** (autonomy levels 1-2). Agents can act without a gate today.
3. **Operator controls:** pause/resume, kill switch, budget caps and spend tracking, and the review-point panel.
4. **Kill switch that acts.** Mission Control detects failure conditions and logs them but takes no action.
5. **Compliance features:** opt-out handling, a consent record, and data export and deletion.
6. **South African payment adapter** (A4) and ZAR pricing.
7. **Report verification pass** (claim-to-source check) before delivery.
8. **Landing page and sample-brief lead magnet.**
