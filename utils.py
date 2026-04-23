import re

URL_REGEX = r'(https?://[^\s]+)'

def extract_urls(text: str):
    return re.findall(URL_REGEX, text)