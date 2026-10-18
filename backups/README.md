# Backups

The Compose deployment mounts this directory at `/config/backups`, which is Home Assistant
Container's local backup location. Backups created from the Home Assistant UI are therefore
available on the host without copying them out of the container.

Do not commit backup archives here. They contain credentials, device keys, and private household
data. The Git ignore rules preserve this document but exclude all backup files.

## Current setup

- Host directory: `./backups/`
- Container directory: `/config/backups`
- Backup location: Home Assistant local backup storage

Keep the backup encryption emergency kit outside Git and outside the Home Assistant host. Store an
additional copy on separate storage before treating this directory as a disaster-recovery backup.

## Restore

1. Stop the Home Assistant container before replacing its configuration.
2. Restore the backup through Home Assistant onboarding or the Backups page.
3. Keep the ZBT-2 connected to the target host when restoring a setup that contains ZHA.
4. Start Home Assistant and test integrations, devices, automations, and notifications.
