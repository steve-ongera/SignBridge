"""
Seed initial sign language types.
Run: python manage.py seed_languages
"""
from django.core.management.base import BaseCommand
from translator.models import SignLanguageType


class Command(BaseCommand):
    help = 'Seed initial sign language types'

    def handle(self, *args, **options):
        languages = [
            {'name': 'American Sign Language', 'code': 'ASL',
             'description': 'Used in the USA and parts of Canada'},
            {'name': 'British Sign Language', 'code': 'BSL',
             'description': 'Used in the United Kingdom'},
            {'name': 'Kenyan Sign Language', 'code': 'KSL',
             'description': 'Used in Kenya — recognized official language'},
            {'name': 'International Sign', 'code': 'IS',
             'description': 'Pidgin sign used at international events'},
            {'name': 'Australian Sign Language', 'code': 'AUSLAN',
             'description': 'Used in Australia'},
        ]
        for lang in languages:
            obj, created = SignLanguageType.objects.get_or_create(
                code=lang['code'], defaults=lang
            )
            status = '✅ Created' if created else '⏭  Exists'
            self.stdout.write(f"{status}: {obj.name} ({obj.code})")
        self.stdout.write(self.style.SUCCESS('\nSign languages seeded successfully!'))