"""
KOPPA Language — setup.py
Install with:  pip install .
Then run:      koppa run script.kop
"""
from setuptools import setup, find_packages
from pathlib import Path

long_description = (Path(__file__).parent / "README.md").read_text(encoding="utf-8")

setup(
    name="koppa-lang",
    version="2.0.0",
    description="KOPPA — Advanced Pentesting Domain-Specific Language",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="KOPPA Team",
    python_requires=">=3.8",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    py_modules=[
        "koppa",
        "lexer",
        "parser",
        "interpreter",
        "compiler",
        "vm",
        "apollo_opcodes",
        "deno_compiler",
    ],
    entry_points={
        "console_scripts": [
            "koppa=koppa:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["../stdlib/*.kop", "../stdlib/*.apo", "../examples/*.kop"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Security",
        "Topic :: Software Development :: Interpreters",
    ],
)
