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
    parser = argparse.ArgumentParser(description="Convert NIfTI ROIs to the DICOM SEG format.")
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
    # Description for the generated DICOM series
    parser.add_argument(
        "-sd",
        "--series_description",
        help="The description of the generated DICOM-SEG series",
        required=False,
        default="Segmentation",
    )
    # Match orientation of segmentation image to  dicom series
    parser.add_argument(
        "-d",
        "--match_orientation",
        help="Match orientation of segmentation image to the dicom series.",
        required=False,
        const=True,
        default=False,
        nargs="?",
    )
    # Match size of segmentation image to dicom series
    parser.add_argument(
        "-s",
        "--match_size",
        help="Match size of segmentation image to the dicom series. WARNING: This involves resampling the segmentation image.",
        required=False,
        const=True,
        default=False,
        nargs="?",
    )
    # Skip empty slices
    parser.add_argument(
        "-e",
        "--skip_empty",
        help="Skip empty slices in the DICOM-SEG file to reduce file size",
        required=False,
        const=True,
        default=False,
        nargs="?",
    )
    # Inplane cropping
    parser.add_argument(
        "-c",
        "--inplane_cropping",
        help="Crop image slices to the minimum bounding box on x and y axes to reduce file size (not supported by OHIF)",
        required=False,
        const=True,
        default=False,
        nargs="?",
    )
    # Skip missing segment
    parser.add_argument(
        "-m",
        "--skip_missing_segment",
        help="Control whether to raise an error when a segment is missing rather than skipping it",
        required=False,
        const=True,
        default=False,
        nargs="?",
    )

    args = parser.parse_args()
    logger.debug(f"parsed args : {vars(args)}")
    return args


def get_nifti_labels(sitk_image):
    print("Reading NIfTI file to identify ROIs...")
    image_data = SimpleITK.GetArrayFromImage(sitk_image)

    labels = np.trim_zeros(np.unique(image_data))
    for label in labels:
        logger.debug(f"found label n°{int(label)} in image")

    return labels


def map_nifti_labels_to_names(labels):
    print(f"Found {len(labels)} regions in the NIfTI file, please input a name for each of them.")

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
            label_id = int(row[0].strip())
            label_name = row[1].strip()
            if label_id in labels:  # only include ids that are actually present in file
                labels_dict[label_id] = label_name
            line_count += 1

        for label in labels:  # check that all labels present in image are included in labels_dict
            if label not in labels_dict:
                raise ValueError(f"Label with pixel value {label} is not present in the CSV file!")

        print(
            f"{len(labels)}/{len(labels)} labels correctly mapped with the provided CSV file, generating DICOM SEG file now..."
        )

    return labels_dict


def get_dicom_paths_from_dir(dicom_dir):
    files = Path(dicom_dir).glob("**/*")
    paths = [str(f) for f in files if f.is_file()]

    return paths


def generate_metadata(roi_dict, series_description="Segmentation"):
    if roi_dict is not None:
        segment_attributes = [get_segments(roi_dict)]
    else:
        segment_attributes = [[get_segment(1, "Probability Map", colormap.colors[0])]]

    basic_info = {
        "ContentCreatorName": "NIfTI to SEG",
        "ClinicalTrialSeriesID": "Session1",
        "ClinicalTrialTimePointID": "1",
        "SeriesDescription": series_description,
        "SeriesNumber": "300",
        "InstanceNumber": "1",
        "segmentAttributes": segment_attributes,
        "ContentLabel": "SEGMENTATION",
        "ContentDescription": "Image segmentation",
        "ClinicalTrialCoordinatingCenterName": "dcmqi",
        "BodyPartExamined": "",
    }

    return basic_info


def get_segments(roi_dict):
    segments = []
    i = 0
    for label, description in roi_dict.items():
        segments.append(get_segment(label, description, colormap.colors[i % len(colormap.colors)]))
        i += 1

    return segments


def get_segment(label, description, color):
    return {
        # Make sure we are using a simple int (not a NumPy type)
        "labelID": int(label),
        "SegmentDescription": description,
        "SegmentLabel": description,
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


def match_orientation(sitk_img_ref, sitk_img_sec, verbose=True):
    orientation_filter = SimpleITK.DICOMOrientImageFilter()
    orientation_ref = orientation_filter.GetOrientationFromDirectionCosines(sitk_img_ref.GetDirection())
    orientation_sec = orientation_filter.GetOrientationFromDirectionCosines(sitk_img_sec.GetDirection())
    if verbose:
        print(f"Reference image has orientation '{orientation_ref}'")
        print(f"Second image has orientation    '{orientation_sec}'")
    if orientation_ref != orientation_sec:
        if verbose:
            print(f"Converting orientation of second image: '{orientation_sec}' --> '{orientation_ref}'")
        orientation_filter.SetDesiredCoordinateOrientation(orientation_ref)
        img_sec_reoriented = orientation_filter.Execute(sitk_img_sec)
        orientation_sec_reoriented = orientation_filter.GetOrientationFromDirectionCosines(
            img_sec_reoriented.GetDirection()
        )
        return img_sec_reoriented
    else:
        return sitk_img_sec


def match_size(sitk_img_ref, sitk_img_sec, verbose=True, interpolator=SimpleITK.sitkNearestNeighbor):
    size_ref = sitk_img_ref.GetSize()
    size_sec = sitk_img_sec.GetSize()
    if verbose:
        print(f"Reference image has size '{size_ref}'")
        print(f"Second image has size    '{size_sec}'")
    if not np.all(size_ref == size_sec):
        if verbose:
            print(f"Resampling second image: '{size_sec}' --> '{size_ref}'")
        resample = SimpleITK.ResampleImageFilter()
        resample.SetReferenceImage(sitk_img_ref)
        resample.SetInterpolator(interpolator)
        sitk_img_sec_resampled = resample.Execute(sitk_img_sec)
        return sitk_img_sec_resampled
    else:
        return sitk_img_sec


def get_dcm_as_sitk(path_to_dcm_dir):
    reader = SimpleITK.ImageSeriesReader()
    dicom_names = reader.GetGDCMSeriesFileNames(path_to_dcm_dir)
    reader.SetFileNames(dicom_names)
    image = reader.Execute()
    return image


def nifti_to_seg(
    sitk_image,
    dicom_input,
    seg_output,
    roi_dict,
    series_description="Segmentation",
    fractional=False,
    match_orientation_flag=False,
    match_size_flag=False,
    skip_empty_slices=True,
    inplane_cropping=False,
    skip_missing_segment=False,
):
    # A segmentation image with integer data type
    # and a single component per voxel
    segmentation: SimpleITK.Image = sitk_image

    # Check if segmentation needs to be cast to unsigned type
    if roi_dict is not None and segmentation.GetPixelID() not in [
        SimpleITK.sitkUInt8,
        SimpleITK.sitkUInt16,
        SimpleITK.sitkUInt32,
        SimpleITK.sitkUInt64,
    ]:
        segmentation = cast_to_unsigned(segmentation)

    # Paths to an imaging series related to the segmentation
    dicom_series_paths = get_dicom_paths_from_dir(dicom_input)
    source_images = [pydicom.dcmread(img, stop_before_pixels=True) for img in dicom_series_paths]

    # Generate template JSON file based on the ROI dict
    metadata = generate_metadata(roi_dict, series_description)
    template = pydicom_seg.template.from_dcmqi_metainfo(metadata)

    # Ensure that segmentation image and dicom image have same orientation and size
    if match_orientation_flag or match_size_flag:
        dicom_img = get_dcm_as_sitk(dicom_input)
        if match_orientation_flag:
            segmentation = match_orientation(dicom_img, segmentation, verbose=True)
        if match_size_flag:
            segmentation = match_size(
                dicom_img,
                segmentation,
                interpolator=SimpleITK.sitkNearestNeighbor,
                verbose=True,
            )

    # Choose writer class (fractional or multiclass)
    writer_class = pydicom_seg.FractionalWriter if fractional else pydicom_seg.MultiClassWriter

    arguments = {
        "template": template,
        "skip_empty_slices": skip_empty_slices,  # Crop image slices to the minimum bounding box on x and y axes
        "skip_missing_segment": skip_missing_segment,  # Control whether to raise an error when a segment is missing
    }

    if not fractional:
        arguments[
            "inplane_cropping"
        ] = inplane_cropping  # Crop image slices to the minimum bounding box on x and y axes

    # Write resulting DICOM SEG to the output
    writer = writer_class(**arguments)
    dcm = writer.write(segmentation, source_images)
    dcm.save_as(seg_output)

    print(f"Successfully wrote output to {seg_output}")


def cast_to_unsigned(segmentation):
    original_pixel_type = segmentation.GetPixelID()

    if original_pixel_type == SimpleITK.sitkInt8:
        new_pixel_type = SimpleITK.sitkUInt8
    elif original_pixel_type == SimpleITK.sitkInt16:
        new_pixel_type = SimpleITK.sitkUInt16
    elif original_pixel_type == SimpleITK.sitkInt32:
        new_pixel_type = SimpleITK.sitkUInt32
    elif original_pixel_type == SimpleITK.sitkInt64:
        new_pixel_type = SimpleITK.sitkUInt64
    else:
        raise ValueError("This segmentation pixel type is not supported!")

    casted_segmentation = SimpleITK.Cast(segmentation, new_pixel_type)

    return casted_segmentation


def is_fractional(sitk_image):
    return sitk_image.GetPixelID() in [SimpleITK.sitkFloat32, SimpleITK.sitkFloat64]


if __name__ == "__main__":

    # Parse Args
    args = parse_args()

    # Read NIfTI ROI with SimpleITK
    sitk_image = SimpleITK.ReadImage(args.nifti_roi)

    # Detect label type (integer = fixed classes, float = fractional)
    fractional = is_fractional(sitk_image)

    if not fractional:
        # If it is not fractional, identify number & IDs of labels
        labels = get_nifti_labels(sitk_image)

        # Map label ID to region names
        if not args.label_map:
            roi_dict = map_nifti_labels_to_names(labels)
        else:
            roi_dict = parse_labelmap_file(args.label_map, labels)
    else:
        roi_dict = None

    # Transform NIfTI file to SEG using pydicom-seg
    nifti_to_seg(
        sitk_image,
        args.dicom_input,
        args.output_seg,
        roi_dict,
        args.series_description,
        fractional,
        args.match_orientation,
        args.match_size,
        args.skip_empty,
        args.inplane_cropping,
        args.skip_missing_segment,
    )
