## Development Conventions

### Predictable Structure
Organize files and directories in a logical, navigable layout.

### Up-to-Date Documentation
Keep README files current with setup steps, architecture overview, and contribution guidelines.

### Clean Version Control
Write clear commit messages, use feature branches, and add meaningful descriptions to pull requests.

### Environment Variables
Store configuration in environment variables; never commit secrets or API keys.

### Minimal Dependencies
Keep dependencies lean and up-to-date; document why major ones are included.

### Consistent Reviews
Follow a defined code review process with clear expectations for reviewers and authors.

### Testing Standards
Define required test coverage (unit, integration, etc.) before merging.

### Feature Flags
Use flags for incomplete features instead of long-lived branches.

### Changelog Updates
Maintain a changelog or release notes for significant changes.

### Build What's Needed
Avoid speculative code and "just in case" additions (see minimal-implementation.md).

---

## Encoding and Tooling

- **UTF-8 encoding**: All source files must be encoded in UTF-8 (`.editorconfig` enforces this)
- **Frontend package manager**: Use `npm@11` only. Do not use `yarn` or `pnpm`. Version is pinned at `npm@11.9.0` via `packageManager` field.
- **Line endings**: LF (Unix-style) — `.editorconfig` enforces this cross-platform
- **Trailing whitespace**: Files must not have trailing whitespace; `.editorconfig` enforces trim on save
