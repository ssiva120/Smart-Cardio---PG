import re, math

POSITIVE_WORDS = {'good':4,'great':5,'fine':3,'well':3,'better':4,'okay':2,'stable':3,'healthy':4,'medicines':2,'took':1,'slept':2,'no':2,'normal':3,'comfortable':3,'relief':3,'improving':4,'recovered':4,'happy':3,'active':2,'eating':1}
NEGATIVE_WORDS = {'bad':-3,'pain':-4,'tired':-2,'dizzy':-4,'weak':-3,'terrible':-5,'severe':-5,'heavy':-3,'scared':-4,'worried':-3,'breathe':-4,'breathing':-4,'pressure':-3,'uncomfortable':-3,'restless':-2,'nausea':-3,'vomit':-4,'sweat':-2,'cold':-2,'shivering':-3,'cannot':-3}
ALERT_WORDS = ['chest','cardiac','arrest','attack','ambulance','hospital','emergency','help','dying','unconscious']
INTENSITY_WORDS = {'very':2.0,'extremely':3.0,'slightly':0.5,'little':0.5,'really':2.0,'quite':1.5,'so':1.5}
NB_CLASSES = ['NORMAL','CONCERNING','EMERGENCY']
NB_CLASS_PRIOR = {'NORMAL':0.576,'CONCERNING':0.132,'EMERGENCY':0.292}
NB_WORD_LIKELIHOOD = {
    'NORMAL':{'stable':0.12,'good':0.10,'normal':0.11,'fine':0.09,'okay':0.08,'medicines':0.07,'better':0.08,'well':0.09,'improving':0.06,'comfortable':0.05,'healthy':0.07,'pain':0.02,'severe':0.01,'chest':0.02,'emergency':0.001},
    'CONCERNING':{'tired':0.10,'dizzy':0.09,'heavy':0.08,'worried':0.09,'breathe':0.07,'pressure':0.08,'uncomfortable':0.07,'pain':0.09,'cholesterol':0.10,'lifestyle':0.06,'stable':0.03,'good':0.03,'severe':0.04,'chest':0.05},
    'EMERGENCY':{'severe':0.12,'chest':0.13,'pain':0.12,'arrest':0.10,'cardiac':0.11,'attack':0.09,'emergency':0.10,'help':0.08,'breathing':0.09,'scared':0.07,'cannot':0.06,'stable':0.01,'good':0.01,'tired':0.04,'dizzy':0.05}
}

def lexicon_analysis(text):
    words = re.sub(r'[^a-z\s]','',text.lower()).split()
    score,mult,has_alert,word_scores = 0.0,1.0,False,[]
    for word in words:
        if word in INTENSITY_WORDS: mult=INTENSITY_WORDS[word]; word_scores.append({'word':word,'score':0,'type':'intensity'})
        elif word in POSITIVE_WORDS: s=POSITIVE_WORDS[word]*mult; score+=s; word_scores.append({'word':word,'score':round(s,1),'type':'positive'}); mult=1.0
        elif word in NEGATIVE_WORDS: s=NEGATIVE_WORDS[word]*mult; score+=s; word_scores.append({'word':word,'score':round(s,1),'type':'negative'}); mult=1.0
        elif word in ALERT_WORDS: has_alert=True; word_scores.append({'word':word,'score':0,'type':'alert'}); mult=1.0
        else: mult=1.0
    label = 'EMERGENCY' if (has_alert and score<-3) else 'CONCERNING' if (score<=-3 or has_alert) else 'NORMAL'
    return {'algorithm':'Lexicon','score':round(score,2),'label':label,'has_alert':has_alert,'word_scores':word_scores}

def naive_bayes_analysis(text):
    words = re.sub(r'[^a-z\s]','',text.lower()).split()
    class_scores = {}
    for cls in NB_CLASSES:
        lp = math.log(NB_CLASS_PRIOR[cls])
        for word in words:
            lp += math.log(NB_WORD_LIKELIHOOD[cls].get(word, 0.001))
        class_scores[cls] = lp
    max_s = max(class_scores.values())
    exp_s = {c:math.exp(class_scores[c]-max_s) for c in NB_CLASSES}
    total = sum(exp_s.values())
    probs = {c:round(exp_s[c]/total*100,1) for c in NB_CLASSES}
    predicted = max(probs, key=probs.get)
    return {'algorithm':'Naive Bayes','label':predicted,'probabilities':probs,'confidence':probs[predicted]}

def analyze_sms(text):
    lexicon = lexicon_analysis(text)
    nb = naive_bayes_analysis(text)
    severity = {'NORMAL':0,'CONCERNING':1,'EMERGENCY':2}
    if lexicon['label']==nb['label']: final,agreement = lexicon['label'],True
    else:
        final = lexicon['label'] if severity[lexicon['label']]>severity[nb['label']] else nb['label']
        agreement = False
    return {'text':text,'final_label':final,'agreement':agreement,'lexicon':lexicon,'naive_bayes':nb}
