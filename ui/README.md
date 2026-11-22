# MEHR AI STUDIO — UI prototype

A dependency-free responsive web interface prototype.

## Design
- Premium SaaS visual language: restrained navy, indigo accent, spacious layout and clear hierarchy.
- Responsive desktop and mobile layouts, including narrow Android screens.
- English/Persian language switch with LTR/RTL direction.
- Light/dark theme switch (stored locally in the browser).
- Plain HTML, CSS and JavaScript; no frontend build tool is required.

## Preview
Open `index.html` in a browser. Or from the repository root run:

```bash
python -m http.server 8000
```

Then open `http://127.0.0.1:8000/ui/` on the same device.

## Current integration boundary
This is an interactive front-end prototype, not a connected application. Navigation, language/theme switching, prompt templates, local file-name display and prompt submission feedback work locally. Project records, file transfer, AI execution, authentication, persistence and real progress events are not connected. Submitting a prompt does not claim to execute an AI workflow.

## Next integration sequence
1. Connect the prompt composer to the existing workflow engine through a secure backend.
2. Replace sample project rows with real project/activity APIs.
3. Implement validated file uploads and controlled storage.
4. Stream workflow status and render structured outputs.
5. Add accessibility and automated browser tests.
6. Preserve human approval for external or irreversible actions.
