from setuptools import find_packages, setup

setup(
    name="slack-service",
    version="0.1.0",
    description="FastAPI Slack service wrapper for OSPSD Homework 2",
    author="Team 4 - Fall 2025",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    include_package_data=True,
    install_requires=[
        "fastapi>=0.115.0",
        "pydantic>=2.7.0",
        "typing-extensions>=4.9.0",
    ],
    python_requires=">=3.10",
)
