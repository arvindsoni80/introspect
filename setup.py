"""Setup configuration for Introspect CLI."""

from setuptools import setup, find_packages
from pathlib import Path

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
with open(requirements_file) as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

# Read README for long description
readme_file = Path(__file__).parent / "README.md"
long_description = ""
if readme_file.exists():
    with open(readme_file, encoding="utf-8") as f:
        long_description = f.read()

setup(
    name="introspect",
    version="1.0.0",
    description="Gong Transcript MEDDPICC Analysis Tool",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/introspect",
    packages=find_packages(exclude=["tests", "tests.*", "venv", "venv.*"]),
    include_package_data=True,
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "introspect=src.cli:cli",
        ],
    },
    python_requires=">=3.8",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    keywords="gong meddpicc sales analysis",
)
