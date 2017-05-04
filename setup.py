try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

from pyre import __version__

setup(
        name='pyre',
        version=__version__,
        description='Python ZRE implementation',
        author='Arnaud Loonstra',
        author_email='arnaud@sphaero.org',
        url='http://www.github.com/zeromq/pyre/',
        packages=['pyre'],
        include_package_data=True,
        requires=['pyzmq', 'ipaddress'],
        install_requires=['pyzmq', 'ipaddress'],
)
