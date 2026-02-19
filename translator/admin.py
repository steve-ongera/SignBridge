from django.contrib import admin
from django.utils.html import format_html
from .models import (SignLanguageType, TranslationSession,
                     TranslationRecord, UserProfile, Feedback)


@admin.register(SignLanguageType)
class SignLanguageTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    list_editable = ('is_active',)
    search_fields = ('name', 'code')


class TranslationRecordInline(admin.TabularInline):
    model = TranslationRecord
    extra = 0
    readonly_fields = ('created_at', 'confidence_score', 'frame_preview')
    fields = ('detected_sign', 'translated_text', 'confidence_score',
              'frame_preview', 'audio_file', 'created_at')

    def frame_preview(self, obj):
        if obj.frame_image:
            return format_html('<img src="{}" width="80" style="border-radius:4px"/>',
                               obj.frame_image.url)
        return "—"
    frame_preview.short_description = "Frame"


@admin.register(TranslationSession)
class TranslationSessionAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'sign_language', 'status', 'started_at',
                    'record_count')
    list_filter = ('status', 'sign_language')
    search_fields = ('user__username',)
    inlines = [TranslationRecordInline]
    readonly_fields = ('started_at', 'ended_at')

    def record_count(self, obj):
        return obj.records.count()
    record_count.short_description = "Records"


@admin.register(TranslationRecord)
class TranslationRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'detected_sign', 'translated_text_short',
                    'confidence_score', 'created_at', 'frame_preview')
    list_filter = ('session__sign_language',)
    search_fields = ('detected_sign', 'translated_text')
    readonly_fields = ('created_at', 'frame_preview')

    def translated_text_short(self, obj):
        return obj.translated_text[:60] + ('…' if len(obj.translated_text) > 60 else '')
    translated_text_short.short_description = "Translation"

    def frame_preview(self, obj):
        if obj.frame_image:
            return format_html('<img src="{}" width="100" style="border-radius:6px"/>',
                               obj.frame_image.url)
        return "—"
    frame_preview.short_description = "Frame Preview"


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'preferred_sign_language', 'total_translations',
                    'created_at')
    list_filter = ('role',)
    search_fields = ('user__username', 'user__email')


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ('id', 'record', 'user', 'rating', 'submitted_at')
    list_filter = ('rating',)
    search_fields = ('user__username', 'correct_translation')


# Customize admin site header
admin.site.site_header = "SignBridge Admin"
admin.site.site_title = "SignBridge"
admin.site.index_title = "SignBridge Management Panel"