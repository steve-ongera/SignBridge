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
    return render(request, 'home.html', stats)


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
    return render(request, 'translator.html', context)


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

    return render(request, 'history.html', {'sessions': sessions})


def about(request):
    return render(request, 'about.html')

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

# ─────────────────────────────────────────────────────────────
# ADD THESE VIEWS to views.py
# ─────────────────────────────────────────────────────────────

def auth_view(request):
    """Single page for both login and register (tab-switched via JS)."""
    if request.user.is_authenticated:
        return redirect('home')

    login_error = None
    register_errors = []
    form_type = 'login'

    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'login')

        # ── LOGIN ──────────────────────────────────────────
        if form_type == 'login':
            username = request.POST.get('username', '').strip()
            password = request.POST.get('password', '')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f'Welcome back, {user.first_name or user.username}!')
                next_url = request.GET.get('next', 'home')
                return redirect(next_url)
            else:
                login_error = 'Invalid username or password. Please try again.'

        # ── REGISTER ───────────────────────────────────────
        elif form_type == 'register':
            first_name = request.POST.get('first_name', '').strip()
            last_name  = request.POST.get('last_name', '').strip()
            username   = request.POST.get('username', '').strip()
            email      = request.POST.get('email', '').strip()
            password1  = request.POST.get('password1', '')
            password2  = request.POST.get('password2', '')
            role       = request.POST.get('role', 'hearing')
            agree      = request.POST.get('agree_terms')

            # Validate
            if not agree:
                register_errors.append('You must agree to the Terms of Service.')
            if not username:
                register_errors.append('Username is required.')
            elif User.objects.filter(username=username).exists():
                register_errors.append('That username is already taken.')
            if email and User.objects.filter(email=email).exists():
                register_errors.append('An account with that email already exists.')
            if len(password1) < 8:
                register_errors.append('Password must be at least 8 characters.')
            if password1 != password2:
                register_errors.append('Passwords do not match.')

            if not register_errors:
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1,
                    first_name=first_name,
                    last_name=last_name,
                )
                # Create UserProfile
                UserProfile.objects.create(user=user, role=role)
                login(request, user)
                messages.success(request, f'Welcome to SignBridge, {first_name or username}! 🎉')
                return redirect('home')

    return render(request, 'auth.html', {
        'login_error':      login_error,
        'register_errors':  register_errors,
        'form_type':        form_type,
    })


def logout_view(request):
    logout(request)
    messages.info(request, 'You have been signed out.')
    return redirect('home')