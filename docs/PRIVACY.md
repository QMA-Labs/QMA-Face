# Local data and privacy

QMA Face runs its configured inference locally once assets are installed. It does not require a hosted inference API key. The chat backend uses a loopback-only local server with a temporary session token; that is not a general security audit or a guarantee about the rest of a user's computer.

- Development data defaults to `.local-data/`; packaged Windows data is outside the application installation directory. `QMA_FACE_DATA_DIR` overrides the location.
- SQLite stores chats and saved analysis reports. Those reports can include point coordinates and photo digests and should be treated as private.
- Photos remain in memory by default. Opt-in retained photos are managed attachments; deleting a chat removes its managed attachment, not the original source image.
- Temporary sessions use an in-memory database. This does not promise secure memory erasure. Exports, model/runtime files, and backups are separate.
- Reports can be exported intentionally. Review a report before sharing it; it may contain image-specific measurements or optional source excerpts.
- Local PDF indexes contain page text and private paths. Keep `sources/local-only/` and the original PDFs out of version control.
- Do not include real people's photographs, private chats, PDF text, local server keys, or identifying diagnostics when filing public issues.

This public source tree excludes user chats, face photos, private PDF files and extracted pages, model weights, runtime binaries, and the personal installer. Documentation images show only the application UI without private content. The repository does not embed or run analytics; GitHub itself and any linked external services have their own behavior and policies.
