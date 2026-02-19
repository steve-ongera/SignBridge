from django.db import models
from django.contrib.auth.models import User


class SignLanguageType(models.Model):
    """Supported sign language varieties e.g. ASL, BSL, KSL (Kenyan)"""
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)  # e.g. ASL, BSL, KSL
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

    class Meta:
        verbose_name = "Sign Language Type"
        verbose_name_plural = "Sign Language Types"


class TranslationSession(models.Model):
    """Each camera session where sign language is captured and translated"""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name='sessions')
    sign_language = models.ForeignKey(SignLanguageType, on_delete=models.SET_NULL,
                                      null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    device_info = models.CharField(max_length=255, blank=True,
                                   help_text="Browser / device used")

    def __str__(self):
        return f"Session #{self.pk} — {self.user or 'Anonymous'} [{self.status}]"

    class Meta:
        ordering = ['-started_at']
        verbose_name = "Translation Session"


class TranslationRecord(models.Model):
    """A single translated sign captured within a session"""
    session = models.ForeignKey(TranslationSession, on_delete=models.CASCADE,
                                related_name='records')
    # Raw frame snapshot (optional – stored as base64 in DB or as file)
    frame_image = models.ImageField(upload_to='frames/%Y/%m/%d/', null=True, blank=True)
    detected_sign = models.CharField(max_length=200,
                                     help_text="Sign / gesture detected by AI")
    translated_text = models.TextField(help_text="Human-readable text translation")
    confidence_score = models.FloatField(default=0.0,
                                        help_text="AI confidence 0-1")
    audio_file = models.FileField(upload_to='audio/%Y/%m/%d/', null=True, blank=True,
                                  help_text="Generated TTS audio file")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'"{self.translated_text[:50]}" (conf: {self.confidence_score:.0%})'

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Translation Record"


class UserProfile(models.Model):
    """Extended profile for SignBridge users"""
    ROLE_CHOICES = [
        ('hearing', 'Hearing Person'),
        ('deaf', 'Deaf / Hard of Hearing'),
        ('interpreter', 'Interpreter'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='hearing')
    preferred_sign_language = models.ForeignKey(SignLanguageType,
                                                on_delete=models.SET_NULL,
                                                null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True)
    total_translations = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} — {self.get_role_display()}"

    class Meta:
        verbose_name = "User Profile"


class Feedback(models.Model):
    """User feedback on a translation to improve the AI model"""
    RATING_CHOICES = [(i, str(i)) for i in range(1, 6)]

    record = models.ForeignKey(TranslationRecord, on_delete=models.CASCADE,
                               related_name='feedbacks')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    rating = models.IntegerField(choices=RATING_CHOICES)
    correct_translation = models.TextField(blank=True,
                                           help_text="What the sign actually meant")
    comment = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback on record #{self.record_id} — {self.rating}★"

    class Meta:
        verbose_name = "Translation Feedback"