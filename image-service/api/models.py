import json
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import redis
from business_presets import GenerationMode, OutputFormat, ProductCategory, UseCase
from config import settings
from pydantic import BaseModel


class BrandKitStyleSnapshot(BaseModel):
    name: Optional[str] = None
    background: str
    lighting: str
    tone: str
    framing: str

    def to_brand_style(self) -> str:
        return ", ".join(
            item
            for item in [
                f"background: {self.background}" if self.background else None,
                f"lighting: {self.lighting}" if self.lighting else None,
                f"tone: {self.tone}" if self.tone else None,
                f"framing: {self.framing}" if self.framing else None,
            ]
            if item
        )


class BrandKitBase(BaseModel):
    name: str
    background: str
    lighting: str
    tone: str
    framing: str

    def __init__(self, **data):
        super().__init__(**data)
        for field_name in ("name", "background", "lighting", "tone", "framing"):
            value = getattr(self, field_name)
            if not value or not value.strip():
                raise ValueError(f"{field_name} is required")
            setattr(self, field_name, value.strip())


class BrandKitCreateRequest(BrandKitBase):
    pass


class BrandKitUpdateRequest(BaseModel):
    name: Optional[str] = None
    background: Optional[str] = None
    lighting: Optional[str] = None
    tone: Optional[str] = None
    framing: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        provided_values = 0
        for field_name in ("name", "background", "lighting", "tone", "framing"):
            value = getattr(self, field_name)
            if value is None:
                continue
            trimmed = value.strip()
            if not trimmed:
                raise ValueError(f"{field_name} cannot be empty")
            setattr(self, field_name, trimmed)
            provided_values += 1
        if provided_values == 0:
            raise ValueError("At least one field must be provided")


class BrandKitResponse(BrandKitBase):
    id: int
    business_id: str
    created_at: datetime
    updated_at: datetime


class GenerateRequest(BaseModel):
    """Request model for business-oriented image generation."""

    image_url: str
    prompt: str
    preset_id: str = settings.default_preset_id
    use_case: UseCase = UseCase.MAIN_PRODUCT_IMAGE
    product_category: ProductCategory = ProductCategory.GENERAL
    brand_style: Optional[str] = None
    brand_kit_id: Optional[int] = None
    brand_kit_snapshot: Optional[BrandKitStyleSnapshot] = None
    output_format: OutputFormat = OutputFormat.PRODUCT_IMAGE
    mode: GenerationMode = GenerationMode.PRODUCTION
    num_outputs: int = 1
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __init__(self, **data):
        super().__init__(**data)
        if not 1 <= self.num_outputs <= 4:
            raise ValueError("num_outputs must be between 1 and 4")


class BatchItem(BaseModel):
    image_url: str
    label: Optional[str] = None
    input_file_name: Optional[str] = None


class BatchGenerateRequest(BaseModel):
    items: List[BatchItem]
    prompt: str
    preset_id: str = settings.default_preset_id
    use_case: UseCase = UseCase.MAIN_PRODUCT_IMAGE
    product_category: ProductCategory = ProductCategory.GENERAL
    brand_style: Optional[str] = None
    brand_kit_id: Optional[int] = None
    brand_kit_snapshot: Optional[BrandKitStyleSnapshot] = None
    output_format: OutputFormat = OutputFormat.PRODUCT_IMAGE
    mode: GenerationMode = GenerationMode.PRODUCTION
    num_outputs: int = 1
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    def __init__(self, **data):
        super().__init__(**data)
        if len(self.items) < 1:
            raise ValueError("Batch must contain at least one item")
        if len(self.items) > settings.max_batch_items:
            raise ValueError(f"Batch must contain no more than {settings.max_batch_items} items")
        if not 1 <= self.num_outputs <= 4:
            raise ValueError("num_outputs must be between 1 and 4")


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BatchItemSummary(BaseModel):
    item_index: Optional[int] = None
    label: Optional[str] = None
    job_id: str
    status: JobStatus
    progress: int
    error: Optional[str] = None
    output_urls: Optional[List[str]] = None


class BatchResponse(BaseModel):
    batch_id: str
    business_id: str
    status: JobStatus
    total_items: int
    completed_items: int
    failed_items: int
    pending_items: int
    progress: int
    created_at: datetime
    updated_at: datetime
    items: List[BatchItemSummary]


class BatchRetryRequest(BaseModel):
    keep_item_labels: bool = True


class BatchRetryResponse(BaseModel):
    batch_id: str
    retry_count: int
    requeued_items: List[Dict[str, str]]


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime
    image_url: Optional[str] = None
    prompt: Optional[str] = None
    preset_id: Optional[str] = None
    use_case: Optional[UseCase] = None
    product_category: Optional[ProductCategory] = None
    brand_style: Optional[str] = None
    brand_kit_id: Optional[int] = None
    brand_kit_snapshot: Optional[Dict[str, Any]] = None
    output_format: Optional[OutputFormat] = None
    mode: Optional[GenerationMode] = None
    num_outputs: Optional[int] = None
    callback_url: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    actual_model: Optional[str] = None
    inference_config_used: Optional[Dict[str, Any]] = None
    batch_id: Optional[str] = None
    item_index: Optional[int] = None
    item_label: Optional[str] = None
    input_file_name: Optional[str] = None
    original_image_url: Optional[str] = None
    output_urls: Optional[List[str]] = None
    result_urls: Optional[List[str]] = None
    progress: Optional[int] = None
    step: Optional[str] = None
    error: Optional[str] = None


class RedisJobStore:
    """Store job metadata in Redis hashes."""

    def __init__(self):
        self.redis = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password,
            decode_responses=True,
        )

    def create_job(
        self,
        job_id: str,
        business_id: str,
        request: GenerateRequest,
        batch_id: Optional[str] = None,
        item_index: Optional[int] = None,
        item_label: Optional[str] = None,
        input_file_name: Optional[str] = None,
        original_image_url: Optional[str] = None,
        brand_kit_id: Optional[int] = None,
        brand_kit_snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        key = f"job:{job_id}"
        self.redis.hset(
            key,
            mapping={
                "business_id": business_id,
                "batch_id": batch_id or "",
                "item_index": str(item_index) if item_index is not None else "",
                "item_label": item_label or "",
                "input_file_name": input_file_name or "",
                "original_image_url": original_image_url or "",
                "status": JobStatus.PENDING.value,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "image_url": request.image_url,
                "prompt": request.prompt,
                "preset_id": request.preset_id,
                "use_case": request.use_case.value,
                "product_category": request.product_category.value,
                "brand_style": request.brand_style or "",
                "brand_kit_id": str(brand_kit_id) if brand_kit_id is not None else "",
                "brand_kit_snapshot": json.dumps(brand_kit_snapshot or {}),
                "output_format": request.output_format.value,
                "mode": request.mode.value,
                "num_outputs": str(request.num_outputs),
                "callback_url": request.callback_url or "",
                "metadata": json.dumps(request.metadata or {}),
                "actual_model": "",
                "inference_config_used": "",
                "output_urls": "",
                "result_urls": "",
                "progress": "0",
                "step": "",
                "error": "",
            },
        )

    def get_job(self, job_id: str) -> Optional[JobResponse]:
        key = f"job:{job_id}"
        data = self.redis.hgetall(key)
        if not data:
            return None

        output_urls = [url for url in data.get("output_urls", "").split(",") if url]
        result_urls = [url for url in data.get("result_urls", "").split(",") if url] or output_urls

        metadata = {}
        if data.get("metadata"):
            try:
                metadata = json.loads(data["metadata"])
            except json.JSONDecodeError:
                metadata = {}

        inference_config_used = None
        if data.get("inference_config_used"):
            try:
                inference_config_used = json.loads(data["inference_config_used"])
            except json.JSONDecodeError:
                inference_config_used = None

        brand_kit_snapshot = None
        if data.get("brand_kit_snapshot"):
            try:
                parsed_snapshot = json.loads(data["brand_kit_snapshot"])
                brand_kit_snapshot = parsed_snapshot or None
            except json.JSONDecodeError:
                brand_kit_snapshot = None

        return JobResponse(
            job_id=job_id,
            status=JobStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            image_url=data.get("image_url"),
            prompt=data.get("prompt"),
            preset_id=data.get("preset_id"),
            use_case=UseCase(data["use_case"]) if data.get("use_case") else None,
            product_category=(
                ProductCategory(data["product_category"])
                if data.get("product_category")
                else None
            ),
            brand_style=data.get("brand_style"),
            brand_kit_id=int(data["brand_kit_id"]) if data.get("brand_kit_id") else None,
            brand_kit_snapshot=brand_kit_snapshot,
            output_format=(
                OutputFormat(data["output_format"])
                if data.get("output_format")
                else None
            ),
            mode=GenerationMode(data["mode"]) if data.get("mode") else None,
            num_outputs=int(data["num_outputs"]) if data.get("num_outputs") else None,
            callback_url=data.get("callback_url") if data.get("callback_url") else None,
            metadata=metadata,
            actual_model=data.get("actual_model") if data.get("actual_model") else None,
            inference_config_used=inference_config_used,
            batch_id=data.get("batch_id") or None,
            item_index=int(data["item_index"]) if data.get("item_index") else None,
            item_label=data.get("item_label") if data.get("item_label") else None,
            input_file_name=data.get("input_file_name") if data.get("input_file_name") else None,
            original_image_url=(
                data.get("original_image_url") if data.get("original_image_url") else None
            ),
            output_urls=output_urls or None,
            result_urls=result_urls or None,
            progress=int(data["progress"]) if data.get("progress") else None,
            step=data.get("step") if data.get("step") else None,
            error=data.get("error") if data.get("error") else None,
        )

    def get_job_business_id(self, job_id: str) -> Optional[str]:
        value = self.redis.hget(f"job:{job_id}", "business_id")
        return value or None

    def update_job_status(
        self,
        job_id: str,
        status: JobStatus,
        output_urls: Optional[List[str]] = None,
        result_urls: Optional[List[str]] = None,
        progress: Optional[int] = None,
        step: Optional[str] = None,
        error: Optional[str] = None,
        actual_model: Optional[str] = None,
        inference_config_used: Optional[Dict[str, Any]] = None,
    ) -> None:
        key = f"job:{job_id}"
        update_data = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat(),
        }
        if output_urls is not None:
            update_data["output_urls"] = ",".join(output_urls)
        if result_urls is not None:
            update_data["result_urls"] = ",".join(result_urls)
        if progress is not None:
            update_data["progress"] = str(progress)
        if step is not None:
            update_data["step"] = step
        if error is not None:
            update_data["error"] = error
        if actual_model is not None:
            update_data["actual_model"] = actual_model
        if inference_config_used is not None:
            update_data["inference_config_used"] = json.dumps(inference_config_used)
        self.redis.hset(key, mapping=update_data)


# ---------------------------------------------------------------------------
# Shopify integration schemas
# ---------------------------------------------------------------------------


class ShopifyOAuthStartRequest(BaseModel):
    shop_domain: str


class ShopifyOAuthStartResponse(BaseModel):
    oauth_url: str
    shop_domain: str


class ShopifyStoreResponse(BaseModel):
    id: int
    business_id: str
    shop_domain: str
    scopes: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class ShopifyStoreListResponse(BaseModel):
    stores: List[ShopifyStoreResponse]


class ShopifyProduct(BaseModel):
    id: str
    title: str
    handle: str
    status: str
    image_url: Optional[str] = None
    variant_count: int


class ShopifyProductListResponse(BaseModel):
    store_id: int
    shop_domain: str
    products: List[ShopifyProduct]


class ShopifyPublishRequest(BaseModel):
    store_id: int
    shopify_product_id: str
    replace_existing_media: bool = False


class ShopifyPublishResponse(BaseModel):
    asset_id: int
    shopify_publish_status: str


class ShopifyBulkPublishItem(BaseModel):
    asset_id: int
    shopify_product_id: str
    replace_existing_media: bool = False


class ShopifyBulkPublishRequest(BaseModel):
    store_id: int
    items: List[ShopifyBulkPublishItem]

    def __init__(self, **data):
        super().__init__(**data)
        if len(self.items) < 1:
            raise ValueError("At least one item is required")
        if len(self.items) > 50:
            raise ValueError("Bulk publish is limited to 50 assets per request")


class ShopifyBulkPublishResponse(BaseModel):
    store_id: int
    queued: List[int]
    skipped: List[int]

