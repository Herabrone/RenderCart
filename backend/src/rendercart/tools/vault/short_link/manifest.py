from rendercart.core.access import Level
from rendercart.registry.models import Category, Limit, Queue, Runtime, SeoMeta, ToolManifest

TOOL = ToolManifest(
    slug="url-shortener",
    name="Private URL Shortener",
    category=Category.VAULT,
    summary="Create expiring owner-managed redirect links.",
    min_level=Level.SUPER_ADMIN,
    restricted=True,
    hidden=True,
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    limits={Level.SUPER_ADMIN: Limit(fair_use_per_hour=30)},
    credit_cost=0,
    ui="vault",
    seo=SeoMeta(title="Private URL Shortener", description="Owner-only expiring redirect links."),
)
