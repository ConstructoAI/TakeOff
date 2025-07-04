# TakeOff AI - Logiciel de Métré PDF avec Intelligence Artificielle

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)
![Status](https://img.shields.io/badge/status-beta-orange.svg)

## 📋 Description

TakeOff AI est un logiciel de métré professionnel qui permet d'effectuer des mesures précises sur des plans PDF avec l'assistance d'une intelligence artificielle. Idéal pour les entrepreneurs, architectes, ingénieurs et professionnels du bâtiment au Québec et ailleurs.

## ✨ Fonctionnalités Principales

### 📐 Mesures Avancées
- **Distance** : Mesure de longueurs avec précision
- **Surface** : Calcul d'aires avec polygones multi-points
- **Périmètre** : Mesure de contours fermés
- **Angle** : Mesure d'angles en 3 points

### 🎯 Outils de Précision
- **Calibration d'échelle** : Conversion automatique des unités PDF vers unités réelles
- **Accrochage intelligent (Snapping)** : Détection automatique des lignes et points du PDF
- **Mode Orthogonal** : Contraintes horizontales/verticales (Shift)
- **Zoom et navigation** : Navigation fluide avec panoramique

### 📊 Gestion de Catalogue
- **Catalogue produits** : Base de données intégrée avec prix et couleurs
- **Association mesures-produits** : Liaison automatique pour estimation
- **Totaux par produit** : Calcul automatique des quantités et coûts
- **Export des données** : CSV, TXT, PDF

### 🤖 Intelligence Artificielle
- **Analyse de documents** : Reconnaissance automatique du type de plan
- **Suggestions de mesures** : Recommandations contextuelles
- **Assistant conversationnel** : Aide interactive pour le métré
- **Profils experts** : Spécialisations par domaine (entrepreneur général, etc.)

### 💾 Gestion de Projets
- **Sauvegarde complète** : PDF, mesures, échelle, catalogue (format .tak)
- **Projets récents** : Accès rapide aux derniers travaux
- **Import/Export** : Partage de catalogues entre projets

## 🚀 Installation

### Prérequis
- Python 3.8 ou supérieur
- tkinter (généralement inclus avec Python)

### Dépendances
```bash
pip install -r requirements.txt
```

**Dépendances principales :**
- `PyMuPDF` : Manipulation de fichiers PDF
- `Pillow` : Traitement d'images
- `anthropic` : API Claude AI
- `reportlab` : Export PDF (optionnel)

### Installation depuis les sources
```bash
git clone https://github.com/votre-username/takeoff-ai.git
cd takeoff-ai
pip install -r requirements.txt
python TAKEOFF_AI_R2507040626.py
```

## 📖 Guide d'utilisation rapide

### 1. Premier lancement
1. Ouvrez un fichier PDF via **Fichier > Ouvrir PDF** (Ctrl+O)
2. Calibrez l'échelle via **Outils > Calibrer Échelle** (F4)
3. Cliquez sur deux points connus et entrez la distance réelle

### 2. Effectuer des mesures
1. Sélectionnez un mode de mesure :
   - **Distance** (F2) : 2 clics
   - **Surface** (F3) : Multiple clics + Double-clic ou Entrée
   - **Périmètre** (F6) : Multiple clics + Double-clic ou Entrée
   - **Angle** (F7) : 3 clics

2. Utilisez les outils d'aide :
   - **Shift** : Mode orthogonal
   - **Accrochage automatique** aux lignes détectées
   - **Molette** : Zoom centré sur curseur

### 3. Gestion des produits
1. Configurez votre catalogue dans l'onglet **Catalogue Produits**
2. Associez les produits aux mesures lors de leur création
3. Consultez les totaux dans l'onglet **Résumé Produits**

### 4. Assistant IA
1. Utilisez **Analyser** (F5) pour une analyse automatique du PDF
2. Posez des questions dans le chat IA
3. Changez de profil expert selon votre domaine

## ⚙️ Configuration

### Variables d'environnement
```bash
export ANTHROPIC_API_KEY="votre_clé_api_claude"
```

### Fichiers de configuration
- **Catalogue** : `~/.takeoffai/product_catalog.json`
- **Profils IA** : `~/.takeoffai/profiles/`
- **Projets récents** : `~/.takeoffai/recent.json`

## 📁 Structure du projet

```
takeoff-ai/
├── TAKEOFF_AI_R2507040626.py    # Application principale
├── profiles/                     # Profils experts IA
├── README.md
├── requirements.txt
└── docs/                        # Documentation
```

## 🎨 Personnalisation

### Couleurs de mesures
Configurez les couleurs par défaut dans l'onglet **Configuration** :
- Distance : Bleu (#0000FF)
- Surface : Vert contour, bleu remplissage
- Angle : Magenta (#FF00FF)
- Points : Rouge (#FF0000)

### Profils experts IA
Créez vos propres profils via **Outils > Gérer Profils Experts IA** pour adapter l'assistant à votre domaine d'expertise.

## 🔧 Dépannage

### Problèmes courants

**L'IA ne fonctionne pas :**
- Vérifiez votre clé API Anthropic
- Consultez la console pour les messages d'erreur

**PDF ne s'affiche pas :**
- Vérifiez que le fichier n'est pas corrompu
- Assurez-vous d'avoir les permissions de lecture

**Accrochage imprécis :**
- Utilisez **Outils > Extraire Lignes PDF** pour régénérer
- Ajustez le seuil dans **Configuration > Accrochage**

### Logs et débogage
Les messages de débogage s'affichent dans la console. Lancez l'application depuis un terminal pour voir les détails.

## 🤝 Contribution

Les contributions sont les bienvenues ! Voici comment participer :

1. Fork le projet
2. Créez une branche feature (`git checkout -b feature/amelioration`)
3. Committez vos changements (`git commit -am 'Ajout nouvelle fonctionnalité'`)
4. Push vers la branche (`git push origin feature/amelioration`)
5. Créez une Pull Request

### Guidelines de développement
- Code en français pour les commentaires et variables métier
- Suivre les conventions PEP 8 pour Python
- Tester les nouvelles fonctionnalités avant PR
- Documenter les changements dans le CHANGELOG

## 📄 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 🙏 Remerciements

- **Anthropic** pour l'API Claude AI
- **PyMuPDF** pour la manipulation PDF
- **Communauté Python** pour les excellentes bibliothèques

## 📞 Support

- **Issues GitHub** : [Créer un ticket](https://github.com/votre-username/takeoff-ai/issues)
- **Email** : support@takeoff-ai.com
- **Documentation** : [Wiki du projet](https://github.com/votre-username/takeoff-ai/wiki)

## 🗺️ Roadmap

### Version 1.2 (Q2 2025)
- [ ] Mesures 3D basiques
- [ ] Templates de catalogues par métier
- [ ] API REST pour intégration
- [ ] Mode collaboratif

### Version 1.3 (Q3 2025)
- [ ] Reconnaissance automatique d'éléments
- [ ] Export vers logiciels de devis
- [ ] Application mobile
- [ ] Intégration cloud

---

**Développé avec ❤️ par Sylvain Leduc**

*TakeOff AI - Révolutionnez votre métré avec l'intelligence artificielle*
