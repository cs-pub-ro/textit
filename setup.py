from setuptools import setup, find_packages

setup(
    name="textit",
    version="0.1",
    packages=find_packages(where="src"),
    package_data={
        'project_name.processors.lang_id': ['lid.176.bin'],
    },
    include_package_data=True,
    package_dir={"": "src"},
)
