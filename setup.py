from setuptools import setup, find_packages

setup(
    name="flakeforge",
    version="1.0.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "libcst>=1.1.0",
        "pytest>=8.0.0",
        "pytest-asyncio>=0.23.0",
        "rich>=13.7.0",
        "click>=8.1.7",
        "httpx>=0.27.0",
        "pydantic>=2.6.0",
        "pydantic-settings>=2.2.0",
        "fastapi>=0.110.0",
        "uvicorn[standard]>=0.28.0",
    ],
    entry_points={
        "console_scripts": [
            "flakeforge=flakeforge.cli:main",
        ],
        "pytest11": [
            "flakeforge=flakeforge.pytest_plugin",
        ],
    },
)
