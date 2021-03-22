# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- New AsyncModel that supports async and await syntax.

### Changed

- Update `google-cloud-firestore`. The 2.0.2 version has an [issue
  with running in async mode against the emulator](https://github.com/googleapis/python-firestore/issues/286),
  that has been fixed in the git `master`, but not included in any official
  release yet. Using the latest master (pinned to the commit hash). In case you 
  are using poetry to install `firedantic`, please be aware that poetry has an 
  [issue with updating from a pypi package to a git
  commit](https://github.com/python-poetry/poetry/issues/3803).
  The simplest work-around is to after updating `firedantic` (and thus also
  `google-cloud-firestore`) delete the virtualenv and then run `poetry install`
  again
- Update `pydantic` to 1.8.1 and `grpcio` to 1.36.1
- Fixes for Mypy errors and warnings
- Updated examples in README


## [0.1.4] - 2020-12-08

### Added

- `Model.find` to do more complex queries supporting all Firestore operators

## [0.1.3] - 2020-11-09

### Changed

- Respect model's aliases when saving a model

### Added

- `CollectionNotDefined` error
- `truncate_collection` class method for `Model`

## [0.1.2] - 2020-09-21

### Changed

- Update README.md
- Add imports to root level init
- Update CHANGELOG.md
- Bump version

## [0.1.1] - 2020-09-21

### Removed

- .nvmrc
- .prettierrc.yaml

### Updated

- README.md with build status badge
- Only run deploy to PyPi on Python 3.6 environment
- CHANGELOG.md
- Bump version

## [0.1.0] - 2020-09-21

### Added

- Project files
- CHANGELOG.md

## Changed

- Update README.md
- Update .gitignore

[Unreleased]: https://github.com/digitalliving/firedantic/compare/0.1.4...HEAD
[0.1.4]: https://github.com/digitalliving/firedantic/compare/0.1.3...0.1.4
[0.1.3]: https://github.com/digitalliving/firedantic/compare/0.1.2...0.1.3
[0.1.2]: https://github.com/digitalliving/firedantic/compare/0.1.1...0.1.2
[0.1.1]: https://github.com/digitalliving/firedantic/compare/0.1.0...0.1.1
[0.1.0]: https://github.com/digitalliving/firedantic/releases/tag/0.1.0
