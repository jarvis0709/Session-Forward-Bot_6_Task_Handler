#Thank you LazyDeveloper for helping me in this journey !
#Must Subscribe On YouTube @LazyDeveloperr 

from flask import Flask
from urllib.parse import quote as url_quote

app = Flask(__name__)

@app.route('/')
def hello_world():
    return '@LazyDeveloper'


if __name__ == "__main__":
    app.run()
