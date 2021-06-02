# Maintenace

Maintenance is based on extra tools that are defined as [optional dependencies](https://setuptools.readthedocs.io/en/latest/userguide/dependency_management.html#optional-dependencies) in [`setup.py`](setup.py).
The sections below refer to them as "extra requirements".

## Testing

You can find a series of unit tests in the [`tests`](tests) directory. The recommended
way to execute them is by using the [`nose`](https://nose.readthedocs.io/en/latest/)
module. It is installed as part of the `test` extra requirements.

To run the tests, execute `python -m nose -v --exe`.

All tests are run automatically on new pull requests via a Github Action.

## Deployment

Deployment to [PyPI](https://pypi.org/project/zeromq-pyre/) is triggered by pushing a
new git tag to the `master` branch. As every git tag needs to have a unique name, and
PyPI requires new module versions for every new release, it is good practice to combine
version bumps with git tags. To simplify the process, this repository is set up to
automatically bump the `patch` version of the project after each merged pull request.
The commit containing the version bump is automatically tagged with the new version.

For this, a Github Action uses [`bump2version`](https://github.com/c4urself/bump2version)
(configured in [`.bumpversion.cfg`](.bumpversion.cfg)). To bump another version part
than the default (`patch`), add one of the `bump:*` labels to the pull request before
merging. Should more than one `bump:*` label be assigned, the Github action will bump
the part with the highest priority (`major` > `minor` > `patch`).

`bump2version` can be installed locally using the `deploy` extra requirements. To
manually bump the version, run `bump2version <part>`, where `<part>` is either `major`,
`minor`, or `patch`.

## Workflow
The workflow from a new pull request to a new PyPI release would look like this:

1. New pull request
1. Automated testing
1. Optional: Manually assign label indicating which version part to bump
1. Manual merge of pull request
1. Automated version bump and git tag
1. Automated PyPI deployment
