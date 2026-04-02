from accounts.models import Course

courses = [
    {'name': 'Frontend dasturlash', 'description': 'HTML, CSS, JavaScript', 'slug': 'frontend'},
    {'name': 'Backend dasturlash', 'description': 'Python, Django, API', 'slug': 'backend'},
    {'name': 'Kiberxavfsizlik', 'description': 'Xavfsizlik asoslari', 'slug': 'cybersecurity'},
    {'name': 'Rus tili', 'description': 'Rus tili kursi', 'slug': 'russian'},
    {'name': 'Koreys tili', 'description': 'Koreys tili kursi', 'slug': 'korean'},
]

for c in courses:
    Course.objects.get_or_create(**c)

print("Courses created")