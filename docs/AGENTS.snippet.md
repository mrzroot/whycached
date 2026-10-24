<!-- Paste into AGENTS.md, CLAUDE.md, .cursorrules or your agent's rules file. Requires `pipx install whycached` (or `uvx whycached`). -->

## When a deployed site still shows the old version

Do not edit code again, and do not redeploy blindly. First run:

```sh
whycached https://your-site.example/page --expect "<a string only in the new version>"
```

- **STALE** means a CDN/proxy is confirmed to serve different bytes than the origin: purge it (the `fix:` lines) or wait out the printed freshness time.
- **LIKELY** items (browser cache, service worker, long-cached assets) are reasons the *user's browser* can still show the old copy: tell the user the printed hard-reload / unregister steps.
- If it says `'<string>' is not in any response`, it is **not** a cache problem: check that the deploy finished and went to the right environment.
- `whycached` only sends GET requests; it never purges or changes anything.
