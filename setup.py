#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""The setup script."""

from setuptools import setup, find_packages

with open('README.md', encoding='utf-8') as readme_file:
    readme = readme_file.read()

with open('HISTORY.md', encoding='utf-8') as history_file:
    history = history_file.read()

install_requires = [
    # Core data science libraries with ARM64 support
    'pandas>=2.0.0',  # Explicit pandas version for data manipulation
    'numpy>=1.24.0',  # Required for pandas and sklearn
    'scikit-learn>=1.3.0',
    'featuretools>=1.27.0',
    'woodwork>=0.31.0',  # Required for featuretools 1.0+ compatibility
    'xgboost>=2.0.0',
    'shap>=0.43.0',

    # Flask stack - updated to latest stable versions
    'flask>=2.3.0',
    'flask-restful>=0.3.10',
    'flask-cors>=4.0.0',
    'flasgger>=0.9.7.1',
    
    # Additional core dependencies
    'python-dateutil>=2.8.0',  # Required for pandas date functionality
    'pytz>=2023.3',  # Required for timezone handling
]

setup_requires = [
    'pytest-runner>=6.0.0',
]

tests_require = [
    'pytest>=7.4.0',
    'pytest-cov>=4.1.0',
]

development_requires = [
    # general
    'bumpversion>=0.6.0',
    'pip>=23.0.0',
    'watchdog>=3.0.0',

    # docs
    'm2r2>=0.3.0',  # Updated from m2r
    'Sphinx>=7.0.0',
    'sphinx_rtd_theme>=1.3.0',
    'autodocsumm>=0.2.8',

    # style check
    'flake8>=6.1.0',
    'isort>=5.12.0',

    # fix style issues
    'autoflake>=2.2.0',
    'autopep8>=2.0.0',

    # distribute on PyPI
    'twine>=4.0.0',
    'wheel>=0.41.0',

    # Advanced testing
    'coverage>=7.3.0',
    'tox>=4.0.0',
]

setup(
    author='MIT Data To AI Lab',
    author_email='dailabmit@gmail.com',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Natural Language :: English',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: POSIX :: Linux',
    ],
    description='Python Boilerplate contains all the boilerplate you need to create a Python '
                'package.',
    extras_require={
        'test': tests_require,
        'dev': development_requires + tests_require,
    },
    install_package_data=True,
    install_requires=install_requires,
    license='MIT license',
    long_description=readme + '\n\n' + history,
    long_description_content_type='text/markdown',
    include_package_data=True,
    keywords='vbridge vbridge VBridge',
    name='vbridge',
    packages=find_packages(include=['vbridge', 'vbridge.*']),
    python_requires='>=3.8',  # Updated minimum Python version
    setup_requires=setup_requires,
    test_suite='tests',
    tests_require=tests_require,
    url='https://github.com/DAI-Lab/vbridge',
    version='0.1.0.dev0',
    zip_safe=False,
)
