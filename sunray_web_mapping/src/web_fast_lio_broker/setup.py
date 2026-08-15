from pathlib import Path

from setuptools import find_packages, setup


package_name = "web_fast_lio_broker"


def data_files_for_tree(root: str):
    entries = []
    root_path = Path(root)
    for path in root_path.rglob("*"):
        if path.is_file():
            entries.append((str(Path("share") / package_name / path.parent), [str(path)]))
    return entries


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", ["launch/mid360_web_mapping.launch.py"]),
        *data_files_for_tree("config"),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="chu",
    maintainer_email="chu@example.com",
    description="Broker and launch integration for FAST-LIO2, Livox MID-360, and web_mapping.",
    license="MIT",
    entry_points={
        "console_scripts": [
            "web_fast_lio_broker = web_fast_lio_broker.broker:main",
            "clean_map_batch_eval = web_fast_lio_broker.clean_map_batch_eval:main",
        ],
    },
)
