import structlog
from celery.exceptions import MaxRetriesExceededError

from api.db import SessionLocal
from api.repositories import get_asset_for_business
from worker.worker import celery

logger = structlog.get_logger(__name__)

@celery.task(bind=True, max_retries=2, default_retry_delay=10, name="worker.publish_to_shopify")
def publish_to_shopify(self, asset_id: int, business_id: str, store_id: int, shopify_product_id: str, replace_existing: bool):
    """Celery task to upload an image from our DB to Shopify."""
    logger.info("starting_shopify_publish_task", asset=asset_id, product=shopify_product_id)
    
    with SessionLocal() as db:
        from api.services.shopify_publish import publish_asset_to_shopify, ShopifyPublishError, ShopifyAuthError
        asset = get_asset_for_business(db, asset_id, business_id)
        if not asset:
            logger.error("asset_not_found_for_publish", asset=asset_id)
            return

        if asset.approval_status != "approved":
            logger.error("asset_not_approved_for_publish", asset=asset_id)
            asset.shopify_publish_status = "failed"
            asset.shopify_error_message = "Asset is not approved."
            db.commit()
            return
            
        asset.shopify_publish_status = "processing"
        asset.shopify_error_message = None
        db.commit()

        try:
            publish_asset_to_shopify(
                db, 
                asset, 
                store_id, 
                business_id, 
                shopify_product_id, 
                replace_existing
            )
        except ShopifyAuthError as e:
            # Token revoked — do not retry, store already marked disconnected.
            logger.warning("shopify_auth_revoked", error=str(e), asset=asset_id, store=store_id)
            asset.shopify_publish_status = "failed"
            asset.shopify_error_message = str(e)
            db.commit()
        except ShopifyPublishError as e:
            logger.warning("shopify_publish_error", error=str(e), asset=asset_id)
            asset.shopify_publish_status = "failed"
            asset.shopify_error_message = str(e)
            db.commit()
        except Exception as exc:
            logger.exception("shopify_publish_hard_failure", error=str(exc))
            try:
                self.retry(exc=exc)
            except MaxRetriesExceededError:
                asset.shopify_publish_status = "failed"
                asset.shopify_error_message = "Unexpected error publishing to Shopify after retries."
                db.commit()


@celery.task(bind=True, max_retries=2, default_retry_delay=15, name="worker.bulk_publish_to_shopify")
def bulk_publish_to_shopify(self, items: list, business_id: str):
    """Celery task that fans out individual publish tasks for a bulk publish request.

    Each item in `items` is a dict with keys: asset_id, store_id,
    shopify_product_id, replace_existing_media.
    """
    logger.info("starting_bulk_shopify_publish", item_count=len(items), business_id=business_id)
    for item in items:
        publish_to_shopify.apply_async(
            args=[
                item["asset_id"],
                business_id,
                item["store_id"],
                item["shopify_product_id"],
                item.get("replace_existing_media", False),
            ],
            queue="shopify_publish",
        )

