# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.12.0] - 2025-11-20

### Changed

- Update underlying libraries to resolve possible security issues.

### Removed

- Removed support of Python 3.9.

## [0.11.0] - 2025-06-06

### Added

- Support for transactions, a big thanks to `@lukwam` for this! For more details of how
  to use this, see the new section in the README.

## [0.10.0] - 2025-02-26

### Added

- Added support for Python 3.13.

### Changed

- Updated underlying libraries, such as pydantic, grpcio and google-cloud-firestore, as
  well as dev dependencies.
- Updates to pre-commit hooks.

### Removed

- Removed support for Python 3.8, it was end of life on 2024-10-07.
- Removed the `remove_prefix` from `firedantic.utils` (needed only for Python 3.8).

## [0.9.0] - 2025-02-21

### Added

- Added support for `exclude_none` and `exclude_unset` in `save` method.

### Fixed

- Switched Firestore `query.where()` to use the 'filter' keyword argument instead of
  positional arguments. This eliminates a UserWarning that was introduced in
  `google-cloud-firestore` 2.11.0.
- Internal, for builds only: Locked poetry in GitHub workflows to version 1.8.5, as
  version 2.0.0 and later create METADATA files with version 2.3 instead of 2.2 and the
  action to publish the package failed with an error about supported metadata versions
  being 1.0, 1.1, 1.2, 2.0, 2.1, 2.2.

## [0.8.1] - 2024-12-09

### Changed

- Improve type hints for `find` and `find_one` methods.

## [0.8.0] - 2024-10-16

### Added

- New `reload` method to refresh model state from the database.

## [0.7.2] - 2024-06-17

### Fixed

- Ensure TTL policies are created by `async_set_up_composite_indexes_and_ttl_policies`
  and `set_up_composite_indexes_and_ttl_policies` also when passing in the models as a
  generator, for example when using `get_all_subclasses()`.

## [0.7.1] - 2024-06-14

### Fixed

- Don't raise an `AttributeError` when setting up indexes for models if there's a model
  without any indexes (i.e. a model does not at all define the `__composite_indexes__`).
- Fix bug that the configured prefix was not used when creating indexes. Please note
  that if you have been using indexes and a collection name prefix, the indexes created
  before this fix will be for the wrong collection names (i.e. missing the prefix)! Thus
  please go through your indexes and remove the accidentally created ones after updating
  to this version.

## [0.7.0] - 2024-03-27

### Added

- Support for composite indexes via `__composite_indexes__` property in model classes.

## [0.6.0] - 2024-02-26

### Added

- Add support for order_by, limit and offset in find queries

## [0.5.1] - 2024-02-12

### Changed

- Fix pytest warnings in console output
- Update CI pipeline to use trusted PyPI publisher instead of a token
- Add make-changelog invoke command

## [0.5.0] - 2023-10-09

### Changed

- Update pydantic from version 1.x to version 2.x

## [0.4.0] - 2023-10-03

### Added

- Support for TTL policies and specifying a `__ttl_field__` in the model classes.

### Removed

- Remove support for Python 3.7, which is EOL, require 3.8.1 or newer.

### Changed

- Switch tests to use new firestore emulator, improve documentation about running it.
- Update authors (company was renamed to IOXIO Ltd).

## [0.3.0] - 2022-08-04

### Changed

- Update dependencies.
- Switch from Travis CI to GitHub actions.
- Update pre-commit hooks.
- Update links to GitHub repo due to organization rename.
- Switch to poetry-core.

### Added

- Add pre-commit hook and configs for prettier.

## [0.2.8] - 2021-10-26

### Fixed

- Validate special characters in document ID and ensure `get_by_id`/`get_by_doc_id`
  raises `ModelNotFoundError` in case of such issues. Especially an uneven number of
  slashes could raise a ValueError. Saving a model can now raise an `InvalidDocumentID`
  exception in case the ID is invalid.

## [0.2.7] - 2021-10-25

### Fixed

- `get_by_id`/`get_by_doc_id` with an empty string raises a `ModelNotFoundError` instead
  of leaking a `google.api_core.exceptions.InvalidArgument` exception.

## [0.2.6] - 2021-09-20

### Added

- Support for subcollections

### Fixed

- Fixing support for `_` prefixed document ID attributes

## [0.2.5] - 2021-08-20

### Added

- Support for customizing the field used to hold the document ID. By subclassing the
  `AsyncBareModel`/`BareModel` it's possible to use any field for the document ID, not
  just the `id`, which is used by `AsyncModel`/`Model`.

### Changed

- Update `grpcio` to `^1.39.0` which fixes a problem with emulator support on Windows.
- Pre-commit hooks for keeping line-endings consistent.

### Fixed

- Incorrect links in CHANGELOG.md

## [0.2.4] - 2021-05-24

### Fixed

- Allow firedantic to be used with older versions of `google-cloud-firestore` that works
  with the firestore emulator on Windows.

## [0.2.3] - 2021-05-21

### Added

- `firedantic.operators` with operators as constants to avoid gotchas with filters like
  `not-in` and `array_contains`. Preferable way to build queries is to
  `import firedantic.operators as op` and then use `op.NOT_IN`, `op.ARRAY_CONTAINS`,
  `op.GTE` and so on.

### Fixed

- Fix filter bug affecting `array_contains` and `array_contains_any`
- Update `pydantic` to ^1.8.2 that fixes CVE-2021-29510

## [0.2.2] - 2021-04-29

### Added

- Helpers for truncating collections

### Changed

- Make the filter optional for `find` and `find_one`

## [0.2.1] - 2021-03-31

### Changed

- Update `google-cloud-firestore` to 2.1.0 that supports async with firestore emulator.
  Using an officially released version of `google-cloud-firestore` from PyPI will also
  make it possible to get this release of `firedantic` uploaded to PyPI.

## [0.2.0] - 2021-03-29

### Added

- New AsyncModel that supports async and await syntax.

### Changed

- Refactor file structure; `models.py` no longer exists, so make sure to import `Model`
  directly from firedantic: `from firedantic import Model`
- Update `google-cloud-firestore`. The 2.0.2 version has an
  [issue with running in async mode against the emulator](https://github.com/googleapis/python-firestore/issues/286),
  that has been fixed in the git `master`, but not included in any official release yet.
  Using the latest master (pinned to the commit hash). In case you are using poetry to
  install `firedantic`, please be aware that poetry has an
  [issue with updating from a pypi package to a git commit](https://github.com/python-poetry/poetry/issues/3803).
  The simplest work-around is to after updating `firedantic` (and thus also
  `google-cloud-firestore`) delete the virtualenv and then run `poetry install` again
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

[unreleased]: https://github.com/ioxiocom/firedantic/compare/0.12.0...HEAD
[0.12.0]: https://github.com/ioxiocom/firedantic/compare/0.11.0...0.12.0
[0.11.0]: https://github.com/ioxiocom/firedantic/compare/0.10.0...0.11.0
[0.10.0]: https://github.com/ioxiocom/firedantic/compare/0.9.0...0.10.0
[0.9.0]: https://github.com/ioxiocom/firedantic/compare/0.8.1...0.9.0
[0.8.1]: https://github.com/ioxiocom/firedantic/compare/0.8.0...0.8.1
[0.8.0]: https://github.com/ioxiocom/firedantic/compare/0.7.2...0.8.0
[0.7.2]: https://github.com/ioxiocom/firedantic/compare/0.7.1...0.7.2
[0.7.1]: https://github.com/ioxiocom/firedantic/compare/0.7.0...0.7.1
[0.7.0]: https://github.com/ioxiocom/firedantic/compare/0.6.0...0.7.0
[0.6.0]: https://github.com/ioxiocom/firedantic/compare/0.5.1...0.6.0
[0.5.1]: https://github.com/ioxiocom/firedantic/compare/0.5.0...0.5.1
[0.5.0]: https://github.com/ioxiocom/firedantic/compare/0.4.0...0.5.0
[0.4.0]: https://github.com/ioxiocom/firedantic/compare/0.3.0...0.4.0
[0.3.0]: https://github.com/ioxiocom/firedantic/compare/0.2.8...0.3.0
[0.2.8]: https://github.com/ioxiocom/firedantic/compare/0.2.7...0.2.8
[0.2.7]: https://github.com/ioxiocom/firedantic/compare/0.2.6...0.2.7
[0.2.6]: https://github.com/ioxiocom/firedantic/compare/0.2.5...0.2.6
[0.2.5]: https://github.com/ioxiocom/firedantic/compare/0.2.4...0.2.5
[0.2.4]: https://github.com/ioxiocom/firedantic/compare/0.2.3...0.2.4
[0.2.3]: https://github.com/ioxiocom/firedantic/compare/0.2.2...0.2.3
[0.2.2]: https://github.com/ioxiocom/firedantic/compare/0.2.1...0.2.2
[0.2.1]: https://github.com/ioxiocom/firedantic/compare/0.2.0...0.2.1
[0.2.0]: https://github.com/ioxiocom/firedantic/compare/0.1.4...0.2.0
[0.1.4]: https://github.com/ioxiocom/firedantic/compare/0.1.3...0.1.4
[0.1.3]: https://github.com/ioxiocom/firedantic/compare/0.1.2...0.1.3
[0.1.2]: https://github.com/ioxiocom/firedantic/compare/0.1.1...0.1.2
[0.1.1]: https://github.com/ioxiocom/firedantic/compare/0.1.0...0.1.1
[0.1.0]: https://github.com/ioxiocom/firedantic/releases/tag/0.1.0
