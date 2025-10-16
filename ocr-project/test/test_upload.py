import logging
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("test_upload.log"),
    ],
)
logger = logging.getLogger("upload_test")


def test_file_upload(
    file_path: str,
    api_url: str = "http://localhost:8000/api/v1/files",
    timeout: int = 30,
) -> requests.Response | None:
    try:
        file_path = Path(file_path)
        logger.info("Uploading file: %s", file_path.name)

        with file_path.open("rb") as f:
            files = {"file": (file_path.name, f, get_content_type(file_path))}
            response = requests.post(api_url, files=files, timeout=timeout)

        logger.info("Status Code: %s", response.status_code)
        try:
            logger.info("Response: %s", response.json())
        except Exception:
            logger.exception("Response Text: %s", response.text)
    except Exception:
        logger.exception(
            "Error uploading file %s",
            file_path.name,
        )
        return None
    return response


def get_content_type(file_path: Path) -> str:
    extension = file_path.suffix.lower()
    if extension == ".pdf":
        return "application/pdf"
    if extension in [".png"]:
        return "image/png"
    if extension in [".jpg", ".jpeg"]:
        return "image/jpeg"
    return "application/octet-stream"


def test_multiple_files(
    image_dir: str,
    file_extensions: list[str] | None = None,
) -> None:
    if file_extensions is None:
        file_extensions = [".pdf", ".png", ".jpg", ".jpeg"]

    image_dir = Path(image_dir)
    if not image_dir.exists() or not image_dir.is_dir():
        logger.error(
            "Directory %s does not exist or is not a directory",
            image_dir,
        )
        return

    files_to_test = []
    for ext in file_extensions:
        files_to_test.extend(image_dir.glob(f"*{ext}"))

    if not files_to_test:
        logger.warning(
            "No files with extensions %s found in %s",
            file_extensions,
            image_dir,
        )
        return

    logger.info("Found %d files to upload:", len(files_to_test))
    for i, file in enumerate(files_to_test, 1):
        logger.info("%d. %s", i, file.name)

    for file in files_to_test:
        test_file_upload(file)
        time.sleep(1)


if __name__ == "__main__":
    test_images_path = Path(__file__).parent / "test_images"

    if not test_images_path.exists():
        test_images_path.mkdir(parents=True)
        logger.info("Created test images directory: %s", test_images_path)
        logger.info(
            "Please place your test files (PDF, PNG, JPG) in this directory",
        )
    else:
        logger.info("Starting test upload process")
        test_multiple_files(str(test_images_path))
