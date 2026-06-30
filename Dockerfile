# 1. Utiliser une image Python officielle légère
FROM python:3.10-slim

# 2. Définir le dossier de travail dans le conteneur
WORKDIR /app

# 3. Installer les dépendances système minimales
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# 4. Copier le fichier des dépendances
COPY requirements.txt .

# 5. Installer les bibliothèques Python
RUN pip install --no-cache-dir -r requirements.txt

# 6. Copier tout le reste du code (y compris le dossier chroma_db s'il existe)
COPY . .

# 7. Exposer le port requis par Hugging Face Spaces
EXPOSE 7860

# 8. Commande pour lancer l'API au démarrage du conteneur
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7860"]