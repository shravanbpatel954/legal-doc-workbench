import re
from collections import Counter

STOP_WORDS = set("""
a about above after again all also an and any are as at be because been before being between both but by
can could did do does doing down during each few for from further had has have having he her here hers him his
how i if in into is it its just may me more most my no nor not now of off on once only or other our out over own
per same shall she should so some such than that the their them then there these they this those through to too
under until up upon very was we were what when where which while who whom whose why will with would you your
page
""".split())


def top_keywords(text, how_many=10):
    """Most common meaningful words in the text, most frequent first."""
    words = re.findall(r"[a-z]{3,}", text.lower())
    counts = Counter(word for word in words if word not in STOP_WORDS)
    return [word for word, _ in counts.most_common(how_many)]
