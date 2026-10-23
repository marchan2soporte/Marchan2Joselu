# Marchan2 project instructions

## Product
Marchan2 is an independent Windows POS and administration application. Preserve the separation between TPV and Administration and their shared local SQLite data. Do not modify Agora or SELUCARTAS300.

## Standing publication instruction from the owner
The canonical repository is https://github.com/marchan2soporte/Marchan2Pedro.git.
The owner explicitly requested that future Marchan2 updates made in this work be committed and pushed to this repository. After each requested update, run the relevant checks, update the version/documentation when appropriate, commit and push the resulting source changes. Do not claim publication unless the remote contains the commit. Never force-push or overwrite unrelated remote changes. If access fails, retain the work locally and explain the exact blocker.

Never commit customer data, databases, QA folders, session files, credentials, build directories or local paths containing personal data. Use isolated data for tests. Do not reset a user's active databases.

## Versions and distribution
Keep release.json, the UI version, build spec output directory and executable integration test path consistent. Executables are distributed as a complete portable folder inside a ZIP, not as isolated EXE files. The release workflow builds this package when a version tag is published; do not upload databases with it.

## Validation
Run `python -m unittest discover -s tests -v` and syntax-check changed JavaScript with Node. On Windows, `python tests/check_dual_apps.py` checks the two apps and their permissions. Build with `python -m PyInstaller --noconfirm Marchan2_dual.spec`, then run `python tests/check_dual_apps.py --frozen` before distributing executables.

Keep feature availability honest. Unimplemented fiscal or operational modules must remain visibly pending. Do not describe TicketBAI or commercial fiscal compliance as implemented until it is actually integrated and validated.
