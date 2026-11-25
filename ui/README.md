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

It is not yet the full MEHR AI orchestration product. The authenticated Python MCP server now exposes tenant-scoped AI registry, matching, catalogue seeding, bounded execution and connector health tools. An opt-in OIDC-protected Streamable HTTP endpoint is available through the mehr-ai-studio-http command. The current dashboard is not yet an MCP client and still calls the separate single-provider Cloudflare Worker; it is not connected to the tenant-scoped orchestration tools. Project records, browser-to-registry dispatch, persistent workflow history, real progress events, validated file uploads and end-user account onboarding remain unconnected.

## Next integration sequence
1. Connect the browser UI to a secure HTTP facade for the existing registry, matcher and bounded execution manager.
2. Replace sample project rows with real project/activity APIs.
3. Add agent/model selection and explainable routing results.
4. Stream workflow status and render structured outputs and comparison views.
5. Implement validated file uploads and controlled storage.
6. Add accessibility, authorization, quota and browser integration tests.
7. Preserve human approval for paid, external or irreversible actions.
