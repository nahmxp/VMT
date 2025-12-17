import argparse
import datetime as dt
import json
import os
import random
import shutil
import sys
import tempfile
import zipfile
from collections import defaultdict
from pathlib import Path

import albumentations as A
import cv2
import numpy as np
import yaml
from PIL import Image
from tqdm import tqdm
from ultralytics import YOLO


def log(msg: str) -> None:
    """Simple timestamped logger."""
    ts = dt.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts} UTC] {msg}", flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "End‑to‑end automation: COCO → YOLO conversion, "
            "YOLO augmentation, training, and TFLite export."
        )
    )

    parser.add_argument(
        "--coco-zip",
        required=True,
        help="Path to COCO dataset ZIP file (e.g. on Azure Files mount).",
    )
    parser.add_argument(
        "--base-model",
        required=True,
        help="Path to base YOLO .pt model (e.g. on Azure Files mount).",
    )
    parser.add_argument(
        "--work-dir",
        required=True,
        help=(
            "Local working directory on the VM where intermediate data is stored "
            "(datasets, runs, temporary models)."
        ),
    )
    parser.add_argument(
        "--tflite-out-dir",
        required=True,
        help=(
            "Directory (typically on Azure Files) where the final TFLite "
            "model will be copied with a datetime suffix."
        ),
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Number of training epochs (default: 100).",
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=50,
        help="Early‑stopping patience in epochs (default: 50).",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=24,
        help="Batch size for training (default: 24).",
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Training image size (default: 640).",
    )
    parser.add_argument(
        "--device",
        default="0",
        help="Training device: GPU index like '0' or 'cpu' (default: '0').",
    )

    return parser.parse_args()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


##############################################
#  COCO → YOLO CONVERSION (from app.py)
##############################################

def coco_to_yolo_noninteractive(
    coco_json: str,
    output_dir: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
) -> tuple[bool, int, int, int, list[str]]:
    """
    Logic copied from Product-detection/app.py::coco_to_yolo_streamlit,
    but without Streamlit callbacks/UI.
    """
    try:
        with open(coco_json, "r") as f:
            coco = json.load(f)

        images = {img["id"]: img for img in coco["images"]}
        annotations = coco["annotations"]
        categories = {cat["id"]: cat["name"] for cat in coco["categories"]}
        category_mapping = {cat_id: idx for idx, cat_id in enumerate(categories.keys())}

        # Create YOLO dirs with structure:
        # output_dir/train/images, valid/images, test/images and labels accordingly
        for split in ["train", "valid", "test"]:
            os.makedirs(os.path.join(output_dir, split, "images"), exist_ok=True)
            os.makedirs(os.path.join(output_dir, split, "labels"), exist_ok=True)

        # Split dataset
        image_ids = list(images.keys())
        random.shuffle(image_ids)
        n_train = int(len(image_ids) * train_ratio)
        n_val = int(len(image_ids) * val_ratio)
        train_ids = set(image_ids[:n_train])
        val_ids = set(image_ids[n_train : n_train + n_val])
        test_ids = set(image_ids[n_train + n_val :])

        img_to_anns: dict[int, list[dict]] = defaultdict(list)
        for ann in annotations:
            img_to_anns[ann["image_id"]].append(ann)

        total_images = len(img_to_anns)

        for img_id, anns in tqdm(img_to_anns.items(), desc="Converting COCO → YOLO"):
            img_info = images[img_id]
            file_name = img_info["file_name"]

            # width/height from JSON or image
            if "width" in img_info and "height" in img_info:
                width, height = img_info["width"], img_info["height"]
            else:
                img_path = Path(coco_json).parent / file_name
                with Image.open(img_path) as im:
                    width, height = im.size

            # Decide split (use "valid" instead of "val")
            if img_id in train_ids:
                split = "train"
            elif img_id in val_ids:
                split = "valid"
            else:
                split = "test"

            # Copy image to split/images
            src_path = Path(coco_json).parent / file_name
            dst_path = Path(output_dir) / split / "images" / Path(file_name).name
            os.makedirs(dst_path.parent, exist_ok=True)
            if os.path.exists(src_path):
                shutil.copy(src_path, dst_path)

            # Write YOLO label to split/labels
            label_path = Path(output_dir) / split / "labels" / (Path(file_name).stem + ".txt")
            with open(label_path, "w") as f:
                for ann in anns:
                    cat_id = ann["category_id"]
                    class_id = category_mapping[cat_id]

                    # Polygon segmentation if available
                    if (
                        "segmentation" in ann
                        and isinstance(ann["segmentation"], list)
                        and len(ann["segmentation"]) > 0
                    ):
                        poly = np.array(ann["segmentation"][0]).reshape(-1, 2)
                        poly[:, 0] /= width
                        poly[:, 1] /= height
                        poly_str = " ".join([f"{x:.6f} {y:.6f}" for x, y in poly])
                        f.write(f"{class_id} {poly_str}\n")
                    else:
                        # Fallback to bbox
                        x, y, w, h = ann["bbox"]
                        cx, cy = (x + w / 2) / width, (y + h / 2) / height
                        nw, nh = w / width, h / height
                        f.write(f"{class_id} {cx:.6f} {cy:.6f} {nw:.6f} {nh:.6f}\n")

        # Create classes.txt
        class_names = [categories[k] for k in sorted(categories.keys())]
        classes_path = Path(output_dir) / "classes.txt"
        with open(classes_path, "w") as cf:
            for class_name in class_names:
                cf.write(f"{class_name}\n")

        # Create data.yaml
        yaml_dict = {
            "path": str(Path(output_dir).absolute()),
            "train": "train/images",
            "val": "valid/images",
            "test": "test/images",
            "nc": len(class_names),
            "names": class_names,
        }
        with open(Path(output_dir) / "data.yaml", "w") as yf:
            yaml.dump(yaml_dict, yf, default_flow_style=False)

        return True, len(train_ids), len(val_ids), len(test_ids), class_names

    except Exception as exc:
        log(f"COCO → YOLO conversion failed: {exc}")
        return False, 0, 0, 0, []


def unzip_and_convert_noninteractive(
    zip_path: str,
    output_dir: str,
    train_ratio: float = 0.7,
    val_ratio: float = 0.2,
    test_ratio: float = 0.1,
) -> tuple[bool, int, int, int, list[str]]:
    """
    Wrapper around coco_to_yolo_noninteractive that mirrors
    unzip_and_convert_streamlit from Product-detection/app.py.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        log(f"Extracting COCO ZIP: {zip_path}")
        with zipfile.ZipFile(zip_path, "r") as zip_ref:
            zip_ref.extractall(tmpdir)

        # Find coco.json or *coco*.json inside extracted folder
        coco_json: str | None = None
        for root, _, files in os.walk(tmpdir):
            if "coco.json" in files:
                coco_json = os.path.join(root, "coco.json")
                break
            for file in files:
                if file.endswith(".json") and "coco" in file.lower():
                    coco_json = os.path.join(root, file)
                    break
            if coco_json:
                break

        if coco_json is None:
            raise FileNotFoundError("coco.json not found inside ZIP!")

        return coco_to_yolo_noninteractive(
            coco_json,
            output_dir,
            train_ratio=train_ratio,
            val_ratio=val_ratio,
            test_ratio=test_ratio,
        )


##############################################
#  AUGMENTATION (from app.py)
##############################################

def parse_yolo_label(line: str) -> dict:
    parts = line.strip().split()
    cls = int(parts[0])
    coords = list(map(float, parts[1:]))
    if len(coords) == 4:
        return {"class": cls, "bbox": coords, "poly": None}
    poly = [(coords[i], coords[i + 1]) for i in range(0, len(coords), 2)]
    return {"class": cls, "bbox": None, "poly": poly}


def save_yolo_label(path: Path, labels: list[dict]) -> None:
    with open(path, "w") as f:
        for lab in labels:
            cls = lab["class"]
            if lab["bbox"] is not None:
                cx, cy, w, h = lab["bbox"]
                f.write(f"{cls} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")
            elif lab["poly"] is not None:
                poly_str = " ".join([f"{x:.6f} {y:.6f}" for x, y in lab["poly"]])
                f.write(f"{cls} {poly_str}\n")


def reconstruct_polygons_from_keypoints(
    keypoints: list[tuple[float, float]],
    poly_splits: list[tuple[int, int, int]],
) -> list[tuple[int, list[tuple[float, float]]]]:
    polys: list[tuple[int, list[tuple[float, float]]]] = []
    for cls, start, length in poly_splits:
        pts = keypoints[start : start + length]
        polys.append((cls, pts))
    return polys


def polygon_to_bbox_norm(
    poly_pts: list[tuple[float, float]],
    img_w: int,
    img_h: int,
) -> list[float]:
    xs = [p[0] for p in poly_pts]
    ys = [p[1] for p in poly_pts]
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    cx = ((x1 + x2) / 2) / img_w
    cy = ((y1 + y2) / 2) / img_h
    bw = (x2 - x1) / img_w
    bh = (y2 - y1) / img_h
    return [cx, cy, bw, bh]


def low_res(img: np.ndarray, **kwargs: object) -> np.ndarray:
    scale_factor = np.random.uniform(0.3, 0.5)
    h, w = img.shape[:2]
    new_h, new_w = max(1, int(h * scale_factor)), max(1, int(w * scale_factor))
    img_small = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    img_up = cv2.resize(img_small, (w, h), interpolation=cv2.INTER_LINEAR)
    return img_up


def augment_dataset_noninteractive(
    input_dir: str,
    output_dir: str,
) -> tuple[bool, dict]:
    """
    Logic copied from Product-detection/app.py::augment_dataset_streamlit,
    but without Streamlit and callbacks.
    """
    try:
        input_path = Path(input_dir)
        output_path = Path(output_dir)

        if output_path.exists():
            shutil.rmtree(output_path)

        # Create output directories
        for split in ["train", "valid", "test"]:
            (output_path / split / "images").mkdir(parents=True, exist_ok=True)
            (output_path / split / "labels").mkdir(parents=True, exist_ok=True)

        geo_augs = [
            ("hflip", A.HorizontalFlip(p=1.0)),
            ("vflip", A.VerticalFlip(p=1.0)),
            ("rot90", A.Rotate(limit=(90, 90), p=1.0)),
            ("rot180", A.Rotate(limit=(180, 180), p=1.0)),
            ("rot270", A.Rotate(limit=(270, 270), p=1.0)),
            ("shear_x15", A.Affine(shear={"x": 15, "y": 0}, p=1.0)),
            ("shear_x-15", A.Affine(shear={"x": -15, "y": 0}, p=1.0)),
            ("shear_y15", A.Affine(shear={"x": 0, "y": 15}, p=1.0)),
            ("shear_y-15", A.Affine(shear={"x": 0, "y": -15}, p=1.0)),
        ]

        fine_rotations = [
            (f"rot{i}", A.Rotate(limit=(i, i), p=1.0)) for i in range(12, 360, 12)
        ]

        zoom_outs = [
            (f"zoom_{scale}", A.Affine(scale=scale / 100.0, p=1.0))
            for scale in range(90, 30, -10)
        ]

        geo_augs = geo_augs + fine_rotations + zoom_outs

        photo_augs = [
            ("brightness_contrast", A.RandomBrightnessContrast(brightness_limit=0.2, contrast_limit=0.2, p=0.7)),
            ("hsv_shift", A.HueSaturationValue(hue_shift_limit=15, sat_shift_limit=20, val_shift_limit=15, p=0.7)),
            ("rgb_shift", A.RGBShift(r_shift_limit=15, g_shift_limit=15, b_shift_limit=15, p=0.5)),
            ("clahe", A.CLAHE(clip_limit=2.0, tile_grid_size=(8, 8), p=0.3)),
            ("gamma", A.RandomGamma(gamma_limit=(80, 120), p=0.5)),
            ("motion_blur", A.MotionBlur(blur_limit=3, p=0.3)),
            ("gauss_noise", A.GaussNoise(p=0.3)),
            ("low_light", A.RandomBrightnessContrast(brightness_limit=(-0.6, -0.4), contrast_limit=(-0.4, -0.2), p=1.0)),
            ("overexposed", A.RandomBrightnessContrast(brightness_limit=(0.4, 0.6), contrast_limit=(0.2, 0.4), p=1.0)),
            (
                "reflection_reduce",
                A.Sequential(
                    [
                        A.MedianBlur(blur_limit=5, p=1.0),
                        A.ColorJitter(
                            brightness=0.3,
                            contrast=0.3,
                            saturation=0.3,
                            hue=0.1,
                            p=1.0,
                        ),
                    ],
                    p=1.0,
                ),
            ),
            ("low_res", A.Lambda(image=low_res, p=1.0)),
        ]

        stats: dict = {
            "original_images": 0,
            "augmented_images": 0,
            "total_augmentations": len(geo_augs) + len(photo_augs),
            "splits": {},
        }

        for split in ["train", "valid", "test"]:
            img_dir = input_path / split / "images"
            lbl_dir = input_path / split / "labels"
            out_img_dir = output_path / split / "images"
            out_lbl_dir = output_path / split / "labels"

            if not img_dir.exists():
                continue

            img_files = sorted(
                list(img_dir.glob("*.jpg"))
                + list(img_dir.glob("*.png"))
                + list(img_dir.glob("*.jpeg"))
            )

            split_stats = {
                "original": len(img_files),
                "augmented": 0,
            }

            log(f"[Augment] {split}: {len(img_files)} images")

            for img_file in img_files:
                label_file = lbl_dir / (img_file.stem + ".txt")
                image = cv2.imread(str(img_file))
                if image is None:
                    continue
                orig_h, orig_w = image.shape[:2]

                labels: list[dict] = []
                if label_file.exists():
                    with open(label_file, "r") as f:
                        for line in f:
                            if line.strip():
                                labels.append(parse_yolo_label(line))

                shutil.copy(str(img_file), str(out_img_dir / img_file.name))
                if label_file.exists():
                    shutil.copy(str(label_file), str(out_lbl_dir / label_file.name))

                keypoints: list[tuple[float, float]] = []
                keypoints_cls: list[int] = []
                poly_splits: list[tuple[int, int, int]] = []
                bboxes_pascal: list[list[float]] = []
                bboxes_cls: list[int] = []

                for lab in labels:
                    if lab["bbox"] is not None:
                        cx, cy, bw, bh = lab["bbox"]
                        x1 = (cx - bw / 2) * orig_w
                        y1 = (cy - bh / 2) * orig_h
                        x2 = (cx + bw / 2) * orig_w
                        y2 = (cy + bh / 2) * orig_h
                        bboxes_pascal.append([x1, y1, x2, y2])
                        bboxes_cls.append(lab["class"])
                    elif lab["poly"] is not None:
                        abs_poly = [(px * orig_w, py * orig_h) for px, py in lab["poly"]]
                        start = len(keypoints)
                        for pt in abs_poly:
                            keypoints.append(pt)
                            keypoints_cls.append(lab["class"])
                        poly_splits.append((lab["class"], start, len(abs_poly)))

                # 1) Geometric augmentations
                if len(bboxes_pascal) > 0 or len(keypoints) > 0:
                    for name, aug in geo_augs:
                        transform = A.Compose(
                            [aug],
                            bbox_params=A.BboxParams(
                                format="pascal_voc", label_fields=["bboxes_cls"]
                            ),
                            keypoint_params=A.KeypointParams(
                                format="xy",
                                remove_invisible=False,
                                label_fields=["keypoints_cls"],
                            ),
                        )

                        transformed = transform(
                            image=image,
                            bboxes=bboxes_pascal,
                            bboxes_cls=bboxes_cls,
                            keypoints=keypoints,
                            keypoints_cls=keypoints_cls,
                        )

                        aug_img = transformed["image"]
                        new_h, new_w = aug_img.shape[:2]

                        new_labels: list[dict] = []
                        for bbox, cls in zip(
                            transformed["bboxes"], transformed["bboxes_cls"]
                        ):
                            x1, y1, x2, y2 = bbox
                            cx = ((x1 + x2) / 2) / new_w
                            cy = ((y1 + y2) / 2) / new_h
                            bw = (x2 - x1) / new_w
                            bh = (y2 - y1) / new_h
                            new_labels.append(
                                {
                                    "class": cls,
                                    "bbox": [cx, cy, bw, bh],
                                    "poly": None,
                                }
                            )

                        if poly_splits:
                            polys = reconstruct_polygons_from_keypoints(
                                transformed["keypoints"], poly_splits
                            )
                            for cls, pts in polys:
                                norm = [
                                    (
                                        max(min(x / new_w, 1.0), 0.0),
                                        max(min(y / new_h, 1.0), 0.0),
                                    )
                                    for x, y in pts
                                ]
                                if len(norm) >= 3:
                                    new_labels.append(
                                        {
                                            "class": cls,
                                            "bbox": None,
                                            "poly": norm,
                                        }
                                    )
                                else:
                                    bbox_norm = polygon_to_bbox_norm(
                                        [(x * new_w, y * new_h) for x, y in norm],
                                        new_w,
                                        new_h,
                                    )
                                    new_labels.append(
                                        {
                                            "class": cls,
                                            "bbox": bbox_norm,
                                            "poly": None,
                                        }
                                    )

                        cv2.imwrite(
                            str(out_img_dir / f"{img_file.stem}_{name}.jpg"), aug_img
                        )
                        save_yolo_label(
                            out_lbl_dir / f"{img_file.stem}_{name}.txt", new_labels
                        )
                        split_stats["augmented"] += 1

                # 2) Photometric augmentations
                for name, aug in photo_augs:
                    transform = A.Compose([aug])
                    transformed = transform(image=image)
                    aug_img = transformed["image"]
                    new_h, new_w = aug_img.shape[:2]

                    cv2.imwrite(
                        str(out_img_dir / f"{img_file.stem}_{name}.jpg"), aug_img
                    )

                    new_labels = []
                    for bbox, cls in zip(bboxes_pascal, bboxes_cls):
                        x1, y1, x2, y2 = bbox
                        cx = ((x1 + x2) / 2) / new_w
                        cy = ((y1 + y2) / 2) / new_h
                        bw = (x2 - x1) / new_w
                        bh = (y2 - y1) / new_h
                        new_labels.append(
                            {
                                "class": cls,
                                "bbox": [cx, cy, bw, bh],
                                "poly": None,
                            }
                        )

                    for cls, start, length in poly_splits:
                        pts = keypoints[start : start + length]
                        norm = [(x / new_w, y / new_h) for x, y in pts]
                        if len(norm) >= 3:
                            new_labels.append(
                                {
                                    "class": cls,
                                    "bbox": None,
                                    "poly": norm,
                                }
                            )
                        else:
                            bbox_norm = polygon_to_bbox_norm(pts, new_w, new_h)
                            new_labels.append(
                                {
                                    "class": cls,
                                    "bbox": bbox_norm,
                                    "poly": None,
                                }
                            )

                    save_yolo_label(
                        out_lbl_dir / f"{img_file.stem}_{name}.txt", new_labels
                    )
                    split_stats["augmented"] += 1

            stats["splits"][split] = split_stats
            stats["original_images"] += split_stats["original"]
            stats["augmented_images"] += split_stats["augmented"]

        # Update YAML
        input_yaml_candidates = ["dataset.yaml", "data.yaml"]
        input_yaml_path: Path | None = None
        for yaml_name in input_yaml_candidates:
            candidate = input_path / yaml_name
            if candidate.exists():
                input_yaml_path = candidate
                break

        output_yaml_path = output_path / "data.yaml"
        if input_yaml_path:
            with open(input_yaml_path, "r") as f:
                data_cfg = yaml.safe_load(f)
            data_cfg["path"] = str(output_path.resolve())
            data_cfg["train"] = "train/images"
            data_cfg["val"] = "valid/images"
            data_cfg["test"] = "test/images"
            with open(output_yaml_path, "w") as f:
                yaml.safe_dump(data_cfg, f, sort_keys=False)

            if "names" in data_cfg:
                classes_path = output_path / "classes.txt"
                with open(classes_path, "w") as cf:
                    for name in data_cfg["names"]:
                        cf.write(f"{name}\n")

        return True, stats

    except Exception as exc:
        log(f"Augmentation failed: {exc}")
        return False, {"error": str(exc)}


def step_coco_to_yolo(coco_zip: Path, yolo_root: Path) -> Path:
    """
    Convert COCO ZIP → YOLO dataset using the same logic as
    Product-detection/app.py (COCO to YOLO converter tab).

    Returns the path to the generated dataset YAML file.
    """
    log(f"Step 1/4: COCO → YOLO conversion\n  COCO ZIP: {coco_zip}\n  YOLO root: {yolo_root}")

    if not coco_zip.is_file():
        raise FileNotFoundError(f"COCO ZIP not found: {coco_zip}")

    if yolo_root.exists():
        log(f"  Removing existing YOLO directory: {yolo_root}")
        shutil.rmtree(yolo_root)

    ensure_dir(yolo_root)

    success, n_train, n_val, n_test, _ = unzip_and_convert_noninteractive(
        zip_path=str(coco_zip),
        output_dir=str(yolo_root),
        train_ratio=0.7,
        val_ratio=0.2,
        test_ratio=0.1,
    )
    if not success:
        raise RuntimeError("COCO → YOLO conversion failed")

    log(f"  COCO → YOLO images: train={n_train}, val={n_val}, test={n_test}")

    # This function creates data.yaml, matching the Streamlit app behavior
    dataset_yaml = yolo_root / "data.yaml"
    if not dataset_yaml.is_file():
        # Older code path used dataset.yaml; check that too
        alt = yolo_root / "dataset.yaml"
        if alt.is_file():
            dataset_yaml = alt
        else:
            raise FileNotFoundError(
                f"Expected data.yaml or dataset.yaml not found in {yolo_root}"
            )

    log(f"  COCO → YOLO complete. Dataset YAML: {dataset_yaml}")
    return dataset_yaml


def step_augment_yolo(yolo_root: Path, aug_root: Path) -> Path:
    """
    Augment YOLO dataset using the same logic as
    Product-detection/app.py (Dataset Augmentation tab).

    Returns the path to the augmented dataset YAML file (data.yaml).
    """
    log(f"Step 2/4: YOLO dataset augmentation\n  Input: {yolo_root}\n  Output: {aug_root}")

    # Accept either dataset.yaml or data.yaml (matching Product-detection/app.py behavior)
    dataset_yaml = yolo_root / "dataset.yaml"
    data_yaml = yolo_root / "data.yaml"
    if not dataset_yaml.is_file() and not data_yaml.is_file():
        raise FileNotFoundError(
            f"Input dataset.yaml or data.yaml not found under {yolo_root}"
        )

    if aug_root.exists():
        log(f"  Removing existing augmented dataset directory: {aug_root}")
        shutil.rmtree(aug_root)

    success, stats = augment_dataset_noninteractive(
        input_dir=str(yolo_root),
        output_dir=str(aug_root),
    )
    if not success:
        raise RuntimeError(f"Augmentation failed: {stats.get('error')}")

    log(
        f"  Augmentation stats: original={stats.get('original_images', 0)}, "
        f"augmented={stats.get('augmented_images', 0)}"
    )

    aug_yaml = aug_root / "data.yaml"
    if not aug_yaml.is_file():
        raise FileNotFoundError(f"Expected augmented data.yaml not found at {aug_yaml}")

    log(f"  Augmentation complete. Augmented YAML: {aug_yaml}")
    return aug_yaml


def step_train(
    base_model_path: Path,
    data_yaml: Path,
    work_dir: Path,
    epochs: int,
    patience: int,
    batch: int,
    imgsz: int,
    device: str,
) -> Path:
    """
    Train YOLO model on the augmented dataset.

    Returns the path to the best.pt weights file.
    """
    log(
        "Step 3/4: Training YOLO model\n"
        f"  Base model: {base_model_path}\n"
        f"  Dataset YAML: {data_yaml}\n"
        f"  Epochs: {epochs}, Patience: {patience}, Batch: {batch}, ImgSz: {imgsz}, Device: {device}"
    )

    if not base_model_path.is_file():
        raise FileNotFoundError(f"Base model not found: {base_model_path}")
    if not data_yaml.is_file():
        raise FileNotFoundError(f"Dataset YAML not found: {data_yaml}")

    runs_root = work_dir / "runs" / "segment"
    ensure_dir(runs_root)

    timestamp = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    run_name = f"train_{timestamp}"

    model = YOLO(str(base_model_path))

    results = model.train(
        data=str(data_yaml),
        imgsz=imgsz,
        batch=batch,
        epochs=epochs,
        patience=patience,
        workers=0,
        device=device,
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        weight_decay=0.0005,
        dropout=0.2,
        mosaic=1.0,
        mixup=0.15,
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        project=str(runs_root),
        name=run_name,
        exist_ok=True,
        verbose=True,
    )

    save_dir = Path(results.save_dir)
    best_path = save_dir / "weights" / "best.pt"
    if not best_path.is_file():
        raise FileNotFoundError(f"best.pt not found at {best_path}")

    log(f"  Training complete. Best weights: {best_path}")
    return best_path


def step_export_tflite(best_model_path: Path, tflite_out_dir: Path) -> Path:
    """
    Export best.pt → TFLite and copy into the requested output directory with datetime suffix.

    Returns the final TFLite path on (e.g.) Azure Files.
    """
    log(
        "Step 4/4: TFLite export\n"
        f"  Input model: {best_model_path}\n"
        f"  TFLite output directory: {tflite_out_dir}"
    )

    if not best_model_path.is_file():
        raise FileNotFoundError(f"Best model not found: {best_model_path}")

    ensure_dir(tflite_out_dir)

    model = YOLO(str(best_model_path))
    exported_path = Path(model.export(format="tflite"))

    if not exported_path.is_file():
        raise FileNotFoundError(f"TFLite export failed, file not found: {exported_path}")

    timestamp = dt.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base_name = best_model_path.stem
    final_name = f"{base_name}_{timestamp}.tflite"
    final_path = tflite_out_dir / final_name

    shutil.copy2(exported_path, final_path)
    log(f"  TFLite export complete.\n    Raw export: {exported_path}\n    Copied to: {final_path}")
    return final_path


def main() -> None:
    args = parse_args()

    coco_zip = Path(args.coco_zip).resolve()
    base_model = Path(args.base_model).resolve()
    work_dir = Path(args.work_dir).resolve()
    tflite_out_dir = Path(args.tflite_out_dir).resolve()

    log("=== Product Detection Training Automation Started ===")
    log(f"Work dir: {work_dir}")

    ensure_dir(work_dir)

    # Directory layout under work_dir
    yolo_root = work_dir / "dataset" / "yolo"
    aug_root = work_dir / "dataset" / "yolo_aug"

    # 1. COCO → YOLO
    dataset_yaml = step_coco_to_yolo(coco_zip, yolo_root)

    # 2. Augmentation
    aug_yaml = step_augment_yolo(yolo_root, aug_root)

    # 3. Training
    best_model_path = step_train(
        base_model_path=base_model,
        data_yaml=aug_yaml,
        work_dir=work_dir,
        epochs=args.epochs,
        patience=args.patience,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device,
    )

    # 4. TFLite export
    final_tflite = step_export_tflite(best_model_path, tflite_out_dir)

    log("=== Automation completed successfully ===")
    log(f"Final TFLite model: {final_tflite}")


if __name__ == "__main__":
    main()


