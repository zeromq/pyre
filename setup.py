import os
import io
import re
try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def read(*names, **kwargs):
    with io.open(
        os.path.join(os.path.dirname(__file__), *names),
        encoding=kwargs.get("encoding", "utf8")
    ) as fp:
        return fp.read()


# pip's single-source version method as described here:
# https://python-packaging-user-guide.readthedocs.io/single_source_version/
def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^__version__ = ['\"]([^'\"]*)['\"]",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


setup(
        name='pyre',
        version=find_version('pyre', '__init__.py'),
        description='Python ZRE implementation',
        author='Arnaud Loonstra',
        author_email='arnaud@sphaero.org',
        url='http://www.github.com/zeromq/pyre/',
        packages=['pyre'],
        include_package_data=True,
        requires=['pyzmq', 'ipaddress'],
        install_requires=['pyzmq', 'ipaddress'],
)
