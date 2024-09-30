# SponsorSync Influencer Marketplace Diagrams

Generated on 2026-04-26T04:29:37Z from README narrative plus project blueprint requirements.

## Marketplace architecture (Vue + Flask + SQLite)

```mermaid
flowchart TD
    N1["Step 1\nConducted discovery workshops to map sponsor and influencer journeys, clarifying r"]
    N2["Step 2\nDesigned Vue.js single-page app with brief intake, search/filter, proposal, negoti"]
    N1 --> N2
    N3["Step 3\nBuilt Flask REST API with SQLite for MVP speed; structured schemas for briefs, bid"]
    N2 --> N3
    N4["Step 4\nIntegrated LLM service to auto-summarise briefs and power Q&A bot so creators can "]
    N3 --> N4
    N5["Step 5\nImplemented notifications, rate cards, basic dispute/flagging to keep negotiations"]
    N4 --> N5
```

## Sponsor ↔ influencer workflow

```mermaid
flowchart LR
    N1["Inputs\nHistorical support chats and FAQ content"]
    N2["Decision Layer\nSponsor ↔ influencer workflow"]
    N1 --> N2
    N3["User Surface\nAPI-facing integration surface described in the README"]
    N2 --> N3
    N4["Business Outcome\nOperating cost per workflow"]
    N3 --> N4
```

## Evidence Gap Map

```mermaid
flowchart LR
    N1["Present\nREADME, diagrams.md, local SVG assets"]
    N2["Missing\nSource code, screenshots, raw datasets"]
    N1 --> N2
    N3["Next Task\nReplace inferred notes with checked-in artifacts"]
    N2 --> N3
```
