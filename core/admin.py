from django.contrib import admin

from core import models


@admin.register(models.Entity)
class EntityAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "timezone")
    list_filter = ("kind",)
    search_fields = ("name",)


@admin.register(models.EntityMember)
class EntityMemberAdmin(admin.ModelAdmin):
    list_display = ("entity", "user", "role")
    list_filter = ("role",)


@admin.register(models.DataSource)
class DataSourceAdmin(admin.ModelAdmin):
    list_display = ("entity", "kind", "status", "last_sync_at")
    list_filter = ("kind", "status")
    # credentials_enc is deliberately not listed or editable here.
    exclude = ("credentials_enc",)


@admin.register(models.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("entity", "type", "dedup_key", "occurred_at", "processed")
    list_filter = ("type", "processed")
    search_fields = ("dedup_key",)


@admin.register(models.MemoryItem)
class MemoryItemAdmin(admin.ModelAdmin):
    list_display = ("entity", "kind", "origin_lane", "confidence", "valid_until", "promoted_at")
    list_filter = ("kind", "origin_lane")
    search_fields = ("content", "provenance")
    exclude = ("embedding",)


@admin.register(models.ExposureItem)
class ExposureItemAdmin(admin.ModelAdmin):
    list_display = ("entity", "kind", "label", "weight", "source", "active")
    list_filter = ("kind", "source", "active")
    search_fields = ("label",)


@admin.register(models.InterestNode)
class InterestNodeAdmin(admin.ModelAdmin):
    list_display = ("entity", "label", "strength", "origin_lane", "created_at")
    list_filter = ("origin_lane",)
    search_fields = ("label",)
    exclude = ("embedding",)


@admin.register(models.Stance)
class StanceAdmin(admin.ModelAdmin):
    list_display = ("entity", "topic", "confidence", "last_challenged_at")
    search_fields = ("topic",)


class ResearchStepInline(admin.TabularInline):
    model = models.ResearchStep
    extra = 0


@admin.register(models.ResearchTask)
class ResearchTaskAdmin(admin.ModelAdmin):
    list_display = ("entity", "lane", "status", "steps_used", "step_budget", "created_at")
    list_filter = ("lane", "status")
    inlines = [ResearchStepInline]


@admin.register(models.ResearchStep)
class ResearchStepAdmin(admin.ModelAdmin):
    # Also inlined under ResearchTask; standalone because the step log is the
    # audit trail behind /task.
    list_display = ("task", "index", "tool", "tokens", "created_at")
    list_filter = ("tool",)


@admin.register(models.SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ("entity", "title", "publisher", "url", "fetched_at")
    search_fields = ("title", "url", "publisher")


@admin.register(models.ImpactFinding)
class ImpactFindingAdmin(admin.ModelAdmin):
    list_display = ("entity", "exposure", "direction", "magnitude", "confidence", "created_at")
    list_filter = ("direction", "magnitude")
    filter_horizontal = ("evidence",)


@admin.register(models.AgentIdentity)
class AgentIdentityAdmin(admin.ModelAdmin):
    list_display = ("display_name", "entity", "trust_level", "endpoint")
    list_filter = ("trust_level",)


@admin.register(models.ShareContract)
class ShareContractAdmin(admin.ModelAdmin):
    list_display = ("entity", "peer", "purpose", "approved_by_user_at", "expires_at")


class MeshMessageInline(admin.TabularInline):
    model = models.MeshMessage
    extra = 0


@admin.register(models.MeshConversation)
class MeshConversationAdmin(admin.ModelAdmin):
    list_display = ("entity", "peer", "topic", "purpose", "status", "created_at")
    list_filter = ("status", "purpose")
    inlines = [MeshMessageInline]


@admin.register(models.MeshMessage)
class MeshMessageAdmin(admin.ModelAdmin):
    list_display = ("conversation", "direction", "kind", "created_at")
    list_filter = ("direction", "kind")


@admin.register(models.ProposedAction)
class ProposedActionAdmin(admin.ModelAdmin):
    list_display = ("entity", "module", "action_type", "risk_level", "status", "created_at")
    list_filter = ("module", "action_type", "risk_level", "status")


@admin.register(models.ActionPolicy)
class ActionPolicyAdmin(admin.ModelAdmin):
    list_display = ("entity", "action_type", "mode")
    list_filter = ("mode",)


@admin.register(models.ExplorationLedger)
class ExplorationLedgerAdmin(admin.ModelAdmin):
    list_display = ("entity", "date", "lane", "items_served", "feedback_up", "promoted")
    list_filter = ("lane",)


@admin.register(models.Briefing)
class BriefingAdmin(admin.ModelAdmin):
    list_display = ("entity", "date", "delivered_at")


@admin.register(models.FeedbackSignal)
class FeedbackSignalAdmin(admin.ModelAdmin):
    list_display = ("entity", "target_type", "target_ref", "signal", "created_at")
    list_filter = ("target_type", "signal")


@admin.register(models.AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("entity", "summary", "action", "created_at")
    search_fields = ("summary",)


@admin.register(models.LLMUsage)
class LLMUsageAdmin(admin.ModelAdmin):
    list_display = ("entity", "date", "tier", "purpose", "cost_usd")
    list_filter = ("tier",)
