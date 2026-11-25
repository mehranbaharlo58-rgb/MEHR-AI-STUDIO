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

It is not yet the full MEHR AI orchestration product. Project records, agent dispatch, model matching, parallel execution, persistent workflow history, real progress events, validated file uploads, user accounts and multi-user authorization are not connected to this UI. The current Worker proxies a single configured OpenAI-compatible model; it does not dispatch across the model catalogue or invoke the Python MCP workflow engine.

## Next integration sequence
1. Connect the browser UI to a secure HTTP facade for the existing registry, matcher and bounded execution manager.
2. Replace sample project rows with real project/activity APIs.
3. Add agent/model selection and explainable routing results.
4. Stream workflow status and render structured outputs and comparison views.
5. Implement validated file uploads and controlled storage.
6. Add accessibility, authorization, quota and browser integration tests.
7. Preserve human approval for paid, external or irreversible actions.
