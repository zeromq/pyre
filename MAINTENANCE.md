# Maintenace

Maintenance is based on extra tools that are defined as [optional dependencies](https://setuptools.readthedocs.io/en/latest/userguide/dependency_management.html#optional-dependencies) in [`setup.py`](setup.py).
The sections below refer to them as "extra requirements".

To automate maintenance as much as possible, this repository features two Github Actions:
1. [Test on push or pull request](.github/workflows/test.yml) - see [Testing](#testing)
1. [Deploy to PyPI](.github/workflows/deploy.yml) - see [Deployment](#deployment)

## Testing

You can find a series of unit tests in the [`tests`](tests) directory. The recommended
way to execute them is by using the [`nose`](https://nose.readthedocs.io/en/latest/)
module. It is installed as part of the `test` extra requirements.

To run the tests locally, execute `python -m nose -v --exe` within the project's root directory.

All tests are run automatically on new pull requests via the
["Test on push or pull request" Github Action](.github/workflows/test.yml). This action
triggers on:
- new pull requests
- pull request updates
- commits being pushed to the `master` branch
- manual dispatch via [Github UI](https://github.com/zeromq/pyre/actions/workflows/test.yml)

## Deployment

Deployment works by bumping the version, building a source distribution (`sdist`), and
uploading it to [PyPI](https://pypi.org/project/zeromq-pyre/) using [`twine`](https://twine.readthedocs.io/).

These steps are automated as part of the ["Deploy to PyPI" Github Action](.github/workflows/deploy.yml).
See below for details.

### Versioning

This project follows the [Semantic Versioning Specification](https://semver.org/).

To avoid human error, it is recommended to use the
[`bump2version`](https://github.com/c4urself/bump2version) tool (configured in
[`.bumpversion.cfg`](.bumpversion.cfg)). `bump2version` can be installed locally using
the `deploy` extra requirements. To manually bump the version, run `bump2version <part>`,
where `<part>` is either `major`, `minor`, or `patch`.

**Note:** It is **not** recommended to run this tool manually. Instead, this step has
been automated as part of the ["Deploy to PyPI" Github Action](.github/workflows/deploy.yml).
To push the version-bumped commit back to the repo, the action requires more permissions
than the [default `GITHUB_TOKEN` provides](https://github.com/zeromq/pyre/pull/155#issuecomment-861020168). 
Instead, it [requires a personal access token](https://docs.github.com/en/actions/reference/authentication-in-a-workflow#granting-additional-permissions)
(PAT; stored and accessed as the `PERSONAL_ACCESS_TOKEN` secret). See below for further details.

### Building a distribution

The lowest common denominator for distributing a Python package is a [source distribution](https://packaging.python.org/guides/distributing-packages-using-setuptools/#source-distributions).
It is a single artifact that can be installed and tested on Python 2 and Python 3.

Note: It is best practice to also provide [pure Python wheels](https://packaging.python.org/guides/distributing-packages-using-setuptools/#pure-python-wheels).
But the project would have to provide different wheels for Python 2 and 3 which would
double the testing effort. Until project support for Python 2.7 is dropped (see #152 for
reference), it is likely the best option to only distribute source distributions.

The ["Test on push or pull request" Github Action](.github/workflows/test.yml) is
setup to install and test the same source distribution that is also distributed to PyPI.

### Python Package Index (PyPI)

The [Python Package Index (PyPI)](https://pypi.org/) is the official repository of
software for the Python programming language. Its tight integration with the [recommended
package installer (`pip`)](https://pypi.org/project/pip/) is the easiest way for users
to install the project. It also allows other projects to easily define this project as
a dependency.

When triggered, the ["Deploy to PyPI" Github Action](.github/workflows/deploy.yml) bumps
the version, builds a source distribution, and deploys it to PyPI. See [Github Action usage](#github-action-usage)
below for information when the Github Action is triggered and how to control the version
part that will be bumped.

#### Authentification

It is [strongly recommended to use PyPI API tokens](https://pypi.org/help/#apitoken) for
the deployment authentification. The ["Deploy to PyPI" Github Action](.github/workflows/deploy.yml)
is set up to use the [`PYPI_TOKEN` repository secret](https://github.com/zeromq/pyre/settings/secrets/actions)
as an API token.

### Github Action usage

The ["Deploy to PyPI" Github Action](.github/workflows/deploy.yml) triggers on:
- merged pull requests
- commits being pushed to the `master` branch
- manual dispatch via [Github UI](https://github.com/zeromq/pyre/actions/workflows/deploy.yml)

There are four version part values for automatic version bumping: `none`, `major`,
`minor`, `patch` (default).  For pull requests, you can assign one of the `bump:*`
labels. If no label is assigned, the action will default to bumping the `patch` part.
Should more than one `bump:*` label be assigned, the Github action will bump
the part with the highest priority (`none` > `major` > `minor` > `patch`).

For the manual action dispatch, one can pass one of the values directly to the action
via the UI.
