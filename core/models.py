"""LIFE OS data model (SPEC 3).

Grouping mirrors the spec: entity and sources, events and memory, self model,
agent loop, mesh, then decision/approval/measurement.
"""
from django.conf import settings as django_settings
from django.contrib.auth.models import User
from django.db import models
from pgvector.django import VectorField

EMBEDDING_DIMENSIONS = getattr(django_settings, "EMBEDDING_DIMENSIONS", 1536)


class Lane(models.TextChoices):
    """Exploration lanes (SPEC 7). Everything not deliberately explored is exploit."""

    EXPLOIT = "exploit", "exploit"
    ADJACENT = "adjacent", "adjacent"
    COUNTER = "counter", "counter"
    RANDOM = "random", "random"


# --------------------------------------------------------------------------
# 3.1 Entity and sources
# --------------------------------------------------------------------------


class Entity(models.Model):
    class Kind(models.TextChoices):
        PERSON = "person", "person"
        COMPANY = "company", "company"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    name = models.CharField(max_length=200)
    timezone = models.CharField(max_length=64, default="Europe/Istanbul")
    # Validated by core.services.settings_schema, not free-form JSON.
    settings = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "entities"

    def __str__(self) -> str:
        return f"{self.name} ({self.kind})"


class EntityMember(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "owner"
        MEMBER = "member", "member"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="entity_memberships")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.OWNER)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entity", "user"], name="uniq_entity_member")
        ]


class DataSource(models.Model):
    class Kind(models.TextChoices):
        GMAIL = "gmail", "gmail"
        GCAL = "gcal", "gcal"
        SHOPIFY = "shopify", "shopify"
        META_ADS = "meta_ads", "meta_ads"
        TELEGRAM = "telegram", "telegram"
        RSS = "rss", "rss"

    class Status(models.TextChoices):
        ACTIVE = "active", "active"
        REAUTH_REQUIRED = "reauth_required", "reauth_required"
        DISABLED = "disabled", "disabled"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="sources")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    # Fernet envelope {key_version, ciphertext}; rotation needs no schema change.
    credentials_enc = models.BinaryField(null=True, blank=True)
    sync_cursor = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.entity.name}:{self.kind}"


# --------------------------------------------------------------------------
# 3.2 Events and memory
# --------------------------------------------------------------------------


class Event(models.Model):
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="events")
    source = models.ForeignKey(DataSource, on_delete=models.SET_NULL, null=True, blank=True)
    type = models.CharField(max_length=100)
    # B1: the source's own stable id, never a timestamp or generated hash.
    dedup_key = models.CharField(max_length=200)
    payload = models.JSONField()
    occurred_at = models.DateTimeField()
    processed = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["entity", "processed", "occurred_at"])]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "type", "dedup_key"], name="uniq_event_dedup"
            ),
            models.CheckConstraint(
                condition=~models.Q(dedup_key=""), name="event_dedup_key_not_blank"
            ),
        ]


class MemoryItem(models.Model):
    class Kind(models.TextChoices):
        EPISODIC = "episodic", "episodic"
        SEMANTIC = "semantic", "semantic"
        RELATIONSHIP = "relationship", "relationship"
        GOAL = "goal", "goal"
        IDENTITY = "identity", "identity"
        EXPOSURE = "exposure", "exposure"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="memories")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    content = models.TextField()
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS, null=True, blank=True)
    embedding_model = models.CharField(max_length=100, blank=True)
    source_event = models.ForeignKey(Event, on_delete=models.SET_NULL, null=True, blank=True)
    # Never blank: a memory without a source cannot be trusted or audited.
    provenance = models.CharField(max_length=200)
    confidence = models.FloatField()
    origin_lane = models.CharField(max_length=20, choices=Lane.choices, default=Lane.EXPLOIT)
    # SPEC 7: exploration items are shielded from decay long enough to prove
    # themselves; the decay rule is otherwise an echo-chamber engine.
    decay_exempt_until = models.DateTimeField(null=True, blank=True)
    promoted_at = models.DateTimeField(null=True, blank=True)
    valid_from = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    superseded_by = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="supersedes"
    )
    last_used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["entity", "kind", "valid_until"])]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(provenance=""), name="memory_provenance_not_blank"
            ),
            models.CheckConstraint(
                condition=models.Q(confidence__gte=0.0) & models.Q(confidence__lte=1.0),
                name="memory_confidence_range",
            ),
        ]


# --------------------------------------------------------------------------
# 3.3 Self model (SPEC 8 self_model)
# --------------------------------------------------------------------------


class ExposureItem(models.Model):
    """Surfaces where the world touches the owner. world_impact scans against these."""

    class Kind(models.TextChoices):
        SECTOR = "sector", "sector"
        CURRENCY = "currency", "currency"
        SUPPLIER = "supplier", "supplier"
        ASSET = "asset", "asset"
        CUSTOMER_SEGMENT = "customer_segment", "customer_segment"
        OBLIGATION = "obligation", "obligation"
        LOCATION = "location", "location"
        SKILL = "skill", "skill"

    class Source(models.TextChoices):
        USER = "user", "user"
        DERIVED = "derived", "derived"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="exposures")
    kind = models.CharField(max_length=30, choices=Kind.choices)
    label = models.CharField(max_length=200)
    detail = models.JSONField(default=dict, blank=True)
    weight = models.FloatField(default=1.0)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.USER)
    # A derived candidate stays inactive until the user confirms it.
    active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.kind}:{self.label}"


class InterestNode(models.Model):
    """Interest map. The adjacent lane (SPEC 7) is drawn by distance from these."""

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="interests")
    label = models.CharField(max_length=200)
    embedding = VectorField(dimensions=EMBEDDING_DIMENSIONS, null=True, blank=True)
    strength = models.FloatField(default=0.5)
    origin_lane = models.CharField(max_length=20, choices=Lane.choices, default=Lane.EXPLOIT)
    created_at = models.DateTimeField(auto_now_add=True)


class Stance(models.Model):
    """A recorded position. The counter lane argues against it, at full strength."""

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="stances")
    topic = models.CharField(max_length=200)
    position = models.TextField()
    confidence = models.FloatField(default=0.5)
    last_challenged_at = models.DateTimeField(null=True, blank=True)


# --------------------------------------------------------------------------
# 3.4 Agent loop (SPEC 5)
# --------------------------------------------------------------------------


class ResearchTask(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "pending"
        RUNNING = "running", "running"
        DONE = "done", "done"
        CAPPED = "capped", "capped"
        FAILED = "failed", "failed"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="research_tasks")
    goal = models.TextField()
    lane = models.CharField(max_length=20, choices=Lane.choices, default=Lane.EXPLOIT)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    step_budget = models.IntegerField(default=8)
    token_budget = models.IntegerField(default=40000)
    steps_used = models.IntegerField(default=0)
    # Derived from LLMUsage, which is the single source of truth for spend (R7).
    tokens_used = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class ResearchStep(models.Model):
    task = models.ForeignKey(ResearchTask, on_delete=models.CASCADE, related_name="steps")
    index = models.IntegerField()
    tool = models.CharField(max_length=50)
    tool_input = models.JSONField(default=dict, blank=True)
    result_ref = models.CharField(max_length=200, blank=True)
    tokens = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["task_id", "index"]
        constraints = [
            models.UniqueConstraint(fields=["task", "index"], name="uniq_research_step_index")
        ]


class SourceDocument(models.Model):
    """Every external document the agent read. The evidence chain starts here."""

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="documents")
    url = models.URLField(max_length=1000)
    title = models.CharField(max_length=500, blank=True)
    text = models.TextField()
    content_hash = models.CharField(max_length=64)
    publisher = models.CharField(max_length=200, blank=True)
    fetched_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "content_hash"], name="uniq_sourcedoc"
            )
        ]


class ImpactFinding(models.Model):
    """SPEC 0/7: a claim with no exposure and no evidence is discarded, not stored."""

    class Direction(models.TextChoices):
        RISK = "risk", "risk"
        OPPORTUNITY = "opportunity", "opportunity"
        NEUTRAL = "neutral", "neutral"

    class Magnitude(models.TextChoices):
        LOW = "low", "low"
        MEDIUM = "medium", "medium"
        HIGH = "high", "high"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="findings")
    task = models.ForeignKey(ResearchTask, on_delete=models.SET_NULL, null=True, blank=True)
    # Not nullable: this is the "because" the briefing has to show.
    exposure = models.ForeignKey(ExposureItem, on_delete=models.CASCADE, related_name="findings")
    claim = models.TextField()
    direction = models.CharField(max_length=20, choices=Direction.choices)
    magnitude = models.CharField(max_length=20, choices=Magnitude.choices)
    confidence = models.FloatField()
    # At least one document is required; enforced by the writing service, since
    # a many-to-many minimum cannot be expressed as a database constraint.
    evidence = models.ManyToManyField(SourceDocument, related_name="findings")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=~models.Q(claim=""), name="finding_claim_not_blank"),
            models.CheckConstraint(
                condition=models.Q(confidence__gte=0.0) & models.Q(confidence__lte=1.0),
                name="finding_confidence_range",
            ),
        ]


# --------------------------------------------------------------------------
# 3.5 Mesh (SPEC 6)
# --------------------------------------------------------------------------


class AgentIdentity(models.Model):
    class TrustLevel(models.TextChoices):
        SELF = "self", "self"
        TRUSTED = "trusted", "trusted"
        KNOWN = "known", "known"
        UNKNOWN = "unknown", "unknown"

    # Set when this identity is one of ours; blank for an external peer.
    entity = models.ForeignKey(
        Entity, on_delete=models.CASCADE, null=True, blank=True, related_name="agent_identities"
    )
    display_name = models.CharField(max_length=200)
    public_key = models.TextField(blank=True)
    endpoint = models.CharField(max_length=300, blank=True)
    trust_level = models.CharField(
        max_length=20, choices=TrustLevel.choices, default=TrustLevel.UNKNOWN
    )

    class Meta:
        verbose_name_plural = "agent identities"

    def __str__(self) -> str:
        return self.display_name


class ShareContract(models.Model):
    """Outbound whitelist. Default is deny; anything not listed never leaves."""

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="share_contracts")
    peer = models.ForeignKey(AgentIdentity, on_delete=models.CASCADE, related_name="contracts")
    allowed_fields = models.JSONField(default=list, blank=True)
    purpose = models.CharField(max_length=200)
    expires_at = models.DateTimeField(null=True, blank=True)
    # A contract is not usable until the human approved it.
    approved_by_user_at = models.DateTimeField(null=True, blank=True)


class MeshConversation(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "open"
        AGREED = "agreed", "agreed"
        DECLINED = "declined", "declined"
        AWAITING_APPROVAL = "awaiting_approval", "awaiting_approval"
        CLOSED = "closed", "closed"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="conversations")
    peer = models.ForeignKey(AgentIdentity, on_delete=models.CASCADE, related_name="conversations")
    topic = models.CharField(max_length=200)
    purpose = models.CharField(max_length=100)
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.OPEN)
    contract = models.ForeignKey(
        ShareContract, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)


class MeshMessage(models.Model):
    class Direction(models.TextChoices):
        IN = "in", "in"
        OUT = "out", "out"

    conversation = models.ForeignKey(
        MeshConversation, on_delete=models.CASCADE, related_name="messages"
    )
    direction = models.CharField(max_length=10, choices=Direction.choices)
    kind = models.CharField(max_length=50)
    body = models.JSONField()
    # What was withheld, so the owner can see the non-disclosure too.
    redaction_note = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["conversation_id", "created_at"]


# --------------------------------------------------------------------------
# 3.6 Decision, approval, measurement
# --------------------------------------------------------------------------


class ProposedAction(models.Model):
    class Risk(models.TextChoices):
        LOW = "low", "low"
        MEDIUM = "medium", "medium"
        HIGH = "high", "high"

    class Status(models.TextChoices):
        PENDING = "pending", "pending"
        APPROVED = "approved", "approved"
        EDITED = "edited", "edited"
        REJECTED = "rejected", "rejected"
        EXECUTED = "executed", "executed"
        FAILED = "failed", "failed"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="actions")
    module = models.CharField(max_length=50)
    action_type = models.CharField(max_length=100)
    dedup_key = models.CharField(max_length=200)
    payload = models.JSONField()
    risk_level = models.CharField(max_length=20, choices=Risk.choices, default=Risk.MEDIUM)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    origin_conversation = models.ForeignKey(
        MeshConversation, on_delete=models.SET_NULL, null=True, blank=True
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "action_type", "dedup_key"], name="uniq_action_dedup"
            ),
            models.CheckConstraint(
                condition=~models.Q(dedup_key=""), name="action_dedup_key_not_blank"
            ),
        ]


class ActionPolicy(models.Model):
    class Mode(models.TextChoices):
        SUGGEST = "suggest", "suggest"
        DRAFT = "draft", "draft"
        AUTO_CANDIDATE = "auto_candidate", "auto_candidate"
        AUTO = "auto", "auto"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="policies")
    action_type = models.CharField(max_length=100)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.DRAFT)
    window_stats = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "action policies"
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "action_type"], name="uniq_action_policy"
            )
        ]


class ExplorationLedger(models.Model):
    """SPEC 7: what makes the quota falsifiable. Promotion is the metric, not likes."""

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="exploration_ledger")
    date = models.DateField()
    lane = models.CharField(max_length=20, choices=Lane.choices)
    items_served = models.IntegerField(default=0)
    feedback_up = models.IntegerField(default=0)
    feedback_down = models.IntegerField(default=0)
    promoted = models.IntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "date", "lane"], name="uniq_explore_ledger"
            )
        ]


class Briefing(models.Model):
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="briefings")
    date = models.DateField()
    sections = models.JSONField(default=list, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    telegram_message_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entity", "date"], name="uniq_briefing_day")
        ]


class FeedbackSignal(models.Model):
    class TargetType(models.TextChoices):
        BRIEFING_ITEM = "briefing_item", "briefing_item"
        DRAFT = "draft", "draft"
        FINDING = "finding", "finding"
        EXPLORATION = "exploration", "exploration"

    class Signal(models.TextChoices):
        UP = "up", "up"
        DOWN = "down", "down"
        EDITED = "edited", "edited"

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="feedback")
    target_type = models.CharField(max_length=30, choices=TargetType.choices)
    target_ref = models.CharField(max_length=200)
    signal = models.CharField(max_length=20, choices=Signal.choices)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # A second tap updates the row instead of creating a duplicate.
            models.UniqueConstraint(
                fields=["entity", "target_type", "target_ref"], name="uniq_feedback"
            )
        ]


class AuditLog(models.Model):
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="audit_logs")
    action = models.ForeignKey(
        ProposedAction, on_delete=models.SET_NULL, null=True, blank=True
    )
    summary = models.CharField(max_length=300)
    detail = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class LLMUsage(models.Model):
    """Single source of truth for spend; the budget guard reads only this."""

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE, related_name="llm_usage")
    date = models.DateField()
    tier = models.CharField(max_length=20)
    purpose = models.CharField(max_length=100)
    input_tokens = models.BigIntegerField(default=0)
    output_tokens = models.BigIntegerField(default=0)
    cost_usd = models.DecimalField(max_digits=8, decimal_places=4, default=0)

    class Meta:
        indexes = [models.Index(fields=["entity", "date"])]
        constraints = [
            models.UniqueConstraint(
                fields=["entity", "date", "tier", "purpose"], name="uniq_llm_usage"
            )
        ]
