import requests
from bs4 import BeautifulSoup
import html2text
import json
from urllib.parse import urlparse

BASE_URL = "https://www.churchofjesuschrist.org"

HEADERS = {
  'User-Agent':
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}


def url_to_filename(url):
  parsed_url = urlparse(url)
  path = parsed_url.path.strip('/').replace('/', '-')
  return path


def get_links(url):
  response = requests.get(f"{BASE_URL}{url}", headers=HEADERS)
  response.encoding = 'utf-8'

  try:
    response.raise_for_status()
  except requests.HTTPError as e:
    print(f"Error fetching {url}: {e}")
    print("Response content:", response.text)
    return []

  soup = BeautifulSoup(response.text, 'html.parser')
  nav = soup.find('nav', class_='manifest')

  if not nav:
    print(f"No navigation links found in {url}")
    return []

  all_links = [link.get('href').split('#')[0] for link in nav.find_all('a')]
  seen = set()
  links = [x for x in all_links if not (x in seen or seen.add(x))]
  return links


def html_to_markdown(url):
  response = requests.get(f"{BASE_URL}{url}", headers=HEADERS)
  response.encoding = 'utf-8'

  try:
    response.raise_for_status()
  except requests.HTTPError as e:
    print(f"Error fetching {url}: {e}")
    print("Response content:", response.text)
    return

  soup = BeautifulSoup(response.text, 'html.parser')
  content_article = soup.select_one('article')

  if content_article is None:
    print(f"No 'article' tag found in {url}")
    return

  for a_tag in content_article.find_all('a'):
    if a_tag.get_text():
      a_tag.replace_with(a_tag.get_text())
    else:
      a_tag.decompose()

  markdown_text = html2text.html2text(str(content_article))
  file_name = url_to_filename(url)
  with open(f"./pages/{file_name}.md", 'w', encoding='utf-8') as file:
    file.write(markdown_text)


handbook_url = "/study/manual/general-handbook?lang=eng"
html_to_markdown(handbook_url)
links = get_links(handbook_url)
if links:
  for link in links:
    html_to_markdown(link)

  with open(f"links.json", 'w') as file:
    file.write(json.dumps(list(links), indent=4, sort_keys=True))

  print(f"Done! Found {len(links)} links.")
  print(f"Wrote {len(links)} markdown files.")
  print(f"Wrote links.json with {len(links)} links.")
else:
  print("No links found.")
