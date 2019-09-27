#!/usr/bin/env python
from setuptools import find_packages, setup


project = "microcosm-caching"
version = "0.3.0"

setup(
    name=project,
    version=version,
    description="Caching for microservices using microcosm.",
    author="Globality Engineering",
    author_email="engineering@globality.com",
    url="https://github.com/globality-corp/microcosm-caching",
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    include_package_data=True,
    zip_safe=False,
    python_requires=">=3.6",
    install_requires=[
        "boto3>=1.5.8",
        "marshmallow>=3.0.0",
        "microcosm>=2.12.0",
        "microcosm-logging>=1.3.0",
        "pymemcache>=2.2.2",
    ],
    extras_require={
        "metrics": "microcosm-metrics>=2.2.0",
    },
    setup_requires=[
        "nose>=1.3.6",
    ],
    dependency_links=[
    ],
    entry_points={
        "microcosm.factories": [
            "resource_cache = microcosm_caching.factories:configure_resource_cache",
        ]
    },
    tests_require=[
        "coverage>=3.7.1",
        "parameterized>=0.7.0",
        "PyHamcrest>=1.8.5",
    ],
)
