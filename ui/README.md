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
This is an early-access front end connected to the authenticated Cloudflare Worker AI endpoint. Navigation, language/theme switching and prompt templates work locally. Text generation is live when a valid Worker URL and owner token are configured. The composer retains up to nine recent user/assistant turns in page memory and sends that context with each request; refreshing or closing the page clears the conversation. Project records, file transfer/content processing, durable conversation storage and real progress events are not implemented.

## Next integration sequence
1. Connect the prompt composer to the existing workflow engine through a secure backend.
2. Replace sample project rows with real project/activity APIs.
3. Implement validated file uploads and controlled storage.
4. Stream workflow status and render structured outputs.
5. Add accessibility and automated browser tests.
6. Preserve human approval for external or irreversible actions.
