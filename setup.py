try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from os.path import join
with open(join('pyre', 'VERSION')) as version_file:
    version = version_file.read().strip()

setup(
        name='pyre',
        version=version,
        description='Python ZRE implementation',
        author='Arnaud Loonstra',
        author_email='arnaud@sphaero.org',
        url='http://www.github.com/zeromq/pyre/',
        packages=['pyre'],
        include_package_data=True,
        requires=['pyzmq', 'ipaddress'],
        install_requires=['pyzmq', 'ipaddress'],
)
