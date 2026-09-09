import re
import requests

H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DRLCA-research-project"}
r = requests.get(
    "https://qualitativemagazine.com/a-copy-of-discrimination-against-persons-with-disabilities-prohibition-act-2018/",
    headers=H,
    timeout=60,
)
print(r.status_code, len(r.content))
open("D:/NGORAG/data/raw/qualitativemagazine_page.html", "wb").write(r.content)
for m in sorted(set(re.findall(r'href="([^"]*(?:\.pdf|download)[^"]*)"', r.text, re.I))):
    print(m[:250])
