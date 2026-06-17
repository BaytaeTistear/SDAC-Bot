# Production Next Steps

The previous production pass covered:

- HTTPS behind Nginx / Let's Encrypt
- domain setup
- Gunicorn bound to `127.0.0.1:5000` behind Nginx
- off-server backup helper
- service hardening
- monitoring and health-check helpers
- Discord error channel documentation
- GitHub Actions release workflow
- database migration tooling
- restore-test script
- server onboarding checklist
- configurable rate-limit controls
- media metadata display
- optional Sentry error reporting

Useful follow-ups for later:

- move the app from `/home/ubuntu/discord-screenshot-bot` to `/opt/sdac-bot`
  with a dedicated `sdac` Linux user
- add a managed database option such as PostgreSQL for larger multi-server use
- add structured log shipping if the bot grows beyond one host
- add automated scheduled restore testing for backups
- add release versioning after each production bundle
