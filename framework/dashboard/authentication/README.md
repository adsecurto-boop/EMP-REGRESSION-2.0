# framework/dashboard/authentication

Folder scaffold only (Phase 5).

CredentialProvider, SessionManager, AuthenticationManager. Design: [Dashboard Authentication](../../../docs/design/Dashboard_Authentication.md). The only place a login may ever be performed (supervised mode only); the collector receives a ready session and never sees credentials. Storage state and credentials are secrets -- never committed, never logged.
