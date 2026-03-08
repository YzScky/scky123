from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence


@dataclass(frozen=True)
class SectorPlaybook:
    name: str
    keywords: Sequence[str]
    catalyst: str
    affected_products: str
    logic: str


PLAYBOOKS: tuple[SectorPlaybook, ...] = (
    SectorPlaybook(
        name="电网设备/特高压",
        keywords=("电网设备", "特高压", "输变电", "变压器"),
        catalyst=(
            "政策和投资扩张驱动，包括智能电网、新型电力系统、"
            "特高压和电网固定资产投资加码。"
        ),
        affected_products="变压器、输变电设备、电线电缆及配套电力设备。",
        logic=(
            "电网投资扩张 -> 设备招标和订单预期提升 -> 变压器/输变电龙头被资金重估。"
        ),
    ),
    SectorPlaybook(
        name="AI应用/AI营销",
        keywords=("AIGC", "AI智能体", "智谱AI", "传媒广告", "广告营销", "出海营销"),
        catalyst=(
            "AI应用商业化、智能体和营销效率提升预期走强，"
            "市场偏好可直接映射到业务收入的AI应用标的。"
        ),
        affected_products="AI营销服务、广告投放、智能投放平台、出海营销业务。",
        logic=(
            "AI应用催化 -> 营销效率和商业化预期提升 -> 相关平台型公司估值和关注度上修。"
        ),
    ),
)


def match_sector_playbook(sector_name: str) -> Optional[SectorPlaybook]:
    if not sector_name:
        return None
    for playbook in PLAYBOOKS:
        if any(keyword in sector_name for keyword in playbook.keywords):
            return playbook
    return None
