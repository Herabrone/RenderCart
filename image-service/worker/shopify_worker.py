import structlog
from celery.exceptions import MaxRetriesExceededError

from api.db import SessionLocal
from api.repositories import get_asset_for_business
from worker.worker import celery
from worker.status_store import update_job_status
from api.services.shopify_crypto import decrypt_token

logger = structlog.get_logger(__name__)

@celery.task(bind=True, max_retries=2, default_retry_delay=10, name="worker.publish_to_shopify")
def publish_to_shopify(self, asset_id: int, business_id: str, store_id: int, shopify_product_id: str, replace_existing: bool):
    """Celery task to upload an image from our DB to Shopify.
    """
    logger.info("starting_shopify_publish_task", asset=asset_id, product=shopify_product_id)
    
    with SessionLocal() as db:
        from api.services.shopify_publish import publish_asset_to_shopify, ShopifyPublishError
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
        except ShopifyPublishError as e:
            logger.warning("shopify_publish_error", error=str(e), asset=asset_id)
            asset.shopify_publish_status = "failed"
            asset.shopify_error_message = str(e)
            db.commit()
        except Exception as exc:
            logger.exception("shopify_publish_hard_failure", error=str(exc))
            # If it's a connection or timeout error, maybe retry
            try:
                self.retry(exc=exc)
            except MaxRetriesExceededError:
                asset.shopify_publish_status = "failed"
                asset.shopify_error_message = "Unexpected error publishing to Shopify after retries."
                db.commit()
