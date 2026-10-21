from rendercart.core.access import Level
from rendercart.registry.models import Category, Limit, Queue, Runtime, SeoMeta, ToolManifest

TOOL = ToolManifest(
    slug="pastebin",
    name="Private Text Share",
    category=Category.VAULT,
    summary="Create encrypted, expiring text shares.",
    min_level=Level.SUPER_ADMIN,
    restricted=True,
    hidden=True,
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    limits={Level.SUPER_ADMIN: Limit(fair_use_per_hour=30, max_characters_per_job=20_000)},
    credit_cost=0,
    ui="vault",
    seo=SeoMeta(
        title="Private Text Share", description="Owner-only encrypted expiring text shares."
    ),
)
