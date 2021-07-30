try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup

setup(
        name='zeromq-pyre',
        version='0.3.4',
        description='Python ZRE implementation',
        author='Arnaud Loonstra',
        author_email='arnaud@sphaero.org',
        url='http://www.github.com/zeromq/pyre/',
        packages=['pyre'],
        include_package_data=True,
        requires=['pyzmq', 'ipaddress'],
        install_requires=['pyzmq', 'ipaddress'],
        extra_requires={'deploy': ['bump2version', 'build'], 'test': ['nose']}
)
