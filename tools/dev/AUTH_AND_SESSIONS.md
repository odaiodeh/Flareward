# Authentication during local development

The UI uses `/identity/api` for Identity login, users and teams; `/api` is the
platform FastAPI API. Vite and nginx proxy both through one browser origin, so the
signed session cookie can be used by both services. Set the same `SECRET_KEY` in
Identity and platform (`FLAREWARD_SECRET_KEY`) and point both at the same Redis.
The platform verifies the signed session against Identity's Redis session record.
Never treat a user ID in a query/body as authority or forward browser cookies into
untrusted execution environments.

`tools/dev/services.yaml` supplies the retained services and proxy addresses.
Use the signed-session examples in `platform/README.md`; development authentication
is an explicit local-only alternative. Worker/receiver authority is separately
scoped by platform access services and execution profiles.

Admin configuration and transparency consent now use `/api/administration/*` and
`/api/consents/ai-transparency`. Human Review is a distinct business workflow using
native engine waits and authenticated review endpoints, not transparency consent.
