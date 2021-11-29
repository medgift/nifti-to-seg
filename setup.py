from setuptools import setup, find_packages

setup(
    name="nifti-to-seg",
    version="1.0.0",
    url="https://github.com/roger-schaer/nifti-to-seg.git",
    author="Roger Schaer",
    author_email="roger.schaer@hevs.ch",
    description="This project allows you to convert a NIfTI file containing one or more non-overlapping regions-of-interest (ROIs) into the DICOM Segmentation (SEG) format",
    packages=find_packages(),
    install_requires=[
        "numpy",
        "pydicom-seg @ git+https://github.com/roger-schaer/pydicom-seg.git",
        "SimpleITK",
        "palettable",
    ],
)
