from setuptools import setup, find_packages

setup(
    name="tomasulo-simulator",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "PyQt6==6.6.1",
        "PyQt6-Qt6==6.6.1",
        "PyQt6-sip==13.6.0",
        "numpy==1.26.3"
    ],
) 