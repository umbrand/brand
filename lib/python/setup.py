from setuptools import setup

setup(
    name='brand',
    version='0.0.0',
    packages=['brand'],
    # Specify any packages that our package itself requires.
    install_requires=[
        'coloredlogs',
        'redis',
        'pyyaml',
        'psutil==5.9.1'
    ]
)
