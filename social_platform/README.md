# Next-Generation Social Platform Foundation

## Product Principles
- **VALUE OVER ENGAGEMENT HACKS**: Discussions are highlighted based on depth and explicit user value, not addictive engagement loops.
- **USER CONTROL OVER FEED**: Feeds are chronological and explicitly curated by the user.
- **PRIVACY BY DEFAULT**: Data is siloed and minimally collected.
- **NO DARK PATTERNS**: Transparent UI without forced interactions.

## Architecture & Implementation Status
- **Client Layer**:
  - [REAL] Client Interaction Layer (`client/client.py`, `client/session.py`, `client/cli.py`, `client/interactive.py`).
  - [REAL] Fluent UserSession workflows for feeds, discussions, communities, courses, DMs, moderation, and privacy.
  - [REAL] Command-Line Interface (`social-cli` via `client/cli.py`) supporting human-readable and structured JSON outputs.
  - [REAL] Interactive console (`client/interactive.py`) for live terminal user journeys.
- **API Layer**: 
  - [REAL] JSON REST API Boundary via standard library HTTP Server (`api/server.py`). 
  - [PLACEHOLDER] FastAPI (Modular, scalable) - Deferred to maintain hermetic execution without network dependencies during early foundation.
- **Data Layer**: 
  - [REAL] Persistent Storage via SQLite3 (`core/database.py`).
  - [PLACEHOLDER] SQLAlchemy ORM with Pydantic for validation - Deferred to maintain zero external dependencies in the initial vertical.
- **State**: 
  - [REAL] Users, Connections/Follows, Discussions/Posts, Multi-Mode Transparent Feeds (Chronological, Following, Interests, Community, Weighted Value, Domain Reputation), Communities, Academic Spaces (Courses, Study Groups, Resources), DMs, Moderation, Appeals.
  - [REAL] Weighted Value Endorsements & Domain Reputation Scoring with academic role scaling, author authority ranking, leaderboard tracking, and study space aggregation.
  - [REAL] Push Notification Registration, User Preferences, & Event Dispatching Engine (`core/database.py`, `core/models.py`, `api/server.py`, `client/client.py`, `client/session.py`, `client/cli.py`, `client/interactive.py`).
  - [REAL] Granular notification preference controls (mentions, replies, endorsements, DMs, connections, study spaces, quiet hours, min endorsement weight, sender muting).

## Tests
- Run `python3 -m unittest discover -s social_platform/tests` to verify deterministic feed behavior, database persistence, REST API boundary, client interaction workflows, weighted endorsements, domain reputation scoring, push notification registration, user preferences, and event dispatching.
