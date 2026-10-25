import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app

if __name__ == "__main__":
    print("\n=== INFOH303 – Plateforme de Résumés ===")
    print("Ouvrez votre navigateur sur : http://localhost:5000\n")
    app.run(debug=False, host="0.0.0.0", port=5000)
