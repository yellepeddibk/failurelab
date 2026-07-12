# Releasing

FailureLab publishes to PyPI through GitHub Actions trusted publishing (OIDC). No API tokens are stored in the repository or its secrets.

## One-time setup (maintainer)

1. Create a PyPI account with 2FA enabled.
2. On PyPI, add a trusted publisher for the project (Publishing settings, "Add a pending publisher" before the first release):
   - PyPI project name: `failurelab`
   - Owner: `yellepeddibk`
   - Repository: `failurelab`
   - Workflow name: `release.yml`
   - Environment name: `pypi`
3. The `pypi` GitHub environment is created automatically on the first publish run. Optionally add protection rules to it under Settings, Environments.

## Release procedure

1. Update `CHANGELOG.md` with a section for the new version.
2. Confirm `project.version` in `pyproject.toml` matches the planned tag. The workflow fails the release if they differ.
3. Land all changes on `main` through the normal PR process with green checks.
4. Tag and push the tag (maintainer, manual):

   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```

5. The `release` workflow builds the sdist and wheel, runs `twine check`, verifies the tag matches the package version, and publishes to PyPI via trusted publishing. Publishing runs only for tag pushes; `workflow_dispatch` runs are build-only dry runs.
6. Verify the release:

   ```bash
   pip install failurelab==X.Y.Z
   failurelab --version
   ```

7. Create a GitHub release from the tag with notes based on the CHANGELOG section.

## Notes

- The tag-version consistency check lives in the `build-release` job; a mismatched tag fails before anything is published.
- Yanking or deleting a published version is a manual PyPI action; prefer publishing a fixed patch release instead.
