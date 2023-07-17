import requests
from bs4 import BeautifulSoup
import html2text
import json
from urllib.parse import urlparse

BASE_URL = "https://www.churchofjesuschrist.org"


def url_to_filename(url):
  # Parse the URL and isolate the path
  parsed_url = urlparse(url)
  path = parsed_url.path

  # Remove leading and trailing slashes
  path = path.strip('/')

  # Replace remaining slashes with hyphens
  path = path.replace('/', '-')

  return path


def get_links(url):
  # Fetch the HTML of the webpage
  response = requests.get(f"{BASE_URL}{url}")
  response.encoding = 'utf-8'

  response.raise_for_status()

  # Use BeautifulSoup to parse the HTML and find the nav
  soup = BeautifulSoup(response.text, 'html.parser')
  nav = soup.find('nav', class_='manifest')

  # Find all the 'a' tags within the nav
  all_links = [link.get('href').split('#')[0] for link in nav.find_all('a')]
  seen = set()
  links = [x for x in all_links if not (x in seen or seen.add(x))]
  return links


def html_to_markdown(url):
  # Fetch the HTML of the webpage
  response = requests.get(f"{BASE_URL}{url}")
  response.encoding = 'utf-8'

  response.raise_for_status()

  # Use BeautifulSoup to extract the text
  soup = BeautifulSoup(response.text, 'html.parser')
  content_article = soup.select_one('article')

  # Check if content_article was found
  if content_article is None:
    print(f"No 'article' tag found in {url}")
    return

  # Find all 'a' tags and replace them with their text content
  for a_tag in content_article.find_all('a'):
    if a_tag.get_text():
      a_tag.replace_with(a_tag.get_text())
    else:
      a_tag.decompose()

  # Use html2text to convert the HTML to Markdown
  markdown_text = html2text.html2text(str(content_article))

  # Write the markdown to a file with the url as the name
  file_name = url_to_filename(url)
  with open(f"./pages/{file_name}.md", 'w', encoding='utf-8') as file:
    file.write(markdown_text)


handbook_url = "/study/manual/general-handbook?lang=eng"
html_to_markdown(handbook_url)
links = get_links(handbook_url)
for link in links:
  html_to_markdown(link)

with open(f"links.json", 'w') as file:
  file.write(json.dumps(list(links), indent=4, sort_keys=True))
