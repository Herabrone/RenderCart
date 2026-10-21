from rendercart.core.access import Level
from rendercart.registry.models import Category, Limit, Queue, Runtime, SeoMeta, ToolManifest

TOOL = ToolManifest(
    slug="temp-file-share",
    name="Private Temporary File Share",
    category=Category.VAULT,
    summary="Create encrypted, expiring download links for owner-selected files.",
    min_level=Level.SUPER_ADMIN,
    restricted=True,
    hidden=True,
    runtime=Runtime.CPU,
    queue=Queue.CPU_DEFAULT,
    limits={Level.SUPER_ADMIN: Limit(fair_use_per_hour=30, max_total_mb=25)},
    credit_cost=0,
    ui="vault",
    seo=SeoMeta(
        title="Private Temporary File Share",
        description="Owner-only encrypted and expiring file shares.",
    ),
)
