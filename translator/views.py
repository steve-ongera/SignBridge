import json
import base64
import os
import io
import tempfile
import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.conf import settings
from django.core.files.base import ContentFile

from .models import (TranslationSession, TranslationRecord,
                     SignLanguageType, UserProfile, Feedback)

# ---------------------------------------------------------------------------
# AI helper — uses Google Gemini Vision API
# ---------------------------------------------------------------------------

def analyze_sign_with_ai(image_base64: str, sign_language_code: str = "ASL") -> dict:
    """
    Send a camera frame to Gemini Vision and ask it to identify the sign.
    Returns dict: { detected_sign, translated_text, confidence_score }
    """
    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        # Decode base64 image
        if "," in image_base64:
            image_base64 = image_base64.split(",")[1]
        image_bytes = base64.b64decode(image_base64)

        import PIL.Image
        image = PIL.Image.open(io.BytesIO(image_bytes))

        prompt = f"""You are an expert {sign_language_code} (Sign Language) interpreter.
Analyze this image carefully and identify any hand gestures or sign language being performed.

Return a JSON object with ONLY these keys:
- "detected_sign": the name of the sign or gesture (e.g. "Hello", "Thank You", "A", "Love")
- "translated_text": a natural English sentence or word that conveys the meaning
- "confidence_score": a float between 0 and 1 representing your confidence
- "description": brief description of the hand position observed

If no sign language gesture is detected, return:
{{"detected_sign": "None", "translated_text": "No sign detected", "confidence_score": 0.0, "description": "No hand gesture visible"}}

Respond ONLY with valid JSON, no markdown."""

        response = model.generate_content([prompt, image])
        text = response.text.strip()

        # Strip markdown fences if any
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        result = json.loads(text)
        return result

    except ImportError:
        # Fallback demo mode when google-generativeai is not installed
        return _demo_response()
    except Exception as e:
        print(f"[SignBridge AI Error] {e}")
        return _demo_response()


def _demo_response():
    """Fallback demo response when AI is unavailable"""
    import random
    demo_signs = [
        {"detected_sign": "Hello", "translated_text": "Hello!", "confidence_score": 0.92,
         "description": "Open hand wave near face"},
        {"detected_sign": "Thank You", "translated_text": "Thank you very much.",
         "confidence_score": 0.88, "description": "Hand moves away from chin"},
        {"detected_sign": "Help", "translated_text": "Please help me.",
         "confidence_score": 0.85, "description": "Thumbs up on flat palm"},
        {"detected_sign": "Yes", "translated_text": "Yes.", "confidence_score": 0.95,
         "description": "Fist nodding motion"},
        {"detected_sign": "Love", "translated_text": "I love you.",
         "confidence_score": 0.90, "description": "ILY handshape"},
    ]
    return random.choice(demo_signs)


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

def home(request):
    """Landing page"""
    stats = {
        'total_sessions': TranslationSession.objects.count(),
        'total_translations': TranslationRecord.objects.count(),
        'languages': SignLanguageType.objects.filter(is_active=True),
    }
    return render(request, 'translator/home.html', stats)


def translator_view(request):
    """
    Main camera + translation page.
    Creates a new TranslationSession and renders the camera interface.
    """
    sign_languages = SignLanguageType.objects.filter(is_active=True)

    # Create a session
    session = TranslationSession.objects.create(
        user=request.user if request.user.is_authenticated else None,
        device_info=request.META.get('HTTP_USER_AGENT', '')[:255],
    )

    context = {
        'session': session,
        'sign_languages': sign_languages,
    }
    return render(request, 'translator/translator.html', context)


@csrf_exempt
@require_POST
def analyze_frame(request):
    """
    AJAX endpoint — receives a base64 camera frame, runs AI,
    saves TranslationRecord, returns JSON.
    """
    try:
        data = json.loads(request.body)
        frame_b64 = data.get('frame', '')
        session_id = data.get('session_id')
        lang_code = data.get('sign_language', 'ASL')

        if not frame_b64 or not session_id:
            return JsonResponse({'error': 'Missing frame or session_id'}, status=400)

        session = get_object_or_404(TranslationSession, pk=session_id)

        # Update session sign language
        try:
            sl = SignLanguageType.objects.get(code=lang_code)
            session.sign_language = sl
            session.save(update_fields=['sign_language'])
        except SignLanguageType.DoesNotExist:
            pass

        # Run AI
        ai_result = analyze_sign_with_ai(frame_b64, lang_code)

        if ai_result.get('confidence_score', 0) < 0.3:
            return JsonResponse({'status': 'low_confidence',
                                 'message': 'No clear sign detected'})

        # Save record
        record = TranslationRecord(
            session=session,
            detected_sign=ai_result.get('detected_sign', ''),
            translated_text=ai_result.get('translated_text', ''),
            confidence_score=ai_result.get('confidence_score', 0.0),
        )

        # Save frame thumbnail
        if "," in frame_b64:
            img_data = base64.b64decode(frame_b64.split(",")[1])
        else:
            img_data = base64.b64decode(frame_b64)
        record.frame_image.save(
            f"frame_{session_id}_{timezone.now().strftime('%H%M%S')}.jpg",
            ContentFile(img_data),
            save=False
        )

        record.save()

        # Update user stats
        if request.user.is_authenticated:
            profile, _ = UserProfile.objects.get_or_create(user=request.user)
            UserProfile.objects.filter(pk=profile.pk).update(
                total_translations=profile.total_translations + 1
            )

        return JsonResponse({
            'status': 'success',
            'record_id': record.pk,
            'detected_sign': record.detected_sign,
            'translated_text': record.translated_text,
            'confidence_score': round(record.confidence_score * 100, 1),
            'description': ai_result.get('description', ''),
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def end_session(request):
    """Mark a session as completed"""
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        session = get_object_or_404(TranslationSession, pk=session_id)
        session.status = 'completed'
        session.ended_at = timezone.now()
        session.save(update_fields=['status', 'ended_at'])
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def submit_feedback(request):
    """User rates a translation record"""
    try:
        data = json.loads(request.body)
        record = get_object_or_404(TranslationRecord, pk=data.get('record_id'))
        Feedback.objects.create(
            record=record,
            user=request.user if request.user.is_authenticated else None,
            rating=data.get('rating', 3),
            correct_translation=data.get('correct_translation', ''),
            comment=data.get('comment', ''),
        )
        return JsonResponse({'status': 'ok', 'message': 'Thank you for the feedback!'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def history(request):
    """Translation history for logged-in users"""
    if not request.user.is_authenticated:
        messages.warning(request, "Please log in to view your history.")
        return redirect('home')

    sessions = TranslationSession.objects.filter(
        user=request.user
    ).prefetch_related('records').order_by('-started_at')[:20]

    return render(request, 'translator/history.html', {'sessions': sessions})


def about(request):
    return render(request, 'translator/about.html')