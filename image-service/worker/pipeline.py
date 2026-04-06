import logging
import random
from io import BytesIO
from typing import Any, Dict, List

from logging_config import log_event, setup_logging
from model_loader import get_default_pipeline

LOGGER = setup_logging()
logger = logging.getLogger("rendercart.worker")
_generation_pipeline = None


def check_gpu_availability() -> bool:
    try:
        import torch

        if not torch.cuda.is_available():
            logger.error("CUDA unavailable for worker")
            return False

        device_index = 0
        device_name = torch.cuda.get_device_name(device_index)
        total_mem_gb = torch.cuda.get_device_properties(device_index).total_memory / (1024 ** 3)
        free_mem_bytes, _ = torch.cuda.mem_get_info(device_index)
        free_mem_gb = free_mem_bytes / (1024 ** 3)

        log_event(
            LOGGER,
            event_type="gpu_preflight",
            status="ok",
            message="CUDA preflight checks passed",
            gpu_name=device_name,
            total_gb=round(total_mem_gb, 2),
            free_gb=round(free_mem_gb, 2),
        )

        if free_mem_gb < 2:
            logger.warning("Low available GPU memory", extra={"free_gb": round(free_mem_gb, 2)})
        return True
    except Exception as exc:
        logger.error("GPU preflight check failed", extra={"error": str(exc)})
        return False


def get_sdxl_pipeline():
    global _generation_pipeline
    if _generation_pipeline is None:
        if not check_gpu_availability():
            raise RuntimeError(
                "GPU preflight check failed. CUDA device is required for generation."
            )
        logger.info("Loading default generation pipeline")
        _generation_pipeline = get_default_pipeline()
    return _generation_pipeline


def generate_images(
    processed_data: Dict[str, Any],
    prompt: str,
    inference_params: Dict[str, Any],
    num_images: int = 1,
) -> List[bytes]:
    import torch
    from PIL import Image

    image = Image.open(BytesIO(processed_data["image_bytes"]))
    pipeline = get_sdxl_pipeline()

    generator = torch.Generator(device="cpu").manual_seed(random.randint(0, 2**32 - 1))
    images = pipeline(
        prompt=prompt,
        image=image,
        num_images_per_prompt=num_images,
        **inference_params,
        generator=generator,
    ).images

    output_format = processed_data.get("output_spec", {}).get("extension", "png").upper()
    if output_format == "JPG":
        output_format = "JPEG"

    rendered_images: List[bytes] = []
    for image in images:
        buffer = BytesIO()
        image.save(buffer, format=output_format)
        rendered_images.append(buffer.getvalue())
    return rendered_images
