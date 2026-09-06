# React Operations Console

## Decision

JobFlow uses an independent React + Vite + TypeScript frontend for the operator console. The existing FastAPI services, PostgreSQL layer, operation logic, and Streamlit dashboard remain unchanged and available as the internal fallback entrypoint.

## Current Scope

- The frontend is a visual and routing skeleton with local demonstration data.
- Sidebar navigation is implemented with React state and works on desktop and mobile.
- Pages: platform overview, operations center, delivery center, analytics, and alerts.
- Delivery controls are visibly disabled until the API contract and confirmation flow are connected.
- No token, password, webhook, cookie, or private-key value is stored in the frontend.

## Integration Order

1. Add a typed API client and a single API base URL configuration.
2. Read health and stage status from a read-only status endpoint.
3. Replace overview mock metrics and recent runs with server responses.
4. Add read-only analytics endpoints for trend, city, and channel aggregates.
5. Connect server-restart checks as an explicit operation with run history.
6. Connect Telegram delivery and WeChat draft creation as separate confirmed actions.
7. Add loading, stale-data, error, and uncertain-result states before enabling production actions.

## Operation Boundaries

- Do not add a one-click full recovery action.
- Do not automatically retry uncertain external delivery requests.
- WeChat remains draft creation only; final publication is manual.
- Every destructive or externally visible action must show its channel, date, and confirmation result.

## Verification

- `npm run build` must pass before frontend changes are accepted.
- API integration must be tested against the existing FastAPI contract before enabling buttons.
- Credentials remain environment/server-side and are never copied into the knowledge vault or client bundle.
