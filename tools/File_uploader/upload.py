from flask import Flask, render_template, request, redirect, url_for, flash
import os

app = Flask(__name__)
app.secret_key = "supersecretkey"  # Required for flash messages

UPLOAD_FOLDER = 'uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure the upload folder exists
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        flash("⚠️ No file part!")
        return redirect(url_for('index'))
    
    file = request.files['file']

    if file.filename == '':
        flash("⚠️ No file selected!")
        return redirect(url_for('index'))

    if file:
        filename = file.filename
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        flash(f"✅ File uploaded successfully: {filename}")
        return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
