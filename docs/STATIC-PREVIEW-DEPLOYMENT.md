# Static preview deployment

The UI in `ui/` is a static front-end preview. It does not contain API credentials and does not connect to the Python workflow engine.

## Enable GitHub Pages once

1. Open the repository **Settings → Pages**.
2. Under **Build and deployment**, choose **GitHub Actions** as the source.
3. Save. The `.github/workflows/deploy-pages.yml` workflow will publish the contents of `ui/` on the next push to `main` (or when manually started from Actions).

The resulting URL is shown by the `deploy-ui-preview` workflow under its `github-pages` environment after a successful deployment. For a project repository it is normally `https://<owner>.github.io/<repository>/`.

## Important boundary

This is a public static preview only. It has no user accounts, server-side API, AI execution, database, or private file storage. Do not add provider API keys to browser JavaScript or static files. Production AI execution requires a separately deployed authenticated backend, a configured OAuth/OIDC issuer, TLS, secret management, rate limiting, and HTTP transport integration tests. See [ADR-0001](adr/0001-authentication-boundary.md).
