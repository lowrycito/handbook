
from flask import Flask, render_template, send_from_directory
import json
import os
import markdown

app = Flask(__name__)

@app.route('/')
def index():
    # Load navigation data
    try:
        with open('navigation.json', 'r') as f:
            navigation = json.load(f)
    except FileNotFoundError:
        navigation = []
    
    return render_template('index.html', navigation=navigation)

@app.route('/page/<filename>')
def view_page(filename):
    try:
        with open(f'pages/{filename}', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Convert markdown to HTML
        html_content = markdown.markdown(content, extensions=['meta'])
        
        # Load navigation for sidebar
        with open('navigation.json', 'r') as f:
            navigation = json.load(f)
        
        return render_template('page.html', content=html_content, navigation=navigation, current_file=filename)
    except FileNotFoundError:
        return "Page not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
