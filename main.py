import requests
from bs4 import BeautifulSoup, Comment
from markdownify import markdownify as md
import json
from urllib.parse import urlparse
import os
import subprocess
from datetime import datetime
import boto3
from botocore.exceptions import ClientError
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import html
import logging
import time

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def get_git_diff():
  # Get the diff of staged changes
  result = subprocess.run(["git", "diff", "--staged", "--color"],
                          capture_output=True,
                          text=True)
  return result.stdout


def colorize_diff(diff):
  # Encode special characters
  diff = html.escape(diff)

  # Convert ANSI color codes to HTML
  ansi_color_pattern = re.compile(
    r'\x1b\[(1|31|32|36)m(.*?)(\x1b\[m|\x1b\[0m)')

  def ansi_to_html(match):
    code, text, _ = match.groups()
    if code == '1':
      return f'<strong>{text}</strong>'
    elif code == '31':
      return f'<span style="color: red;">{text}</span>'
    elif code == '32':
      return f'<span style="color: green;">{text}</span>'
    elif code == '36':
      return f'<span style="color: cyan;">{text}</span>'

  diff = ansi_color_pattern.sub(ansi_to_html, diff)

  # Replace newlines with <br> tags
  diff = diff.replace('\n', '<br>')

  return diff


def send_email(subject, body, html_body=None):
  sender = "John Lowry <john@bryt.works>"
  recipient = "jrlowry@gmail.com"

  aws_region = "us-west-2"
  aws_access_key_id = os.environ['AWS_ACCESS_KEY_ID']
  aws_secret_access_key = os.environ['AWS_SECRET_ACCESS_KEY']

  client = boto3.client('ses',
                        region_name=aws_region,
                        aws_access_key_id=aws_access_key_id,
                        aws_secret_access_key=aws_secret_access_key)

  msg = MIMEMultipart('alternative')
  msg['Subject'] = subject
  msg['From'] = sender
  msg['To'] = recipient

  # Attach plain text part
  text_part = MIMEText(body, 'plain')
  msg.attach(text_part)

  # Attach HTML part if provided
  if html_body:
    html_part = MIMEText(html_body, 'html')
    msg.attach(html_part)

  try:
    response = client.send_raw_email(Source=sender,
                                     Destinations=[recipient],
                                     RawMessage={'Data': msg.as_string()})
  except ClientError as e:
    print(f"An error occurred: {e.response['Error']['Message']}")
    print(f"Error Code: {e.response['Error']['Code']}")
    print(f"Request ID: {e.response['ResponseMetadata']['RequestId']}")
  else:
    print(f"Email sent! Message ID: {response['MessageId']}")


def changes_detected():
  # Check if there are any changes to commit
  result = subprocess.run(["git", "status", "--porcelain"],
                          capture_output=True,
                          text=True)
  return bool(result.stdout.strip())


def git_push():
  token = os.environ['GITHUB_TOKEN']
  repo_url = f"https://{token}@github.com/lowrycito/handbook.git"

  subprocess.run(
    ["git", "config", "--global", "user.email", "jrlowry@gmail.com"])
  subprocess.run(["git", "config", "--global", "user.name", "John Lowry"])

  # Stage all changes
  subprocess.run(["git", "add", "."])

  # Get the diff before committing
  diff = get_git_diff()

  # Generate the commit message with the current date and time
  commit_message = datetime.now().strftime("%m/%d/%Y %H:%M")

  result = subprocess.run(["git", "commit", "-m", commit_message],
                          capture_output=True,
                          text=True)

  if "nothing to commit" not in result.stdout:
    subprocess.run(["git", "push", repo_url])
    print("Changes pushed to GitHub successfully.")
    return diff
  else:
    print("No changes to commit.")
    return None


BASE_URL = "https://www.churchofjesuschrist.org"

HEADERS = {
  'User-Agent':
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
}


def url_to_filename(url):
  parsed_url = urlparse(url)
  path = parsed_url.path.strip('/').replace('/', '-')
  return path


def get_links(url, max_retries=3):
  for attempt in range(max_retries):
    try:
      response = requests.get(f"{BASE_URL}{url}", headers=HEADERS, timeout=30)
      response.encoding = 'utf-8'
      response.raise_for_status()
      break
    except requests.RequestException as e:
      logging.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
      if attempt == max_retries - 1:
        logging.error(f"Failed to fetch {url} after {max_retries} attempts")
        return []
      time.sleep(2 ** attempt)  # Exponential backoff

  soup = BeautifulSoup(response.text, 'html.parser')
  nav = soup.find('nav', class_='manifest')

  if not nav:
    print(f"No navigation links found in {url}")
    return []

  all_links = [link.get('href').split('#')[0] for link in nav.find_all('a')]
  seen = set()
  links = [x for x in all_links if not (x in seen or seen.add(x))]
  return links


def clean_html_for_conversion(content_article):
  """Minimal cleaning - preserve ALL content within article tag"""
  # Only remove script and style tags that don't contain content
  for unwanted in content_article(["script", "style"]):
    unwanted.decompose()
  
  # Remove HTML comments only
  for comment in content_article.find_all(string=lambda text: isinstance(text, Comment)):
    comment.extract()
  
  # Preserve ALL other elements including nav, header, footer, aside, etc.
  # These contain important structural information and content
  
  return content_article


def html_to_markdown(url, max_retries=3):
  for attempt in range(max_retries):
    try:
      response = requests.get(f"{BASE_URL}{url}", headers=HEADERS, timeout=30)
      response.encoding = 'utf-8'
      response.raise_for_status()
      break
    except requests.RequestException as e:
      logging.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
      if attempt == max_retries - 1:
        logging.error(f"Failed to fetch {url} after {max_retries} attempts")
        return
      time.sleep(2 ** attempt)

  soup = BeautifulSoup(response.text, 'html.parser')
  content_article = soup.select_one('article')

  if content_article is None:
    logging.warning(f"No 'article' tag found in {url}")
    return

  # Clean up the HTML before conversion
  content_article = clean_html_for_conversion(content_article)

  # Configure markdownify to convert ALL elements and preserve structure
  markdown_text = md(
    str(content_article),
    heading_style="ATX",           # Use # style headers
    bullets="-",                   # Use - for bullets  
    wrap=False,                    # Don't wrap lines to preserve structure
    # Convert ALL common HTML elements to preserve complete structure
    convert=['table', 'thead', 'tbody', 'tfoot', 'tr', 'th', 'td', 'div', 'p', 'br', 'strong', 'b', 'em', 'i', 'u', 'strike', 'del', 'ins', 'ul', 'ol', 'li', 'dl', 'dt', 'dd', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'span', 'section', 'article', 'aside', 'main', 'header', 'footer', 'nav', 'figure', 'figcaption', 'blockquote', 'pre', 'code', 'a', 'img', 'iframe', 'cite', 'abbr', 'acronym', 'address', 'big', 'small', 'sub', 'sup', 'q', 'samp', 'kbd', 'var', 'dfn', 'time', 'mark', 'ruby', 'rt', 'rp'],
    escape_asterisks=False,        # Don't escape asterisks unnecessarily
    escape_underscores=False,      # Don't escape underscores unnecessarily
    default_title=True,            # Include title attributes
    strip=None                     # Don't strip any tags - convert everything
  )
  
  # Post-process the markdown to fix common issues
  markdown_text = post_process_markdown(markdown_text)
  
  file_name = url_to_filename(url)
  with open(f"./pages/{file_name}.md", 'w', encoding='utf-8') as file:
    file.write(markdown_text)


def post_process_markdown(markdown_text):
  """Post-process markdown to fix only critical formatting issues"""
  # Only fix excessive newlines (more than 4 consecutive)
  markdown_text = re.sub(r'\n{5,}', '\n\n\n\n', markdown_text)
  
  # Clean up any residual HTML entities
  markdown_text = html.unescape(markdown_text)
  
  return markdown_text.strip()


# Ensure pages directory exists
os.makedirs('./pages', exist_ok=True)

# Main execution
handbook_url = "/study/manual/general-handbook?lang=eng"
logging.info("Starting handbook scraping process")
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

if changes_detected():
  print("Changes detected. Pushing to GitHub...")
  diff = git_push()
  if diff:
    plain_body = f"Changes detected. Pushing to GitHub...\n\nDiff:\n{diff}"
    colorized_diff = colorize_diff(diff)
    html_body = f"""
      <html>
      <head>
          <meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
          <style type="text/css">
              pre {{ 
                  font-family: monospace, monospace; 
                  white-space: pre-wrap; 
                  word-wrap: break-word;
                  background-color: #f5f5f5;
                  padding: 10px;
                  border: 1px solid #ccc;
                  border-radius: 4px;
              }}
          </style>
      </head>
      <body>
          <p>Changes detected. Pushing to GitHub...</p>
          <pre>
          {colorized_diff}
          </pre>
      </body>
      </html>
      """
    send_email("Handbook changes detected", plain_body, html_body)
  else:
    send_email(
      "Handbook changes detected",
      "Changes detected, but git push failed or no changes were committed.")
else:
  send_email("No Handbook changes detected", "No changes detected.")
  print("No changes detected. Skipping push to GitHub.")
