# 🤟 SignBridge

> **Bridging the gap between sign language and voice — one gesture at a time.**

SignBridge is a Django + AI web app that uses your laptop or phone camera to detect sign language gestures in real time and convert them to **spoken voice** using Google Gemini Vision AI and the browser's Web Speech API.

---

## 📁 Project Structure

```
signbridge/
├── signbridge/          ← Django project config
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── translator/          ← Single Django app
│   ├── models.py        ← DB models
│   ├── admin.py         ← Admin panel
│   ├── views.py         ← Views + AI integration
│   ├── urls.py          ← URL routes
│   ├── templates/
│   │   └── translator/
│   │       ├── base.html
│   │       ├── home.html
│   │       ├── translator.html  ← Main camera page
│   │       ├── history.html
│   │       └── about.html
│   └── management/commands/seed_languages.py
├── requirements.txt
└── README.md
```

---

## 🚀 Setup & Run

### 1. Clone and install
```bash
git clone <your-repo>
cd signbridge
pip install -r requirements.txt
```

### 2. Set your Gemini API key
Get a free key at https://makersuite.google.com/app/apikey

```bash
export GEMINI_API_KEY="your-key-here"
```

Or edit `signbridge/settings.py`:
```python
GEMINI_API_KEY = 'your-key-here'
```

### 3. Run migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Seed sign languages
```bash
python manage.py seed_languages
```

### 5. Create admin user
```bash
python manage.py createsuperuser
```

### 6. Start the server
```bash
python manage.py runserver
```

Open http://127.0.0.1:8000

---

## 🔗 URL Routes

| URL | View | Description |
|-----|------|-------------|
| `/` | home | Landing page |
| `/translate/` | translator_view | Live camera + AI translator |
| `/history/` | history | Past sessions (auth required) |
| `/about/` | about | About page |
| `/api/analyze-frame/` | analyze_frame | POST — AI frame analysis |
| `/api/end-session/` | end_session | POST — close session |
| `/api/feedback/` | submit_feedback | POST — rate translation |
| `/admin/` | Django Admin | Full management panel |

---

## 🤖 AI Integration

SignBridge uses **Google Gemini 1.5 Flash** (vision model) to:
1. Receive a base64 JPEG frame from the browser
2. Analyze hand position and gesture
3. Return: `detected_sign`, `translated_text`, `confidence_score`

The browser then uses the **Web Speech API** (`SpeechSynthesisUtterance`) to speak the translation aloud — no server-side audio needed.

**Demo mode**: If the Gemini API key is not set, a random demo response is returned so you can test the UI.

---

## 🗄️ Database Models

| Model | Purpose |
|-------|---------|
| `SignLanguageType` | ASL, BSL, KSL, etc. |
| `TranslationSession` | One camera session |
| `TranslationRecord` | Single detected sign + frame snapshot |
| `UserProfile` | Extended user info (role, preferences) |
| `Feedback` | Star ratings + correction data |

---

## 🌍 Supported Sign Languages
- ASL — American Sign Language
- BSL — British Sign Language
- KSL — Kenyan Sign Language *(Kenya officially recognizes KSL!)*
- IS — International Sign
- AUSLAN — Australian Sign Language