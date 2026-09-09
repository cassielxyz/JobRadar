import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

MONEY = re.compile(r"(?:₹|rs\.?|inr)\s*([0-9][0-9,]*(?:\.\d+)?)\s*(k|lpa|lakh)?", re.I)
EXP = re.compile(r"(?:(\d+(?:\.\d+)?)\s*(?:-|to)\s*(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\+?)\s*(?:years?|yrs?)", re.I)

def money_to_monthly(value, unit):
    n=float(value.replace(',','')); u=(unit or '').lower()
    if u=='k': return int(n*1000)
    if u in ('lpa','lakh'): return int(n*100000/12)
    return int(n)

def infer_money(text):
    vals=[]
    for m in MONEY.finditer(text or ''):
        try: vals.append(money_to_monthly(m.group(1),m.group(2)))
        except: pass
    vals=[v for v in vals if 1000 <= v <= 1000000]
    return (min(vals), max(vals)) if vals else (None,None)

def infer_experience(text):
    m=EXP.search(text or '')
    if not m: return (None,None)
    if m.group(1): return float(m.group(1)),float(m.group(2))
    v=float(m.group(3)); return (v,v)

def links_from_html(html, base_url):
    soup=BeautifulSoup(html,'html.parser'); out=[]
    for a in soup.find_all('a', href=True):
        title=' '.join(a.stripped_strings)
        href=urljoin(base_url,a['href'])
        if title and href.startswith(('http://','https://')):
            out.append((title,href))
    return out
