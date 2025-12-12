# 2D Texture Listing - Application Windows

Application standalone pour comparer les images listées dans des fichiers texte avec celles présentes dans un dossier, avec **suppression directe** des fichiers.

## 🎯 Fonctionnalités

### ✅ Toutes les fonctionnalités de la version web :
- Import de plusieurs fichiers texte (JSON, JS, TXT, etc.)
- Analyse récursive des dossiers
- Comparaison automatique des images
- Filtres et recherche
- Statistiques détaillées avec tailles de fichiers
- Interface moderne et intuitive

### 🆕 Fonctionnalités supplémentaires :
- **Suppression directe des fichiers** depuis l'application
- Pas besoin de navigateur web
- Application native Windows
- Performances optimisées

## 📦 Installation et Compilation

### Prérequis
- Python 3.8 ou supérieur
- Windows 10/11

### Méthode 1 : Utiliser le script de build (RECOMMANDÉ)

1. Double-cliquez sur `build.bat`
2. Attendez la fin de la compilation
3. L'exécutable sera dans le dossier `dist\2D-Texture-Listing.exe`

### Méthode 2 : Installation manuelle

```bash
# Installer les dépendances
pip install -r requirements.txt

# Compiler l'exécutable
pyinstaller --name="2D-Texture-Listing" --onefile --windowed app.py

# L'exécutable sera dans dist\2D-Texture-Listing.exe
```

## 🚀 Utilisation

### Lancer l'application
- Double-cliquez sur `2D-Texture-Listing.exe`
- Ou lancez directement avec Python : `python app.py`

### Workflow typique

1. **Colonne 1 - Fichiers Source**
   - Cliquez sur "📁 Sélectionner un ou plusieurs fichiers"
   - Choisissez vos fichiers JSON/JS/TXT contenant des références d'images
   - Les fichiers importés s'affichent avec le nombre d'images trouvées

2. **Colonne 2 - Dossier d'Images**
   - Cliquez sur "📂 Sélectionner un dossier"
   - Choisissez le dossier contenant vos images
   - L'analyse récursive inclut tous les sous-dossiers

3. **Colonne 3 - Statistiques**
   - Cliquez sur n'importe quelle carte pour voir les détails
   - **"Uniquement dans le dossier"** : Affiche les images non référencées
   - Sélectionnez les images à supprimer
   - Cliquez sur "🗑️ Supprimer les fichiers sélectionnés"

### Suppression de fichiers

1. Cliquez sur la carte "❌ Uniquement dans le dossier"
2. Une fenêtre s'ouvre avec toutes les images non référencées
3. Utilisez "✅ Tout sélectionner" ou cliquez individuellement sur "🗑️ Supprimer"
4. Les fichiers marqués deviennent semi-transparents avec bordure rouge
5. Cliquez sur "🗑️ Supprimer les fichiers sélectionnés"
6. Confirmez la suppression
7. Les fichiers sont **supprimés définitivement** du disque

⚠️ **ATTENTION** : La suppression est **IRRÉVERSIBLE** ! Assurez-vous de bien vérifier avant de confirmer.

## 🎨 Interface

L'application reproduit fidèlement l'interface de la version HTML :
- Design moderne avec dégradés violet/bleu
- 3 colonnes pour une navigation claire
- Pastilles de couleur pour identifier rapidement les statuts
- Miniatures des images dans les fenêtres de détails
- Boutons d'actualisation pour rafraîchir les listes

## 🔧 Développement

### Structure du projet
```
Texture-cleaner/
├── app.py              # Application principale
├── requirements.txt    # Dépendances Python
├── build.bat          # Script de compilation
├── README.md          # Ce fichier
└── dist/              # Dossier créé après compilation
    └── 2D-Texture-Listing.exe
```

### Modifier l'application

1. Éditez `app.py`
2. Testez avec : `python app.py`
3. Recompilez : `build.bat`

## 📝 Notes techniques

- **Framework** : PyQt6 pour l'interface graphique native
- **Compilation** : PyInstaller pour créer l'exécutable standalone
- **Taille** : ~50-80 MB (inclut Python et toutes les dépendances)
- **Compatibilité** : Windows 10/11 (64-bit)

## ⚡ Avantages vs version HTML

| Fonctionnalité | HTML | Application Windows |
|----------------|------|---------------------|
| Suppression directe | ❌ (script PowerShell) | ✅ Directe |
| Besoin de navigateur | ✅ Requis | ❌ Standalone |
| Performances | Moyen | Excellent |
| Installation | Aucune | Une fois |
| Sécurité fichiers | Limitée | Complète |

## 🐛 Dépannage

### L'exécutable ne se lance pas
- Vérifiez que vous avez les droits administrateur
- Désactivez temporairement l'antivirus (faux positif possible)
- Vérifiez les logs dans le dossier de l'application

### Erreur lors de la compilation
- Vérifiez que Python 3.8+ est installé
- Mettez à jour pip : `python -m pip install --upgrade pip`
- Réinstallez les dépendances : `pip install -r requirements.txt --force-reinstall`

### Les images ne s'affichent pas
- Vérifiez que les fichiers existent
- Vérifiez les permissions du dossier
- Formats supportés : JPG, PNG, GIF, BMP, WEBP, TIFF

## 📄 Licence

Cet outil est fourni tel quel, sans garantie. Utilisez-le à vos propres risques.

## 👤 Auteur

Créé pour faciliter la gestion des textures dans les projets de développement.

---

**Version** : 1.0.0  
**Date** : Décembre 2024
