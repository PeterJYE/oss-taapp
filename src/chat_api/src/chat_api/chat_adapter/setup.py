"""Packaging metadata for slack_adapter."""

from setuptools import find_packages, setup

setup(
    name="slack_adapter",
    version="0.1.0",
    description="Service-backed Slack Chat Client adapter",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    package_data={"slack_adapter": ["py.typed"]},
    install_requires=[
        "httpx>=0.27",
        "fastapi>=0.110",
    ],
    python_requires=">=3.12",
)
