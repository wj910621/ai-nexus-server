# React Router RSC advisory exception

- Advisory: `GHSA-qwww-vcr4-c8h2`
- Affected dependency: React Router 7.18.1
- Review deadline: 2026-08-31
- Scope: The advisory affects React Server Components and Server Action request
  handling. Y·NEX Story Studio is a client-only `BrowserRouter` SPA and does
  not import server/RSC router APIs.
- Compensating control: `npm run audit:production` permits only this exact
  advisory, verifies the SPA routing architecture, rejects every other npm
  vulnerability, and fails after the review deadline.
- Exit condition: upgrade to the first patched stable React Router release and
  remove this exception.
