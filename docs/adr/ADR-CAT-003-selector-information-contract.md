# ADR-CAT-003 — CAT selector by item information

## Status
Accepted

## Context
After item model and theta estimator, CAT needs a canonical selector contract.
The selector must prefer items that are most informative around current theta.

## Decision
Introduce:
- item_information(item, theta)
- rank_candidates_for_theta(items, theta, exclude_item_ids)
- select_next_item_for_theta(items, theta, exclude_item_ids)

Ranking policy:
1. higher Fisher information first
2. smaller distance from item difficulty to theta
3. higher discrimination as tie-breaker
4. lower item_id as stable final tie-breaker

## Consequences
This creates the first deterministic CAT item-selection layer.
It is enough to wire estimator -> selector and later add:
- exposure control
- content balancing
- enemy set / overlap rules
- operational constraints

## Next
1. stopping rule contract
2. CAT session state contract
3. mode integration into Level/CIPLE pipeline
