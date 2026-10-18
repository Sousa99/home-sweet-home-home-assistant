# Home Assistant Repository Guidance

This repository is configuration-as-code for the Home Sweet Home household Home Assistant
installation.

## Rules

- Read `.specify/memory/constitution.md` before making changes.
- Never commit secrets, tokens, private keys, device credentials, or generated state.
- Keep device and automation changes reviewable and documented.
- Validate YAML and Docker Compose configuration before deployment.
- Test affected automations and notifications on the real Home Assistant instance.
- Keep LLM, MCP, and conversation orchestration in `home-sweet-home-agent`.
- Prefer local integrations; document every cloud dependency.

## Change workflow

1. Describe the device, integration, or automation behavior.
2. Update configuration and documentation together.
3. Run configuration validation.
4. Test normal, unavailable, and recovery behavior.
5. Record hardware-specific setup or manual UI steps.
