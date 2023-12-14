# NIfTI to SEG Converter

This project allows you to convert a NIfTI file containing
one or more non-overlapping regions-of-interest (ROIs)
into the DICOM Segmentation (SEG) format.

## Getting Started

The following instructions will help you to perform your
first NIfTI to SEG conversion. 

### Prerequisites

You can either run the project directly with Python, or
use Docker instead. If you want to run it directly with
Python, you need to install the dependencies listed in
requirements.txt:

```
numpy
git+https://github.com/roger-schaer/pydicom-seg.git#egg=pydicom-seg
SimpleITK
palettable
```

### General usage

The script expects the following arguments:

* `-i, --dicom_input` :  The path of the folder with the 
original DICOM images (from which ROIs were extracted)
* `-n, --nifti_roi` : The path of the NIfTI file containing 
the ROI(s) to convert to DICOM SEG
* `-o, --output_seg` : The path where the created DICOM SEG 
file should be saved
* `-l, --label_map` : *(OPTIONAL)* The path to a CSV file containing 
pairs of `<label_id>,<label_name>` entries
* `-d, --match_orientation` : *(OPTIONAL)* No value; 
  presence of argument indicates that orientation of NIfTI file will be matched to DICOM images  
* `-s, --match_size` : *(OPTIONAL)* No value; 
  presence of argument indicates that size of NIfTI file will be matched to DICOM images.
* `-e, --skip_empty` : *(OPTIONAL)* No value;
  presence of argument indicates that empty slices should not be included in the output DICOM SEG file
* `-c, --inplane_cropping` : *(OPTIONAL)* No value;
  presence of argument indicates that the images should be cropped to the minimum bounding box on the
  x & y axes (NOTE: this is not supported for display by all image viewers, e.g. OHIF)
* `-m, --skip_missing_segment` : *(OPTIONAL)* No value;
  presence of argument indicates that segments not declared in the provided label map should be skipped
  rather than an error being raised about the missing segment metadata
  
To execute the script, run:

```
python nifti_to_seg.py -i /path/to/dicom/images -n /path/to/nifti.nii -o /path/to/seg.dcm
```

When the script is executed, it will analyze the provided 
NIfTI file to identify the various ROIs saved within. This
is done by detecting the **unique** pixel values present in
the image.

#### Without a label map file (manual label name entry)

If you have not provided a label map file path, you will then 
be prompted to map each of these values to a string describing 
the content of the associated ROI. To know which pixel value 
corresponds to which ROI, you may need to refer to the software 
that generated the NIfTI file (e.g. ITK-SNAP, which uses label 
numbers starting from 1).

The output looks like this:

```
Found X regions in the NIfTI file, please input a name for each of them.
(1/X) - Please insert a name for the region with the assigned number N: ...
```

Once the names have been input, the SEG file will be
generated and saved at the path provided in the `-o`
argument.

#### With a label map file (bulk processing)

Instead of inputting the label mappings manually, you can also provide
the `-l` / `--label_map` parameter pointing to a CSV file containing
pairs of `<label_id>,<label_name>` entries.

**NOTE :** This methods requires you to know in advance the existing
pixel values in the NIfTI segmentation file. Only exhaustive files
containing a label for each identified pixel value are accepted.

## Usage with Docker

To run the script using docker, use the following syntax:

``` 
docker run --rm -it \
-v /path/to/data/on/host:/data \
medgift/nifti-to-seg:latest \
--dicom_input=/data/dicom_folder \
--nifti_roi=/data/seg.nii \
--output_seg=/data/seg.dcm \
--label_map=/data/labels.csv (OPTIONAL)
... (other OPTIONAL arguments)
```

The parameters are the following:
* `--rm` removes the container once the script completes.
* `-it` allows interacting with the container in the console.
* `medgift/nifti-to-seg:latest` is the Docker image.
* `-v` maps a folder from your computer to the container (on `/data`). 
Put all necessary files in that folder (DICOM & NIfTI), and the
output will be written there as well.
* The other parameters are the same as for general Python usage.

## Usage with Singularity  

See the [singularity](https://sylabs.io/docs/) pages for setup.

### Building Image
Enter the directory where this readme file is located.
Build the singularity image with name *meshtool.sif* by

```
sudo singularity build nifti_to_seg.sif Singularity.nifti-to-seg
```

### Running MeshTool from Singularity Image

You can enter a shell in the singularity container by

```
singularity shell -e /path/to/nifti_to_seg.sif
```

Leave the singularity shell again with `exit`.

## Authors

* **Roger Schaer** - *Initial work* - [roger-schaer](https://github.com/roger-schaer)
* **Daniel Abler** - *Improvements and Singularity support*  - [danielabler](https://github.com/danielabler)

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details

## Acknowledgments

* [razorx89](https://github.com/razorx89) for the great work 
on [pydicom-seg](https://github.com/razorx89/pydicom-seg),
which is the core of this script

