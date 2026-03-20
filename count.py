import csv
from collections import Counter

f = open('cardio.csv', encoding='utf-8-sig')
reader = csv.DictReader(f)

normal_words     = []
concerning_words = []
emergency_words  = []

for row in reader:
    feedback = row.get('Doctor_Feedback','').lower()
    label    = row.get('Alert_Level','').upper()
    words    = feedback.split()

    if 'CALL DOCTOR' in label or 'EMERGENCY' in label:
        emergency_words.extend(words)
    elif 'NURSE' in label:
        concerning_words.extend(words)
    else:
        normal_words.extend(words)

normal_count     = Counter(normal_words)
concerning_count = Counter(concerning_words)
emergency_count  = Counter(emergency_words)

print("TOP 30 NORMAL WORDS")
print(normal_count.most_common(30))
print()
print("TOP 30 CONCERNING WORDS")
print(concerning_count.most_common(30))
print()
print("TOP 30 EMERGENCY WORDS")
print(emergency_count.most_common(30))

print()
print("Total NORMAL words     =", len(normal_words))
print("Total CONCERNING words =", len(concerning_words))
print("Total EMERGENCY words  =", len(emergency_words))
