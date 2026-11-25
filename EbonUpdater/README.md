# EbonUpdater v0.1.1 — GitHub integration test

A standalone WotLK 3.3.5a addon and an opt-in Windows command-line updater. No client changes, libraries, background service, account credentials, or player-to-player broadcasts. The native HTTP request sends only the public manifest URL (normal network metadata such as IP address is visible to the host). This is an experimental integration; ask Ebonhold staff whether third-party use of its login-message HTTP API is supported before distribution.

## 1. Installation and demo

Install the entire EbonUpdater folder in Interface/AddOns with WoW closed. Restart WoW. Run `/ebonupdate demo` for a display-only test. Installed version: 0.1.1.

## 2. Live manifest configuration

This package is already configured for Aeskyndr/EbonUpdater. Create the public repository with a main branch. Publish the v0.1.1 release with the explicit asset EbonUpdater.zip first; then upload the v0.1.1 versions.json at the repository root. For the live update test, install the configured v0.1.0 package locally. Keep the v0.1.1 ZIP as the GitHub asset only. Run `/ebonupdate check` to detect the update. If a check is running, let it finish first. Raw GitHub can cache results briefly.

The protocol marker is a format marker, not a cryptographic signature. Stable numeric versions only. The date uses YYYY-MM-DD and is informational. Repository and addon folder must match metadata. Only register addons that have an actual release.

## 3. Register another addon

Add these fields (use real repo and actual installed version) to the addon's main TOC:

```ini
## Version: 1.0.0
## X-GitHub: Aeskyndr/EbonLoot
```

Add the folder name, repository and latest stable release version to the central manifest. There is no need to add Lua code or an EbonUpdater dependency. Disabled addons are also scanned where the client exposes their TOC metadata. No arbitrary third-party addons without matching manifest entries are updated.

## 4. Publish an installable release

For addon `EbonLoot` version `1.0.0`, create GitHub release tag `v1.0.0` in its declared repository. Upload an explicit asset named `EbonLoot.zip`, containing a single top-level folder `EbonLoot/` with `EbonLoot.toc` and the addon files. The TOC must include the actual matching repo and version. Do not use GitHub's automatically generated source archive, which has a different layout. Only after uploading the asset, update the manifest. Do the same for EbonUpdater itself. If shipping a new version, change the TOC version before packing. EbonUpdater release assets must include `Helper/` and `Update addons.cmd` as well as the Lua files. The launcher runs a temporary copy of the helper so a full folder replacement can update the helper too. If the release lacks a prebuilt EXE, the launcher falls back to Python.

## 5. Windows helper

Requires Python 3.10+ on Windows unless you build a standalone executable. Keep the complete `EbonUpdater` folder inside `Interface/AddOns/`. Double-click `Update addons.cmd` inside it. The launcher derives the game root from its installed location and starts a temporary copy of the helper outside the game folder, allowing the installed EbonUpdater folder to be replaced. Review detected updates, close the game and type `UPDATE` to approve installation. No files are replaced just by opening the helper. For checking only: `py -3 Helper/updater.py "C:\\Games\\Ebonhold" --check`.

For an optional EXE build on Windows: install PyInstaller (`py -3 -m pip install pyinstaller`), then run `Helper/Build exe.cmd`. The executable is created at `Helper/EbonUpdater.exe`. A Windows binary has not been built or tested in this package. The CLI is intentional for the first prototype; a graphical window can be added later.

The helper downloads the exact stable release tag and named ZIP, validates repository/version metadata, asset size and SHA-256 digest if GitHub provides one, rejects unsafe archive paths, links, duplicate files and Windows path collisions, then stages files before replacing the installed folder. It checks the Windows process list before installing and again before each swap. Keep WoW closed and do not launch it mid-update; process checks are best-effort, not an OS lock. Existing directories are renamed into `Interface/EbonUpdater-backups/` (outside AddOns) and restored on a failed swap when possible. `WTF` and SavedVariables are not accessed. Files manually edited inside addon folders will be replaced, but remain in the backup. No automatic backup deletion. To manually roll back, close WoW, move the new folder out of AddOns, then move the desired backed-up folder back with its original name. Updates are per-addon, not one transaction across all addons.

## 6. Commands and runtime behavior

- `/ebonupdate`: cached status and commands.
- `/ebonupdate check`: manually request a fresh manifest (also works with auto checks off).
- `/ebonupdate on` / `off`: enable/disable automatic checks (on takes effect on next login; off stops polling, not an already started native request).
- `/ebonupdate open`: open the configured repository's Releases page in the browser.
- `/ebonupdate demo`: show a simulated version notification.

Automatic check starts 8 seconds after PLAYER_LOGIN, with a 15-minute persistent cooldown, a 15-second Lua polling timeout and 0.5-second polling. There is no permanent OnUpdate handler. Existing cache is not overwritten on failures. Native request state is shared with the client login-message system and cannot be locked or cancelled by our addon. An unrelated response is rejected by format and self-repository checks, but this cannot eliminate all contention, identify request ownership, or guarantee the DLL's native request timeout. The official glue UI only polls while its login screen is visible, according to the public source. Automatic HTTP can be disabled at any time. The code never modifies native client state or requests any gameplay-related operation.

## Validation performed

- Python tests: `python -m unittest discover -s tests -v` (8 tests).
- Lua tests: `lua tests/test_lua.lua` from inside the EbonUpdater folder (mocked client, run locally on Lua 5.4; code uses Lua 5.1-compatible syntax).
- Not yet tested: actual custom manifest over Ebonhold HTTP, Windows launcher and temporary-copy self-update, Windows process discovery/installation, actual full live update cycle, live GitHub release download, staff approval. The user's manual GitHub commit HTTP request and the ingame v0.1.0 demo succeeded. v0.1.1 is a version-bump test release, not a new feature release.

Reference: https://github.com/ProjectEbonhold/ebonhold-utils (native HTTP API and login-screen behavior).
