# Plan: Read the Docs runs the tutorials against a prebuilt Pulse

**Status:** scoped 2026-10-23 for later; not started. Facts re-checked at source on 2026-10-23, including against the first live RTD build (35357557). Today the Read the Docs (RTD)
build publishes the four tutorials as code only: `documentation/conf.py:33-36`
excludes `tutorials/*` from execution when `READTHEDOCS == "True"`, tags the build
`hosted`, and suppresses `mystnb.glue` warnings (commits `41bba44`, `2342c5a`). The goal:
RTD executes the tutorials against the **real** engine. Pulse can't be built inside a
15-minute RTD build, so a GitHub Actions workflow builds it once per engine pin and
publishes a runtime archive as a GitHub Release asset. RTD downloads it, verifies a
checksum pinned in the repo, points `PULSE_INSTALL_DIR` at it and builds the docs.

This plan **extends [plan-ci-pulse-build.md](plan-ci-pulse-build.md)** (the CI plan):
the build itself is that plan's cold path. See "Shared with the CI plan" below.

## Facts (verified at source)

| Fact | Source |
|---|---|
| RTD Community: 15 min build time, 7 GB memory, 5 GB disk (soft), 2 concurrent builds. No caching between builds is documented; every step runs in a Docker container from the `build.os` image | docs.readthedocs.com/platform/stable/builds.html ("Build resources") |
| `build.jobs` hooks (`post_checkout` ... `post_build`) keep the default steps. `build.jobs.build.html` overrides the HTML build and must write to `$READTHEDOCS_OUTPUT/html`. `build.commands` replaces the whole build and can't be combined with `apt_packages` | docs.readthedocs.com/platform/stable/config-file/v2.html (`build.jobs`, `build.commands`) |
| Each job command runs in a **new shell**, so exported variables don't persist. Variables are expanded per command, the working directory is the repo root, and any non-zero exit fails the build immediately | docs.readthedocs.com/platform/stable/build-customization.html ("Features and limitations") |
| Predefined variables include `READTHEDOCS`, `READTHEDOCS_OUTPUT`, `READTHEDOCS_REPOSITORY_PATH`, `READTHEDOCS_VIRTUALENV_PATH`, `READTHEDOCS_GIT_COMMIT_HASH` and `READTHEDOCS_VERSION_TYPE` (`external` for PR builds). Dashboard variables live outside the repo and are not secret when marked Public | docs.readthedocs.com/platform/stable/reference/environment-variables.html; .../guides/environment-variables.html |
| Builds have network access: the first live build (35357557) fetched `vivarium-workbench.git@aa2b7d2b` and PyPI packages during install. RTD's own Git LFS example also `wget`s a GitHub release asset in `post_checkout` | RTD build log 35357557 (`/api/v2/build/35357557/`); build-customization.html ("Support Git LFS") |
| `build.os: ubuntu-24.04` is the `readthedocs/build:ubuntu-24.04` image (`FROM ubuntu:24.04`, label `ubuntu-24.04-2026.10.21`). `python: "3.12"` is **CPython 3.12.13**, built with asdf, not 3.12.12 | `readthedocs.org` `readthedocs/builds/constants_docker.py:27,40`; `readthedocs-docker-images` branch `releases/ubuntu-24.04` `Dockerfile:2,4`; RTD build log 35357557 (`asdf global python 3.12.13`) |
| The current `.readthedocs.yaml` installs with `method: uv, command: sync, groups: [docs]`. No `uv.lock` is committed, so every RTD build resolves from scratch, and `pyproject.toml:26` leaves `protobuf` unpinned: the first live build resolved **`protobuf==7.36.2`** (harmless while no Pulse code loads there). The generated `_pb2` code was produced by protobuf 7.35.0 | `.readthedocs.yaml`; `pyproject.toml:20,26`; `install/python/pulse/cdm/bind/Patient_pb2.py:12-18` (`ValidateProtobufRuntimeVersion(..., 7, 35, 0, ...)`); RTD build log 35357557 |
| GitHub `ubuntu-24.04` runner: Ubuntu 24.04.5, GCC 12.4/13.3/14.2, Clang 16/17/18, JDK 17 default. Public repos get 4 CPUs, 16 GB RAM and 14 GB SSD, free and unlimited. Jobs can run for up to 6 h | `actions/runner-images` `images/ubuntu/Ubuntu2404-Readme.md:9-22,120`; docs.github.com/en/actions/reference/runners/github-hosted-runners; .../actions/reference/limits |
| **This repo is public** (`AlexPatrie/viva-pulse`). The CI plan's cost section assumed 2-vCPU private-repo runners and billed minutes; both are now stale | `gh repo view --json visibility` -> `PUBLIC` |
| Both images draw from the same Ubuntu archive: noble `libc6` 2.39-0ubuntu8.9 and `libstdc++6` 14.2.0-4ubuntu2~24.04.1 (gcc-14, so `GLIBCXX_3.4.33`) | Launchpad API `getPublishedBinaries` (noble/amd64, Release/Updates/Security) |
| CPython's ABI is compatible across patch releases "if these are compiled the same way" (same compiler, libraries, options and platform). A cp312 extension built against 3.12.12 should load in RTD's 3.12.13. **Live probe needed** across the python-build-standalone and asdf builds | docs.python.org/3/c-api/stable.html |
| PyPulse links only system libraries; protobuf, abseil and Eigen are static. viva-pulse loads only `pulse.cdm` and `pulse.engine`, and those import only numpy, pandas and `google.protobuf` beyond the standard library | `otool -L bin/PyPulse.cpython-312-darwin.so`; import trace with `.venv/bin/python -I`; `grep` of `viva_pulse/` |
| `PULSE_INSTALL_DIR` is used when the `install_dir` config is empty, and an invalid location raises `PulseNotFoundError` with no fallback. A valid install needs `bin/PyPulse*`, `bin/states/` and `python/pulse/`. Paths resolve against the **kernel's** working directory (MyST-NB runs a notebook in its source directory), so the variable must be absolute | `viva_pulse/runtime.py:15,25-56` |
| Release assets: each file under 2 GiB, up to 1000 per release, no limit on total size or bandwidth. The asset API returns a `digest` | docs.github.com/en/repositories/releasing-projects-on-github/about-releases; .../rest/releases/assets |
| `permissions: contents: write` lets `GITHUB_TOKEN` create a release. Events that `GITHUB_TOKEN` causes (such as a tag push) start no new workflow runs, except `workflow_dispatch`/`repository_dispatch` | docs.github.com workflow-syntax (`permissions`); .../actions/concepts/security/github_token |
| Existing releases are semver (`v0.2.0` ... `v0.6.0`, Latest `v0.6.0`). `build-and-push.yml` runs only on `v*` tags. `gh release create` supports `--prerelease` and `--latest=false` | `gh release list`; `.github/workflows/build-and-push.yml` (`on:`); `gh release create --help` (gh 2.95.0) |
| Immutable releases lock the tag and the assets once published (title and notes stay editable) | docs.github.com/en/code-security/supply-chain-security/understanding-your-software-supply-chain/immutable-releases |
| After a repository transfer, links to the old location redirect | docs.github.com/en/repositories/creating-and-managing-repositories/transferring-a-repository |
| `.pulse-build/install` is 469 MB (bin 265, lib 170, include 13, python 22). The CI plan's `bin/` + `python/` is 287 MB, **85 MB** gzipped. A runtime allowlist is 65 MB, **6.7 MB** at `gzip -9`: `PyPulse*`, `bin/{config,ecg,environments,nutrition,patients,states,substances}`, the five `bin/*.json` and `python/pulse/{cdm,engine}`. It leaves out 14 drivers (about 14 MB each), `protoc*`, `Pulse.jar`, `libPulse{C,JNI}`, `validation/` and `python/pulse/study` (18 MB). These are macOS arm64 sizes; Linux needs measuring | `du`/`tar`/`gzip` on the local tree |
| The install tree has no Pulse or third-party LICENSE/NOTICE for what the archive ships. The only license-like files are `python/pulse/study/neural_ode/neural_ode/LICENSE` and `include/google/protobuf/compiler/notices.h`, both outside the runtime allowlist. The engine root has `LICENSE` (Apache-2.0) and `NOTICE`, which credits BioGears 6.1.1 (ARA), Eigen, protobuf, abseil and pybind11 | `find .pulse-build/install -iname '*license*'`; `../engine/NOTICE` |
| Superbuild dependencies and their licenses (the license texts are in `.pulse-build/External/<dep>/src/` after a build): Eigen 5.0.1, mainly **MPL-2.0** with BSD/MINPACK/Apache parts; abseil 20260526.0, Apache-2.0; protobuf 35.0, BSD-3, plus `third_party/utf8_range` (MIT); pybind11 3.0.4, BSD-3 | `../engine/cmake/external/External_{Eigen3,absl,protobuf,pybind11}.cmake`; `External/Eigen3/src/COPYING.README` |
| `src/cpp/cdm/utils/xpstl/*` carries a 1998 ObjectFusion "All rights reserved" notice, but nothing outside that directory includes it, so it is not in the binary | `grep -rn xpstl ../engine/src ../engine/cmake` |
| Local docs timing: `make docs` takes about 66 s, of which tutorial 1 is about 40 s. WholeBody runs about 35x real time. The tutorials simulate about 1,680 whole-body seconds (2x600, 2x60 + 3 at 0.02 s, 2x60 plus 2x60 ventilation-mechanics, 2x120 with all modules), so about 48 s of engine time on macOS arm64 | `CURRENT.md:49-50`; `.build-progress.md:155`; `documentation/tutorials/0[1-4]-*.md` |
| The tutorial prose hard-codes no engine values. Numbers are glued (`svr_ratio`, `last_time` in tutorial 2), and the rest are directional claims, listed under "Platform numerics" | `documentation/tutorials/*.md` |

## Shared with the CI plan (reuse, don't duplicate)

These pieces of the CI plan are reused as they stand:

- **Toolchain:** Temurin 17, `cmake==4.0.3` via `uv tool`, clang, `uv python install 3.12.12`, `uv venv --seed`.
- **Engine source:** shallow clone of `REL_4_4_0` with a SHA assert.
- **Build script:** `.github/scripts/build-pulse.sh`, with the configure and build from `.build-progress.md`.
- **Verify before keeping a build.** The CI plan verifies before caching; here the same check gates publishing.
- **protobuf 7.35.0 pin and assertion.**
- **Canary:** `tests/test_engine_canary.py`.
- **Platform-numerics rule:** record the Linux values in `.build-progress.md` and never loosen tolerances blindly.
- **Watch items:** the `External_protobuf.cmake:88` bug and cold-path rot.

New in this plan:

- the runtime archive (allowlist, licenses, build info);
- publication as a prerelease;
- the RTD fetch and checksum;
- the RTD canary in RTD's own image;
- the docs switch-over.

**This plan changes the CI plan in two ways:**

1. Its optional decision "tighten `protobuf`" becomes **required**: RTD's `uv sync` resolves from scratch, so the pin must live in `pyproject.toml`.
2. Its warm path can download this release asset instead of `actions/cache`. That removes the 7-day eviction and the weekly cron, and gives CI and docs one artifact (open decision 3).

## Approach

- **One workflow, manual trigger only: `.github/workflows/pulse-engine-release.yml`.**
  - Trigger: `workflow_dispatch`, with inputs `engine_sha` and `revision` (default `1`). Manual only, because publishing a release needs an explicit go-ahead every time.
  - **Job `build`** (`ubuntu-24.04`, `timeout-minutes: 180`):
    - Run the CI plan's cold path and verification.
    - Package the archive (below).
    - Run the strict docs build against the *extracted archive*, with `READTHEDOCS=True`, in a venv set up as on RTD. This executes all four tutorials on Linux.
    - Upload the archive with `actions/upload-artifact`.
  - **Job `rtd-canary`** (`container: readthedocs/build:ubuntu-24.04-2026.10.21`, the RTD image pinned by tag):
    - `asdf install python 3.12.13` (RTD's own Python recipe), then a venv.
    - `pip install -e .` and `protobuf==7.35.0`.
    - Extract the artifact and run `tests/test_engine_canary.py`.
    - Check that `ldd` on `PyPulse*.so` reports no `not found`.
    - This proves the glibc, libstdc++ and Python 3.12.13 ABI hypotheses in RTD's own userland before anything is published.
  - **Job `publish`** (needs both jobs; it is the only job with `permissions: contents: write`): `gh release create pulse-engine-<sha9>-r<N> --prerelease --latest=false --target $GITHUB_SHA`. It attaches the archive and puts the build info and SHA-256 in the notes.
- **Release naming.** A dedicated prerelease per engine pin and build revision, e.g. tag `pulse-engine-5e29e5b13-r1`, asset `pulse-engine-5e29e5b13-r1-linux-x86_64-cp312.tar.gz`.
  - Prerelease plus `--latest=false` keeps `v0.6.0` as Latest.
  - The `pulse-engine-` prefix never matches `v*`, so `build-and-push.yml` doesn't fire. The tag is created by `GITHUB_TOKEN`, which starts no runs anyway.
  - `-rN` exists so a packaging or toolchain change for the same pin gets a new, immutable tag instead of replacing assets.
  - Old engine releases are **never deleted**: a docs build of an old tag fetches the asset pinned in that commit.
- **Alternatives weighed:**
  - GHCR via ORAS has content-addressed pulls and no Releases-list noise. But it adds a second pinned binary (`oras`) to download and verify on RTD, a package whose visibility must be made public, and `packages: write`.
  - Actions artifacts expire and need authentication to download.
  - Git LFS has bandwidth quotas.
  - A release asset needs only `curl`, `sha256sum` and `tar`, all already in the RTD image. **Recommended.**
- **Archive contents.** An allowlist, not the CI plan's whole `bin/` + `python/`, so what ships is stated explicitly:
  - the runtime files from the Facts table, at their install-tree paths, so the extracted directory is a valid `PULSE_INSTALL_DIR`;
  - `requirements.txt` from the engine at the pin;
  - `LICENSES/`, holding:
    - Pulse `LICENSE` and `NOTICE`, verbatim (Apache-2.0 §4(a) and §4(d));
    - every Eigen `COPYING.*`;
    - the LICENSE files of protobuf, utf8_range, abseil and pybind11, copied from `.pulse-build/External/*/src/` at packaging time;
  - `BUILDINFO`, holding:
    - the engine SHA and tag;
    - the Python, compiler and CMake versions;
    - the workflow run URL;
    - each dependency's source URL and hash from `External_*.cmake`, which also tells users where to get Eigen's source (MPL-2.0 §3.2).

  The packaging fails if any license source file is missing.
- **RTD side.** One script, `scripts/fetch-pulse-engine.sh <dest>`, is the single source of truth: its top pins the repo URL, tag, asset name and SHA-256. It runs with `set -euo pipefail`, then:
  1. `curl -fsSL --retry 3`;
  2. `sha256sum -c --strict`;
  3. `tar -xzf`;
  4. checks for `bin/PyPulse*`.

  `.readthedocs.yaml` then gains three jobs:
  - `post_checkout`: `bash scripts/fetch-pulse-engine.sh "$READTHEDOCS_REPOSITORY_PATH/.pulse-engine"`. This fails before any install time is spent.
  - `post_install`: a one-line check that protobuf's version starts with `7.35.`, and that `import PyPulse` through `viva_pulse.runtime.ensure_pulse_importable` succeeds and prints `PyPulse.__file__` to the log.
  - `build.html`: `PULSE_INSTALL_DIR="$READTHEDOCS_REPOSITORY_PATH/.pulse-engine" "$READTHEDOCS_VIRTUALENV_PATH/bin/python" -m sphinx -T -W --keep-going -b html documentation "$READTHEDOCS_OUTPUT/html"`.

  The `build.html` override is needed because a new shell drops exports. It must carry `-W --keep-going` itself: RTD's docs define `sphinx.fail_on_warning` for their own Sphinx command and don't say whether it applies to an overridden `build.html`, so the override states it explicitly. A dashboard variable was rejected: config outside the repo isn't reproducible. Extracting into `.pulse-build/install` and relying on the default was rejected too: it is implicit and works only for editable installs.
- **conf.py switch-over.** Delete the whole `READTHEDOCS` branch (`conf.py:33-36`), `tutorials/_hosted.md`, its four includes, the `{only} not hosted` block in `index.md` and the `.readthedocs.yaml` header comment. Afterwards no environment-conditional path can skip execution.

## Failure behavior (must be loud, never code-only)

| Failure | What stops the build |
|---|---|
| Asset missing, release deleted, or repo private (404) | `curl -f` exits non-zero in `post_checkout` |
| Asset corrupt, truncated or swapped | `sha256sum -c --strict` against the in-repo pin |
| Archive incomplete (no states or `python/pulse`) | the script's `bin/PyPulse*` check; then `PulseNotFoundError` in the first tutorial cell, with `nb_execution_raise_on_error = True` |
| Wrong protobuf resolved | the `post_install` version assertion |
| ABI mismatch (glibc, libstdc++, Python minor) | the `post_install` `import PyPulse` |
| Someone reintroduces a hosted code-only path | regression test (step 6): the strict docs build runs with `READTHEDOCS=True` and asserts every tutorial page contains `cell_output` |

## Platform numerics (tutorial prose measured on macOS arm64)

The prose's directional claims become hidden assertions (`:tags: [remove-cell]`) placed after the cell that computes them. A platform where the prose is false then fails the build, locally and on RTD. Each threshold comes from the **words of the claim**, not from a measured value plus a tolerance. The claims:

- **Tutorial 1:**
  - the bleed costs more than a quarter of the starting blood volume;
  - heart rate rises;
  - MAP stays near its start for several minutes before it falls;
  - the controller starts after MAP falls below 90 mmHg, late in the run;
  - the treated run ends with more blood volume and higher MAP than the untreated run.
- **Tutorial 2:** MAP barely moves; heart rate and cardiac output fall.
- **Tutorial 3:**
  - ventilation_mechanics: tidal volume falls and the rate is unchanged;
  - whole_body: the rate rises.
- **Tutorial 4:** PaO2 rises several-fold; heart rate falls; breathing rate rises.

The glued numbers are correct on any platform by construction. If an assertion fails on Linux, treat it as a real platform difference, because state files are generated per platform. Rewrite the claim to what both platforms show, or glue the value. Never widen the threshold until it passes. Record the Linux values next to the macOS ones in `.build-progress.md`, in the CI plan's numerics table. The wall-time phrases ("about 40 seconds") are macOS timings; see open decision 7.

## Steps (each independently verifiable)

1. **Pin protobuf** to `protobuf>=7.35,<7.36` in `pyproject.toml`.
   - Extend `tests/test_packaging.py::test_dependencies_resolve_for_every_supported_python` to assert that the fresh `uv lock` resolves protobuf 7.35.x. That is the same resolution RTD's `uv sync` performs.
   - Verify: the test fails without the pin (it resolves 7.36.x) and passes with it.
2. **Build script** (the CI plan's step): `.github/scripts/build-pulse.sh`.
   - Verify: a dispatch run whose `build` job ends at the CI plan's verify-before-cache checks.
3. **Packaging script** `.github/scripts/package-pulse-runtime.sh <install> <out>`.
   - Verify locally on the macOS tree: extract into the scratchpad, set `PULSE_INSTALL_DIR` to it, then run `uv run --no-sync pytest -q` (full suite) and the strict docs build. Both green proves the allowlist is enough.
   - Record the archive size and `LICENSES/` listing.
4. **Tutorial claim assertions**, plus the `cell_output` assertion in `tests/test_docs.py`.
   - Verify: green on macOS. Each assertion fails on a deliberately inverted copy of its claim, in the scratchpad.
5. **Workflow** `pulse-engine-release.yml` (build, rtd-canary, publish). Dispatch once with the user's go-ahead.
   - Verify:
     - the Linux docs build executes all four tutorials;
     - the RTD-image canary passes;
     - `gh release list` still shows `v0.6.0` as Latest;
     - an anonymous `curl -fL` of the asset matches the SHA-256 in the notes and the API `digest`.
   - Record the Linux numerics and archive size.
6. **Switch-over PR**, one bundle per the Book of Jim:
   - `scripts/fetch-pulse-engine.sh` with the pins;
   - the `.readthedocs.yaml` jobs;
   - the conf.py, `_hosted.md` and `index.md` removals;
   - `test_hosted_build_needs_no_engine` replaced: the main docs test runs with `READTHEDOCS=True` plus the `cell_output` assertion;
   - `.pulse-engine/` added to `.gitignore`;
   - README, installation page, `CLAUDE.md` and `CURRENT.md` updated.

   Negative probes, run in the scratchpad: one changed hex digit and a wrong tag must each make the script exit non-zero.
7. **Live RTD probe** before merge: a PR build (or an activated branch version). Read the log for:
   - the checksum `OK` line;
   - the printed `PyPulse.__file__` under `.pulse-engine`;
   - protobuf 7.35.x;
   - the four tutorials executed;
   - total build time.

   Check the rendered tutorial pages for outputs and for unexpected Pulse log lines in the cell output.
8. Merge. Tag or release only on the user's explicit go-ahead.

## Cost and risk

- **RTD build time (main risk).**
  - The engine work is about 48 s on Apple silicon. RTD's CPU isn't documented; at 2-3x slower per core, that's about 2-3 min.
  - Add the `uv sync` install (about 1-3 min, including the workbench from git), RTD's environment setup (about 1 min) and the archive fetch (seconds for tens of MB).
  - Estimate: **about 5-8 min against the 15 min cap**.
  - The code-only RTD build that exists now gives the non-engine baseline; step 7 measures the rest.
  - If a real build passes about 10 min, stop and decide (open decision 6) rather than trimming tutorial content.
- **Build workflow:** a cold build on 4-CPU public runners is estimated at 45-90 min, free. It runs once per engine pin or revision.
- **Hosting:** the archive is tens of MB per release, with no bandwidth limit.
- **ABI risk:** low. Both images build on `ubuntu:24.04` and the archive's glibc and libstdc++ are identical. The Python patch versions differ: 3.12.12 python-build-standalone in CI, 3.12.13 asdf on RTD. The `rtd-canary` job settles all three questions before publishing.
- **RTD changes `python: "3.12"` to a new patch, or rebuilds its image.** Within 3.12 this is ABI-compatible. Re-dispatching the canary after RTD image bumps is cheap. A change of minor version fails loudly at import.
- **Repo transfer** (vivarium-collective) **or going private.**
  - Transfer: the old URLs redirect. Still, keep the owner in the one pin line of `fetch-pulse-engine.sh`, and update that line after a move.
  - Private: anonymous downloads 404 and the build fails loudly. That would need a token, which RTD can only hold as a dashboard secret, and not for PR builds.
- **Licensing:** the archive redistributes binaries. Shipping `LICENSES/` and `BUILDINFO` meets the Apache-2.0 §4, BSD-3, MIT and MPL-2.0 §3.2 notice duties. viva-pulse's own Apache-2.0 license (`d4e7a18`) is separate.

## Open decisions for the user

1. **Pin protobuf** to `>=7.35,<7.36` in `pyproject.toml`. This plan needs it (RTD resolves from scratch). It answers the CI plan's first decision. Recommended.
2. **Archive scope:** a runtime allowlist (about 65 MB, 6.7 MB gzipped on macOS; recommended) or the CI plan's full `bin/` + `python/` (287 MB, 85 MB gzipped).
3. **Should the CI plan's warm path consume this release asset** instead of `actions/cache`? Recommended: one artifact, no eviction cron. It then needs the step 3 proof on Linux too, which the CI suite gives.
4. **Hosting:** a `pulse-engine-<sha9>-r<N>` prerelease (recommended) or GHCR/ORAS.
5. **Enable immutable releases** for the repo? This would also lock the semver releases' assets.
6. **Action if RTD builds exceed about 10 min:** ask RTD support for more build time (builds.html mentions it but doesn't say whether Community qualifies), move to Business, or shorten tutorials.
7. **The tutorials' wall-time phrases** ("about 40 seconds"): keep them as approximate, or restate them as simulated time.
8. **The live probe** needs RTD pull-request builds enabled, or a branch version activated, in the RTD dashboard.
