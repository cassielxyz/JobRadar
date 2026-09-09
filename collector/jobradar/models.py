from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Category:
    id: str
    name: str
    slug: str
    type: str
    role_keywords: list[str]
    hidden_keywords: list[str]
    exclude_keywords: list[str]
    locations: list[str]
    max_experience_years: float = 2
    salary_min_monthly: Optional[int] = None
    salary_max_monthly: Optional[int] = None
    stipend_min_monthly: Optional[int] = None
    stipend_max_monthly: Optional[int] = None
    require_paid: bool = False
    require_official_verification: bool = False
    source_kinds: list[str] = field(default_factory=list)
    alert_threshold: int = 70

@dataclass
class Job:
    title: str
    company: str
    location: str
    description: str
    source_id: str
    source_url: str
    canonical_url: str
    employment_type: str = "unknown"
    experience_min: Optional[float] = None
    experience_max: Optional[float] = None
    salary_min_monthly: Optional[int] = None
    salary_max_monthly: Optional[int] = None
    stipend_monthly: Optional[int] = None
    deadline: Optional[str] = None
    posted_at: Optional[str] = None
    official_verified: bool = False
    apply_url: Optional[str] = None
    notification_url: Optional[str] = None
    apply_verified: bool = False
    link_confidence: int = 0
    event_type: str = "vacancy"  # vacancy | exam_update
    application_status: str = "unknown"  # open | closed | update | unknown
    raw: dict = field(default_factory=dict)
