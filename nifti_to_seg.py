import argparse
import csv
import logging
import numpy as np
import SimpleITK
import pydicom
import pydicom_seg
from pathlib import Path
from palettable.tableau import tableau

# Set the log level
logging.basicConfig(level=logging.WARN)

# Create logger
logger = logging.getLogger("NIfTI to SEG")

# Get color palette
colormap = tableau.get_map("Tableau_20")

# Default CSV delimiter
CSV_DELIMITER = ","


def parse_args():
    parser = argparse.ArgumentParser(
        description="Convert NIfTI ROIs to the DICOM SEG format."
    )
    # DICOM path with the original images
    parser.add_argument(
        "-i",
        "--dicom_input",
        help="The path of the folder with the original DICOM images",
        required=True,
    )
    # NIfTI path with the ROI
    parser.add_argument(
        "-n",
        "--nifti_roi",
        help="The path of the NIfTI file containing the ROI(s) to convert to DICOM SEG",
        required=True,
    )
    # Output path for the DICOM SEG file
    parser.add_argument(
        "-o",
        "--output_seg",
        help="The path where the created DICOM SEG file should be saved",
        required=True,
    )
    # Label map for the ROIs
    parser.add_argument(
        "-l",
        "--label_map",
        help="The path to a CSV file containing pairs of <label_id>,<label_name> entries",
        required=False,
    )
    args = parser.parse_args()
    logger.debug(f"parsed args : {vars(args)}")
    return args


def get_nifti_labels(path):

    print("Reading NIfTI file to identify ROIs...")

    sitk_image = SimpleITK.ReadImage(path)
    image_data = SimpleITK.GetArrayFromImage(sitk_image)

    labels = np.trim_zeros(np.unique(image_data))
    for label in labels:
        logger.debug(f"found label n°{int(label)} in image")

    return labels


def map_nifti_labels_to_names(labels):

    print(
        f"Found {len(labels)} regions in the NIfTI file, please input a name for each of them."
    )

    labels_dict = {}
    i = 1
    for label in labels:
        label_name = input(
            f"({i}/{len(labels)}) - Please insert a name for the region with assigned number {int(label)}: "
        )
        labels_dict[label] = label_name
        i += 1

    print("Thank you, DICOM SEG file will be generated now...")

    return labels_dict


def parse_labelmap_file(labelmap_path, labels):
    labels_dict = {}
    line_count = 0

    with open(labelmap_path) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=CSV_DELIMITER)
        for row in csv_reader:
            label_id = row[0]
            label_name = row[1]
            labels_dict[int(label_id)] = label_name
            line_count += 1

        if len(labels) != line_count:
            raise ValueError(
                "Number of <label_id>,<label_name> pairs doesn't match the number of labels in the NIfTI file"
            )

        for label in labels:
            if label not in labels_dict:
                raise ValueError(
                    f"Label with pixel value {label} is not present in the CSV file!"
                )

        print(
            f"{len(labels)}/{len(labels)} labels correctly mapped with the provided CSV file, generating DICOM SEG file now..."
        )

    return labels_dict


def get_dicom_paths_from_dir(dicom_dir):
    files = Path(dicom_dir).glob("**/*")
    paths = [str(f) for f in files if f.is_file()]

    return paths


def generate_metadata(roi_dict):
    basic_info = {
        "ContentCreatorName": "NIfTI to SEG",
        "ClinicalTrialSeriesID": "Session1",
        "ClinicalTrialTimePointID": "1",
        "SeriesDescription": "Segmentation",
        "SeriesNumber": "300",
        "InstanceNumber": "1",
        "segmentAttributes": [get_segments(roi_dict)],
        "ContentLabel": "SEGMENTATION",
        "ContentDescription": "Image segmentation",
        "ClinicalTrialCoordinatingCenterName": "dcmqi",
        "BodyPartExamined": "",
    }

    return basic_info


def get_segments(roi_dict):
    segments = []

    for label, description in roi_dict.items():
        segments.append(
            get_segment(label, description, colormap.colors[label % len(colormap.colors)])
        )

    return segments


def get_segment(label, description, color):
    return {
        # Make sure we are using a simple int (not a NumPy type)
        "labelID": int(label),
        "SegmentDescription": description,
        "SegmentAlgorithmType": "AUTOMATIC",
        "SegmentAlgorithmName": "Automatic",
        # Snomed Coding for Tissue
        "SegmentedPropertyCategoryCodeSequence": {
            "CodeValue": "85756007",
            "CodingSchemeDesignator": "SCT",
            "CodeMeaning": "Tissue",
        },
        # Snomed Coding for Organ
        "SegmentedPropertyTypeCodeSequence": {
            "CodeValue": "113343008",
            "CodingSchemeDesignator": "SCT",
            "CodeMeaning": "Organ",
        },
        # Color to display
        "recommendedDisplayRGBValue": color,
    }


def nifti_to_seg(nifti_roi, dicom_input, seg_output, roi_dict):

    # Read NIfTI ROI with SimpleITK
    sitk_image = SimpleITK.ReadImage(nifti_roi)

    # A segmentation image with integer data type
    # and a single component per voxel
    segmentation: SimpleITK.Image = sitk_image

    # Paths to an imaging series related to the segmentation
    dicom_series_paths = get_dicom_paths_from_dir(dicom_input)
    source_images = [
        pydicom.dcmread(img, stop_before_pixels=True) for img in dicom_series_paths
    ]

    # Generate template JSON file based on the ROI dict
    metadata = generate_metadata(roi_dict)
    template = pydicom_seg.template.from_dcmqi_metainfo(metadata)

    # Write resulting DICOM SEG to the output
    writer = pydicom_seg.MultiClassWriter(
        template=template,
        # Crop image slices to the minimum bounding box on x and y axes
        inplane_cropping=False,
        # Don't encode slices with only zeros
        skip_empty_slices=False,
        # If a segment definition is missing in the template, then raise an error instead of skipping it
        skip_missing_segment=False,
    )
    dcm = writer.write(segmentation, source_images)
    dcm.save_as(seg_output)

    print(f"Successfully wrote output to {seg_output}")


if __name__ == "__main__":

    # Parse Args
    args = parse_args()

    # Load ROI to identify number & IDs of labels
    labels = get_nifti_labels(args.nifti_roi)

    # Map label ID to region names
    if not args.label_map:
        roi_dict = map_nifti_labels_to_names(labels)
    else:
        roi_dict = parse_labelmap_file(args.label_map, labels)

    # Transform NIfTI file to SEG using pydicom-seg
    seg_output = nifti_to_seg(
        args.nifti_roi, args.dicom_input, args.output_seg, roi_dict
    )
