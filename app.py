from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    # Flask va chercher automatiquement dans le dossier 'templates/index.html'
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)