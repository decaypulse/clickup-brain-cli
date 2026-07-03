from setuptools import setup, find_packages
from pathlib import Path

# Читаем README
readme = Path(__file__).parent / "README-AGENT.md"
long_description = readme.read_text(encoding="utf-8") if readme.exists() else ""

setup(
    name="clickup-brain-cli",
    version="1.0.0",
    description="Полноценный AI агент с сессиями и памятью для ClickUp Brain",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Your Name",
    author_email="your.email@example.com",
    url="https://github.com/yourusername/clickup-brain-cli",
    packages=find_packages(),
    py_modules=["clickup_agent", "clickup_capture", "clickup_auth"],
    install_requires=[
        "playwright>=1.40.0",
        "rich>=13.0.0",
        "prompt_toolkit>=3.0.0",
        "requests>=2.28.0",
    ],
    entry_points={
        "console_scripts": [
            "braincli=clickup_agent:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Programming Language :: Python :: 3.11",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.11",
)
