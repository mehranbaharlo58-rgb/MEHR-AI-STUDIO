# MEHR AI STUDIO — responsive dashboard

A dependency-free responsive web dashboard prototype for the MEHR AI STUDIO control plane.

## Visual system
- Original AI-workspace interface informed by common SaaS/AI product conventions; it does not copy a single product.
- Deep navy navigation, restrained indigo/violet actions, spacious cards, clear hierarchy and subtle gradients.
- Persian RTL is the default; English LTR is available from the language control.
- Light/dark themes and responsive desktop, tablet and narrow Android layouts.
- Plain HTML, CSS and JavaScript; no frontend build tool is required.

## Preview
Open `index.html` in a browser. Or from the repository root run:

```bash
python -m http.server 8000
```

Then open `http://127.0.0.1:8000/ui/` on the same device.

## Current integration boundary
This is an interactive front-end prototype with a limited single-provider generation adapter. Navigation, Persian/English switching, theme switching, prompt templates, local file-name display, session-only API credentials, health checks and text generation against the configured Worker can work when that Worker is deployed and configured.

It is not yet the full MEHR AI orchestration product. The authenticated Python MCP server now exposes tenant-scoped AI registry, matching, catalogue seeding, bounded execution and connector health tools. These tools are not yet exposed through a browser-facing HTTP API, and the current UI/Cloudflare Worker still uses a single configured OpenAI-compatible model. Project records, browser-to-registry dispatch, persistent workflow history, real progress events, validated file uploads and end-user account onboarding remain unconnected. The MCP server is an authenticated service boundary, not yet a deployed browser API.

## Next integration sequence
1. Connect the browser UI to a secure HTTP facade for the existing registry, matcher and bounded execution manager.
2. Replace sample project rows with real project/activity APIs.
3. Add agent/model selection and explainable routing results.
4. Stream workflow status and render structured outputs and comparison views.
5. Implement validated file uploads and controlled storage.
6. Add accessibility, authorization, quota and browser integration tests.
7. Preserve human approval for paid, external or irreversible actions.
