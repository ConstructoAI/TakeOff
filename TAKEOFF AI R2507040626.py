# --- START OF FILE TAKEOFF AI R2504090719_WITH_TOTALS.py ---

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog, colorchooser # Added colorchooser
from PIL import Image, ImageTk
import fitz  # PyMuPDF pour la manipulation de PDF
import numpy as np
import math
import os
import sys
from datetime import datetime
import json
import csv
from anthropic import Anthropic
import time
# Import for PDF Export (will be used later)
# --- Importation conditionnelle pour éviter l'erreur si reportlab n'est pas installé ---
try:
    from reportlab.lib.pagesizes import letter, landscape
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    print("AVERTISSEMENT: La bibliothèque 'reportlab' n'est pas installée. L'exportation PDF sera désactivée.")
    print("Pour l'activer, installez-la via pip: pip install reportlab")


def resource_path(relative_path):
    """Obtient le chemin absolu vers la ressource, fonctionne en développement et après compilation"""
    try:
        # PyInstaller crée un dossier temporaire et stocke le chemin dans _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def get_app_data_path():
    """Retourne le chemin du dossier de données de l'application"""
    app_name = "TakeOffAI"
    if os.name == 'nt':  # Windows
        app_data = os.path.join(os.environ['APPDATA'], app_name)
    else:  # macOS/Linux
        app_data = os.path.join(os.path.expanduser('~'), f'.{app_name.lower()}')

    # Créer le dossier s'il n'existe pas
    if not os.path.exists(app_data):
        try:
            os.makedirs(app_data)
        except Exception as e:
            print(f"Erreur lors de la création du dossier AppData {app_data}: {e}")
            # Return a fallback path in the current directory if creation fails
            fallback_path = os.path.abspath(f".{app_name.lower()}_data")
            if not os.path.exists(fallback_path):
                try:
                    os.makedirs(fallback_path)
                except Exception as e_fallback:
                     print(f"Erreur critique: Impossible de créer un dossier de données: {e_fallback}")
                     # As a last resort, return the script directory path
                     return os.path.abspath(".")
            print(f"Utilisation du dossier de secours: {fallback_path}")
            app_data = fallback_path


    profiles_dir = os.path.join(app_data, 'profiles')
    if not os.path.exists(profiles_dir):
        try:
            os.makedirs(profiles_dir)
        except Exception as e:
            print(f"Erreur lors de la création du sous-dossier 'profiles' : {e}")


    # Catalog and recent files path definition (creation/checking handled later)
    # catalog_file = os.path.join(app_data, 'product_catalog.json')
    # recent_file = os.path.join(app_data, 'recent.json')

    return app_data

class ExpertProfileManager:
    def __init__(self):
        self.profiles = {}
        self.load_profiles()
        # Ensure default profiles are available if none were loaded
        self.ensure_default_profiles() # Call ensure_default_profiles after initial load attempt

    def load_profiles(self):
        """Charge les profils experts"""
        print("Chargement des profils...")  # Debug

        loaded_ids = set() # Keep track of loaded profile IDs to avoid duplicates

        # Helper function to load from a directory
        def load_from_dir(directory, source_type):
            if not os.path.exists(directory) or not os.path.isdir(directory):
                print(f"Dossier de profils {source_type} non trouvé ou invalide: {directory}") # Debug
                return

            print(f"Recherche de profils {source_type} dans: {directory}") # Debug
            try:
                profile_files = [f for f in os.listdir(directory) if f.endswith('.txt')]
            except Exception as e:
                print(f"Erreur lors de la lecture du dossier {directory}: {e}")
                return

            for profile_file in profile_files:
                profile_id = os.path.splitext(profile_file)[0]
                if profile_id in loaded_ids: # Skip if already loaded
                    continue

                profile_path = os.path.join(directory, profile_file)
                try:
                    with open(profile_path, 'r', encoding='utf-8') as file:
                        content = file.read()
                        # Use the first line as name, fallback to ID if empty
                        lines = content.strip().split('\n')
                        name = lines[0].replace('TU ES UN ', '').strip() if lines and lines[0].strip() else profile_id
                        self.add_profile(profile_id, name, content)
                        loaded_ids.add(profile_id) # Mark as loaded
                        print(f"Profil {source_type} chargé: {profile_id} - {name}")  # Debug
                except Exception as e:
                    print(f"Erreur lors du chargement du profil {source_type} {profile_file}: {str(e)}")

        # 1. Try loading from local 'profiles' directory (development/portable)
        local_profiles_dir = "profiles"
        load_from_dir(local_profiles_dir, "local")

        # 2. Try loading from AppData directory
        app_data = get_app_data_path()
        appdata_profiles_dir = os.path.join(app_data, 'profiles')
        load_from_dir(appdata_profiles_dir, "AppData")

        # 3. Try loading from bundled resources (PyInstaller _MEIPASS)
        try:
            resource_profiles_dir = resource_path("profiles")
            if os.path.isdir(resource_profiles_dir): # Check if it's actually a directory
                 load_from_dir(resource_profiles_dir, "Resource")
        except Exception as e:
            print(f"Erreur lors de l'accès aux profils ressources: {e}")


    def ensure_default_profiles(self):
        """Assure que les profils par défaut sont disponibles s'ils manquent après le chargement."""
        default_profiles_info = {
            "entrepreneur_general": {
                "name": "Entrepreneur Général",
                "content_func": self.get_default_entrepreneur_profile
            }
            # Add other default profiles here if needed
        }

        made_changes = False
        for profile_id, info in default_profiles_info.items():
            if profile_id not in self.profiles:
                print(f"Profil par défaut '{profile_id}' manquant, création...") # Debug
                profile_content = info["content_func"]()
                self.add_profile(profile_id, info["name"], profile_content)
                # Attempt to save the newly created default profile to AppData
                if self.save_profile_to_file(profile_id):
                    print(f"Profil par défaut '{profile_id}' sauvegardé dans AppData.") # Debug
                else:
                    print(f"Erreur lors de la sauvegarde du profil par défaut '{profile_id}'.") # Debug
                made_changes = True

        if made_changes:
             print("Profils par défaut assurés.") # Debug


    def get_default_entrepreneur_profile(self):
        """Retourne le profil entrepreneur par défaut"""
        # (Keep the long profile string here as before)
        return """
TU ES UN ENTREPRENEUR GÉNÉRAL EXPERT EN CONSTRUCTION AU QUÉBEC

**EXPÉRIENCE ET EXPERTISE :**
- 40 ans dans l'industrie de la construction au Québec
- Spécialisation en construction résidentielle et commerciale
- Expert en rénovation et construction neuve
- Maîtrise des techniques adaptées au climat québécois
- Certification RBQ et adhésion aux associations professionnelles pertinentes

**DOMAINES DE COMPÉTENCE :**

**1. Réglementations et normes**
- Code de construction du Québec à jour
- Code national du bâtiment (CNB)
- Règlements municipaux et zonage
- Normes Novoclimat et LEED
- Réglementation environnementale
- Processus d'obtention des permis

**2. Gestion de projets**
- Planification et séquençage des travaux
- Coordination des corps de métier
- Gestion des échéanciers
- Contrôle qualité
- Supervision de chantier
- Sécurité et prévention
- Relations avec les clients et intervenants

**3. Expertise technique**
- Techniques de construction évoluées
- Solutions d'efficacité énergétique
- Systèmes mécaniques et électriques
- Enveloppe du bâtiment
- Fondations adaptées au sol québécois
- Construction en climat nordique
- Rénovation patrimoniale

**4. Gestion financière**
- Estimation détaillée des coûts
- Budgétisation précise
- Contrôle des dépenses
- Analyse de rentabilité
- Gestion des changements
- Négociation avec fournisseurs
- Optimisation des ressources

**APPROCHE CLIENT :**

**1. Analyse des besoins**
- Évaluation approfondie du projet
- Compréhension des objectifs
- Identification des contraintes
- Analyse de faisabilité
- Recommandations personnalisées
- Solutions adaptées au budget

**2. Communication**
- Vulgarisation technique
- Transparence totale
- Rapports réguliers
- Documentation détaillée
- Réponses claires et précises
- Disponibilité constante

**SPÉCIALITÉS PARTICULIÈRES :**

**1. Construction durable**
- Matériaux écologiques
- Efficacité énergétique
- Gestion des déchets
- Certification environnementale
- Innovations vertes
- Récupération des eaux

**2. Rénovation complexe**
- Bâtiments patrimoniaux
- Agrandissements majeurs
- Transformation d'espaces
- Mise aux normes
- Réhabilitation structurale
- Décontamination

**3. Construction neuve**
- Résidentiel haut de gamme
- Commercial et industriel
- Bâtiments institutionnels
- Projets multilogements
- Bâtiments spécialisés
- Constructions sur mesure

**CONNAISSANCES ACTUELLES :**

**1. Tendances du marché**
- Évolution des prix
- Disponibilité des matériaux
- Nouvelles technologies
- Innovations constructives
- Tendances design
- Demandes du marché

**2. Enjeux de l'industrie**
- Pénurie de main-d'œuvre
- Hausse des coûts
- Délais d'approvisionnement
- Changements réglementaires
- Développement durable
- Transformation numérique

**APPROCHE CONSEIL :**

**1. Méthodologie**
- Analyse exhaustive
- Recommandations fondées
- Solutions pragmatiques
- Alternatives viables
- Optimisation des ressources
- Suivi rigoureux

**2. Services-conseils**
- Planification stratégique
- Choix des matériaux
- Sélection des sous-traitants
- Obtention des permis
- Gestion des risques
- Contrôle qualité

**ENGAGEMENT PROFESSIONNEL :**
- Excellence du service
- Qualité supérieure
- Respect des normes
- Éthique professionnelle
- Formation continue
- Innovation constante

**ESTIMATION BUDGÉTAIRE DES COÛTS DE CONSTRUCTION AU QUÉBEC (2025)**

**CONSTRUCTION ÉCONOMIQUE (225-275$/pi²)** - Moyenne : 250$/pi²
* Fondation (40$/pi²)
  - Main-d'œuvre : 35% (14$/pi²)
  - Matériaux : 65% (26$/pi²)
* Structure/charpente (25$/pi²)
  - Main-d'œuvre : 45% (11.25$/pi²)
  - Matériaux : 55% (13.75$/pi²)
* Toiture (15$/pi²)
  - Main-d'œuvre : 40% (6$/pi²)
  - Matériaux : 60% (9$/pi²)
* Finition extérieure (15$/pi²) mur
  - Main-d'œuvre : 45% (6.75$/pi²) mur
  - Matériaux : 55% (8.25$/pi²) mur
* Plomberie (20$/pi²)
  - Main-d'œuvre : 35% (7$/pi²)
  - Matériaux : 65% (13$/pi²)
* Électricité (15$/pi²)
  - Main-d'œuvre : 40% (6$/pi²)
  - Matériaux : 60% (9$/pi²)
* Ventilation/HVAC (12$/pi²)
  - Main-d'œuvre : 45% (5.40$/pi²)
  - Matériaux : 55% (6.60$/pi²)
* Isolation (10$/pi²)
  - Main-d'œuvre : 45% (4.50$/pi²)
  - Matériaux : 55% (5.50$/pi²)
* Finition intérieure (30$/pi²)
  - Main-d'œuvre : 60% (18$/pi²)
  - Matériaux : 40% (12$/pi²)
* Aménagement extérieur (10$/pi²)
  - Main-d'œuvre : 55% (5.50$/pi²)
  - Matériaux : 45% (4.50$/pi²)
Sous-total : 192$/pi² + 58$/pi² (frais/taxes) = 250$/pi²

**CONSTRUCTION DE BASE (300-350$/pi²)** - Moyenne : 325$/pi²
* Fondation (45$/pi²)
  - Main-d'œuvre : 35% (15.75$/pi²)
  - Matériaux : 65% (29.25$/pi²)
* Structure/charpente (30$/pi²)
  - Main-d'œuvre : 40% (12$/pi²)
  - Matériaux : 60% (18$/pi²)
* Toiture (18$/pi²)
  - Main-d'œuvre : 35% (6.30$/pi²)
  - Matériaux : 65% (11.70$/pi²)
* Finition extérieure (18$/pi²) mur
  - Main-d'œuvre : 40% (7.20$/pi²) mur
  - Matériaux : 60% (10.80$/pi²) mur
* Plomberie (25$/pi²)
  - Main-d'œuvre : 32% (8$/pi²)
  - Matériaux : 68% (17$/pi²)
* Électricité (18$/pi²)
  - Main-d'œuvre : 35% (6.30$/pi²)
  - Matériaux : 65% (11.70$/pi²)
* Ventilation/HVAC (15$/pi²)
  - Main-d'œuvre : 40% (6$/pi²)
  - Matériaux : 60% (9$/pi²)
* Isolation (12$/pi²)
  - Main-d'œuvre : 40% (4.80$/pi²)
  - Matériaux : 60% (7.20$/pi²)
* Finition intérieure (35$/pi²)
  - Main-d'œuvre : 55% (19.25$/pi²)
  - Matériaux : 45% (15.75$/pi²)
* Aménagement extérieur (12$/pi²)
  - Main-d'œuvre : 50% (6$/pi²)
  - Matériaux : 50% (6$/pi²)
Sous-total : 228$/pi² + 97$/pi² (frais/taxes) = 325$/pi²

**CONSTRUCTION MOYENNE (350-425$/pi²)** - Moyenne : 387$/pi²
* Fondation (48$/pi²)
  - Main-d'œuvre : 35% (16.80$/pi²)
  - Matériaux : 65% (31.20$/pi²)
* Structure/charpente (35$/pi²)
  - Main-d'œuvre : 35% (12.25$/pi²)
  - Matériaux : 65% (22.75$/pi²)
* Toiture (20$/pi²)
  - Main-d'œuvre : 30% (6$/pi²)
  - Matériaux : 70% (14$/pi²)
* Finition extérieure (22$/pi²) mur
  - Main-d'œuvre : 35% (7.70$/pi²) mur
  - Matériaux : 65% (14.30$/pi²) mur
* Plomberie (30$/pi²)
  - Main-d'œuvre : 30% (9$/pi²)
  - Matériaux : 70% (21$/pi²)
* Électricité (20$/pi²)
  - Main-d'œuvre : 32% (6.40$/pi²)
  - Matériaux : 68% (13.60$/pi²)
* Ventilation/HVAC (18$/pi²)
  - Main-d'œuvre : 35% (6.30$/pi²)
  - Matériaux : 65% (11.70$/pi²)
* Isolation (15$/pi²)
  - Main-d'œuvre : 35% (5.25$/pi²)
  - Matériaux : 65% (9.75$/pi²)
* Finition intérieure (45$/pi²)
  - Main-d'œuvre : 45% (20.25$/pi²)
  - Matériaux : 55% (24.75$/pi²)
* Aménagement extérieur (15$/pi²)
  - Main-d'œuvre : 40% (6$/pi²)
  - Matériaux : 60% (9$/pi²)
Sous-total : 268$/pi² + 119$/pi² (frais/taxes) = 387$/pi²

**CONSTRUCTION HAUT DE GAMME (425-550$/pi²)** - Moyenne : 487$/pi²
* Fondation (55$/pi²)
  - Main-d'œuvre : 35% (19.25$/pi²)
  - Matériaux : 65% (35.75$/pi²)
* Structure/charpente (40$/pi²)
  - Main-d'œuvre : 30% (12$/pi²)
  - Matériaux : 70% (28$/pi²)
* Toiture (25$/pi²)
  - Main-d'œuvre : 25% (6.25$/pi²)
  - Matériaux : 75% (18.75$/pi²)
* Finition extérieure (30$/pi²) mur
  - Main-d'œuvre : 30% (9$/pi²) mur
  - Matériaux : 70% (21$/pi²) mur
* Plomberie (35$/pi²)
  - Main-d'œuvre : 25% (8.75$/pi²)
  - Matériaux : 75% (26.25$/pi²)
* Électricité (25$/pi²)
  - Main-d'œuvre : 30% (7.50$/pi²)
  - Matériaux : 70% (17.50$/pi²)
* Ventilation/HVAC (25$/pi²)
  - Main-d'œuvre : 30% (7.50$/pi²)
  - Matériaux : 70% (17.50$/pi²)
* Isolation (20$/pi²)
  - Main-d'œuvre : 30% (6$/pi²)
  - Matériaux : 70% (14$/pi²)
* Finition intérieure (60$/pi²)
  - Main-d'œuvre : 35% (21$/pi²)
  - Matériaux : 65% (39$/pi²)
* Aménagement extérieur (20$/pi²)
  - Main-d'œuvre : 35% (7$/pi²)
  - Matériaux : 65% (13$/pi²)
Sous-total : 335$/pi² + 152$/pi² (frais/taxes) = 487$/pi²

Pour toiture plate ajouter 15% au prix à la section Toiture

**FRAIS INCLUS (pour chaque catégorie)**

**CONSTRUCTION ÉCONOMIQUE**
(Prix cible 250$/pi² ou 250 000$ pour 1000pi²)
- Base corps de métier : 192$/pi² (192 000$)
- Administration : 3.23% (6 208$)
- Profit : 0% (0$)
- Contingences : 12% (23 040$)
- TPS : 5% (9 600$)
- TVQ : 9.975% (19 152$)
Total des frais : 30.2% (58 000$)
Total final : 250 000$

**CONSTRUCTION DE BASE**
(Prix cible 325$/pi² ou 325 000$ pour 1000pi²)
- Base corps de métier : 228$/pi² (228 000$)
- Administration : 3% (6 840$)
- Profit : 12.6% (28 657$)
- Contingences : 12% (27 360$)
- TPS : 5% (11 400$)
- TVQ : 9.975% (22 743$)
Total des frais : 42.5% (97 000$)
Total final : 325 000$

**CONSTRUCTION MOYENNE**
(Prix cible 387$/pi² ou 387 000$ pour 1000pi²)
- Base corps de métier : 268$/pi² (268 000$)
- Administration : 3% (8 040$)
- Profit : 14.4% (38 667$)
- Contingences : 12% (32 160$)
- TPS : 5% (13 400$)
- TVQ : 9.975% (26 733$)
Total des frais : 44.4% (119 000$)
Total final : 387 000$

**CONSTRUCTION HAUT DE GAMME**
(Prix cible 487$/pi² ou 487 000$ pour 1000pi²)
- Base corps de métier : 335$/pi² (335 000$)
- Administration : 3% (10 050$)
- Profit : 15.4% (51 584$)
- Contingences : 12% (40 200$)
- TPS : 5% (16 750$)
- TVQ : 9.975% (33 416$)
Total des frais : 45.4% (152 000$)
Total final : 487 000$

**NOTES**
1. Calculs basés sur 1000 pi²
2. Pourcentages calculés sur le montant des corps de métier
3. Base corps de métier inclut main d'œuvre et matériaux
4. Administration économique inclut 0.23% supplémentaire
5. Contingences couvrent les imprévus de chantier

**FACTEURS DE VARIATION**
- Région géographique
- Complexité du projet
- Conditions du site
- Volume des travaux
- Fluctuations du marché
- Disponibilité de la main-d'œuvre
- Délais d'approvisionnement

Pour les éléments qui se calculent au pied linéaire, notamment la plomberie et la ventilation, les coûts ont été établis en pourcentage du projet total. Ces pourcentages ont ensuite été convertis en pieds carrés, puis exprimés en ratio pour une maison type d'une superficie au sol de 1000 pieds carrés.

**CALCUL DE LA SUPERFICIE HABITABLE BRUTE**
1. **Niveaux principaux**
- Surface intérieure totale (murs extérieurs inclus)
- Inclut toutes les pièces chauffées
- Inclut les cages d'escalier
- Inclut l'épaisseur des murs intérieurs
- Inclut les garde-robes et rangements intégrés
2. **Sous-sol**
- Compté à 100% si fini et chauffé
- Compté à 50% si semi-fini (chauffé mais non fini)
- Non compté si brut
- Les plafonds doivent avoir une hauteur minimale de 7'6"
3. **Espaces exclus du calcul**
- Garages non chauffés
- Vides sanitaires
- Combles non aménagés
- Balcons et terrasses
- Espaces avec moins de 5' de hauteur

**FORMULE PROPOSÉE POUR UNE BASE DE 325$/PI²**
Base 325$/pi² tout inclus
Maison 1000 pi² :
RDC seul = 1000 pi² × 325$ = 325 000$
(Inclus : fondation, murs, toit, tout)
RDC : 100% = 325$/pi²
Étages intermédiaires : 80% = 260$/pi²
Dernier étage : 85% = 276$/pi² (inclut les contraintes du toit)
Donc pour 1000 pi² par étage :
1 étage = 325 000$
2 étages = (1000 × 325$) + (1000 × 276$) = 601 000$
3 étages = (1000 × 325$) + (1000 × 260$) + (1000 × 276$) = 861 000$

Ces pourcentages sont approximatifs et devraient être ajustés selon :
- La complexité du projet
- La qualité des finitions
- Les conditions du site
- Les spécificités régionales

**DISTRIBUTION H/PI² PAR CORPS DE MÉTIER AU QUÉBEC (2025)**

EXCAVATION/FONDATION = 0.068 heure/pi²
STRUCTURE ET CHARPENTE = 0.12 heure/pi²
TOITURE = 0.035 heure/pi²
FINITION EXTÉRIEURE = 0.04 heure/pi²
PLOMBERIE = 0.025 heure/pi²
ÉLECTRICITÉ = 0.025 heure/pi²
VENTILATION = 0.025 heure/pi²
ISOLATION = 0.02 heure/pi²
FINITION INTÉRIEURE = 0.1125 heure/pi²
AMÉNAGEMENT EXTÉRIEUR = 0.008 heure/pi²ratio

Total du projet de 0.4785 heure/pi²

Estimation rapide : 0.5 heure/pi² ou 333 pieds/mois

Calcul détaillé pour 1000 pieds carrés
Données de base :
Superficie totale : 1000 pi²

Calcul par phase :

1. EXCAVATION/FONDATION (8.0%)
Calcul : 1000 pi² × 0.068 heure/pi²
Heures totales : 68 heures
Détails :
- Excavation : 27 heures
- Installation drain français et membrane : 11 heures
- Coffrage : 14 heures
- Coulée et finition : 16 heures

2. STRUCTURE ET CHARPENTE (28.3%)
Calcul : 1000 pi² × 0.12 heure/pi²
Heures totales : 120 heures

3. TOITURE (4.1%)
Calcul : 1000 pi² × 0.035 heure/pi²
Heures totales : 35 heures

4. FINITION EXTÉRIEURE (9.4%)
Calcul : 1000 pi² × 0.04 heure/pi²
Heures totales : 40 heures

5. PLOMBERIE (5.9%)
Calcul : 1000 pi² × 0.025 heure/pi²
Heures totales : 25 heures

6. ÉLECTRICITÉ (5.9%)
Calcul : 1000 pi² × 0.025 heure/pi²
Heures totales : 25 heures

7. VENTILATION (5.9%)
Calcul : 1000 pi² × 0.025 heure/pi²
Heures totales : 25 heures

8. ISOLATION (4.7%)
Calcul : 1000 pi² × 0.02 heure/pi²
Heures totales : 20 heures

9. FINITION INTÉRIEURE (26.5%)
Calcul : 1000 pi² × 0.1125 heure/pi²
Heures totales : 112.5 heures

10. AMÉNAGEMENT EXTÉRIEUR (1.9%)
Calcul : 1000 pi² × 0.008 heure/pi²
Heures totales : 8 heures

Total des heures
Somme totale des heures : 478.5 heures
        """

    def add_profile(self, profile_id, display_name, profile_content):
        """Ajoute un profil expert à la collection"""
        self.profiles[profile_id] = {
            "id": profile_id,
            "name": display_name,
            "content": profile_content
        }

    def get_profile(self, profile_id):
        """Récupère un profil par son identifiant"""
        return self.profiles.get(profile_id, None)

    def get_all_profiles(self):
        """Récupère tous les profils disponibles"""
        return self.profiles

    def save_profile_to_file(self, profile_id):
        """Sauvegarde un profil dans un fichier dans AppData"""
        profile = self.get_profile(profile_id)
        if not profile:
            return False

        app_data = get_app_data_path()
        profiles_dir = os.path.join(app_data, 'profiles')
        if not os.path.exists(profiles_dir):
             try:
                 os.makedirs(profiles_dir)
             except Exception as e:
                 print(f"Impossible de créer le dossier de profils AppData: {e}")
                 return False

        filepath = os.path.join(profiles_dir, f"{profile_id}.txt")

        try:
            with open(filepath, 'w', encoding='utf-8') as file:
                file.write(profile["content"])
            return True
        except Exception as e:
            print(f"Erreur lors de la sauvegarde du profil {profile_id} dans {filepath}: {str(e)}")
            return False

class ProductCatalog:
    """Classe pour gérer le catalogue de produits"""
    def __init__(self):
        self.categories = {}
        self.app_data_file = os.path.join(get_app_data_path(), 'product_catalog.json')
        self.is_dirty = False # Flag pour savoir si des modifs non sauv. existent
        # Essayer de charger le catalogue existant
        if not self.load_catalog_from_appdata():
            # Si aucun catalogue existant, charger le catalogue par défaut
            self.load_default_catalog()
            self.is_dirty = True # Default catalog is considered a change initially

    def load_default_catalog(self):
        """Charge un catalogue par défaut avec quelques exemples"""
        # Catégorie Portes
        self.categories["Portes"] = {
            "Porte d'entrée standard": {"dimensions": "90x215", "prix": 450.0, "color": None}, # Added color
            "Porte intérieure": {"dimensions": "80x200", "prix": 120.0, "color": None},
            "Porte coupe-feu": {"dimensions": "90x215", "prix": 580.0, "color": None},
            "Porte-fenêtre coulissante": {"dimensions": "240x215", "prix": 850.0, "color": None}
        }

        # Catégorie Fenêtres
        self.categories["Fenêtres"] = {
            "Fenêtre standard PVC": {"dimensions": "120x100", "prix": 320.0, "color": None},
            "Fenêtre double vitrage": {"dimensions": "120x150", "prix": 450.0, "color": None},
            "Fenêtre triple vitrage": {"dimensions": "120x150", "prix": 620.0, "color": None},
            "Fenêtre de toit": {"dimensions": "78x98", "prix": 480.0, "color": None}
        }

        # Catégorie Portes de garage
        self.categories["Portes de garage"] = {
            "Porte sectionnelle standard": {"dimensions": "240x200", "prix": 1200.0, "color": None},
            "Porte basculante manuelle": {"dimensions": "240x200", "prix": 800.0, "color": None},
            "Porte sectionnelle motorisée": {"dimensions": "300x215", "prix": 1800.0, "color": None}
        }
        # Example with color
        self.categories["Revêtements"] = {
            "Pierre Type A (Gris)": {"dimensions": "N/A", "prix": 75.0, "color": "#808080"},
            "Bois Type B (Brun)": {"dimensions": "N/A", "prix": 50.0, "color": "#A0522D"}
        }
        self.mark_dirty() # Mark as dirty after loading defaults

    def mark_dirty(self):
        """Marque le catalogue comme ayant des modifications non sauvegardées."""
        if not self.is_dirty:
             print("[DEBUG] Catalogue marqué comme modifié (dirty).")
             self.is_dirty = True

    def save_catalog_to_appdata(self):
        """Sauvegarde le catalogue dans le dossier de données de l'application"""
        print(f"[DEBUG] Tentative de sauvegarde du catalogue vers : {self.app_data_file}") # DEBUG
        try:
            with open(self.app_data_file, 'w', encoding='utf-8') as f:
                print("[DEBUG] Fichier catalogue ouvert pour écriture...") # DEBUG
                json.dump(self.categories, f, indent=2, ensure_ascii=False)
                print("[DEBUG] json.dump du catalogue terminé.") # DEBUG
            print("[DEBUG] Sauvegarde catalogue terminée avec succès.") # DEBUG
            self.is_dirty = False # Reset flag only on successful save
            return True
        except Exception as e:
            print(f"[DEBUG] Erreur lors de la sauvegarde du catalogue dans {self.app_data_file}: {str(e)}") # DEBUG
            # Consider showing an error to the user maybe via the main app status bar?
            return False

    def load_catalog_from_appdata(self):
        """Charge le catalogue depuis le dossier de données de l'application"""
        try:
            if os.path.exists(self.app_data_file):
                with open(self.app_data_file, 'r', encoding='utf-8') as f:
                    self.categories = json.load(f)
                self.is_dirty = False # Freshly loaded, no changes yet
                print(f"Catalogue chargé depuis {self.app_data_file}")
                return True
            print(f"Fichier catalogue non trouvé à {self.app_data_file}")
            return False
        except Exception as e:
            print(f"Erreur lors du chargement du catalogue depuis {self.app_data_file}: {str(e)}")
            # Ensure categories is a dict even if loading fails
            self.categories = {}
            self.is_dirty = False # Consider it clean state after error
            return False

    def add_category(self, category_name):
        """Ajoute une nouvelle catégorie"""
        if category_name not in self.categories:
            self.categories[category_name] = {}
            self.mark_dirty() # NE PAS SAUVEGARDER ICI
            return True
        return False

    def remove_category(self, category_name):
        """Supprime une catégorie"""
        if category_name in self.categories:
            del self.categories[category_name]
            self.mark_dirty() # NE PAS SAUVEGARDER ICI
            return True
        return False

    def add_product(self, category, product_name, attributes):
        """Ajoute un produit à une catégorie"""
        if category in self.categories:
            self.categories[category][product_name] = attributes
            self.mark_dirty() # NE PAS SAUVEGARDER ICI
            return True
        return False

    def update_product(self, category, product_name, attributes):
        """Met à jour un produit existant"""
        if category in self.categories and product_name in self.categories[category]:
            # Avoid marking dirty if attributes are identical? Optional optimization.
            # if self.categories[category][product_name] != attributes:
            self.categories[category][product_name] = attributes
            self.mark_dirty() # NE PAS SAUVEGARDER ICI
            return True
        return False

    def remove_product(self, category, product_name):
        """Supprime un produit"""
        if category in self.categories and product_name in self.categories[category]:
            del self.categories[category][product_name]
            self.mark_dirty() # NE PAS SAUVEGARDER ICI
            return True
        return False

    def get_categories(self):
        """Retourne la liste des catégories"""
        return list(self.categories.keys())

    def get_products(self, category):
        """Retourne la liste des produits d'une catégorie"""
        if category in self.categories:
            return list(self.categories[category].keys())
        return []

    def get_product_attributes(self, category, product_name):
        """Retourne les attributs d'un produit"""
        if category in self.categories and product_name in self.categories[category]:
            return self.categories[category][product_name]
        return None

    def save_to_json(self, filename):
        """Enregistre le catalogue dans un fichier JSON externe"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.categories, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving catalog to {filename}: {e}")
            return False


    def load_from_json(self, filename):
        """Charge le catalogue depuis un fichier JSON externe"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                loaded_categories = json.load(f) # Load into temporary variable
            self.categories = loaded_categories # Replace current catalog
            # Sauvegarder également dans le fichier par défaut AppData après import
            if self.save_catalog_to_appdata(): # This also resets is_dirty flag
                 print(f"Catalogue importé de {filename} et sauvegardé dans AppData.")
            else:
                 print(f"Catalogue importé de {filename}, mais échec sauvegarde dans AppData.")
                 self.is_dirty = True # Mark as dirty if AppData save failed
            return True
        except Exception as e:
            print(f"Error loading catalog from {filename}: {e}")
            return False

class AIAssistant:
    """Classe pour l'assistant IA intégré"""
    def __init__(self):
         # --- !!! SECURITY WARNING !!! ---
         # Hardcoding API keys is a major security risk.
         # Replace this with a secure method like environment variables or config files.
         # Example: self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        # self.api_key = "YOUR_ANTHROPIC_API_KEY_HERE" # <-- Replace with env var or config read
        self.api_key = "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" # <-- WARNING: HARDCODED KEY - NE PAS METTRE EN PRODUCTION !
        if not self.api_key:
            print("AVERTISSEMENT: Clé API Anthropic non trouvée. Les fonctionnalités IA seront désactivées.")
            self.anthropic = None
        else:
            try:
                self.anthropic = Anthropic(api_key=self.api_key)
            except Exception as e:
                print(f"Erreur lors de l'initialisation du client Anthropic: {e}. Les fonctionnalités IA pourraient être désactivées.")
                self.anthropic = None

        self.conversation_history = []

        # Ajouter le gestionnaire de profils
        self.profile_manager = ExpertProfileManager()
        # Assigner un profil par défaut valide au démarrage
        default_profile_id = "entrepreneur_general"
        if default_profile_id not in self.profile_manager.get_all_profiles():
             # Fallback if the default is somehow missing after ensure_default_profiles
             available_profiles = list(self.profile_manager.get_all_profiles().keys())
             if available_profiles:
                  default_profile_id = available_profiles[0]
             else:
                  # Critical error - no profiles available at all
                  print("ERREUR CRITIQUE: Aucun profil expert IA disponible.")
                  # Handle this case gracefully, maybe disable AI features?
                  default_profile_id = None # Or a dummy ID

        self.current_profile_id = default_profile_id


    def set_current_profile(self, profile_id):
        """Change le profil expert courant"""
        if profile_id in self.profile_manager.get_all_profiles():
            self.current_profile_id = profile_id
            return True
        return False

    def get_current_profile(self):
        """Récupère le profil expert courant"""
        if self.current_profile_id is None: # Handle case where no profile could be set initially
            return {
                     "id": "no_profile",
                     "name": "Aucun Profil",
                     "content": "ERREUR: Aucun profil IA chargé."
                 }

        profile = self.profile_manager.get_profile(self.current_profile_id)

        # Si le profil n'est pas trouvé (ne devrait pas arriver si ID est valide), retourner un profil d'erreur
        if not profile:
             print(f"ERREUR: Profil courant ID '{self.current_profile_id}' introuvable!")
             # Try to recover by setting to the first available profile
             available_profiles = self.profile_manager.get_all_profiles()
             if available_profiles:
                  first_profile_id = next(iter(available_profiles))
                  self.current_profile_id = first_profile_id
                  return available_profiles[first_profile_id]
             else: # Absolute fallback
                  return {
                      "id": "fallback_error",
                      "name": "Erreur Profil",
                      "content": "ERREUR: Impossible de charger un profil expert."
                  }
        return profile

    def get_response(self, user_query, measures=None, pdf_info=None):
        """Obtient une réponse de l'IA basée sur le contexte actuel"""
        if not self.anthropic:
            return "Désolé, le client IA n'est pas initialisé. Vérifiez la clé API."

        # Préparation du contexte avec les informations du document et des mesures
        context = "État actuel du document et des mesures :\n"

        if pdf_info:
            context += f"Document PDF: {pdf_info['filename']}\n"
            context += f"Nombre de pages: {pdf_info['page_count']}\n"
            if 'scale' in pdf_info and pdf_info['scale']:
                # Display scale in a more user-friendly way if possible
                try:
                    # Affichons l'échelle en unités par point PDF
                    context += f"Échelle absolue (approx.): 1 pt PDF = {pdf_info['scale']:.5f} mètres\n"
                except:
                     context += f"Échelle (absolue): {pdf_info['scale']}\n" # Fallback
            else:
                context += "Échelle: Non définie\n"
            # Add current page info
            if 'current_page' in pdf_info:
                context += f"Page actuelle: {pdf_info['current_page'] + 1}\n"


        if measures and len(measures) > 0:
            context += "\nMesures effectuées (les plus récentes):\n"
            # Show only the last few measures to keep context concise
            max_measures_in_context = 5
            start_index = max(0, len(measures) - max_measures_in_context)
            for i, measure in enumerate(measures[start_index:], start_index + 1):
                # Include product info if available
                product_str = ""
                if measure.get("product_name"):
                    product_str = f" (Produit: {measure['product_name']})"
                # Ensure display_text exists
                display_val = measure.get("display_text", f"Valeur N/A ({measure.get('value', '?')})")
                # Format output clearly
                context += f"{i}. {measure.get('type','N/A').capitalize()}: {display_val}{product_str} (Page {measure.get('page', '?') + 1})\n"
        else:
            context += "\nAucune mesure n'a encore été effectuée.\n"

        # Conserver un historique limité des conversations
        max_history = 3 # Garder les 3 derniers échanges (user+assistant)
        # Make sure history entries are valid dicts
        self.conversation_history = [entry for entry in self.conversation_history if isinstance(entry, dict) and 'user' in entry and 'assistant' in entry]
        if len(self.conversation_history) > max_history * 2 : # Store pairs
            self.conversation_history = self.conversation_history[-(max_history*2):]


        # Construire le prompt avec l'historique
        history_for_prompt = []
        for entry in self.conversation_history:
             history_for_prompt.append({"role": "user", "content": entry['user']})
             history_for_prompt.append({"role": "assistant", "content": entry['assistant']})

        # Récupérer le profil actuel
        profile = self.get_current_profile()
        if not profile or "ERREUR" in profile["content"]: # Check for error profile
             return "Erreur: Impossible de charger un profil expert valide pour l'IA."

        # System Prompt (Profile Content)
        system_prompt = profile['content']

        # Construct messages list for API
        messages = history_for_prompt + [{"role": "user", "content": f"Contexte actuel du projet:\n{context}\n---\nQuestion: {user_query}"}]


        try:
            # model = "claude-3-opus-20240229" # Using Opus for potentially better reasoning
            # model="claude-3-haiku-20240307" # Faster/cheaper option if Opus is too slow/expensive
            model="claude-3-7-sonnet-20250219" # Use the latest Sonnet model

            response = self.anthropic.messages.create(
                model=model,
                max_tokens=1500, # Adjust token limit as needed
                system=system_prompt, # Use the system parameter for the profile/persona
                messages=messages
            )

            # Handle potential empty or non-text response content
            if response.content and isinstance(response.content, list) and len(response.content) > 0:
                 if hasattr(response.content[0], 'text'):
                     answer = response.content[0].text
                 else:
                     answer = "[Réponse IA non textuelle ou vide]"
                     print(f"Avertissement: Réponse IA inattendue: {response.content}")
            else:
                 answer = "[Réponse IA vide]"
                 print(f"Avertissement: Réponse IA vide: {response}")


            # Enregistrer dans l'historique (vérifier que la réponse n'est pas vide)
            if user_query and answer:
                 self.conversation_history.append({
                     "user": user_query,
                     "assistant": answer
                 })

            return answer

        except Exception as e:
             error_message = f"Désolé, une erreur est survenue lors de la communication avec l'IA : {str(e)}"
             print(error_message) # Log the error for debugging
             # Optionally add to history to show the user an error occurred
             # self.conversation_history.append({"user": user_query, "assistant": error_message})
             return error_message


    def analyze_pdf(self, pdf_path):
        """Analyse un document PDF et fournit des informations pertinentes"""
        if not self.anthropic:
            return "Désolé, le client IA n'est pas initialisé."
        if not os.path.exists(pdf_path):
             return "Erreur: Le fichier PDF spécifié n'existe pas."

        try:
            # Extraire le contenu du PDF (limit pages/text size for performance)
            document = fitz.open(pdf_path)
            pdf_text = ""
            max_pages_analyze = 5 # Limit analysis to first few pages
            max_text_length = 15000 # Limit total text length sent to AI

            for i in range(min(max_pages_analyze, document.page_count)):
                page = document[i]
                page_text_content = page.get_text("text") # Extract text only
                if page_text_content: # Ensure content is not None
                    pdf_text += page_text_content
                    pdf_text += f"\n--- Fin de la page {i+1} ---\n"
                    if len(pdf_text) > max_text_length:
                        break # Stop if text limit reached

            # Tronquer si nécessaire
            if len(pdf_text) > max_text_length:
                pdf_text = pdf_text[:max_text_length] + f"...(texte tronqué après {max_pages_analyze} pages ou {max_text_length} caractères)..."

            document.close() # Close the document after extraction

            # Récupérer le profil actuel
            profile = self.get_current_profile()
            if not profile or "ERREUR" in profile["content"]:
                 return "Erreur: Impossible de charger un profil expert valide pour l'IA."

            # System Prompt (Profile)
            system_prompt = profile['content']

            # User Prompt pour l'analyse du document
            user_prompt = f"""
Voici le contenu textuel des premières pages d'un document PDF ({os.path.basename(pdf_path)}) que l'utilisateur souhaite analyser :
--- DEBUT EXTRAIT PDF ---
{pdf_text if pdf_text else "[Aucun texte extrait ou texte vide]"}
--- FIN EXTRAIT PDF ---

En tant qu'expert en lecture de plans et devis, veuillez analyser cet extrait et fournir un résumé concis incluant :
1.  **Type de document probable** (ex: plan architectural, plan de structure, devis technique, etc.). Justifiez brièvement.
2.  **Informations clés repérées** (ex: nom du projet, adresse, échelle mentionnée, type de construction, matériaux principaux, etc.). Listez les éléments trouvés. S'il y a une échelle, citez-la explicitement.
3.  **Conseils généraux pour le métré** sur ce type de document (ex: éléments importants à mesurer, points de vigilance, conventions typiques).
4.  **Étape suivante suggérée** pour l'utilisateur dans le logiciel TakeOff AI (ex: calibrer l'échelle si trouvée, commencer à mesurer les murs, etc.).

Répondez de manière structurée et facile à lire. Si le texte est insuffisant pour une analyse complète, mentionnez-le.
            """

            try:
                # model="claude-3-opus-20240229" # Opus for better analysis
                model="claude-3-7-sonnet-20250219" # Use the latest Sonnet model

                response = self.anthropic.messages.create(
                    model=model,
                    max_tokens=2000,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}]
                )

                # Handle potential empty or non-text response content
                if response.content and isinstance(response.content, list) and len(response.content) > 0:
                     if hasattr(response.content[0], 'text'):
                         return response.content[0].text
                     else:
                         return "[Réponse IA (analyse) non textuelle ou vide]"
                else:
                     return "[Réponse IA (analyse) vide]"

            except Exception as e:
                error_message = f"Désolé, une erreur est survenue lors de l'analyse IA : {str(e)}"
                print(error_message)
                return error_message

        except Exception as e:
             error_message = f"Erreur lors de l'extraction du contenu du PDF pour analyse : {str(e)}"
             print(error_message)
             return error_message

    def get_measurement_suggestions(self, pdf_info):
        """Suggère des points importants à mesurer dans le document"""
        if not self.anthropic:
            return "Désolé, le client IA n'est pas initialisé."

        # Récupérer le profil actuel
        profile = self.get_current_profile()
        if not profile or "ERREUR" in profile["content"]:
             return "Erreur: Impossible de charger un profil expert valide pour l'IA."

        # Build context string from pdf_info
        context = f"L'utilisateur travaille sur le document PDF '{pdf_info.get('filename', 'inconnu')}' ({pdf_info.get('page_count', '?')} pages).\n"
        context += f"Il est actuellement à la page {pdf_info.get('current_page', '?') + 1}.\n"
        if pdf_info.get('scale'):
            try:
                # Display scale correctly (meters per PDF point)
                context += f"L'échelle absolue actuelle est définie à environ 1 pt PDF = {pdf_info['scale']:.5f} mètres.\n"
            except:
                 context += f"L'échelle absolue actuelle est définie à {pdf_info.get('scale')}.\n"
        else:
             context += "L'échelle n'est pas encore définie.\n"
        # You could add more context here, like the document type if known from a previous analysis


        # System Prompt (Profile)
        system_prompt = profile['content']

        user_prompt = f"""
Contexte : {context}

Basé sur votre expertise en métré et le contexte fourni (en particulier le type de document si vous le connaissez), suggérez 3 à 5 types de mesures **spécifiques** et **pertinentes** que l'utilisateur devrait probablement effectuer sur ce genre de document.

Pour chaque suggestion :
1.  Nommez clairement l'élément à mesurer (ex: "Murs extérieurs", "Superficie des pièces", "Longueur des fondations", "Nombre de fenêtres Type A").
2.  Expliquez **brièvement** pourquoi cette mesure est typiquement importante pour un projet de construction (ex: calcul des matériaux, estimation des coûts, conformité, etc.).

Donnez une réponse concise et directement exploitable par un professionnel utilisant TakeOff AI. Si l'échelle n'est pas définie, suggérez de la calibrer en premier si pertinent.
        """

        try:
            # model="claude-3-haiku-20240307" # Haiku is likely sufficient for suggestions
            model="claude-3-7-sonnet-20250219" # Use the latest Sonnet model

            response = self.anthropic.messages.create(
                model=model,
                max_tokens=1000,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )

            # Handle potential empty or non-text response content
            if response.content and isinstance(response.content, list) and len(response.content) > 0:
                 if hasattr(response.content[0], 'text'):
                      return response.content[0].text
                 else:
                      return "[Réponse IA (suggestions) non textuelle ou vide]"
            else:
                 return "[Réponse IA (suggestions) vide]"


        except Exception as e:
             error_message = f"Désolé, une erreur est survenue lors de la génération de suggestions : {str(e)}"
             print(error_message)
             return error_message


class MetrePDFApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Constructo AI - TakeOff")
        self.root.geometry("1300x850") # Slightly larger default size
        # Configuration des couleurs principales
        self.root.configure(bg="#2c3e50")  # Couleur bleu foncé pour le fond

        # Variables
        self.pdf_document = None
        self.pdf_path = None # Store the path of the loaded PDF
        self.current_page = 0
        self.zoom_factor = 1.0
        self.absolute_scale = None # Scale at zoom=1.0 (METERS per PDF point unit), constant after calibration
        self.points = [] # Temporary points for ongoing measurement (STORE PDF COORDS)
        self.measures = []  # Storage of completed measurements {id, type, value (pdf_pts/pdf_pts^2/deg), points (pdf), page, display_text, product_info...}
        self.mode = "distance"  # Modes: "distance", "surface", "perimeter", "angle", "calibration"
        self.lines_by_page = {}  # Storage of detected lines for snapping {page_index: [((x0_pdf,y0_pdf),(x1_pdf,y1_pdf)), ...]}
        self.ortho_mode = False  # State of orthogonal mode (Shift key)
        self.panning = False
        self.pan_start_x = 0
        self.pan_start_y = 0
        self.pan_accum_x = 0.0 # Accumulator for smoother panning
        self.pan_accum_y = 0.0 # Accumulator for smoother panning
        self.pan_sensitivity = 10.0 # Adjusted sensitivity

        # --- AJOUT pour surbrillance ---
        self.selected_measure_id = None # ID de la mesure sélectionnée dans la liste

        # --- AJOUT pour totaux par produit ---
        self.totals_list = None # Sera initialisé dans create_side_panel

        # Initialiser le catalogue de produits
        self.product_catalog = ProductCatalog()

        # Variables pour la gestion des produits (catalog tab)
        self.current_category = tk.StringVar()
        self.current_product = tk.StringVar()
        self.product_color_var = tk.StringVar() # Added for product color

        # Initialiser l'assistant IA
        self.ai_assistant = AIAssistant()

        # Couleurs spécifiques pour l'interface
        self.colors = {
            "primary": "#2c3e50",     # Bleu foncé
            "secondary": "#3498db",   # Bleu clair
            "accent": "#27ae60",      # Vert
            "warning": "#e74c3c",     # Rouge
            "text_light": "#ecf0f1",  # Blanc cassé
            "text_dark": "#2c3e50",   # Bleu foncé
            "bg_light": "#f0f0f0",    # Gris très clair
            "user_msg": "#e3f2fd",    # Bleu clair pour messages utilisateur
            "ai_msg": "#e8f5e9",      # Vert clair pour messages IA
            "angle": "#FF00FF",       # Magenta for angles (Default)
            "perimeter": "#FFA500"    # Orange for perimeter
        }

        # Style pour les widgets
        self.setup_styles()

        # Créer l'interface
        self.create_widgets()

        # Update treeview columns AFTER creating it in create_side_panel
        self.update_measures_treeview_columns()

        # Créer le menu
        self.create_menu() # Create menu after main widgets

        # Projets récents (Load after menu creation)
        self.recent_projects = self.load_recent_projects()
        self.update_recent_projects_menu() # Update menu after loading

        # Initial status
        self.status_bar.config(text="Prêt. Ouvrez un fichier PDF ou un projet.")

        # Bind Shift keys globally to the root window for ortho mode
        self.root.bind("<KeyPress-Shift_L>", self.shift_pressed)
        self.root.bind("<KeyRelease-Shift_L>", self.shift_released)
        self.root.bind("<KeyPress-Shift_R>", self.shift_pressed)
        self.root.bind("<KeyRelease-Shift_R>", self.shift_released)

        # Bind pan keys to canvas specifically
        self.canvas.bind("<ButtonPress-2>", self.start_pan) # Button-2 is often middle mouse button
        self.canvas.bind("<ButtonPress-3>", self.start_pan) # Use Button-3 (right-click) on macOS if no middle button
        self.canvas.bind("<B2-Motion>", self.on_pan)
        self.canvas.bind("<B3-Motion>", self.on_pan) # Allow pan with right mouse on macOS
        self.canvas.bind("<ButtonRelease-2>", self.end_pan)
        self.canvas.bind("<ButtonRelease-3>", self.end_pan) # Allow pan release with right mouse

        # Handle window close event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_styles(self):
        """Configure les styles pour les widgets"""
        style = ttk.Style()
        style.theme_use('clam') # Use a theme that allows more customization

        # General Styles
        style.configure("TButton", font=('Arial', 10), padding=5)
        style.configure("TFrame", background=self.colors["bg_light"])
        style.configure("TLabelframe", background=self.colors["bg_light"], relief="groove", borderwidth=1)
        style.configure("TLabelframe.Label", background=self.colors["bg_light"], foreground=self.colors["text_dark"], font=('Arial', 10, 'bold'))
        style.configure("TLabel", background=self.colors["bg_light"], foreground=self.colors["text_dark"])
        style.configure("TNotebook", background=self.colors["bg_light"])
        style.configure("TNotebook.Tab", padding=[8, 4], font=('Arial', 10))
        style.map("TNotebook.Tab",
                  foreground=[('selected', self.colors["primary"]), ('!selected', self.colors["text_dark"])],
                  background=[('selected', self.colors["bg_light"]), ('!selected', '#d0d0d0')])


        # Style for Toolbar buttons
        style.configure("Toolbar.TButton", padding=6, relief="flat", background="#e0e0e0")
        style.map("Toolbar.TButton",
                  background=[('active', self.colors["secondary"]), ('pressed', self.colors["accent"])],
                  foreground=[('active', self.colors["text_light"]), ('pressed', self.colors["text_light"])])

        # Style for Action buttons
        style.configure("Action.TButton",
                        background=self.colors["secondary"],
                        foreground=self.colors["text_light"],
                        font=('Arial', 10, 'bold'), relief="raised")
        style.map("Action.TButton",
                  background=[('active', '#2980b9')]) # Darker blue on hover/press

        # Style for Treeview
        style.configure("Treeview", rowheight=25, font=('Arial', 10))
        style.configure("Treeview.Heading", font=('Arial', 10, 'bold'), background="#d0d0d0", relief="flat")
        style.map("Treeview.Heading", relief=[('active','groove'),('pressed','sunken')])


    def create_widgets(self):
        # Frame principal
        self.main_frame = ttk.Frame(self.root, style="TFrame") # Use ttk Frame
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Header avec le titre principal
        self.header_frame = tk.Frame(self.main_frame, bg=self.colors["primary"], height=50) # Reduced height
        self.header_frame.pack(fill=tk.X)
        self.header_frame.pack_propagate(False) # Prevent resizing

        # Titre principal
        tk.Label(self.header_frame, text="Constructo AI - TakeOff",
                 font=('Arial', 20, 'bold'), fg=self.colors["text_light"],
                 bg=self.colors["primary"]).pack(pady=10, anchor="center")

        # Barre d'outils (Create before PanedWindow)
        self.create_toolbar()

        # Panneau principal divisé en trois parties
        self.panel_frame = ttk.PanedWindow(self.main_frame, orient=tk.HORIZONTAL)
        self.panel_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5)) # No top padding

        # Zone de visualisation PDF (Left)
        self.create_pdf_viewer()

        # Panneau latéral pour les mesures et informations (Middle)
        self.create_side_panel()

        # Panneau pour l'assistant IA (Right)
        self.create_ai_panel()

        # Barre de statut
        self.status_bar = ttk.Label(
            self.root, # Attach to root so it's always at the bottom
            text="Prêt",
            relief=tk.SUNKEN,
            anchor=tk.W,
            padding=(5, 2),
            background="#e0e0e0",
            foreground=self.colors["text_dark"]
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_toolbar(self):
        """Crée la barre d'outils"""
        # Use a standard Frame with a background color for the toolbar container
        self.toolbar_container = tk.Frame(self.main_frame, bg="#d0d0d0", bd=1, relief=tk.RAISED)
        self.toolbar_container.pack(fill=tk.X, pady=(0, 5)) # Add padding below

        self.toolbar = ttk.Frame(self.toolbar_container, style="TFrame") # Use ttk Frame inside
        self.toolbar.pack(fill=tk.X, padx=5, pady=5)

        # --- File Operations ---
        file_frame = ttk.Frame(self.toolbar)
        file_frame.pack(side=tk.LEFT, padx=(0, 10)) # Add padding to the right
        ttk.Button(file_frame, text="📂 Ouvrir",
                   command=self.open_pdf, style="Toolbar.TButton", width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="💾 Enregistrer",
                   command=self.save_project, style="Toolbar.TButton", width=10).pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="📄 Exporter",
                   command=self.export_measurements, style="Toolbar.TButton", width=8).pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        # --- Navigation ---
        nav_frame = ttk.Frame(self.toolbar)
        nav_frame.pack(side=tk.LEFT, padx=5)
        self.prev_btn = ttk.Button(nav_frame, text="◀", width=3,
                                   command=self.prev_page, style="Toolbar.TButton")
        self.prev_btn.pack(side=tk.LEFT, padx=2)
        self.page_label = ttk.Label(nav_frame, text="Page: 0/0", width=10, anchor='center')
        self.page_label.pack(side=tk.LEFT, padx=5)
        self.next_btn = ttk.Button(nav_frame, text="▶", width=3,
                                   command=self.next_page, style="Toolbar.TButton")
        self.next_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        # --- Measurement Tools ---
        tools_frame = ttk.Frame(self.toolbar)
        tools_frame.pack(side=tk.LEFT, padx=5)
        self.distance_btn = ttk.Button(tools_frame, text="📏 Dist", width=7,
                                       command=lambda: self.set_mode("distance"), style="Toolbar.TButton")
        self.distance_btn.pack(side=tk.LEFT, padx=2)
        self.surface_btn = ttk.Button(tools_frame, text="■ Aire", width=7, # Changed text for clarity
                                      command=lambda: self.set_mode("surface"), style="Toolbar.TButton")
        self.surface_btn.pack(side=tk.LEFT, padx=2)
        self.perimeter_btn = ttk.Button(tools_frame, text="○ Périm", width=7, # Changed text
                                        command=lambda: self.set_mode("perimeter"), style="Toolbar.TButton")
        self.perimeter_btn.pack(side=tk.LEFT, padx=2)
        self.angle_btn = ttk.Button(tools_frame, text="📐 Angle", width=7,
                                    command=lambda: self.set_mode("angle"), style="Toolbar.TButton")
        self.angle_btn.pack(side=tk.LEFT, padx=2)
        self.calibrate_btn = ttk.Button(tools_frame, text="⚖ Calibrer", width=8,
                                        command=lambda: self.set_mode("calibration"), style="Toolbar.TButton")
        self.calibrate_btn.pack(side=tk.LEFT, padx=2)
        self.finalize_btn = ttk.Button(tools_frame, text="✓ Terminer", width=9,
                                       command=self.finalize_shape_if_possible, style="Toolbar.TButton")
        self.finalize_btn.pack(side=tk.LEFT, padx=2)


        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        # --- Zoom Controls ---
        zoom_frame = ttk.Frame(self.toolbar)
        zoom_frame.pack(side=tk.LEFT, padx=5)
        self.zoom_out_btn = ttk.Button(zoom_frame, text="🔍-", width=3,
                                       command=self.zoom_out, style="Toolbar.TButton")
        self.zoom_out_btn.pack(side=tk.LEFT, padx=2)
        self.zoom_level = ttk.Label(zoom_frame, text="100%", width=5, anchor='center')
        self.zoom_level.pack(side=tk.LEFT, padx=5)
        self.zoom_in_btn = ttk.Button(zoom_frame, text="🔍+", width=3,
                                      command=self.zoom_in, style="Toolbar.TButton")
        self.zoom_in_btn.pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=2)

        # --- Other Tools ---
        other_tools_frame = ttk.Frame(self.toolbar)
        other_tools_frame.pack(side=tk.LEFT, padx=5)
        self.extract_lines_btn = ttk.Button(other_tools_frame, text="〰 Lignes", width=8,
                                            command=self.extract_lines_from_pdf, style="Toolbar.TButton")
        self.extract_lines_btn.pack(side=tk.LEFT, padx=2)

        # --- AI Tools (Right Aligned) ---
        ai_frame = ttk.Frame(self.toolbar)
        ai_frame.pack(side=tk.RIGHT, padx=(10, 0)) # Padding Left
        self.analyze_btn = ttk.Button(ai_frame, text="🤖 Analyser", width=9,
                                     command=self.analyze_with_ai, style="Toolbar.TButton")
        self.analyze_btn.pack(side=tk.RIGHT, padx=2)

    def create_pdf_viewer(self):
        """Crée la zone de visualisation du PDF"""
        # Use a simple Frame as the direct child for PanedWindow
        self.pdf_frame_container = tk.Frame(self.panel_frame, bg="gray")
        self.panel_frame.add(self.pdf_frame_container, weight=5) # Give more weight to PDF view

        # Canvas with Scrollbars
        self.canvas = tk.Canvas(
            self.pdf_frame_container,
            bg="gray", # Background for area outside PDF
            highlightthickness=0 # Remove canvas border
        )

        self.h_scrollbar = ttk.Scrollbar(self.pdf_frame_container, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.v_scrollbar = ttk.Scrollbar(self.pdf_frame_container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=self.h_scrollbar.set, yscrollcommand=self.v_scrollbar.set)

        # Layout scrollbars and canvas using grid for better control
        self.pdf_frame_container.grid_rowconfigure(0, weight=1)
        self.pdf_frame_container.grid_columnconfigure(0, weight=1)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")


        # Gestionnaires d'événements pour le canvas
        self.canvas.bind("<Button-1>", self.on_canvas_click) # Left click
        self.canvas.bind("<Motion>", self.on_canvas_move)
        self.canvas.bind("<Double-Button-1>", self.on_canvas_double_click) # Double click
        self.canvas.bind("<MouseWheel>", self.on_mousewheel)  # For Windows/macOS Trackpad
        self.canvas.bind("<Button-4>", lambda e: self.on_mousewheel(e, 1))  # For Linux scroll up
        self.canvas.bind("<Button-5>", lambda e: self.on_mousewheel(e, -1)) # For Linux scroll down

        # Pan bindings are set in __init__


    def create_side_panel(self):
        """Crée le panneau latéral pour les mesures et informations"""
        # Use a simple Frame as the direct child for PanedWindow
        self.side_panel_container = tk.Frame(self.panel_frame)
        self.panel_frame.add(self.side_panel_container, weight=2) # Adjust weight as needed

        # Notebook pour organiser les différents panneaux
        self.notebook = ttk.Notebook(self.side_panel_container, style="TNotebook")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Onglet des mesures ---
        self.measures_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.measures_tab, text="Mesures")

        # Liste des mesures
        self.measures_frame = ttk.LabelFrame(self.measures_tab, text="Liste des mesures", style="TLabelframe")
        self.measures_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5,0)) # No bottom padding

        # Configure Treeview here
        self.measures_list = ttk.Treeview(
            self.measures_frame,
            # Columns defined later in update_measures_treeview_columns
            show="headings",
            style="Treeview"
        )
        # Add scrollbar to treeview
        measure_vsb = ttk.Scrollbar(self.measures_frame, orient="vertical", command=self.measures_list.yview)
        measure_hsb = ttk.Scrollbar(self.measures_frame, orient="horizontal", command=self.measures_list.xview)
        self.measures_list.configure(yscrollcommand=measure_vsb.set, xscrollcommand=measure_hsb.set)

        self.measures_list.grid(row=0, column=0, sticky='nsew')
        measure_vsb.grid(row=0, column=1, sticky='ns')
        measure_hsb.grid(row=1, column=0, sticky='ew')

        self.measures_frame.grid_rowconfigure(0, weight=1)
        self.measures_frame.grid_columnconfigure(0, weight=1)

        # --- AJOUT : Lier l'événement de sélection ---
        self.measures_list.bind('<<TreeviewSelect>>', self.on_measure_select)

        # Boutons d'actions pour les mesures
        self.measures_buttons_frame = ttk.Frame(self.measures_tab) # Use ttk Frame
        self.measures_buttons_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(self.measures_buttons_frame, text="Supprimer", width=10,
                   command=self.delete_selected_measure).pack(side=tk.LEFT, padx=2)
        ttk.Button(self.measures_buttons_frame, text="Tout Effacer", width=10,
                   command=self.clear_all_measures).pack(side=tk.LEFT, padx=2)

        # --- Onglet Catalogue de produits ---
        self.create_catalog_tab() # Create this tab

        # --- AJOUT: Onglet Résumé Produits ---
        self.create_totals_tab() # <--- NOUVEL APPEL

        # --- Onglet Configuration ---
        self.config_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.config_tab, text="Configuration")

        # Use a main frame inside the config tab for better padding control
        config_main_frame = ttk.Frame(self.config_tab)
        config_main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)


        # Frame for Document Info and Scale (moved to Config)
        doc_scale_frame = ttk.Frame(config_main_frame)
        doc_scale_frame.pack(fill=tk.X, pady=(0, 10))

        self.doc_info_frame = ttk.LabelFrame(doc_scale_frame, text="Infos Document", style="TLabelframe")
        self.doc_info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.doc_info = ttk.Label(self.doc_info_frame, text="Aucun document ouvert", wraplength=200, justify=tk.LEFT)
        self.doc_info.pack(padx=5, pady=5, fill=tk.X)

        self.scale_frame = ttk.LabelFrame(doc_scale_frame, text="Échelle", style="TLabelframe")
        self.scale_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))
        self.scale_info = ttk.Label(self.scale_frame, text="Non définie", wraplength=200, justify=tk.LEFT)
        self.scale_info.pack(padx=5, pady=5, fill=tk.X)
        # Add button to recalibrate here?
        ttk.Button(self.scale_frame, text="Calibrer...", width=10,
                   command=lambda: self.set_mode("calibration")).pack(pady=5)


        # Configuration des unités
        self.units_frame = ttk.LabelFrame(config_main_frame, text="Unités de Mesure", style="TLabelframe")
        self.units_frame.pack(fill=tk.X, pady=(0, 10))

        self.unit_var = tk.StringVar(value="m") # Default to meters
        units = [("Mètres (m)", "m"), ("Centimètres (cm)", "cm"), ("Millimètres (mm)", "mm"),
                 ("Pieds (ft)", "ft"), ("Pouces (in)", "in")]
        # Arrange radio buttons in columns
        col_max = 3
        for i, (text, val) in enumerate(units):
            rb = ttk.Radiobutton(self.units_frame, text=text,
                                variable=self.unit_var, value=val,
                                command=self.update_measurements_display_units) # Update display on change
            rb.grid(row=i // col_max, column=i % col_max, padx=5, pady=2, sticky=tk.W)


        # Configuration du snapping
        self.setup_snapping(config_main_frame) # Pass parent frame

        # Configuration des couleurs
        self.setup_colors(config_main_frame) # Pass parent frame

    # --- NOUVELLE MÉTHODE ---
    def create_totals_tab(self):
        """Crée l'onglet pour afficher les totaux par produit."""
        self.totals_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.totals_tab, text="Résumé Produits")

        totals_frame = ttk.LabelFrame(self.totals_tab, text="Totaux par Produit", style="TLabelframe")
        totals_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Treeview pour les totaux avec colonne coût ajoutée
        self.totals_list = ttk.Treeview(
            totals_frame,
            columns=("type", "total", "unit", "nb", "cost"),
            show="tree headings", # Afficher l'arbre ET les en-têtes
            style="Treeview"
        )

        # Configurer les colonnes
        self.totals_list.heading("#0", text="Produit / Catégorie", anchor='w')
        self.totals_list.heading("type", text="Type Mesure", anchor='w')
        self.totals_list.heading("total", text="Total", anchor='e')
        self.totals_list.heading("unit", text="Unité", anchor='w')
        self.totals_list.heading("nb", text="Nb.", anchor='center') # Nombre de mesures
        self.totals_list.heading("cost", text="Coût ($CAD)", anchor='e') # Nouvelle colonne pour le coût

        # Configurer les largeurs de colonne
        self.totals_list.column("#0", width=150, stretch=tk.YES, anchor='w')
        self.totals_list.column("type", width=80, stretch=tk.NO, anchor='w')
        self.totals_list.column("total", width=90, stretch=tk.NO, anchor='e')
        self.totals_list.column("unit", width=50, stretch=tk.NO, anchor='w')
        self.totals_list.column("nb", width=40, stretch=tk.NO, anchor='center')
        self.totals_list.column("cost", width=100, stretch=tk.NO, anchor='e') # Largeur pour le coût

        # Ajouter les barres de défilement
        totals_vsb = ttk.Scrollbar(totals_frame, orient="vertical", command=self.totals_list.yview)
        totals_hsb = ttk.Scrollbar(totals_frame, orient="horizontal", command=self.totals_list.xview)
        self.totals_list.configure(yscrollcommand=totals_vsb.set, xscrollcommand=totals_hsb.set)

        # Utiliser pack pour le layout (plus simple pour cet onglet)
        totals_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        totals_hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.totals_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Frame pour le total général
        total_cost_frame = ttk.Frame(self.totals_tab)
        total_cost_frame.pack(fill=tk.X, pady=(5, 0), padx=5)
        
        # Label pour afficher le coût total
        self.total_cost_label = ttk.Label(total_cost_frame, text="Coût Total: 0.00 $CAD", 
                                          font=("Arial", 10, "bold"), anchor='e')
        self.total_cost_label.pack(side=tk.RIGHT, padx=5)

        # Ajouter un bouton pour rafraîchir manuellement
        refresh_button = ttk.Button(self.totals_tab, text="🔄 Rafraîchir Totaux",
                                   command=self.update_product_totals_display)
        refresh_button.pack(pady=5)

    def update_measures_treeview_columns(self):
         """Sets or updates the columns for the measures Treeview."""
         self.measures_list["columns"] = ("type", "valeur", "produit", "page")
         self.measures_list.heading("#0", text="", anchor='w') # Hide the first default column
         self.measures_list.heading("type", text="Type", anchor='w')
         self.measures_list.heading("valeur", text="Valeur", anchor='w')
         self.measures_list.heading("produit", text="Produit", anchor='w')
         self.measures_list.heading("page", text="Page", anchor='center')

         # Adjust column widths
         self.measures_list.column("#0", width=0, stretch=tk.NO)
         self.measures_list.column("type", width=70, stretch=tk.NO, anchor='w')
         self.measures_list.column("valeur", width=120, anchor='w') # Give more space to value
         self.measures_list.column("produit", width=100, anchor='w')
         self.measures_list.column("page", width=40, stretch=tk.NO, anchor='center')


    def setup_snapping(self, parent_frame):
        """Configure les options de snapping dans l'interface"""
        self.snapping_frame = ttk.LabelFrame(parent_frame, text="Accrochage (Snapping)", style="TLabelframe")
        self.snapping_frame.pack(fill=tk.X, pady=(0, 10))

        # Internal frame for padding
        inner_snap_frame = ttk.Frame(self.snapping_frame)
        inner_snap_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Settings
        self.enable_snapping = tk.BooleanVar(value=True)
        cb_enable = ttk.Checkbutton(inner_snap_frame, text="Activer l'accrochage aux lignes",
                       variable=self.enable_snapping)
        cb_enable.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=(0,5))

        ttk.Label(inner_snap_frame, text="Seuil (pixels):").grid(row=1, column=0, sticky=tk.W, padx=(0,5))
        self.snap_threshold = tk.IntVar(value=10)
        # Use a spinbox for easier threshold setting
        sb_threshold = ttk.Spinbox(inner_snap_frame, from_=1, to=30, increment=1,
                                  textvariable=self.snap_threshold, width=5)
        sb_threshold.grid(row=1, column=1, sticky=tk.W)


        self.show_detected_lines = tk.BooleanVar(value=False) # Default off for performance
        cb_show_lines = ttk.Checkbutton(inner_snap_frame, text="Afficher lignes détectées (expérimental)",
                       variable=self.show_detected_lines,
                       command=self.toggle_line_display)
        cb_show_lines.grid(row=2, column=0, columnspan=2, sticky=tk.W, pady=(5,0))

        # Snap Types Frame
        snap_types_frame = ttk.LabelFrame(inner_snap_frame, text="Accrocher aux:", style="TLabelframe")
        snap_types_frame.grid(row=3, column=0, columnspan=2, sticky=tk.EW, pady=(5,0))

        self.snap_to_endpoints = tk.BooleanVar(value=True)
        ttk.Checkbutton(snap_types_frame, text="Extrémités",
                       variable=self.snap_to_endpoints).pack(side=tk.LEFT, padx=5, pady=2)

        self.snap_to_midpoints = tk.BooleanVar(value=True)
        ttk.Checkbutton(snap_types_frame, text="Milieux",
                       variable=self.snap_to_midpoints).pack(side=tk.LEFT, padx=5, pady=2)

        self.snap_to_intersections = tk.BooleanVar(value=True)
        ttk.Checkbutton(snap_types_frame, text="Intersections",
                       variable=self.snap_to_intersections).pack(side=tk.LEFT, padx=5, pady=2)


        # Ortho Mode Info
        ortho_frame = ttk.LabelFrame(parent_frame, text="Mode Ortho", style="TLabelframe")
        ortho_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(ortho_frame, text="Maintenir [Shift] pour contraindre horizontal/vertical.", padding=5).pack(anchor=tk.W)

    def setup_colors(self, parent_frame):
        """Configure les options de couleurs dans l'interface"""
        color_frame_container = ttk.LabelFrame(parent_frame, text="Couleurs de Mesure (Défauts)", style="TLabelframe")
        color_frame_container.pack(fill=tk.X)

        # Internal frame for padding
        self.color_frame = ttk.Frame(color_frame_container)
        self.color_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Color variables with defaults
        self.distance_color = tk.StringVar(value="#0000FF")  # Blue
        self.surface_color = tk.StringVar(value="#00FF00")  # Green (Outline)
        self.surface_fill_color = tk.StringVar(value="#3498DB") # Blue (Base fill, alpha added separately)
        self.angle_color = tk.StringVar(value=self.colors["angle"]) # Magenta from self.colors
        self.point_color = tk.StringVar(value="#FF0000")  # Red

        # Color entries and labels using grid
        labels = ["Distance:", "Surface (contour):", "Surface (remplissage):", "Angle:", "Points:"]
        vars = [self.distance_color, self.surface_color, self.surface_fill_color, self.angle_color, self.point_color]

        for i, (label_text, var) in enumerate(zip(labels, vars)):
            lbl = ttk.Label(self.color_frame, text=label_text)
            lbl.grid(row=i, column=0, padx=5, pady=3, sticky=tk.W)
            entry = ttk.Entry(self.color_frame, textvariable=var, width=10)
            entry.grid(row=i, column=1, padx=5, pady=3, sticky=tk.W)
            # Add color picker button
            btn = ttk.Button(self.color_frame, text="...", width=3,
                             command=lambda v=var: self.pick_color(v))
            btn.grid(row=i, column=2, padx=(0,5), pady=3, sticky=tk.W)


        # Transparency
        transparency_label = ttk.Label(self.color_frame, text="Transparence Remplissage Surface (%):")
        transparency_label.grid(row=len(labels), column=0, columnspan=3, padx=5, pady=(10, 2), sticky=tk.W)

        self.fill_transparency = tk.IntVar(value=50) # 0=Opaque, 100=Invisible
        transparency_scale = ttk.Scale(self.color_frame, from_=0, to=100, # 0 to 100%
                                     orient=tk.HORIZONTAL, variable=self.fill_transparency,
                                     command=self.update_transparency) # Update on change
        transparency_scale.grid(row=len(labels)+1, column=0, columnspan=3, padx=5, pady=2, sticky=tk.EW)


    def pick_color(self, color_variable):
        """Ouvre un sélecteur de couleur et met à jour la variable."""
        # Get current color, handle potential errors if format is bad
        try:
            initial_color = color_variable.get()
            if not (isinstance(initial_color, str) and initial_color.startswith('#') and len(initial_color) == 7):
                 initial_color = "#FFFFFF" # Default to white if invalid
        except:
            initial_color = "#FFFFFF"

        try:
            # Use the imported colorchooser module directly
            color_code = colorchooser.askcolor(title="Choisir une couleur", initialcolor=initial_color, parent=self.root)
            if color_code and color_code[1]: # Check if a color was chosen (returns tuple: (rgb, hex))
                color_variable.set(color_code[1]) # Set the hex value
                self.redraw_measurements() # Redraw immediately
        except tk.TclError:
             messagebox.showwarning("Erreur Couleur", "Le sélecteur de couleur n'a pas pu être initialisé.", parent=self.root)


    def update_transparency(self, *args):
        """Met à jour la prévisualisation ou redessine lors du changement de transparence."""
        # Redraw measurements to reflect new transparency via stipple pattern
        self.redraw_measurements()


    def get_fill_color_with_alpha(self):
         """Calcule la couleur RGBA pour le remplissage (Non utilisé car stipple est préféré)."""
         base_color = self.surface_fill_color.get()
         # Ensure base_color is valid hex #RRGGBB
         if not (isinstance(base_color, str) and base_color.startswith('#') and len(base_color) == 7):
              base_color = "#3498DB" # Fallback

         # Alpha calculation: 0% transparency = FF alpha, 100% = 00 alpha
         transparency_percent = self.fill_transparency.get()
         alpha_value = int(255 * (1 - transparency_percent / 100.0))
         alpha_hex = hex(alpha_value)[2:].zfill(2) # Convert to 2-char hex

         return f"{base_color}{alpha_hex}"

    def get_stipple_pattern(self):
        """Retourne un motif stipple basé sur la transparence pour Tkinter."""
        transparency = self.fill_transparency.get()
        if transparency <= 15: # Almost opaque
            return "" # No stipple
        elif transparency <= 35:
            return "gray75"
        elif transparency <= 65:
            return "gray50"
        elif transparency <= 85:
            return "gray25"
        else: # Almost transparent
            return "gray12"


    def apply_color_settings(self):
        """Applique les changements de couleurs (Redraws measurements)."""
        # This might be redundant if redraw happens on color pick / transparency change
        self.redraw_measurements()
        self.status_bar.config(text="Couleurs mises à jour")


    def create_catalog_tab(self):
        """Crée l'onglet de gestion du catalogue de produits"""
        self.catalog_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.catalog_tab, text="Catalogue Produits")

        # Utiliser PanedWindow avec une taille minimale plus grande pour les deux volets
        catalog_paned = ttk.PanedWindow(self.catalog_tab, orient=tk.VERTICAL) # Séparation Verticale
        catalog_paned.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Haut : Treeview ---
        tree_frame = ttk.Frame(catalog_paned)
        catalog_paned.add(tree_frame, weight=3) # Moins de poids pour laisser plus de place aux détails

        # Treeview pour les catégories et produits
        self.catalog_tree = ttk.Treeview(tree_frame, show="headings", style="Treeview")

        # Barres de défilement pour Treeview
        cat_vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=self.catalog_tree.yview)
        cat_hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.catalog_tree.xview) # Barre horizontale
        self.catalog_tree.configure(yscrollcommand=cat_vsb.set, xscrollcommand=cat_hsb.set) # Lier la barre horizontale

        # --- MODIFICATION : Remplacement de grid par pack ---
        # Placer les barres de défilement D'ABORD
        cat_vsb.pack(side=tk.RIGHT, fill=tk.Y)
        cat_hsb.pack(side=tk.BOTTOM, fill=tk.X) # Barre horizontale en bas
        # Placer le Treeview ENSUITE pour qu'il remplisse l'espace restant
        self.catalog_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # --- FIN DE LA MODIFICATION ---

        # Liaison d'événement pour le changement de sélection
        self.catalog_tree.bind('<<TreeviewSelect>>', self.on_catalog_item_select)

        # --- Bas : Formulaire Détails/Édition ---
        # Créer un frame avec une hauteur minimale fixe pour assurer la visibilité
        details_frame_container = ttk.Frame(catalog_paned, height=250)  # Définir hauteur minimale
        details_frame_container.pack_propagate(False)  # Empêcher le redimensionnement plus petit que spécifié
        catalog_paned.add(details_frame_container, weight=2)  # Plus de poids aux détails

        self.details_frame = ttk.LabelFrame(details_frame_container, text="Détails / Édition", style="TLabelframe")
        self.details_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(5,0))

        # Champs du formulaire
        form_pad_x = (10, 5)
        form_pad_y = 3

        # Catégorie
        ttk.Label(self.details_frame, text="Catégorie:").grid(row=0, column=0, sticky=tk.W, padx=form_pad_x, pady=form_pad_y)
        self.category_entry = ttk.Combobox(self.details_frame, textvariable=self.current_category, width=30)
        self.category_entry.grid(row=0, column=1, columnspan=2, sticky=tk.EW, padx=form_pad_x, pady=form_pad_y)
        # Remplir les valeurs plus tard

        # Produit
        ttk.Label(self.details_frame, text="Produit:").grid(row=1, column=0, sticky=tk.W, padx=form_pad_x, pady=form_pad_y)
        self.product_entry = ttk.Entry(self.details_frame, textvariable=self.current_product, width=30)
        self.product_entry.grid(row=1, column=1, columnspan=2, sticky=tk.EW, padx=form_pad_x, pady=form_pad_y)

        # Dimensions
        ttk.Label(self.details_frame, text="Dimensions:").grid(row=2, column=0, sticky=tk.W, padx=form_pad_x, pady=form_pad_y)
        self.dimensions_entry = ttk.Entry(self.details_frame, width=30)
        self.dimensions_entry.grid(row=2, column=1, columnspan=2, sticky=tk.EW, padx=form_pad_x, pady=form_pad_y)

        # Prix
        ttk.Label(self.details_frame, text="Prix:").grid(row=3, column=0, sticky=tk.W, padx=form_pad_x, pady=form_pad_y)
        self.price_entry = ttk.Entry(self.details_frame, width=15) # Largeur plus courte pour le prix
        self.price_entry.grid(row=3, column=1, sticky=tk.W, padx=form_pad_x, pady=form_pad_y)
        
        # NOUVELLE SECTION: Unité de prix
        self.price_unit_var = tk.StringVar(value="metric")
        unit_frame = ttk.Frame(self.details_frame)
        unit_frame.grid(row=3, column=2, sticky=tk.W, pady=form_pad_y, padx=(0,10))
        ttk.Radiobutton(unit_frame, text="$/m²", variable=self.price_unit_var, value="metric").pack(side=tk.LEFT)
        ttk.Radiobutton(unit_frame, text="$/ft²", variable=self.price_unit_var, value="imperial").pack(side=tk.LEFT)

        # --- Sélection de Couleur ---
        ttk.Label(self.details_frame, text="Couleur:").grid(row=4, column=0, sticky=tk.W, padx=form_pad_x, pady=form_pad_y)
        self.product_color_entry = ttk.Entry(self.details_frame, textvariable=self.product_color_var, width=10)
        self.product_color_entry.grid(row=4, column=1, sticky=tk.W, padx=form_pad_x, pady=form_pad_y)
        # Bouton pour ouvrir le sélecteur de couleur
        ttk.Button(self.details_frame, text="...", width=3,
                  command=lambda: self.pick_color(self.product_color_var)
                  ).grid(row=4, column=2, sticky=tk.W, padx=(0,10), pady=form_pad_y)

        # Frame des boutons d'action (ajuster l'index de ligne)
        button_frame = ttk.Frame(self.details_frame)
        button_frame.grid(row=5, column=0, columnspan=3, pady=(10, 5)) # Changé ligne de 4 à 5

        ttk.Button(button_frame, text="➕ Nouveau", width=10, command=self.new_product_form).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="💾 Sauvegarder", width=12, command=self.save_product_changes).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="❌ Supprimer", width=10, command=self.remove_catalog_item).pack(side=tk.LEFT, padx=5)

        # Bouton Ajouter Catégorie (séparé des boutons d'item)
        category_button_frame = ttk.Frame(details_frame_container)
        category_button_frame.pack(fill=tk.X, padx=5, pady=(0,5), side=tk.BOTTOM)
        ttk.Button(category_button_frame, text="+ Ajouter Catégorie", command=self.add_category_dialog).pack(side=tk.LEFT, padx=5)
        ttk.Button(category_button_frame, text="📁 Importer Catalogue...", command=self.import_catalog).pack(side=tk.LEFT, padx=5)
        ttk.Button(category_button_frame, text="📁 Exporter Catalogue...", command=self.export_catalog).pack(side=tk.LEFT, padx=5)

        # Charger les données initiales
        self.populate_catalog_tree() # Assurez-vous que les colonnes sont définies correctement ici
        self.update_category_dropdown() # Remplir le combobox


    def populate_catalog_tree(self):
        """Remplit le treeview avec les données du catalogue"""
        # Stocker la sélection et les états ouverts
        selected_iid = self.catalog_tree.selection()
        open_categories = set()
        # Obtenir les enfants avant de les supprimer
        current_children = self.catalog_tree.get_children()
        for item_id in current_children:
             # Vérifier si l'item existe toujours (pour éviter les erreurs TclError rares)
             if self.catalog_tree.exists(item_id):
                  if self.catalog_tree.item(item_id, 'open'):
                       open_categories.add(item_id) # Stocker l'IID (nom de catégorie)

        # Effacer les éléments existants de l'arbre
        for item in current_children: # Utiliser la liste stockée
            try:
                self.catalog_tree.delete(item)
            except tk.TclError:
                 # Gérer le cas où l'item aurait pu être supprimé entre-temps (rare)
                 print(f"[DEBUG] Avertissement: Impossible de supprimer l'élément Treeview {item}, peut-être déjà supprimé.")

        # --- IMPORTANT: Correction de la structure du TreeView ---
        # Il faut utiliser show="tree headings" pour avoir à la fois l'arborescence et les en-têtes de colonnes
        self.catalog_tree.configure(show="tree headings")

        # --- Configurer les Colonnes ---
        # Définir les colonnes qui seront affichées
        self.catalog_tree["columns"] = ("prix", "dimensions", "couleur")

        # Définir les en-têtes pour chaque colonne
        self.catalog_tree.heading("#0", text="Catégorie / Produit", anchor='w') # La colonne de l'arbre elle-même
        self.catalog_tree.heading("prix", text="Prix ($CAD)", anchor='e') # Alignement à droite pour prix
        self.catalog_tree.heading("dimensions", text="Dimensions", anchor='w')
        self.catalog_tree.heading("couleur", text="Couleur", anchor='w')

        # Définir les propriétés de chaque colonne (largeur, alignement, comportement d'étirement)
        self.catalog_tree.column("#0", width=180, minwidth=150, anchor='w', stretch=tk.YES) # La colonne principale peut s'étirer
        self.catalog_tree.column("prix", width=70, minwidth=70, anchor='e', stretch=tk.NO)   # Largeur fixe, alignée à droite
        self.catalog_tree.column("dimensions", width=80, minwidth=80, anchor='w', stretch=tk.NO) # Largeur fixe, alignée à gauche
        self.catalog_tree.column("couleur", width=70, minwidth=70, anchor='w', stretch=tk.NO) # Largeur fixe, alignée à gauche

        # Obtenir les catégories de l'objet catalogue
        categories = self.product_catalog.get_categories()
        categories.sort() # Trier les catégories par ordre alphabétique pour l'affichage

        # Itérer à travers les catégories et les insérer comme nœuds parents
        for category in categories:
            # Utiliser le nom de la catégorie comme Item ID (iid) pour référence facile
            cat_id = category
            # Vérifier si cette catégorie était précédemment ouverte
            is_open = cat_id in open_categories
            # Insérer la ligne de catégorie dans le treeview
            # Utiliser les tags au besoin plus tard
            self.catalog_tree.insert("", "end", iid=cat_id, text=category, open=is_open) # Restaurer l'état ouvert

            # Obtenir les produits pour la catégorie actuelle
            products = self.product_catalog.get_products(category)
            products.sort() # Trier les produits par ordre alphabétique dans la catégorie

            # Itérer à travers les produits et les insérer comme nœuds enfants sous la catégorie
            for product in products:
                # Obtenir les attributs du produit (prix, dimensions, couleur)
                attributes = self.product_catalog.get_product_attributes(category, product)
                price_str = ""
                if attributes and 'prix' in attributes:
                    try:
                       price_val = attributes['prix']
                       # Formater le prix correctement, gérer None
                       price_str = f"{float(price_val):.2f}" if price_val is not None else ""
                    except (ValueError, TypeError):
                       # Fallback si le prix n'est pas un nombre valide
                       price_str = str(attributes['prix'])

                dims_str = attributes.get("dimensions", "") if attributes else ""
                # Obtenir la couleur, s'assurer que c'est une chaîne vide si None ou manquante
                color_str = attributes.get("color", "") if attributes and attributes.get("color") else ""

                # Créer un Item ID unique pour le produit (optionnel, mais bonne pratique)
                # Combine le nom de catégorie et le nom de produit
                prod_iid = f"{cat_id}::{product}"

                # Insérer la ligne du produit comme enfant du nœud de catégorie
                # Le tuple 'values' doit correspondre à l'ordre défini dans self.catalog_tree["columns"]
                try:
                    self.catalog_tree.insert(cat_id, "end", iid=prod_iid, text=product,
                                            values=(price_str, dims_str, color_str)) # Passer les données pour les colonnes
                except tk.TclError as e:
                     # Gérer les erreurs potentielles comme un iid dupliqué si la logique le permet
                     print(f"[DEBUG] Erreur TclError lors de l'insertion produit {prod_iid}: {e}")


        # Restaurer la sélection si un élément était sélectionné avant la mise à jour
        # Vérifier que selected_iid est un tuple/liste non vide
        if selected_iid and isinstance(selected_iid, (tuple, list)) and len(selected_iid) > 0:
            first_selected_iid = selected_iid[0]
            # Vérifier si l'élément existe toujours dans l'arbre mis à jour
            if self.catalog_tree.exists(first_selected_iid):
                try:
                    self.catalog_tree.selection_set(first_selected_iid) # Rétablir la sélection
                    self.catalog_tree.focus(first_selected_iid) # Définir le focus clavier
                    self.catalog_tree.see(first_selected_iid) # Faire défiler l'élément pour qu'il soit visible
                except tk.TclError as e:
                     # Cela peut arriver si l'élément a été supprimé entre l'obtention de la sélection et sa restauration
                     print(f"[DEBUG] Avertissement: Impossible de restaurer la sélection Treeview pour {first_selected_iid}: {e}")

    def update_category_dropdown(self):
         """Met à jour la liste déroulante des catégories."""
         current_selection = self.current_category.get() # Store current value
         categories = self.product_catalog.get_categories()
         categories.sort()
         self.category_entry['values'] = categories
         # Try to restore selection if it still exists
         if current_selection in categories:
              self.current_category.set(current_selection)
         elif categories:
              # Optionally set a default or leave blank
              # self.current_category.set(categories[0])
              pass
         else:
              self.current_category.set("")


    def on_catalog_item_select(self, event=None):
         """Charge les détails de l'élément sélectionné dans le formulaire."""
         selected_iid = self.catalog_tree.selection()
         if not selected_iid:
              # Don't reset form if selection is lost temporarily during update
              # self.reset_product_form() # Clear form if selection is removed
              return

         selected_iid = selected_iid[0] # Get the actual item ID

         if not self.catalog_tree.exists(selected_iid):
             print(f"Avertissement: IID sélectionné '{selected_iid}' n'existe plus dans Treeview.")
             return # Item might have been deleted

         item = self.catalog_tree.item(selected_iid)
         parent_iid = self.catalog_tree.parent(selected_iid)

         if not parent_iid: # It's a category (IID is category name)
             self.current_category.set(item['text'])
             self.current_product.set("") # Clear product field
             self.dimensions_entry.delete(0, tk.END)
             self.price_entry.delete(0, tk.END)
             self.product_color_var.set("") # Clear color field
             self.price_unit_var.set("metric") # Reset price unit to default
         else: # It's a product
             category_name = self.catalog_tree.item(parent_iid)['text']
             product_name = item['text']
             attributes = self.product_catalog.get_product_attributes(category_name, product_name)

             self.current_category.set(category_name)
             self.current_product.set(product_name)
             self.dimensions_entry.delete(0, tk.END)
             self.price_entry.delete(0, tk.END)
             self.product_color_var.set("") # Clear color field first
             self.price_unit_var.set("metric") # Reset to default before loading

             if attributes:
                  self.dimensions_entry.insert(0, attributes.get('dimensions', ''))
                  price_val = attributes.get('prix')
                  # Handle None price correctly in display
                  price_display = str(price_val) if price_val is not None else ""
                  self.price_entry.insert(0, price_display)
                  # --- Set price unit ---
                  price_unit = attributes.get('price_unit', 'metric')
                  self.price_unit_var.set(price_unit)
                  # --- Load color ---
                  product_color = attributes.get('color', '') # Get color, default to empty string if None
                  self.product_color_var.set(product_color)


    def add_category_dialog(self):
        """Affiche une boîte de dialogue pour ajouter une catégorie"""
        category_name = simpledialog.askstring("Nouvelle catégorie", "Nom de la nouvelle catégorie:", parent=self.root)
        if category_name:
            category_name = category_name.strip() # Remove leading/trailing spaces
            if not category_name:
                 messagebox.showwarning("Nom Invalide", "Le nom de la catégorie ne peut pas être vide.", parent=self.root)
                 return

            if self.product_catalog.add_category(category_name):
                self.populate_catalog_tree()
                self.update_category_dropdown()
                # --- MODIFICATION: Message de statut au lieu de popup ---
                self.status_bar.config(text=f"Catégorie '{category_name}' ajoutée (non sauvegardée).")
            else:
                messagebox.showwarning("Avertissement", f"La catégorie '{category_name}' existe déjà.", parent=self.root)

    def edit_catalog_item(self):
        """Édite l'élément sélectionné (handled by on_catalog_item_select now)."""
        # This function might be redundant now as selection automatically fills the form.
        self.on_catalog_item_select()


    def remove_catalog_item(self):
        """Supprime l'élément sélectionné (catégorie ou produit)."""
        selected_iid = self.catalog_tree.selection()
        if not selected_iid:
            messagebox.showwarning("Sélection requise", "Veuillez sélectionner une catégorie ou un produit à supprimer.", parent=self.root)
            return

        selected_iid = selected_iid[0]
        if not self.catalog_tree.exists(selected_iid): return # Selection might be invalid

        item = self.catalog_tree.item(selected_iid)
        item_text = item['text']
        parent_iid = self.catalog_tree.parent(selected_iid)

        if not parent_iid:  # C'est une catégorie
            if messagebox.askyesno("Confirmation", f"Supprimer la catégorie '{item_text}' et TOUS ses produits ? Cette action est irréversible.", parent=self.root):
                if self.product_catalog.remove_category(item_text):
                    self.populate_catalog_tree()
                    self.update_category_dropdown()
                    self.reset_product_form()
                    self.status_bar.config(text=f"Catégorie '{item_text}' supprimée (non sauvegardée).")
        else:  # C'est un produit
            category_name = self.catalog_tree.item(parent_iid)['text']
            product_name = item_text
            if messagebox.askyesno("Confirmation", f"Supprimer le produit '{product_name}' de la catégorie '{category_name}' ?", parent=self.root):
                if self.product_catalog.remove_product(category_name, product_name):
                    self.populate_catalog_tree()
                    self.reset_product_form() # Clear form after deletion
                    self.status_bar.config(text=f"Produit '{product_name}' supprimé (non sauvegardé).")


    def save_product_changes(self):
        """Sauvegarde les modifications du formulaire (ajoute ou met à jour)."""
        category = self.current_category.get().strip()
        product = self.current_product.get().strip()

        if not category:
            messagebox.showwarning("Champ requis", "Le nom de la catégorie est obligatoire.", parent=self.root)
            self.category_entry.focus_set()
            return
        if not product:
            messagebox.showwarning("Champ requis", "Le nom du produit est obligatoire.", parent=self.root)
            self.product_entry.focus_set()
            return

        try:
            # Allow empty price, treat as None
            price_str = self.price_entry.get().strip().replace(',', '.')
            price = float(price_str) if price_str else None
        except ValueError:
            messagebox.showwarning("Format invalide", "Le prix doit être un nombre valide (ex: 120.50) ou laissé vide.", parent=self.root)
            self.price_entry.focus_set()
            return

        dimensions = self.dimensions_entry.get().strip()
        
        # Get price unit
        price_unit = self.price_unit_var.get()

        # --- NEW: Get and validate color ---
        color_hex = self.product_color_var.get().strip()
        if color_hex and not (color_hex.startswith('#') and len(color_hex) == 7):
            messagebox.showwarning("Format Invalide", "La couleur doit être au format hexadécimal #RRGGBB (ex: #FF0000 pour rouge) ou laissée vide.", parent=self.root)
            self.product_color_entry.focus_set()
            return
        elif not color_hex:
            color_hex = None # Store None if field is empty
        # --- END NEW ---

        attributes = {
            "dimensions": dimensions,
            "prix": price, # Store None if empty
            "color": color_hex, # Add color to attributes dictionary
            "price_unit": price_unit # Store price unit (metric/imperial)
        }

        # Add category if it doesn't exist (e.g., typed in combobox)
        category_created = False
        if category not in self.product_catalog.get_categories():
            self.product_catalog.add_category(category)
            self.update_category_dropdown() # Update dropdown immediately
            category_created = True

        # Check if product exists to determine add vs update
        existing_products = self.product_catalog.get_products(category)
        success = False
        is_update = False
        if product in existing_products:
            # Update existing product
            if self.product_catalog.update_product(category, product, attributes):
                 success = True
                 is_update = True
            else: # Should not happen if checks pass, but good to have
                 messagebox.showerror("Erreur", f"Erreur lors de la mise à jour du produit '{product}'.", parent=self.root)
        else:
            # Add new product
            if self.product_catalog.add_product(category, product, attributes):
                 success = True
                 is_update = False
            else:
                 messagebox.showerror("Erreur", f"Erreur lors de l'ajout du produit '{product}'.", parent=self.root)


        if success:
             # --- MODIFICATION: Message de statut au lieu de popup ---
             action_text = "mis à jour" if is_update else "ajouté"
             cat_text = f" (Catégorie '{category}' créée)" if category_created else ""
             self.status_bar.config(text=f"Produit '{product}' {action_text}{cat_text} (non sauvegardé).")
             self.populate_catalog_tree()
             # Try to re-select the item just saved/edited
             prod_iid = f"{category}::{product}"
             if self.catalog_tree.exists(prod_iid):
                  self.catalog_tree.selection_set(prod_iid)
                  self.catalog_tree.focus(prod_iid)
                  self.catalog_tree.see(prod_iid)


    def new_product_form(self):
        """Prépare le formulaire pour un nouvel ajout (garde la catégorie si possible)."""
        # Keep the currently selected category if one is selected in the tree or combobox
        current_cat_in_form = self.current_category.get()

        # Clear other fields
        self.current_product.set("")
        self.dimensions_entry.delete(0, tk.END)
        self.price_entry.delete(0, tk.END)
        self.product_color_var.set("") # Clear color field

        # Restore category if it was set
        self.current_category.set(current_cat_in_form)

        # Set focus to product name for quick entry
        self.product_entry.focus_set()
        # De-select tree item to avoid confusion
        if self.catalog_tree.selection():
             self.catalog_tree.selection_set("")


    def reset_product_form(self):
        """Réinitialise complètement le formulaire."""
        self.current_category.set("")
        self.current_product.set("")
        self.dimensions_entry.delete(0, tk.END)
        self.price_entry.delete(0, tk.END)
        self.product_color_var.set("") # Clear color field
        if self.catalog_tree.selection():
             self.catalog_tree.selection_set("") # Deselect tree item


    def import_catalog(self):
        """Importe un catalogue depuis un fichier JSON."""
        file_path = filedialog.askopenfilename(
            title="Importer Catalogue Produits",
            filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")],
            parent=self.root
        )
        if not file_path:
            return

        if messagebox.askyesno("Confirmation d'importation",
                               "Importer ce fichier écrasera le catalogue actuel et le sauvegardera. Continuer?",
                               parent=self.root):
            if self.product_catalog.load_from_json(file_path):
                 # --- MODIFICATION: is_dirty est géré dans load_from_json ---
                 self.populate_catalog_tree()
                 self.update_category_dropdown()
                 self.reset_product_form()
                 messagebox.showinfo("Succès", "Catalogue importé et sauvegardé avec succès.", parent=self.root)
            else:
                 messagebox.showerror("Erreur d'importation", f"Impossible de charger le catalogue depuis {os.path.basename(file_path)}.", parent=self.root)


    def export_catalog(self):
        """Exporte le catalogue actuel vers un fichier JSON."""
        # --- MODIFICATION: Sauvegarder avant d'exporter? Non, l'export reflète l'état actuel en mémoire. ---
        # if self.product_catalog.is_dirty:
        #    if messagebox.askyesno("Exporter Catalogue", "Le catalogue a des modifications non enregistrées.\nVoulez-vous les enregistrer avant d'exporter?", parent=self.root):
        #         if not self.product_catalog.save_catalog_to_appdata():
        #              messagebox.showerror("Erreur Sauvegarde", "Impossible d'enregistrer les modifications du catalogue.", parent=self.root)
        #              return # Abort export if save failed and user wanted to save

        file_path = filedialog.asksaveasfilename(
            title="Exporter Catalogue Produits",
            defaultextension=".json",
            filetypes=[("Fichiers JSON", "*.json"), ("Tous les fichiers", "*.*")],
            initialfile="catalogue_produits.json",
            parent=self.root
        )
        if not file_path:
            return

        if self.product_catalog.save_to_json(file_path):
             messagebox.showinfo("Succès", f"Catalogue exporté avec succès vers {os.path.basename(file_path)}.", parent=self.root)
             self.status_bar.config(text=f"Catalogue exporté vers {os.path.basename(file_path)}.")
        else:
             messagebox.showerror("Erreur d'exportation", "Une erreur est survenue lors de l'exportation du catalogue.", parent=self.root)


    def create_ai_panel(self):
        """Crée le panneau pour l'assistant IA"""
        # Use a simple Frame as the direct child for PanedWindow
        self.ai_panel_container = tk.Frame(self.panel_frame)
        self.panel_frame.add(self.ai_panel_container, weight=3) # Adjust weight

        # Main Frame for AI content
        self.ai_panel = ttk.Frame(self.ai_panel_container)
        self.ai_panel.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # --- Profile Selection ---
        profile_frame = ttk.LabelFrame(self.ai_panel, text="Expert IA", style="TLabelframe")
        profile_frame.pack(fill=tk.X, pady=(0, 5))

        inner_profile_frame = ttk.Frame(profile_frame) # Inner frame for padding
        inner_profile_frame.pack(fill=tk.X, padx=5, pady=5)


        ttk.Label(inner_profile_frame, text="Profil:").pack(side=tk.LEFT, padx=(0, 5))

        self.profile_var = tk.StringVar()
        # Get available profiles AFTER AI assistant is initialized
        profiles_dict = self.ai_assistant.profile_manager.get_all_profiles()
        # Create (name, id) list for mapping, sorted by name
        self.profile_name_id_map = sorted([(data["name"], pid) for pid, data in profiles_dict.items()])
        profile_display_names = [name for name, pid in self.profile_name_id_map]


        # Set initial value based on current AI profile
        current_ai_profile = self.ai_assistant.get_current_profile()
        if current_ai_profile:
             self.profile_var.set(current_ai_profile.get("name", "Erreur"))
        else: # Fallback if AI init failed badly
             self.profile_var.set("N/A")


        self.profile_dropdown = ttk.Combobox(
            inner_profile_frame,
            textvariable=self.profile_var,
            values=profile_display_names,
            state="readonly", # Prevent typing new values
            width=25 # Adjust width
        )
        if not profile_display_names: # Handle case with no profiles loaded
            self.profile_dropdown['values'] = ["Aucun profil"]
            self.profile_var.set("Aucun profil")
            self.profile_dropdown.config(state="disabled")

        self.profile_dropdown.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.profile_dropdown.bind("<<ComboboxSelected>>", self.on_profile_changed)

        # Manage Profiles Button
        ttk.Button(inner_profile_frame, text="Gérer...", width=8,
                 command=self.manage_profiles).pack(side=tk.LEFT, padx=(5, 0))


        # --- Chat Area ---
        chat_container_frame = ttk.Frame(self.ai_panel)
        chat_container_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.chat_display = scrolledtext.ScrolledText(
            chat_container_frame,
            wrap=tk.WORD,
            bg="white",
            fg=self.colors["text_dark"],
            font=("Arial", 10),
            relief=tk.SUNKEN,
            bd=1,
            padx=5,
            pady=5
        )
        self.chat_display.pack(fill=tk.BOTH, expand=True)
        self.chat_display.config(state=tk.DISABLED) # Read-only

        # Configure tags for message styling
        self.chat_display.tag_configure("user", background=self.colors["user_msg"], lmargin1=10, lmargin2=10, spacing1=2, spacing3=2, relief='raised', borderwidth=1)
        self.chat_display.tag_configure("assistant", background=self.colors["ai_msg"], lmargin1=10, lmargin2=10, spacing1=2, spacing3=2, relief='raised', borderwidth=1)
        self.chat_display.tag_configure("system", foreground="#555555", font=("Arial", 9, "italic"), lmargin1=5, lmargin2=5, spacing1=1, spacing3=5)
        self.chat_display.tag_configure("error", foreground=self.colors["warning"], font=("Arial", 10, "bold"), lmargin1=10, lmargin2=10, spacing1=2, spacing3=2)
        self.chat_display.tag_configure("timestamp", foreground="#777777", font=("Arial", 8))
        self.chat_display.tag_configure("bold", font=("Arial", 10, "bold"))


        # --- Input Area ---
        self.input_frame = ttk.Frame(self.ai_panel)
        self.input_frame.pack(fill=tk.X)

        self.user_input = ttk.Entry(
            self.input_frame,
            font=("Arial", 10)
        )
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=2) # Internal padding
        self.user_input.bind("<Return>", self.send_message_to_ai)

        send_button = ttk.Button(
            self.input_frame,
            text="Envoyer", width=8,
            command=self.send_message_to_ai,
            style="Action.TButton" # Use action style
        )
        send_button.pack(side=tk.RIGHT)

        # Add initial welcome message
        self.display_ai_message("system", f"Assistant IA initialisé. Profil actif: {self.profile_var.get()}.")
        self.display_ai_message("assistant", "Bonjour! Comment puis-je vous aider avec votre projet de métré aujourd'hui?")

    def on_profile_changed(self, event=None):
        """Gère le changement de profil expert."""
        selected_name = self.profile_var.get()

        # Find the ID corresponding to the selected name
        selected_id = None
        for name, pid in self.profile_name_id_map:
             if name == selected_name:
                  selected_id = pid
                  break

        if selected_id:
            success = self.ai_assistant.set_current_profile(selected_id)
            if success:
                # Reset conversation history on profile change? Optional.
                # self.ai_assistant.conversation_history = []

                # Clear chat display and show new welcome message - maybe not fully clear?
                # self.chat_display.config(state=tk.NORMAL)
                # self.chat_display.delete('1.0', tk.END)
                # self.chat_display.config(state=tk.DISABLED)

                profile = self.ai_assistant.get_current_profile()
                self.display_ai_message("system", f"Profil expert changé en: {profile['name']}")
                # self.display_ai_message("assistant", "Bonjour! Comment puis-je vous aider avec ce nouveau profil?") # Avoid repetitive greetings

                self.status_bar.config(text=f"Profil expert changé: {profile['name']}")
            else:
                 messagebox.showerror("Erreur", f"Impossible de changer le profil vers '{selected_name}'.", parent=self.root)
                 # Revert dropdown to the actual current profile
                 current_profile = self.ai_assistant.get_current_profile()
                 self.profile_var.set(current_profile.get("name", "Erreur"))


    def manage_profiles(self):
        """Ouvre la fenêtre de gestion des profils experts"""
        profile_window = tk.Toplevel(self.root)
        profile_window.title("Gestion des Profils Experts IA")
        profile_window.geometry("700x550")
        profile_window.configure(bg=self.colors["bg_light"])
        profile_window.transient(self.root)
        profile_window.grab_set()


        # --- Layout ---
        top_frame = ttk.Frame(profile_window)
        top_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        bottom_frame = ttk.Frame(profile_window)
        bottom_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # Paned window for list and editor
        paned_window = ttk.PanedWindow(top_frame, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True)

        # --- Left Pane: List ---
        list_frame = ttk.LabelFrame(paned_window, text="Profils Existants", style="TLabelframe")
        paned_window.add(list_frame, weight=1)

        profile_listbox = tk.Listbox(list_frame, width=25, font=('Arial', 10))
        profile_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        profile_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=profile_listbox.yview)
        profile_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        profile_listbox.config(yscrollcommand=profile_scrollbar.set)

        # --- Right Pane: Editor ---
        edit_frame = ttk.LabelFrame(paned_window, text="Éditeur de Profil", style="TLabelframe")
        paned_window.add(edit_frame, weight=3)

        # Editor fields
        field_frame = ttk.Frame(edit_frame)
        field_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(field_frame, text="ID (unique, sans espace):").grid(row=0, column=0, sticky=tk.W, pady=2)
        id_entry_var = tk.StringVar()
        id_entry = ttk.Entry(field_frame, textvariable=id_entry_var, width=40)
        id_entry.grid(row=0, column=1, sticky=tk.EW, pady=2, padx=(5,0))

        ttk.Label(field_frame, text="Nom Affiché:").grid(row=1, column=0, sticky=tk.W, pady=2)
        name_entry_var = tk.StringVar()
        name_entry = ttk.Entry(field_frame, textvariable=name_entry_var, width=40)
        name_entry.grid(row=1, column=1, sticky=tk.EW, pady=2, padx=(5,0))

        field_frame.grid_columnconfigure(1, weight=1) # Allow entry to expand

        ttk.Label(edit_frame, text="Contenu du Profil (Instructions pour l'IA):").pack(anchor="w", padx=5, pady=(10, 2))

        content_text = scrolledtext.ScrolledText(edit_frame, wrap=tk.WORD, width=50, height=15, font=('Courier New', 9))
        content_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0,5))


        # --- Populate Listbox ---
        profiles = self.ai_assistant.profile_manager.get_all_profiles()
        profile_name_map = {} # Map displayed name back to ID
        def populate_list():
            profile_listbox.delete(0, tk.END)
            profile_name_map.clear()
            # Sort by name for display
            sorted_profiles = sorted(profiles.values(), key=lambda p: p["name"])
            for profile in sorted_profiles:
                 display_name = f"{profile['name']} ({profile['id']})"
                 profile_listbox.insert(tk.END, display_name)
                 profile_name_map[display_name] = profile["id"]
        populate_list()

        # --- Listbox Selection Logic ---
        def load_profile_to_editor(event=None):
            selection_indices = profile_listbox.curselection()
            if selection_indices:
                selected_display_name = profile_listbox.get(selection_indices[0])
                selected_id = profile_name_map.get(selected_display_name)

                if selected_id:
                    profile = self.ai_assistant.profile_manager.get_profile(selected_id)
                    if profile:
                        id_entry_var.set(profile["id"])
                        name_entry_var.set(profile["name"])
                        content_text.delete('1.0', tk.END)
                        content_text.insert('1.0', profile["content"])
                        # Prevent editing ID of default profile
                        if selected_id == "entrepreneur_general":
                             id_entry.config(state='disabled')
                        else:
                             id_entry.config(state='normal')
                    else:
                        clear_editor() # Clear if profile not found somehow
            else:
                clear_editor() # Clear if no selection

        profile_listbox.bind('<<ListboxSelect>>', load_profile_to_editor)


        # --- Editor Functions ---
        def clear_editor():
            id_entry_var.set("")
            name_entry_var.set("")
            content_text.delete('1.0', tk.END)
            profile_listbox.selection_clear(0, tk.END) # Deselect list item
            id_entry.config(state='normal') # Enable ID field for new entry
            id_entry.focus_set() # Focus on ID for new entry


        def save_profile():
            profile_id = id_entry_var.get().strip().replace(" ", "_") # Force no spaces in ID
            profile_name = name_entry_var.get().strip()
            profile_content = content_text.get('1.0', tk.END).strip()

            if not profile_id:
                messagebox.showerror("Erreur", "L'ID du profil est requis et ne doit pas contenir d'espaces.", parent=profile_window)
                return
            if not profile_name:
                messagebox.showerror("Erreur", "Le nom affiché du profil est requis.", parent=profile_window)
                return
            if not profile_content:
                messagebox.showerror("Erreur", "Le contenu du profil (instructions IA) est requis.", parent=profile_window)
                return

            # Check if ID exists (for adding vs updating)
            # We need the original ID if the ID field was disabled (editing default)
            original_id = profile_id
            selection_indices = profile_listbox.curselection()
            if selection_indices:
                 selected_display_name = profile_listbox.get(selection_indices[0])
                 original_id = profile_name_map.get(selected_display_name, profile_id)
            else: # If nothing selected, assume it's a new profile
                original_id = None


            # Check if renaming an existing profile (other than default)
            if original_id and original_id != profile_id and original_id != "entrepreneur_general":
                 if profile_id in self.ai_assistant.profile_manager.get_all_profiles():
                      messagebox.showerror("Erreur", f"Le nouvel ID '{profile_id}' existe déjà. Choisissez un autre ID.", parent=profile_window)
                      return
                 # If renaming, delete the old one first (file and in memory)
                 if original_id in self.ai_assistant.profile_manager.profiles:
                      del self.ai_assistant.profile_manager.profiles[original_id]
                 app_data_path = get_app_data_path()
                 old_file_path = os.path.join(app_data_path, 'profiles', f"{original_id}.txt")
                 try:
                      if os.path.exists(old_file_path): os.remove(old_file_path)
                 except Exception as e:
                      print(f"Avertissement: Erreur suppression ancien fichier profil {original_id}: {e}")
                 print(f"Profil renommé de '{original_id}' vers '{profile_id}'")


            is_updating = profile_id in self.ai_assistant.profile_manager.get_all_profiles() and original_id == profile_id

            # Add or update in the manager
            self.ai_assistant.profile_manager.add_profile(profile_id, profile_name, profile_content)

            # Save to file in AppData
            if self.ai_assistant.profile_manager.save_profile_to_file(profile_id):
                messagebox.showinfo("Succès", f"Profil '{profile_name}' {'mis à jour' if is_updating else 'enregistré'} avec succès.", parent=profile_window)

                # Refresh the list and main window dropdown
                profiles = self.ai_assistant.profile_manager.get_all_profiles() # Get updated dict
                populate_list()
                self.update_profile_selector() # Update main window dropdown

                # Reselect the saved item
                found = False
                for i in range(profile_listbox.size()):
                    if profile_name_map.get(profile_listbox.get(i)) == profile_id:
                         profile_listbox.selection_set(i)
                         profile_listbox.see(i)
                         load_profile_to_editor() # Reload to editor
                         found = True
                         break
                if not found: clear_editor() # Clear if item not found after save (shouldn't happen)

            else:
                messagebox.showerror("Erreur", f"Profil enregistré en mémoire, mais erreur lors de la sauvegarde du fichier pour '{profile_id}'. Vérifiez les permissions.", parent=profile_window)


        def delete_profile():
             selection_indices = profile_listbox.curselection()
             if not selection_indices:
                  messagebox.showwarning("Sélection requise", "Veuillez sélectionner un profil à supprimer.", parent=profile_window)
                  return

             selected_display_name = profile_listbox.get(selection_indices[0])
             selected_id = profile_name_map.get(selected_display_name)

             if selected_id == "entrepreneur_general": # Prevent deleting the default core profile easily
                  messagebox.showwarning("Suppression Interdite", "Le profil par défaut 'Entrepreneur Général' ne peut pas être supprimé.", parent=profile_window)
                  return

             if selected_id:
                  # Check if this profile is currently active in the main app
                  current_main_profile_id = self.ai_assistant.current_profile_id
                  if selected_id == current_main_profile_id:
                       messagebox.showerror("Erreur Suppression", f"Impossible de supprimer le profil '{selected_display_name}' car il est actuellement actif.\nChangez de profil dans la fenêtre principale avant de le supprimer.", parent=profile_window)
                       return

                  if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer le profil '{selected_display_name}' ? Cette action est irréversible.", parent=profile_window):
                       # Remove from manager
                       if selected_id in self.ai_assistant.profile_manager.profiles:
                            del self.ai_assistant.profile_manager.profiles[selected_id]

                       # Attempt to delete file
                       app_data_path = get_app_data_path()
                       file_path = os.path.join(app_data_path, 'profiles',
                       f"{selected_id}.txt")
                       deleted_file = False
                       try:
                            if os.path.exists(file_path):
                                 os.remove(file_path)
                                 deleted_file = True
                                 print(f"Fichier profil supprimé: {file_path}")
                       except Exception as e:
                            messagebox.showwarning("Erreur Fichier", f"Profil supprimé de la mémoire, mais erreur lors de la suppression du fichier : {e}", parent=profile_window)


                       messagebox.showinfo("Succès", f"Profil '{selected_display_name}' supprimé.", parent=profile_window)
                       profiles = self.ai_assistant.profile_manager.get_all_profiles() # Update internal list
                       populate_list()
                       self.update_profile_selector() # Update main window dropdown
                       clear_editor()


        # --- Bottom Buttons ---
        ttk.Button(bottom_frame, text="➕ Nouveau", command=clear_editor).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="💾 Enregistrer", command=save_profile).pack(side=tk.LEFT, padx=5)
        ttk.Button(bottom_frame, text="❌ Supprimer Sélection", command=delete_profile).pack(side=tk.LEFT, padx=5)
        ttk.Separator(bottom_frame, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        ttk.Button(bottom_frame, text="Fermer", command=profile_window.destroy).pack(side=tk.RIGHT, padx=5)


        # Load first profile initially if list is not empty
        if profile_listbox.size() > 0:
             profile_listbox.selection_set(0)
             load_profile_to_editor()
        else:
             clear_editor()


    def update_profile_selector(self):
        """Met à jour le combobox de sélection de profil dans le panneau IA."""
        print("[DEBUG] Mise à jour du sélecteur de profil...")
        profiles_dict = self.ai_assistant.profile_manager.get_all_profiles()
        self.profile_name_id_map = sorted([(data["name"], pid) for pid, data in profiles_dict.items()])
        profile_display_names = [name for name, pid in self.profile_name_id_map]

        current_profile = self.ai_assistant.get_current_profile()
        current_name = current_profile.get("name", "") if current_profile else ""
        print(f"[DEBUG] Profil actuel: {current_name} ({self.ai_assistant.current_profile_id})")
        print(f"[DEBUG] Profils disponibles pour dropdown: {profile_display_names}")

        if not profile_display_names:
             print("[DEBUG] Aucun profil disponible pour dropdown.")
             self.profile_dropdown['values'] = ["Aucun profil"]
             self.profile_var.set("Aucun profil")
             self.profile_dropdown.config(state="disabled")
        else:
             self.profile_dropdown['values'] = profile_display_names
             self.profile_dropdown.config(state="readonly")
             # Try to set the current profile, fallback to first if not found
             if current_name in profile_display_names:
                  print(f"[DEBUG] Sélection du profil actuel dans dropdown: {current_name}")
                  self.profile_var.set(current_name)
             elif profile_display_names:
                  print(f"[DEBUG] Profil actuel non trouvé, sélection du premier: {profile_display_names[0]}")
                  self.profile_var.set(profile_display_names[0])
                  # Update AI assistant's current profile ID to match the fallback selection
                  first_profile_id = self.profile_name_id_map[0][1]
                  self.ai_assistant.set_current_profile(first_profile_id)
                  print(f"[DEBUG] ID profil AI mis à jour vers: {first_profile_id}")
             else:
                  # This case should technically not happen if profile_display_names is not empty
                  print("[DEBUG] Erreur logique: liste de noms de profils non vide mais impossible de sélectionner.")
                  self.profile_var.set("")

    def display_ai_message(self, sender, message):
        """Ajoute un message formaté au chat de l'assistant IA."""
        if not message: return # Avoid adding empty messages

        self.chat_display.config(state=tk.NORMAL)

        timestamp = ""
        sender_tag = "system" # Default tag
        sender_display = sender # Default display name

        if sender.lower() == "vous":
             sender_tag = "user"
             timestamp = f"[{time.strftime('%H:%M:%S')}] "
        elif sender.lower() == "assistant":
             sender_tag = "assistant"
             timestamp = f"[{time.strftime('%H:%M:%S')}] "
        elif sender.lower() == "erreur":
             sender_tag = "error"
             sender_display = "Erreur" # Display "Erreur" as sender

        # Insert timestamp if applicable
        if timestamp:
             self.chat_display.insert(tk.END, timestamp, "timestamp")

        # Insert sender (bold for user/assistant)
        sender_font_tag = "bold" if sender_tag in ["user", "assistant", "error"] else ""
        self.chat_display.insert(tk.END, f"{sender_display}: ", (sender_tag, sender_font_tag))

        # Insert message content
        self.chat_display.insert(tk.END, f"{message}\n\n", sender_tag)

        # Scroll to the end
        self.chat_display.see(tk.END)
        self.chat_display.config(state=tk.DISABLED)


    def send_message_to_ai(self, event=None):
        """Envoie un message à l'assistant IA et affiche la réponse."""
        user_message = self.user_input.get().strip()
        if not user_message:
            return

        # Display user message
        self.display_ai_message("Vous", user_message)

        # Clear input field
        self.user_input.delete(0, tk.END)

        # Show thinking status
        self.status_bar.config(text="L'assistant IA réfléchit...")
        self.root.update_idletasks() # Process UI updates

        # Prepare context for AI
        pdf_info_context = None
        if self.pdf_document:
            pdf_info_context = {
                'filename': os.path.basename(self.pdf_path) if self.pdf_path else 'Inconnu',
                'page_count': self.pdf_document.page_count,
                'current_page': self.current_page,
                'scale': self.absolute_scale # Send the absolute scale
            }

        # Get response from AI
        ai_response = self.ai_assistant.get_response(user_message, self.measures, pdf_info_context)

        # Display AI response (or error message)
        # Check if the response indicates an error from the AI class itself
        if "Désolé, une erreur est survenue" in ai_response or "client IA n'est pas initialisé" in ai_response or "Impossible de charger un profil expert" in ai_response:
             self.display_ai_message("Erreur", ai_response)
        else:
             self.display_ai_message("Assistant", ai_response)


        # Reset status bar
        self.status_bar.config(text="Prêt")

    def analyze_with_ai(self):
        """Lance l'analyse du document PDF actuel avec l'IA."""
        if not self.pdf_path or not os.path.exists(self.pdf_path):
            messagebox.showinfo("Information", "Veuillez d'abord ouvrir un document PDF valide.", parent=self.root)
            return
        if not self.ai_assistant.anthropic:
             messagebox.showerror("Erreur IA", "Le client IA n'est pas initialisé. Vérifiez la clé API.", parent=self.root)
             return

        # Update status bar
        self.status_bar.config(text="Analyse du document par l'IA...")
        self.root.update_idletasks()

        # Get analysis
        analysis = self.ai_assistant.analyze_pdf(self.pdf_path)

        # Display analysis
        self.display_ai_message("system", f"--- Analyse IA du document ({os.path.basename(self.pdf_path)}) ---")
        if "Erreur" in analysis:
            self.display_ai_message("Erreur", analysis)
        else:
            self.display_ai_message("Assistant", analysis)

        # Get measurement suggestions
        if self.pdf_document:
             pdf_info_context = {
                 'filename': os.path.basename(self.pdf_path),
                 'page_count': self.pdf_document.page_count,
                 'current_page': self.current_page,
                 'scale': self.absolute_scale,
                 # Could add document type if analysis provided one
             }
             suggestions = self.ai_assistant.get_measurement_suggestions(pdf_info_context)
             self.display_ai_message("system", "--- Suggestions de Mesures ---")
             if "Erreur" in suggestions:
                 self.display_ai_message("Erreur", suggestions)
             else:
                 self.display_ai_message("Assistant", suggestions)


        # Reset status bar
        self.status_bar.config(text="Analyse IA terminée.")

    # --- PDF Handling ---

    def open_pdf(self, file_path=None):
        """Ouvre un fichier PDF."""
        if not file_path:
            file_path = filedialog.askopenfilename(
                title="Ouvrir un fichier PDF",
                filetypes=[("Fichiers PDF", "*.pdf"), ("Tous les fichiers", "*.*")],
                parent=self.root
            )

        if not file_path:
            return

        # --- MODIFICATION: Sauvegarde Catalogue Avant Ouverture? Non, perte potentielle. ---
        # Sauvegarder le catalogue en cours si modifié avant d'ouvrir un nouveau PDF/Projet?
        # Cela pourrait être ajouté ici ou dans load_project si nécessaire, avec confirmation.
        # self.product_catalog.save_catalog_if_dirty()

        try:
            # Close existing document if open
            if self.pdf_document:
                self.pdf_document.close()
                self.canvas.delete("all") # Clear canvas
                self.measures = [] # Clear measures
                self.lines_by_page = {} # Clear detected lines
                self.absolute_scale = None
                self.update_measures_list() # Clear treeview
                self.scale_info.config(text="Non définie")
                self.selected_measure_id = None # Reset selection
                self.update_product_totals_display() # Reset totals display


            # Open the new document
            self.pdf_document = fitz.open(file_path)
            self.pdf_path = file_path # Store the path
            self.current_page = 0
            self.zoom_factor = 1.0 # Reset zoom
            self.zoom_level.config(text="100%")

            # Perform initial setup for the new document
            self.status_bar.config(text="Extraction des lignes...")
            self.root.update_idletasks()
            self.extract_lines_from_pdf() # Extract lines for snapping

            self.display_page() # Display the first page
            self.update_document_info() # Update side panel info
            self.status_bar.config(text=f"Document ouvert: {os.path.basename(file_path)}")
            self.root.title(f"TakeOff AI - {os.path.basename(file_path)}") # Update window title

            # Add to recent projects (handle based on whether it's a .tak file later)
            if not file_path.lower().endswith(".tak"): # Only add raw PDFs opened directly
                self.add_recent_project(file_path) # Treat raw PDF opening as a 'project' for recent list

            # Inform user and AI
            self.display_ai_message("system", f"Document PDF ouvert: {os.path.basename(file_path)}")
            self.display_ai_message("assistant", f"Document '{os.path.basename(file_path)}' ({self.pdf_document.page_count} pages) chargé. Vous pouvez calibrer l'échelle, commencer les mesures ou demander une analyse IA.")

        except Exception as e:
            messagebox.showerror("Erreur d'Ouverture", f"Impossible d'ouvrir le fichier PDF '{os.path.basename(file_path)}':\n{str(e)}", parent=self.root)
            self.pdf_document = None
            self.pdf_path = None
            self.measures = []
            self.lines_by_page = {}
            self.absolute_scale = None
            self.selected_measure_id = None
            self.canvas.delete("all")
            self.update_measures_list()
            self.update_document_info()
            self.scale_info.config(text="Non définie")
            self.update_product_totals_display() # Reset totals display
            self.status_bar.config(text="Erreur d'ouverture. Prêt.")
            self.root.title("TakeOff AI")

    def extract_lines_from_pdf(self):
        """Extrait les lignes et segments du document PDF actuel pour snapping."""
        if not self.pdf_document:
            return

        self.status_bar.config(text="Extraction des lignes (peut prendre du temps)...")
        self.root.update_idletasks()

        self.lines_by_page = {}
        total_lines_extracted = 0

        # Define a minimum length to filter out very small segments (noise)
        # Use squared length in PDF points (1/72 inch) for efficiency
        min_length_pts = 3 # Ignore lines shorter than ~1mm
        min_line_length_sq = min_length_pts**2

        start_time = time.time()

        for page_index in range(self.pdf_document.page_count):
            page = self.pdf_document[page_index]
            page_lines = []
            try:
                # Use get_drawings() which extracts vector paths
                paths = page.get_drawings()
                for path in paths:
                    # Items represent points in lines, curves, rects
                    # path: {'color': (r,g,b), 'fill': (r,g,b), 'rect': Rect(...), 'items': [('l', Point(x,y)), ('c', ...)], 'type': 'f'/'s'/'fs'}
                    items = path.get("items")
                    if not items: continue

                    # Process simple lines ('l') and rectangle borders ('re')
                    # type 's' is stroke, 'f' is fill, 'fs' is fill then stroke
                    if path.get("type") in ['s','fs']: # Only consider stroked paths for lines
                        current_pos = None
                        for i in range(len(items)):
                            op = items[i][0] # Operation: 'm' (moveto), 'l' (lineto), 'c' (curveto), 're' (rect)
                            pt = items[i][1] # Point object

                            if op == 'm': # Move To
                                current_pos = (pt.x, pt.y)
                            elif op == 'l': # Line To
                                if current_pos:
                                     p1 = current_pos
                                     p2 = (pt.x, pt.y)
                                     # Check length
                                     dx = p2[0] - p1[0]
                                     dy = p2[1] - p1[1]
                                     if (dx*dx + dy*dy) >= min_line_length_sq:
                                         page_lines.append(((p1[0], p1[1]), (p2[0], p2[1])))
                                         total_lines_extracted += 1
                                current_pos = (pt.x, pt.y) # Update current position
                            elif op == 're': # Rectangle
                                rect = items[i][1] # Rect object
                                if rect and rect.is_valid and not rect.is_empty:
                                    p1 = (rect.x0, rect.y0); p2 = (rect.x1, rect.y0)
                                    p3 = (rect.x1, rect.y1); p4 = (rect.x0, rect.y1)
                                    segments = [(p1, p2), (p2, p3), (p3, p4), (p4, p1)]
                                    for seg_start, seg_end in segments:
                                         dx = seg_end[0] - seg_start[0]
                                         dy = seg_end[1] - seg_start[1]
                                         if (dx*dx + dy*dy) >= min_line_length_sq:
                                              page_lines.append((seg_start, seg_end))
                                              total_lines_extracted += 1
                                # Where does 're' leave current_pos? Assume bottom-left? Let's reset.
                                current_pos = None # Reset position after rect? Or is it implicit? Assume reset.
                            # Ignore curves ('c') for simple line snapping for now
                            # 'h' (close path) - draw line back to start? Depends on path start. Ignore for now.


            except Exception as e:
                print(f"Avertissement: Erreur lors de l'extraction des dessins de la page {page_index + 1}: {str(e)}")

            self.lines_by_page[page_index] = page_lines
            # Provide progress update if many pages?
            if self.pdf_document.page_count > 10 and (page_index + 1) % 5 == 0:
                 elapsed = time.time() - start_time
                 print(f"Extraction lignes... Page {page_index+1}/{self.pdf_document.page_count} ({elapsed:.1f}s)")
                 self.status_bar.config(text=f"Extraction lignes... {page_index+1}/{self.pdf_document.page_count}")
                 self.root.update_idletasks()


        end_time = time.time()
        print(f"Extraction lignes terminée en {end_time - start_time:.2f} secondes.")
        self.status_bar.config(text=f"Extraction lignes terminée: {total_lines_extracted} segments détectés.")

        # Optionally redraw detected lines if visible
        if self.show_detected_lines.get():
            self.display_detected_lines()


    def display_page(self):
        """Affiche la page courante du PDF sur le canvas."""
        if not self.pdf_document:
            self.canvas.delete("all")
            self.page_label.config(text="Page: 0/0")
            return

        # Ensure current page is valid
        if not (0 <= self.current_page < self.pdf_document.page_count):
             print(f"Erreur: Numéro de page invalide ({self.current_page}). Réinitialisation à 0.")
             self.current_page = 0
             if self.pdf_document.page_count == 0: return # No pages

        self.canvas.delete("all") # Clear previous drawings

        try:
            page = self.pdf_document[self.current_page]

            # Calculate the transformation matrix for zoom level
            # Use a higher resolution factor for rendering than just the zoom factor
            # This makes text sharper when zoomed in.
            display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5 # Render at least 1.5x, more if zoomed
            mat = fitz.Matrix(display_resolution_factor, display_resolution_factor)

            # Render the page to a Pixmap
            pix = page.get_pixmap(matrix=mat, alpha=False) # alpha=False for opaque RGB

            # Convert Pixmap to a PIL Image
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            # Convert PIL Image to PhotoImage for Tkinter
            # Store reference to avoid garbage collection
            self._current_page_photoimage = ImageTk.PhotoImage(image=img)

            # Display the image on the canvas
            # The image coordinates are scaled by display_resolution_factor relative to PDF points
            self.canvas.create_image(0, 0, image=self._current_page_photoimage, anchor=tk.NW, tags="page_image")

            # Configure the scroll region to match the image size
            self.canvas.config(scrollregion=(0, 0, pix.width, pix.height))

            # Update page navigation label
            page_text = f"Page: {self.current_page + 1}/{self.pdf_document.page_count}"
            self.page_label.config(text=page_text)

            # Redraw measurements for the current page AFTER displaying the page image
            self.redraw_measurements()

            # Redraw detected lines if the option is enabled
            if self.show_detected_lines.get():
                 self.display_detected_lines()

        except Exception as e:
            messagebox.showerror("Erreur d'Affichage", f"Impossible d'afficher la page {self.current_page + 1}:\n{str(e)}", parent=self.root)
            self.canvas.delete("all") # Clear canvas on error

    def redraw_measurements(self):
        """Redessine toutes les mesures visibles sur la page courante, en surlignant la mesure sélectionnée."""
        if not self.pdf_document:
            return

        self.canvas.delete("measurement") # Clear only measurement items

        display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
        highlight_color = "yellow" # Couleur de surbrillance
        highlight_width_increase = 2 # Augmentation de l'épaisseur pour la surbrillance

        for measure in self.measures:
            if measure.get("page") == self.current_page:
                measure_id = measure.get('id')
                measure_type = measure.get("type")
                pdf_points = measure.get("points", [])
                display_text = measure.get("display_text", "")

                # Est-ce la mesure sélectionnée ?
                is_selected = (measure_id is not None and measure_id == self.selected_measure_id)

                scaled_points = [(p[0] * display_resolution_factor, p[1] * display_resolution_factor) for p in pdf_points]

                if not scaled_points: continue

                # --- NEW: Determine Color ---
                # 1. Get measure-specific color, if defined and valid
                measure_specific_color = measure.get('color')
                is_valid_specific_color = (isinstance(measure_specific_color, str) and
                                           measure_specific_color.startswith('#') and
                                           len(measure_specific_color) == 7)

                # 2. Get default global colors
                base_distance_color = self.distance_color.get()
                base_surface_outline = self.surface_color.get()
                base_surface_fill = self.surface_fill_color.get()
                base_perimeter_color = self.colors.get("perimeter", "#FFA500")
                base_angle_color = self.angle_color.get()
                base_point_color = self.point_color.get()
                base_width = 2

                # 3. Decide drawing colors based on type and specific color availability
                draw_color = base_distance_color # Default fallback for outlines

                # MODIFICATION: Utiliser la couleur spécifique pour le remplissage plutôt que pour le contour
                # Initialiser la couleur de remplissage par défaut
                fill_color = base_surface_fill # Couleur de remplissage par défaut

                # Si une couleur spécifique est définie pour la mesure, l'utiliser pour le remplissage
                if is_valid_specific_color:
                    fill_color = measure_specific_color

                # Pour les contours, utiliser les couleurs par défaut
                if measure_type == "distance":
                    draw_color = base_distance_color
                elif measure_type == "surface":
                    draw_color = base_surface_outline
                elif measure_type == "perimeter":
                    draw_color = base_perimeter_color
                elif measure_type == "angle":
                    draw_color = base_angle_color

                point_color = base_point_color # Use global point color

                # --- Apply Highlight Override ---
                current_draw_color = draw_color
                current_fill_color = fill_color
                current_point_color = point_color
                current_width = base_width

                if is_selected:
                    current_draw_color = highlight_color
                    # Ne pas changer la couleur de remplissage en cas de surbrillance
                    # pour garder la couleur du produit visible
                    # current_fill_color = highlight_color
                    current_point_color = highlight_color
                    current_width = base_width + highlight_width_increase

                # Determine text color (use original draw_color before highlight applied, or highlight color)
                current_text_color = highlight_color if is_selected else draw_color

                m_tag = f"measure_{measure_id}"
                all_tags = ("measurement", m_tag)

                # --- Draw based on type (using determined colors) ---
                if measure_type == "distance" and len(scaled_points) == 2:
                    # Pour les distances, on continue à utiliser current_draw_color pour la ligne
                    x1, y1 = scaled_points[0]; x2, y2 = scaled_points[1]
                    self.canvas.create_oval(x1-3, y1-3, x1+3, y1+3, fill=current_point_color, outline=current_point_color, tags=all_tags)
                    self.canvas.create_oval(x2-3, y2-3, x2+3, y2+3, fill=current_point_color, outline=current_point_color, tags=all_tags)
                    self.canvas.create_line(x1, y1, x2, y2, fill=current_draw_color, width=current_width, tags=all_tags)
                    text_x = (x1 + x2) / 2; text_y = (y1 + y2) / 2
                    self.draw_measure_text(text_x, text_y, display_text, current_text_color, all_tags, highlight=is_selected)

                elif measure_type == "surface" and len(scaled_points) >= 3:
                    stipple = self.get_stipple_pattern()
                    flat_points = [coord for point in scaled_points for coord in point]
                    try:
                        # Utiliser current_fill_color pour le remplissage (avec la couleur du produit si définie)
                        poly_id = self.canvas.create_polygon(flat_points,
                                                fill=current_fill_color,    # Couleur du produit ou couleur par défaut
                                                outline=current_draw_color, # Couleur de contour standard
                                                width=current_width,
                                                stipple=stipple,
                                                tags=all_tags)
                    except tk.TclError as e:
                        print(f"Erreur TclError lors du dessin du polygone: {e} - Points: {flat_points}")
                        continue

                    for x, y in scaled_points:
                        self.canvas.create_oval(x-3, y-3, x+3, y+3, fill=current_point_color, outline=current_point_color, tags=all_tags)

                    if scaled_points:
                        cx = sum(p[0] for p in scaled_points) / len(scaled_points)
                        cy = sum(p[1] for p in scaled_points) / len(scaled_points)
                        self.draw_measure_text(cx, cy, display_text, current_text_color, all_tags, highlight=is_selected)

                elif measure_type == "perimeter" and len(scaled_points) >= 2:
                    flat_perimeter_points = [coord for point in scaled_points for coord in point]
                    if len(scaled_points) > 2:
                        flat_perimeter_points.extend(scaled_points[0])

                    try:
                        self.canvas.create_line(flat_perimeter_points, fill=current_draw_color, width=current_width, tags=all_tags)
                    except tk.TclError as e:
                        print(f"Erreur TclError lors du dessin de la polyligne (périmètre): {e} - Points: {flat_perimeter_points}")
                        continue

                    for x, y in scaled_points:
                        self.canvas.create_oval(x-3, y-3, x+3, y+3, fill=current_point_color, outline=current_point_color, tags=all_tags)

                    if scaled_points:
                        cx = sum(p[0] for p in scaled_points) / len(scaled_points)
                        cy = sum(p[1] for p in scaled_points) / len(scaled_points)
                        self.draw_measure_text(cx, cy, display_text, current_text_color, all_tags, highlight=is_selected)

                elif measure_type == "angle" and len(scaled_points) == 3:
                    # Les angles utilisent toujours leur couleur spécifique
                    p1, p2, p3 = scaled_points
                    try:
                        v1_x, v1_y = p1[0] - p2[0], p1[1] - p2[1]
                        v2_x, v2_y = p3[0] - p2[0], p3[1] - p2[1]
                        start_angle_rad = math.atan2(-v1_y, v1_x)
                        end_angle_rad = math.atan2(-v2_y, v2_x)
                        start_deg = math.degrees(start_angle_rad)

                        raw_extent = math.degrees(end_angle_rad - start_angle_rad)
                        while raw_extent > 180: raw_extent -= 360
                        while raw_extent <= -180: raw_extent += 360
                        extent_deg = raw_extent

                        for x, y in scaled_points:
                            self.canvas.create_oval(x-3, y-3, x+3, y+3, fill=current_point_color, outline=current_point_color, tags=all_tags)
                        self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill=current_draw_color, width=current_width, tags=all_tags)
                        self.canvas.create_line(p2[0], p2[1], p3[0], p3[1], fill=current_draw_color, width=current_width, tags=all_tags)
                        arc_radius = 20
                        arc_bbox = (p2[0] - arc_radius, p2[1] - arc_radius, p2[0] + arc_radius, p2[1] + arc_radius)
                        arc_width = current_width if is_selected else 1
                        self.canvas.create_arc(arc_bbox, start=start_deg, extent=extent_deg,
                                            style=tk.ARC, outline=current_draw_color, width=arc_width, tags=all_tags)
                        mid_angle_rad = start_angle_rad + math.radians(extent_deg / 2.0)
                        text_offset = arc_radius + 10
                        text_x = p2[0] + text_offset * math.cos(mid_angle_rad)
                        text_y = p2[1] - text_offset * math.sin(mid_angle_rad)
                        self.draw_measure_text(text_x, text_y, display_text, current_text_color, all_tags, highlight=is_selected)
                    except Exception as e:
                        print(f"Erreur dessin angle: {e}")
                        for x, y in scaled_points:
                             self.canvas.create_oval(x-3, y-3, x+3, y+3, fill=current_point_color, outline=current_point_color, tags=all_tags)


    def draw_measure_text(self, x, y, text, color, tags, highlight=False): # Ajout du paramètre highlight
         """Helper function to draw measurement text with a background."""
         try:
             # Utiliser une couleur de fond différente si surligné
             bg_fill_color = "yellow" if highlight else "white"
             text_font = ("Arial", 9, "bold")

             # Estimate text bounding box to create background rectangle
             temp_text_id = self.canvas.create_text(x, y, text=text, fill=color,
                                                    font=text_font, anchor=tk.CENTER, tags=("temp_text",))
             bbox = self.canvas.bbox(temp_text_id)
             if bbox:
                  pad = 2
                  # Appliquer la couleur de fond calculée
                  bg_id = self.canvas.create_rectangle(bbox[0]-pad, bbox[1]-pad, bbox[2]+pad, bbox[3]+pad,
                                                 fill=bg_fill_color, outline="", tags=tags + ("text_bg",))
                  # Raise background slightly above image but below text? Maybe not needed.
                  # self.canvas.tag_raise(bg_id, "page_image")
             else:
                 bg_id = None # No background if bbox failed
             self.canvas.delete(temp_text_id) # Delete temporary text item

             # Dessiner le texte réel par-dessus
             text_id = self.canvas.create_text(x, y, text=text, fill=color,
                                         font=text_font, anchor=tk.CENTER, tags=tags + ("text_fg",))
             # Raise text above background if created
             # if bg_id:
             #    self.canvas.tag_raise(text_id, bg_id)

         except tk.TclError as e:
              print(f"Erreur TclError lors du dessin du texte de mesure: {e} - Texte: {text}")
         except Exception as e:
              print(f"Erreur inattendue lors du dessin du texte de mesure: {e} - Texte: {text}")


    # --- Snapping & Ortho ---

    def find_closest_line_point(self, x_canvas, y_canvas, threshold):
        """Trouve le point d'accrochage le plus proche (extrémité, milieu, ligne).
           Prend les coordonnées CANVAS, retourne les coordonnées CANVAS du point d'accrochage."""
        if not self.pdf_document or self.current_page not in self.lines_by_page:
            return None

        closest_snap = None
        min_dist_sq = threshold**2 # Use squared distance for efficiency

        # Use the same resolution factor as display_page
        display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
        if display_resolution_factor == 0: return None # Avoid division by zero

        # Get lines for the current page (lines are stored in PDF points)
        lines_on_page = self.lines_by_page.get(self.current_page, [])

        for line in lines_on_page:
            # Original PDF coordinates
            (x0_pdf, y0_pdf), (x1_pdf, y1_pdf) = line

            # Convert PDF coordinates to current display coordinates
            x0_disp, y0_disp = x0_pdf * display_resolution_factor, y0_pdf * display_resolution_factor
            x1_disp, y1_disp = x1_pdf * display_resolution_factor, y1_pdf * display_resolution_factor

            # --- Check Endpoints ---
            if self.snap_to_endpoints.get():
                dist_sq_e1 = (x_canvas - x0_disp)**2 + (y_canvas - y0_disp)**2
                if dist_sq_e1 < min_dist_sq:
                    min_dist_sq = dist_sq_e1
                    closest_snap = {"point": (x0_disp, y0_disp), "type": "endpoint", "pdf_point": (x0_pdf, y0_pdf)}

                dist_sq_e2 = (x_canvas - x1_disp)**2 + (y_canvas - y1_disp)**2
                if dist_sq_e2 < min_dist_sq:
                    min_dist_sq = dist_sq_e2
                    closest_snap = {"point": (x1_disp, y1_disp), "type": "endpoint", "pdf_point": (x1_pdf, y1_pdf)}

            # --- Check Midpoint ---
            if self.snap_to_midpoints.get():
                mid_x_disp = (x0_disp + x1_disp) / 2
                mid_y_disp = (y0_disp + y1_disp) / 2
                dist_sq_mid = (x_canvas - mid_x_disp)**2 + (y_canvas - mid_y_disp)**2
                if dist_sq_mid < min_dist_sq:
                    min_dist_sq = dist_sq_mid
                    mid_x_pdf = (x0_pdf + x1_pdf) / 2
                    mid_y_pdf = (y0_pdf + y1_pdf) / 2
                    closest_snap = {"point": (mid_x_disp, mid_y_disp), "type": "midpoint", "pdf_point": (mid_x_pdf, mid_y_pdf)}

            # --- Check Line Projection (Perpendicular) ---
            dx_disp, dy_disp = x1_disp - x0_disp, y1_disp - y0_disp
            line_len_sq_disp = dx_disp*dx_disp + dy_disp*dy_disp

            if line_len_sq_disp > 1e-6: # Avoid division by zero for zero-length lines
                # Project point onto the line (using display coordinates)
                t = ((x_canvas - x0_disp) * dx_disp + (y_canvas - y0_disp) * dy_disp) / line_len_sq_disp

                # If projection is within the line segment (0 <= t <= 1)
                if 0 <= t <= 1:
                    proj_x_disp = x0_disp + t * dx_disp
                    proj_y_disp = y0_disp + t * dy_disp
                    dist_sq_proj = (x_canvas - proj_x_disp)**2 + (y_canvas - proj_y_disp)**2

                    if dist_sq_proj < min_dist_sq:
                        min_dist_sq = dist_sq_proj
                        # Calculate corresponding PDF point
                        dx_pdf, dy_pdf = x1_pdf - x0_pdf, y1_pdf - y0_pdf
                        proj_x_pdf = x0_pdf + t * dx_pdf
                        proj_y_pdf = y0_pdf + t * dy_pdf
                        closest_snap = {"point": (proj_x_disp, proj_y_disp), "type": "line", "pdf_point": (proj_x_pdf, proj_y_pdf)}

        # TODO: Add Intersection Snapping (more complex)

        return closest_snap


    def on_canvas_move(self, event):
        """Gestion des mouvements de souris sur le canvas avec snapping et mode ortho."""
        if not self.pdf_document or self.panning: # Don't process during pan
            return

        # Get raw canvas coordinates from event
        x_canvas, y_canvas = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        # --- Determine Final Point (Snapping/Ortho) ---
        # This final point is in CANVAS coordinates for drawing temporary lines/indicators
        final_x_disp, final_y_disp = x_canvas, y_canvas
        snap_applied_type = None
        ortho_applied = False

        # 1. Apply Snapping if enabled
        if self.enable_snapping.get():
            threshold = self.snap_threshold.get()
            snap_info = self.find_closest_line_point(x_canvas, y_canvas, threshold)
            if snap_info:
                final_x_disp, final_y_disp = snap_info["point"]
                snap_applied_type = snap_info["type"]

        # 2. Apply Ortho Mode if enabled AND snapping didn't occur AND points exist
        # Ortho snaps relative to the LAST PLACED POINT (in display coords)
        if self.ortho_mode and not snap_applied_type and self.points:
            last_x_pdf, last_y_pdf = self.points[-1] # Last recorded PDF point
            display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
            last_x_disp, last_y_disp = last_x_pdf * display_resolution_factor, last_y_pdf * display_resolution_factor

            dx = abs(x_canvas - last_x_disp) # Use raw canvas coords for ortho calculation
            dy = abs(y_canvas - last_y_disp)

            if dx > dy: # Snap horizontally
                final_y_disp = last_y_disp
            else: # Snap vertically
                final_x_disp = last_x_disp
            ortho_applied = True

        # --- Draw Indicators ---
        self.canvas.delete("snap_indicator")
        self.canvas.delete("ortho_indicator")
        self.canvas.delete("temp_line")
        self.canvas.delete("temp_angle")

        if snap_applied_type:
             # Afficher un repère visuel pour le snap
             snap_color = "cyan" # Default for line
             snap_size = 4
             if snap_applied_type == "endpoint":
                  snap_color = "lime" # Green for endpoint
                  self.canvas.create_rectangle(final_x_disp - snap_size, final_y_disp - snap_size,
                                              final_x_disp + snap_size, final_y_disp + snap_size,
                                              outline=snap_color, tags="snap_indicator")
             elif snap_applied_type == "midpoint":
                  snap_color = "magenta" # Magenta for midpoint
                  self.canvas.create_polygon(final_x_disp, final_y_disp - snap_size,
                                             final_x_disp - snap_size, final_y_disp + snap_size,
                                             final_x_disp + snap_size, final_y_disp + snap_size,
                                             outline=snap_color, fill="", tags="snap_indicator")
             else: # Line snap
                 self.canvas.create_line(final_x_disp - snap_size, final_y_disp, final_x_disp + snap_size, final_y_disp, fill=snap_color, width=1, tags="snap_indicator")
                 self.canvas.create_line(final_x_disp, final_y_disp - snap_size, final_x_disp, final_y_disp + snap_size, fill=snap_color, width=1, tags="snap_indicator")

        elif ortho_applied and self.points: # Draw ortho indicator only if applied
            last_x_pdf, last_y_pdf = self.points[-1]
            display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
            last_x_disp, last_y_disp = last_x_pdf * display_resolution_factor, last_y_pdf * display_resolution_factor
            self.canvas.create_line(last_x_disp, last_y_disp, final_x_disp, final_y_disp,
                                   fill="orange", width=1, dash=(3, 3), tags="ortho_indicator")
            self.canvas.create_rectangle(final_x_disp-2, final_y_disp-2, final_x_disp+2, final_y_disp+2, outline="orange", tags="ortho_indicator")


        # --- Update Status Bar ---
        status_text = f"X: {final_x_disp:.1f}, Y: {final_y_disp:.1f} (Disp)"
        if self.absolute_scale:
             # Convert final display coords back to PDF coords, then to real units
             display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
             if display_resolution_factor > 1e-6:
                  final_x_pdf = final_x_disp / display_resolution_factor
                  final_y_pdf = final_y_disp / display_resolution_factor
                  real_x = final_x_pdf * self.absolute_scale # Assumes scale is meters/PDF point
                  real_y = final_y_pdf * self.absolute_scale # Need to define absolute_scale correctly
                  # Let's define absolute_scale as meters / PDF point
                  unit = self.unit_var.get()
                  display_val_x, display_unit_x = self.convert_units(real_x, unit)
                  display_val_y, display_unit_y = self.convert_units(real_y, unit)
                  status_text += f" | {display_val_x:.2f}{display_unit_x}, {display_val_y:.2f}{display_unit_y}"
        else:
             status_text += " | Échelle Non Définie"

        if snap_applied_type:
            status_text += f" | Accroché ({snap_applied_type})"
        elif ortho_applied:
            status_text += " | Mode Ortho [Shift]"
        self.status_bar.config(text=status_text)


        # --- Draw Temporary Measurement Visuals ---
        if self.points: # Only draw temp lines if a measurement is in progress
            last_x_pdf, last_y_pdf = self.points[-1]
            display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
            last_x_disp, last_y_disp = last_x_pdf * display_resolution_factor, last_y_pdf * display_resolution_factor

            # Draw line from last placed point to current cursor position (final_x_disp, final_y_disp)
            temp_line_color = "gray"
            if self.mode == "distance": temp_line_color = self.distance_color.get()
            elif self.mode == "surface": temp_line_color = self.surface_color.get()
            elif self.mode == "perimeter": temp_line_color = self.colors.get("perimeter", "#FFA500")
            elif self.mode == "angle": temp_line_color = self.angle_color.get()

            if self.mode != "angle" or len(self.points) == 1: # Draw simple temp line
                 self.canvas.create_line(last_x_disp, last_y_disp, final_x_disp, final_y_disp,
                                        dash=(4, 4), fill=temp_line_color, tags="temp_line")

            # For Surface/Perimeter, also draw closing line preview if needed
            if self.mode in ["surface", "perimeter"] and len(self.points) > 1:
                 first_x_pdf, first_y_pdf = self.points[0]
                 first_x_disp, first_y_disp = first_x_pdf * display_resolution_factor, first_y_pdf * display_resolution_factor
                 self.canvas.create_line(first_x_disp, first_y_disp, final_x_disp, final_y_disp,
                                        dash=(2, 2), fill=temp_line_color, tags="temp_line")

            # For Angle, draw second arm and arc preview
            if self.mode == "angle" and len(self.points) == 2:
                vertex_pdf = self.points[1]
                vertex_disp = (vertex_pdf[0] * display_resolution_factor, vertex_pdf[1] * display_resolution_factor)
                p1_pdf = self.points[0]
                p1_disp = (p1_pdf[0] * display_resolution_factor, p1_pdf[1] * display_resolution_factor)

                # Draw fixed first arm (dashed)
                self.canvas.create_line(p1_disp[0], p1_disp[1], vertex_disp[0], vertex_disp[1],
                                       fill=temp_line_color, width=1, dash=(2,2), tags="temp_angle")
                # Draw moving second arm
                self.canvas.create_line(vertex_disp[0], vertex_disp[1], final_x_disp, final_y_disp,
                                       dash=(4, 4), fill=temp_line_color, tags="temp_angle")

                # Draw temporary arc preview
                try:
                    # Calculate angle for preview using display coordinates
                    temp_p3_disp = (final_x_disp, final_y_disp)
                    # Convert display points back to PDF points for calculation consistency?
                    # Or calculate directly from display points? Let's use display for visual preview.
                    angle_val, start_rad_disp, end_rad_disp = self.calculate_angle_display(p1_disp, vertex_disp, temp_p3_disp)

                    start_deg_disp = math.degrees(start_rad_disp)
                    raw_extent_disp = math.degrees(end_rad_disp - start_rad_disp)
                    while raw_extent_disp > 180: raw_extent_disp -= 360
                    while raw_extent_disp <= -180: raw_extent_disp += 360
                    extent_deg_disp = raw_extent_disp

                    arc_radius = 20
                    arc_bbox = (vertex_disp[0] - arc_radius, vertex_disp[1] - arc_radius, vertex_disp[0] + arc_radius, vertex_disp[1] + arc_radius)
                    self.canvas.create_arc(arc_bbox, start=start_deg_disp, extent=extent_deg_disp,
                                          style=tk.ARC, outline=temp_line_color, width=1, dash=(2,2), tags="temp_angle")
                    # Preview angle value
                    mid_angle_rad_disp = start_rad_disp + math.radians(extent_deg_disp / 2.0)
                    text_offset = arc_radius + 10
                    text_x = vertex_disp[0] + text_offset * math.cos(mid_angle_rad_disp)
                    text_y = vertex_disp[1] - text_offset * math.sin(mid_angle_rad_disp) # Y inverted
                    self.canvas.create_text(text_x, text_y, text=f"{angle_val:.1f}°", fill=temp_line_color, font=("Arial", 9), tags="temp_angle")
                except Exception as e: # Ignore errors during temporary preview calculation
                    print(f"Erreur aperçu angle: {e}")
                    pass


    def on_canvas_click(self, event):
        """Gestion des clics sur le canvas pour placer les points de mesure."""
        if not self.pdf_document or self.panning:
            return

        # Get raw canvas coordinates
        x_canvas, y_canvas = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        # --- Determine Final Point (Apply Snapping/Ortho) ---
        # The result needs to be the accurate PDF coordinate to store.
        final_x_pdf, final_y_pdf = 0.0, 0.0
        final_x_disp, final_y_disp = x_canvas, y_canvas # For drawing the point marker

        snap_applied_type = None
        ortho_applied = False
        display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
        if display_resolution_factor == 0: return # Avoid division by zero


        # 1. Apply Snapping if enabled
        if self.enable_snapping.get():
            threshold = self.snap_threshold.get()
            snap_info = self.find_closest_line_point(x_canvas, y_canvas, threshold)
            if snap_info:
                final_x_disp, final_y_disp = snap_info["point"] # Snapped display point
                final_x_pdf, final_y_pdf = snap_info["pdf_point"] # Corresponding PDF point
                snap_applied_type = snap_info["type"]

        # 2. Apply Ortho Mode if enabled AND snapping didn't occur AND points exist
        if self.ortho_mode and not snap_applied_type and self.points:
            last_x_pdf, last_y_pdf = self.points[-1] # Last recorded PDF point
            last_x_disp, last_y_disp = last_x_pdf * display_resolution_factor, last_y_pdf * display_resolution_factor

            dx_c = abs(x_canvas - last_x_disp)
            dy_c = abs(y_canvas - last_y_disp)

            if dx_c > dy_c: # Snap horizontally
                final_y_disp = last_y_disp
                # Calculate corresponding PDF Y
                final_y_pdf = last_y_pdf
                # Use original X canvas click converted to PDF X
                final_x_pdf = x_canvas / display_resolution_factor
                # Also update final_x_disp to match the effective position
                final_x_disp = x_canvas
            else: # Snap vertically
                final_x_disp = last_x_disp
                # Calculate corresponding PDF X
                final_x_pdf = last_x_pdf
                # Use original Y canvas click converted to PDF Y
                final_y_pdf = y_canvas / display_resolution_factor
                # Also update final_y_disp to match the effective position
                final_y_disp = y_canvas

            ortho_applied = True

        # 3. If no snapping or ortho, convert raw canvas click to PDF coords
        if not snap_applied_type and not ortho_applied:
            final_x_pdf = x_canvas / display_resolution_factor
            final_y_pdf = y_canvas / display_resolution_factor
            # final_x_disp, final_y_disp remain x_canvas, y_canvas


        # --- Store the precise PDF coordinate ---
        point_to_add = (final_x_pdf, final_y_pdf)


        # --- Call specific handler based on mode ---
        # Pass the PDF coordinate to the handlers
        if self.mode == "distance":
            self.handle_distance_measurement(point_to_add, final_x_disp, final_y_disp)
        elif self.mode == "surface":
            self.handle_surface_measurement(point_to_add, final_x_disp, final_y_disp)
        elif self.mode == "perimeter":
            self.handle_perimeter_measurement(point_to_add, final_x_disp, final_y_disp)
        elif self.mode == "angle":
            self.handle_angle_measurement(point_to_add, final_x_disp, final_y_disp)
        elif self.mode == "calibration":
            self.handle_calibration(point_to_add, final_x_disp, final_y_disp)


    def on_canvas_double_click(self, event):
        """Gestion du double-clic sur le canvas."""
        # Peut être utilisé pour finaliser une forme (surface/périmètre)
        if self.mode in ["surface", "perimeter"]:
             self.finalize_shape_if_possible()

    def start_pan(self, event):
        """Commence le panoramique lorsque le bouton 2 ou 3 de la souris est enfoncé."""
        if self.panning or not self.pdf_document:
            return
        self.canvas.config(cursor="fleur")
        self.panning = True
        # Record the starting screen coordinates for panning delta calculation
        self.pan_start_x = event.x
        self.pan_start_y = event.y
        # Reset accumulators
        self.pan_accum_x = 0.0
        self.pan_accum_y = 0.0

    def on_pan(self, event):
        """Déplace la vue du document pendant le panoramique."""
        if not self.panning or not self.pdf_document:
            return

        # Calculate the difference in SCREEN coordinates since last event
        dx_screen = event.x - self.pan_start_x
        dy_screen = event.y - self.pan_start_y

        # Update the starting point for the next motion event *before* calculations
        self.pan_start_x = event.x
        self.pan_start_y = event.y

        if self.pan_sensitivity > 0:
            # Add the *scaled* delta to the accumulator
            # Note: We add the delta divided by sensitivity.
            self.pan_accum_x += dx_screen / self.pan_sensitivity
            self.pan_accum_y += dy_screen / self.pan_sensitivity

            # Determine how many *whole* units of scrolling are pending
            # Important: Scroll amount must be integer
            scroll_x_units = int(self.pan_accum_x)
            scroll_y_units = int(self.pan_accum_y)

            # Apply scroll if accumulated value is >= 1 or <= -1
            if scroll_x_units != 0:
                # print(f"Scrolling X by {-scroll_x_units} units (Accum: {self.pan_accum_x:.2f})") # Optional debug
                self.canvas.xview_scroll(-scroll_x_units, "units") # Scroll opposite to mouse movement
                self.pan_accum_x -= scroll_x_units # Subtract the scrolled amount, keeping the remainder

            if scroll_y_units != 0:
                # print(f"Scrolling Y by {-scroll_y_units} units (Accum: {self.pan_accum_y:.2f})") # Optional debug
                self.canvas.yview_scroll(-scroll_y_units, "units") # Scroll opposite to mouse movement
                self.pan_accum_y -= scroll_y_units # Subtract the scrolled amount, keeping the remainder

        self.status_bar.config(text="Panoramique...")

    def end_pan(self, event):
        """Termine le panoramique."""
        if self.panning:
            self.canvas.config(cursor="") # Restore default cursor
            self.panning = False
            self.status_bar.config(text="Prêt")


    def shift_pressed(self, event):
        """Active le mode ortho quand Shift est enfoncé."""
        if not self.ortho_mode:
             self.ortho_mode = True
             # Status bar update is now handled in on_canvas_move


    def shift_released(self, event):
        """Désactive le mode ortho quand Shift est relâché."""
        if self.ortho_mode:
            self.ortho_mode = False
            self.canvas.delete("ortho_indicator") # Clear indicator
            # Status bar update is now handled in on_canvas_move

    # --- Measurement Handlers (Take PDF coords and display coords) ---

    def handle_distance_measurement(self, pdf_point, disp_x, disp_y):
        """Gestion des mesures de distance."""
        self.points.append(pdf_point) # Store PDF point

        # Draw point marker at display location
        self.canvas.create_oval(disp_x-3, disp_y-3, disp_x+3, disp_y+3,
                               fill=self.point_color.get(), tags="measurement_temp_dist")

        if len(self.points) == 2:
            p1_pdf, p2_pdf = self.points[0], self.points[1]

            self.canvas.delete("measurement_temp_dist") # Clear temp points
            self.canvas.delete("temp_line") # Clear temp line

            # Calculate distance using PDF coordinates
            dx_pdf = p2_pdf[0] - p1_pdf[0]
            dy_pdf = p2_pdf[1] - p1_pdf[1]
            distance_pdf_units = math.sqrt(dx_pdf**2 + dy_pdf**2)

            # Convert to real units using ABSOLUTE scale (meters per PDF point)
            display_text = ""
            real_distance = 0.0
            if self.absolute_scale:
                real_distance = distance_pdf_units * self.absolute_scale # Now correctly meters
                unit = self.unit_var.get()
                display_value, display_unit = self.convert_units(real_distance, unit)
                display_text = f"{display_value:.2f} {display_unit}"
            else:
                display_text = f"{distance_pdf_units:.1f} pt" # Fallback to PDF points

            # Add measurement to list
            # Value stored is distance in PDF points
            self.add_measurement("distance", distance_pdf_units, display_text)

            # Redraw handles showing the final measurement
            self.redraw_measurements()

            # Reset for next measurement
            self.points = []


    def handle_surface_measurement(self, pdf_point, disp_x, disp_y):
        """Ajoute un point pour la mesure de surface."""
        self.points.append(pdf_point) # Store PDF point

        display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5

        # Draw point marker (use a temp tag until finalized)
        self.canvas.create_oval(disp_x-3, disp_y-3, disp_x+3, disp_y+3,
                               fill=self.point_color.get(), tags="measurement_temp_poly")

        # Draw lines between temp points (using display coords for visuals)
        if len(self.points) > 1:
             prev_pdf = self.points[-2]
             prev_disp = (prev_pdf[0] * display_resolution_factor, prev_pdf[1] * display_resolution_factor)
             self.canvas.create_line(prev_disp[0], prev_disp[1], disp_x, disp_y,
                                    fill=self.surface_color.get(), width=1, dash=(2,2), tags="measurement_temp_poly")
        self.status_bar.config(text=f"Surface: Point {len(self.points)} ajouté. Double-clic ou [✓ Terminer] pour finaliser.")


    def handle_perimeter_measurement(self, pdf_point, disp_x, disp_y):
        """Ajoute un point pour la mesure de périmètre."""
        self.points.append(pdf_point) # Store PDF point

        display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5

        # Draw point marker (use a temp tag until finalized)
        self.canvas.create_oval(disp_x-3, disp_y-3, disp_x+3, disp_y+3,
                               fill=self.point_color.get(), tags="measurement_temp_poly")

        # Draw lines between temp points (using display coords)
        if len(self.points) > 1:
             prev_pdf = self.points[-2]
             prev_disp = (prev_pdf[0] * display_resolution_factor, prev_pdf[1] * display_resolution_factor)
             self.canvas.create_line(prev_disp[0], prev_disp[1], disp_x, disp_y,
                                    fill=self.colors.get("perimeter", "#FFA500"), width=1, dash=(2,2), tags="measurement_temp_poly")
        self.status_bar.config(text=f"Périmètre: Point {len(self.points)} ajouté. Double-clic ou [✓ Terminer] pour finaliser.")


    def handle_angle_measurement(self, pdf_point, disp_x, disp_y):
        """Gestion des mesures d'angle (3 clics)."""
        self.points.append(pdf_point) # Store PDF point

        display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
        angle_draw_color = self.angle_color.get()

        # Draw point marker
        self.canvas.create_oval(disp_x - 3, disp_y - 3, disp_x + 3, disp_y + 3,
                               fill=self.point_color.get(), tags="measurement_temp_angle")

        if len(self.points) == 1:
            self.status_bar.config(text="Angle: Cliquez le sommet")
        elif len(self.points) == 2:
            # Draw first arm (temp) using display coords
            p1_pdf = self.points[0]
            p1_disp = (p1_pdf[0] * display_resolution_factor, p1_pdf[1] * display_resolution_factor)
            self.canvas.create_line(p1_disp[0], p1_disp[1], disp_x, disp_y, # disp_x, disp_y is vertex here
                                   fill=angle_draw_color, width=1, dash=(2, 2), tags="measurement_temp_angle")
            self.status_bar.config(text="Angle: Cliquez le dernier point")
        elif len(self.points) == 3:
            # Final point - calculate and finalize
            p1_pdf, p2_pdf, p3_pdf = self.points[0], self.points[1], self.points[2]

            # Calculate angle using PDF points
            angle_deg, _, __ = self.calculate_angle(p1_pdf, p2_pdf, p3_pdf)
            display_text = f"{angle_deg:.1f}°"

            # Clear temporary visuals
            self.canvas.delete("measurement_temp_angle")
            self.canvas.delete("temp_angle") # Clear moving preview too


            # Add the final measurement (value is angle degrees)
            self.add_measurement("angle", angle_deg, display_text)

            # Redraw to show the final angle measurement
            self.redraw_measurements()

            # Reset for next angle
            self.points = []
            self.status_bar.config(text="Mode Angle: Cliquez le premier point")


    def handle_calibration(self, pdf_point, disp_x, disp_y):
        """Gestion de la calibration d'échelle."""
        self.points.append(pdf_point) # Store PDF point

        calib_color = "purple"

        # Draw calibration point marker
        self.canvas.create_oval(disp_x-4, disp_y-4, disp_x+4, disp_y+4,
                               outline=calib_color, width=2, tags="calibration_visual")

        if len(self.points) == 1:
             self.status_bar.config(text="Calibration: Cliquez le deuxième point.")
        elif len(self.points) == 2:
            p1_pdf, p2_pdf = self.points[0], self.points[1]
            display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
            p1_disp = (p1_pdf[0] * display_resolution_factor, p1_pdf[1] * display_resolution_factor)
            p2_disp = (p2_pdf[0] * display_resolution_factor, p2_pdf[1] * display_resolution_factor)


            # Draw calibration line visual
            self.canvas.create_line(p1_disp[0], p1_disp[1], p2_disp[0], p2_disp[1],
                                   fill=calib_color, width=2, tags="calibration_visual")

            # Calculate distance in PDF points
            dx_pdf = p2_pdf[0] - p1_pdf[0]
            dy_pdf = p2_pdf[1] - p1_pdf[1]
            distance_pdf_units = math.sqrt(dx_pdf**2 + dy_pdf**2)

            if distance_pdf_units < 1e-6:
                 messagebox.showwarning("Calibration", "Les points de calibration sont trop proches.", parent=self.root)
                 self.canvas.delete("calibration_visual")
                 self.points = []
                 self.status_bar.config(text="Calibration annulée. Cliquez le premier point.")
                 return

            # Ask for the real distance corresponding to the PDF point distance
            real_distance_meters = self.ask_real_distance() # Returns distance in METERS

            if real_distance_meters is not None and real_distance_meters > 0:
                # Calculate the ABSOLUTE scale (METERS per PDF point unit)
                self.absolute_scale = real_distance_meters / distance_pdf_units

                # Update UI display for scale
                self.update_scale_info_display() # Use helper function

                self.status_bar.config(text=f"Échelle calibrée.")

                # Update existing measurements with the new scale
                self.update_measurements_display_units() # Recalculate all display texts

                # Inform AI
                self.display_ai_message("system", f"Échelle calibrée: {self.scale_info.cget('text')}") # Get text from label
                self.display_ai_message("assistant", "L'échelle a été définie. Les mesures existantes et futures utiliseront cette échelle.")

            else:
                # Calibration cancelled or invalid input
                self.status_bar.config(text="Calibration annulée.")

            # Clean up visuals and points regardless of success
            self.canvas.delete("calibration_visual")
            self.points = []
            # Optionally switch back to distance mode?
            # self.set_mode("distance")


    def finalize_shape_if_possible(self):
        """Finalise la mesure de surface ou périmètre si possible (e.g., via button or double-click)."""
        if self.mode == "surface":
            if len(self.points) >= 3:
                self.finalize_surface_measurement()
            else:
                messagebox.showwarning("Surface", "Au moins 3 points sont nécessaires pour une surface.", parent=self.root)
        elif self.mode == "perimeter":
            if len(self.points) >= 2:
                self.finalize_perimeter_measurement()
            else:
                 messagebox.showwarning("Périmètre", "Au moins 2 points sont nécessaires pour un périmètre.", parent=self.root)


    def finalize_surface_measurement(self):
        """Finalise la mesure de surface en cours."""
        if not self.mode == "surface" or len(self.points) < 3:
            return # Should not happen if called correctly, but safety check

        # Calculate area using PDF points (Shoelace formula)
        area_pdf_units_sq = self.calculate_polygon_area(self.points)

        # Convert to real units using ABSOLUTE scale
        display_text = ""
        if self.absolute_scale:
            # absolute_scale is meters/pdf_point, so scale^2 is m^2 / pdf_point^2
            real_area_sq_meters = area_pdf_units_sq * (self.absolute_scale ** 2)
            unit = self.unit_var.get()
            display_value, display_unit = self.convert_area_units(real_area_sq_meters, unit)
            display_text = f"{display_value:.2f} {display_unit}²"
        else:
            display_text = f"{area_pdf_units_sq:.1f} pt²" # Fallback to PDF points squared

        # Clear temporary visuals
        self.canvas.delete("measurement_temp_poly")
        self.canvas.delete("temp_line")

        # Add the final measurement
        # Value stored is area in PDF points squared
        self.add_measurement("surface", area_pdf_units_sq, display_text)

        # Redraw to show final measurement
        self.redraw_measurements()

        # Reset for next measurement
        self.points = []
        self.status_bar.config(text="Surface ajoutée. Prêt pour la suivante.")


    def finalize_perimeter_measurement(self):
        """Finalise la mesure de périmètre en cours."""
        if not self.mode == "perimeter" or len(self.points) < 2:
            return

        # Calculate perimeter using PDF points
        perimeter_pdf_units = 0
        num_points = len(self.points)
        for i in range(num_points):
            p1 = self.points[i]
            p2 = self.points[(i + 1) % num_points] # Wrap around for closing segment
            dx_pdf = p2[0] - p1[0]
            dy_pdf = p2[1] - p1[1]
            perimeter_pdf_units += math.sqrt(dx_pdf**2 + dy_pdf**2)

        # Convert to real units using ABSOLUTE scale
        display_text = ""
        if self.absolute_scale:
            real_perimeter_meters = perimeter_pdf_units * self.absolute_scale
            unit = self.unit_var.get()
            display_value, display_unit = self.convert_units(real_perimeter_meters, unit)
            display_text = f"P: {display_value:.2f} {display_unit}"
        else:
            display_text = f"P: {perimeter_pdf_units:.1f} pt" # Fallback

        # Clear temporary visuals
        self.canvas.delete("measurement_temp_poly")
        self.canvas.delete("temp_line")

        # Add the final measurement
        # Value stored is perimeter in PDF points
        self.add_measurement("perimeter", perimeter_pdf_units, display_text)

        # Redraw to show final measurement
        self.redraw_measurements()

        # Reset for next measurement
        self.points = []
        self.status_bar.config(text="Périmètre ajouté. Prêt pour le suivant.")


    # --- Calculation Helpers ---

    def calculate_polygon_area(self, pdf_points):
        """Calcule l'aire d'un polygone avec la formule de Shoelace (prend des points PDF)."""
        n = len(pdf_points)
        if n < 3: return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += pdf_points[i][0] * pdf_points[j][1]
            area -= pdf_points[j][0] * pdf_points[i][1]
        return abs(area) / 2.0

    def calculate_angle(self, p1_pdf, p2_pdf, p3_pdf):
        """Calcule l'angle au sommet p2 (prend des points PDF). Retourne angle (deg), start_rad, end_rad."""
        # Vecteurs p2->p1 et p2->p3 (en coordonnées PDF)
        v1_x, v1_y = p1_pdf[0] - p2_pdf[0], p1_pdf[1] - p2_pdf[1]
        v2_x, v2_y = p3_pdf[0] - p2_pdf[0], p3_pdf[1] - p2_pdf[1]

        # Angle de chaque vecteur par rapport à l'axe X+ (mathématique standard)
        angle1_rad = math.atan2(v1_y, v1_x)
        angle2_rad = math.atan2(v2_y, v2_x)

        # Angle entre les deux (différence)
        angle_rad_diff = angle2_rad - angle1_rad

        # Normaliser la différence entre -pi et pi
        while angle_rad_diff > math.pi: angle_rad_diff -= 2 * math.pi
        while angle_rad_diff <= -math.pi: angle_rad_diff += 2 * math.pi

        # Convertir en degrés positifs
        angle_deg = abs(math.degrees(angle_rad_diff))

        # Convention: retourner le plus petit angle (<= 180)
        if angle_deg > 180:
            angle_deg = 360 - angle_deg

        return angle_deg, angle1_rad, angle2_rad

    def calculate_angle_display(self, p1_disp, p2_disp, p3_disp):
        """Calcule l'angle au sommet p2 (prend des points DISPLAY). Retourne angle (deg), start_rad, end_rad."""
        # Vecteurs p2->p1 et p2->p3 (en coordonnées display)
        v1_x, v1_y = p1_disp[0] - p2_disp[0], p1_disp[1] - p2_disp[1]
        v2_x, v2_y = p3_disp[0] - p2_disp[0], p3_disp[1] - p2_disp[1]

        # Angle de chaque vecteur par rapport à l'axe X+ (avec Y inversé pour Tkinter)
        angle1_rad = math.atan2(-v1_y, v1_x)
        angle2_rad = math.atan2(-v2_y, v2_x)

        # Angle entre les deux (différence)
        angle_rad_diff = angle2_rad - angle1_rad

        # Normaliser la différence entre -pi et pi
        while angle_rad_diff > math.pi: angle_rad_diff -= 2 * math.pi
        while angle_rad_diff <= -math.pi: angle_rad_diff += 2 * math.pi

        # Convertir en degrés positifs
        angle_deg = abs(math.degrees(angle_rad_diff))

        # Convention: retourner le plus petit angle (<= 180)
        if angle_deg > 180:
            angle_deg = 360 - angle_deg

        return angle_deg, angle1_rad, angle2_rad


    def convert_units(self, value_meters, target_unit):
        """Convertit une longueur en mètres vers l'unité cible."""
        conv_factors = {"m": 1.0, "cm": 100.0, "mm": 1000.0, "ft": 3.28084, "in": 39.3701}
        factor = conv_factors.get(target_unit, 1.0) # Default to meters if unit unknown
        return value_meters * factor, target_unit


    def convert_area_units(self, value_sq_meters, target_unit):
        """Convertit une aire en m² vers l'unité cible²."""
        conv_factors_len = {"m": 1.0, "cm": 100.0, "mm": 1000.0, "ft": 3.28084, "in": 39.3701}
        factor_len = conv_factors_len.get(target_unit, 1.0)
        factor_area = factor_len ** 2 # Square the length factor for area
        return value_sq_meters * factor_area, target_unit


    def ask_real_distance(self):
        """Demande la distance réelle pour calibration. Retourne la distance en MÈTRES ou None."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Calibration d'échelle")
        dialog.geometry("350x180")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.colors["bg_light"])

        tk.Label(dialog, text="Entrez la distance réelle connue\nentre les deux points cliqués:",
                 font=("Arial", 11), bg=self.colors["bg_light"], justify=tk.CENTER).pack(pady=(15, 10))

        input_frame = ttk.Frame(dialog)
        input_frame.pack(pady=5)

        entry_var = tk.StringVar()
        entry = ttk.Entry(input_frame, textvariable=entry_var, width=12, font=("Arial", 11))
        entry.pack(side=tk.LEFT, padx=5)
        entry.focus_set()

        unit_var = tk.StringVar(value=self.unit_var.get()) # Default to current app unit
        unit_dropdown = ttk.Combobox(input_frame, textvariable=unit_var,
                                     values=["m", "cm", "mm", "ft", "in"],
                                     width=5, state="readonly")
        unit_dropdown.pack(side=tk.LEFT, padx=5)

        result_meters = [None] # Use list to pass result out of closures

        def on_ok():
            try:
                value_str = entry_var.get().replace(',', '.') # Allow comma decimal
                value = float(value_str)
                unit = unit_var.get()
                if value <= 0: raise ValueError("Distance must be positive")

                # Convert input value to METERS
                input_in_meters = value
                if unit == "cm": input_in_meters /= 100.0
                elif unit == "mm": input_in_meters /= 1000.0
                elif unit == "ft": input_in_meters *= 0.3048
                elif unit == "in": input_in_meters *= 0.0254

                result_meters[0] = input_in_meters
                dialog.destroy()
            except ValueError as e:
                messagebox.showerror("Erreur de Valeur", f"Veuillez entrer une distance numérique positive valide.\n({e})", parent=dialog)

        def on_cancel():
             result_meters[0] = None
             dialog.destroy()

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15)
        ttk.Button(button_frame, text="OK", command=on_ok, style="Action.TButton").pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Annuler", command=on_cancel).pack(side=tk.LEFT, padx=10)

        # Allow Enter key to trigger OK
        dialog.bind('<Return>', lambda event=None: on_ok())
        # Allow Esc key to trigger Cancel
        dialog.bind('<Escape>', lambda event=None: on_cancel())


        # Center the window
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 3) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")

        self.root.wait_window(dialog)
        return result_meters[0]

    # --- Measurement List Handling ---

    def add_measurement(self, measure_type, value, display_text):
        """Ajoute une mesure finalisée à la liste interne et au Treeview."""
        # value is: pdf_points (distance, perimeter), pdf_points^2 (area), degrees (angle)
        measure_id = time.time() # Use timestamp for a unique-ish ID

        measure = {
            "id": measure_id,
            "type": measure_type,
            "value": value, # Value in PDF units (points, points^2) or degrees
            "points": list(self.points), # Store PDF points used
            "page": self.current_page,
            "display_text": display_text, # Initial text (calculated value + unit/symbol)
            "unit_at_creation": self.unit_var.get(), # Store unit used for display_text
            "color": None, # <<< --- ADDED: Default color is None
            # Initialize product fields as empty/None
            "product_category": None,
            "product_name": None,
            "product_attributes": None,
        }

        product_name_for_display = ""
        product_category_for_display = ""
        # Ask for product association only if applicable and user wants it
        if measure_type != "angle": # Don't associate products with angles
            if measure_type in ["distance", "surface", "perimeter"]:
                 # Maybe make this configurable? Always ask? Never ask?
                 if messagebox.askyesno("Association Produit",
                                       f"Associer un produit du catalogue à cette mesure de {measure_type}?", parent=self.root):
                    product_info = self.select_product_dialog()
                    if product_info:
                        category, product = product_info
                        attributes = self.product_catalog.get_product_attributes(category, product)

                        measure["product_category"] = category
                        measure["product_name"] = product
                        measure["product_attributes"] = attributes
                        product_name_for_display = product
                        product_category_for_display = category

                        # --- NEW: Get and store color from product attributes ---
                        if attributes:
                            measure["color"] = attributes.get('color') # Gets color or None
                        # --- END NEW ---

                        # Append product name to the stored display_text for clarity
                        measure["display_text"] += f" [{product}]"


        self.measures.append(measure)
        self.update_measures_list() # Refresh the entire list view
        self.update_product_totals_display() # <--- AJOUTER CET APPEL

    def update_measures_list(self):
        """Met à jour (recrée) l'affichage dans le Treeview des mesures."""
        # Store selection
        selected_iids = self.measures_list.selection()

        # Clear existing items
        for item in self.measures_list.get_children():
            self.measures_list.delete(item)

        # Re-populate from self.measures
        for measure in self.measures:
             measure_id = measure.get("id", "")
             m_type = measure.get("type", "N/A").capitalize()
             m_page = measure.get("page", -1) + 1
             m_display = measure.get("display_text", "") # Includes product if associated

             # Extract just the value part for the 'Valeur' column if needed, or show full text
             value_part = m_display.split(' [')[0] # Get text before product association bracket
             product_name = measure.get("product_name", "")

             values_tuple = (m_type, value_part, product_name, m_page)

             # Use measure ID as item ID for reliable selection/deletion
             try:
                 iid_str = str(measure_id)
                 self.measures_list.insert("", "end", iid=iid_str, values=values_tuple)
             except tk.TclError as e:
                 # Handle potential duplicate IDs if timestamps collide (very unlikely)
                 print(f"Erreur TclError lors de l'insertion mesure dans Treeview: {e} - ID: {measure_id}")
                 # Try adding a suffix if ID exists
                 try:
                      iid_str = f"{measure_id}_{time.time()}" # Add more uniqueness
                      self.measures_list.insert("", "end", iid=iid_str, values=values_tuple)
                 except tk.TclError as e2:
                      print(f"Échec de l'insertion Treeview même avec suffixe: {e2}")


        # Restore selection if possible
        if selected_iids:
            # Filter IDs that still exist
            valid_selection = [iid for iid in selected_iids if self.measures_list.exists(iid)]
            if valid_selection:
                try:
                    self.measures_list.selection_set(valid_selection)
                    self.measures_list.focus(valid_selection[0])
                    self.measures_list.see(valid_selection[0])
                except tk.TclError:
                     print("Avertissement: Impossible de restaurer la sélection après mise à jour de la liste des mesures.")

    # --- AJOUT: Gestion de la sélection de mesure ---
    def on_measure_select(self, event=None):
        """Appelé lorsque la sélection change dans la liste des mesures."""
        selected_iids = self.measures_list.selection()

        new_selected_id = None
        if selected_iids:
            # Prendre le premier sélectionné (Treeview gère la sélection multiple, mais on surligne un seul)
            selected_iid_str = selected_iids[0]
            try:
                # Convertir l'IID (string) en float pour correspondre à l'ID de mesure
                new_selected_id = float(selected_iid_str)
            except ValueError:
                print(f"Erreur: IID de mesure sélectionné invalide '{selected_iid_str}'")
                new_selected_id = None

        # Vérifier si la sélection a réellement changé
        if new_selected_id != self.selected_measure_id:
            self.selected_measure_id = new_selected_id
            # Déclencher un redessin pour appliquer la surbrillance
            self.redraw_measurements()

            # Optionnel : Aller à la page de la mesure sélectionnée
            if new_selected_id is not None:
                for measure in self.measures:
                    if measure.get('id') == new_selected_id:
                        target_page = measure.get('page')
                        if target_page is not None and target_page != self.current_page:
                            print(f"Aller à la page {target_page + 1} pour la mesure sélectionnée...")
                            self.current_page = target_page
                            self.points = [] # Clear points when changing page
                            self.cancel_current_measurement()
                            self.display_page() # Ceci appelle déjà redraw_measurements
                            self.update_document_info()
                        break # Sortir de la boucle une fois la mesure trouvée


    def delete_selected_measure(self):
        """Supprime la mesure sélectionnée dans le Treeview et la liste interne."""
        selected_iids = self.measures_list.selection()
        if not selected_iids:
            messagebox.showwarning("Sélection requise", "Veuillez sélectionner une mesure à supprimer.", parent=self.root)
            return

        deleted_count = 0
        remaining_measures = []
        ids_to_delete_float = set()

        # Convert selected IIDs (strings) to float IDs for matching
        for iid_str in selected_iids:
             try:
                  ids_to_delete_float.add(float(iid_str))
             except ValueError:
                  print(f"Avertissement: ID Treeview invalide ignoré: {iid_str}")

        if not ids_to_delete_float: return # No valid IDs selected


        # Filter the measures list
        for measure in self.measures:
             m_id = measure.get("id")
             if m_id in ids_to_delete_float:
                  deleted_count += 1
             else:
                  remaining_measures.append(measure)

        if deleted_count > 0:
             confirm_msg = f"Supprimer la mesure sélectionnée ?" if deleted_count == 1 else f"Supprimer les {deleted_count} mesures sélectionnées ?"
             if messagebox.askyesno("Confirmation", confirm_msg, parent=self.root):
                 self.measures = remaining_measures
                 # Si la mesure supprimée était celle sélectionnée, désélectionner
                 if self.selected_measure_id in ids_to_delete_float:
                      self.selected_measure_id = None
                 self.update_measures_list() # Update Treeview
                 self.redraw_measurements() # Redraw canvas
                 self.status_bar.config(text=f"{deleted_count} mesure(s) supprimée(s).")
                 self.update_product_totals_display() # <--- AJOUTER CET APPEL
        else:
             messagebox.showerror("Erreur", "Impossible de trouver les mesures correspondantes à supprimer.", parent=self.root)


    def clear_all_measures(self):
        """Efface toutes les mesures."""
        if not self.measures:
             messagebox.showinfo("Information", "Aucune mesure à effacer.", parent=self.root)
             return

        if messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer TOUTES les mesures ?\nCette action est irréversible.", parent=self.root, icon='warning'):
            self.measures = []
            self.selected_measure_id = None # Reset selection
            self.update_measures_list() # Update Treeview
            self.canvas.delete("measurement") # Clear visuals
            self.status_bar.config(text="Toutes les mesures ont été supprimées.")
            self.display_ai_message("system", "Toutes les mesures ont été effacées.")
            self.update_product_totals_display() # <--- AJOUTER CET APPEL


    def update_measurements_display_units(self):
        """Met à jour le texte affiché des mesures existantes si l'unité ou l'échelle change."""
        if not self.absolute_scale:
             # If scale is not set, display should ideally revert to PDF points/degrees
             # Or indicate scale is missing in the display text itself?
             print("[DEBUG] Tentative de mise à jour des unités sans échelle définie.")

        target_unit = self.unit_var.get()
        needs_redraw = False

        for measure in self.measures:
            measure_type = measure.get("type")
            value = measure.get("value") # PDF points, PDF points^2, or degrees
            old_display_text = measure.get("display_text", "")
            new_display_text_base = "" # The value + unit part

            # Preserve product suffix if present
            product_suffix = ""
            if " [" in old_display_text:
                 parts = old_display_text.split(" [", 1)
                 old_value_part = parts[0]
                 product_suffix = " [" + parts[1]
            else:
                 old_value_part = old_display_text

            # Recalculate display text based on current scale and unit
            if self.absolute_scale:
                if measure_type == "distance" or measure_type == "perimeter":
                    real_value_meters = value * self.absolute_scale
                    display_value, display_unit = self.convert_units(real_value_meters, target_unit)
                    prefix = "P: " if measure_type == "perimeter" else ""
                    new_display_text_base = f"{prefix}{display_value:.2f} {display_unit}"

                elif measure_type == "surface":
                    real_value_sq_meters = value * (self.absolute_scale ** 2)
                    display_value, display_unit = self.convert_area_units(real_value_sq_meters, target_unit)
                    new_display_text_base = f"{display_value:.2f} {display_unit}²"

                elif measure_type == "angle":
                    new_display_text_base = f"{value:.1f}°" # Angle doesn't change

                else: # Unknown type
                    new_display_text_base = old_value_part # Keep old text? Or indicate error?

            else: # No absolute scale defined
                if measure_type == "distance" or measure_type == "perimeter":
                     prefix = "P: " if measure_type == "perimeter" else ""
                     new_display_text_base = f"{prefix}{value:.1f} pt"
                elif measure_type == "surface":
                     new_display_text_base = f"{value:.1f} pt²"
                elif measure_type == "angle":
                     new_display_text_base = f"{value:.1f}°"
                else:
                     new_display_text_base = old_value_part

            # Combine base text and product suffix
            final_display_text = new_display_text_base + product_suffix

            # Update measure dict if text changed
            if final_display_text != old_display_text:
                measure["display_text"] = final_display_text
                measure["unit_at_creation"] = target_unit # Update unit context for future ref?
                needs_redraw = True

        if needs_redraw:
             self.update_measures_list() # Update Treeview display
             self.redraw_measurements() # Update canvas display
             self.status_bar.config(text=f"Affichage mis à jour pour unité: {target_unit}")
             self.update_product_totals_display() # <--- AJOUTER CET APPEL ICI


    def update_scale_info_display(self):
        """Met à jour le label d'information de l'échelle."""
        if self.absolute_scale:
            unit = self.unit_var.get()
            # Convert scale (meters per PDF point) to target unit per PDF point
            display_val_per_pt, display_unit = self.convert_units(self.absolute_scale, unit)
            scale_display_text = f"1 pt ≈ {display_val_per_pt:.4f} {display_unit}" # Show scale per PDF point
            self.scale_info.config(text=scale_display_text)
        else:
            self.scale_info.config(text="Non définie")

    def calculate_product_totals(self):
        """Calcule les totaux agrégés par produit et type de mesure, incluant le coût."""
        print("[DEBUG] Début du calcul des totaux de produits...")
        totals = {} # Format: {product_name: {agg_type: {total_base: float, count: int, cost: float}, "category": str}}
                    # agg_type sera 'distance' (pour distance/perimeter) ou 'surface'
                    # total_base sera en mètres ou mètres carrés

        if not self.absolute_scale:
            # On ne peut pas calculer de totaux significatifs sans échelle
            print("[Avertissement] Calcul des totaux impossible: échelle non définie.")
            return None # Retourne None pour indiquer l'échec

        for measure in self.measures:
            product_name = measure.get("product_name")
            if not product_name:
                continue # Passer les mesures sans produit associé

            measure_type = measure.get("type")
            value_pdf = measure.get("value") # Valeur en unités PDF ou degrés
            category = measure.get("product_category", "Inconnue")

            # Récupérer les attributs du produit pour obtenir le prix
            product_attributes = measure.get("product_attributes", {})
            product_price = None
            price_unit = "metric" # Unité de prix par défaut (métrique)
            
            if product_attributes:
                price_val = product_attributes.get("prix")
                price_unit = product_attributes.get("price_unit", "metric") # Récupérer l'unité de prix
                print(f"[DEBUG] Produit '{product_name}' - Valeur prix brute: {price_val}, Unité: {price_unit}")
                
                product_price = float(price_val) if isinstance(price_val, (int, float)) else None
                if price_val is not None and not isinstance(price_val, (int, float)):
                    # Essayer de convertir une chaîne en nombre
                    try:
                        if isinstance(price_val, str):
                            product_price = float(price_val.replace(',', '.'))
                    except ValueError:
                        print(f"[DEBUG] Impossible de convertir '{price_val}' en nombre")

                print(f"[DEBUG] Produit '{product_name}' - Prix récupéré: {price_val}, Converti en: {product_price}")

            agg_type = None
            base_value = 0.0 # Valeur en mètres ou m²
            imperial_value = 0.0 # Valeur en pieds ou ft²
            cost = 0.0 # Coût en $CAD

            if measure_type == "distance" or measure_type == "perimeter":
                agg_type = "distance"
                base_value = value_pdf * self.absolute_scale # Mètres
                imperial_value = base_value * 3.28084 # Conversion en pieds (1m = 3.28084ft)
                
                # Calculer le coût si le prix est disponible
                if product_price is not None:
                    if price_unit == "imperial":
                        # Prix par pied, utiliser directement la valeur impériale
                        cost = imperial_value * product_price
                        print(f"[DEBUG] Distance/Périmètre - Base: {imperial_value:.2f}ft, Prix: {product_price:.2f}/ft, Coût: {cost:.2f}")
                    else:
                        # Prix par mètre, utiliser la valeur métrique
                        cost = base_value * product_price
                        print(f"[DEBUG] Distance/Périmètre - Base: {base_value:.2f}m, Prix: {product_price:.2f}/m, Coût: {cost:.2f}")
                else:
                    print(f"[DEBUG] Distance/Périmètre - Prix non disponible pour '{product_name}'")
            
            elif measure_type == "surface":
                agg_type = "surface"
                base_value = value_pdf * (self.absolute_scale ** 2) # Mètres carrés
                imperial_value = base_value * 10.7639 # Conversion en pieds carrés (1m² = 10.7639ft²)
                
                # Calculer le coût si le prix est disponible
                if product_price is not None:
                    if price_unit == "imperial":
                        # Prix par pied carré, utiliser directement la valeur impériale
                        cost = imperial_value * product_price
                        print(f"[DEBUG] Surface - Base: {imperial_value:.2f}ft², Prix: {product_price:.2f}/ft², Coût: {cost:.2f}")
                    else:
                        # Prix par mètre carré, utiliser la valeur métrique
                        cost = base_value * product_price
                        print(f"[DEBUG] Surface - Base: {base_value:.2f}m², Prix: {product_price:.2f}/m², Coût: {cost:.2f}")
                else:
                    print(f"[DEBUG] Surface - Prix non disponible pour '{product_name}'")
            else:
                print(f"[DEBUG] Type de mesure ignoré: {measure_type}")
                continue # Ignorer les types non sommables comme 'angle'

            # Initialiser l'entrée produit si elle n'existe pas
            if product_name not in totals:
                totals[product_name] = {"category": category}

            # Initialiser l'entrée type d'agrégation si elle n'existe pas
            if agg_type not in totals[product_name]:
                totals[product_name][agg_type] = {"total_base": 0.0, "total_imperial": 0.0, "count": 0, "cost": 0.0, "price_unit": price_unit}

            # Ajouter la valeur, le coût et incrémenter le compteur
            totals[product_name][agg_type]["total_base"] += base_value
            totals[product_name][agg_type]["total_imperial"] += imperial_value
            totals[product_name][agg_type]["cost"] += cost
            totals[product_name][agg_type]["count"] += 1
            
            print(f"[DEBUG] Ajout pour '{product_name}', type {agg_type}: +{base_value:.2f}m/m², +{imperial_value:.2f}ft/ft², +{cost:.2f}$, +1 mesure")

        print(f"[DEBUG] Totaux calculés pour {len(totals)} produits")
        return totals

    def populate_totals_tree(self, totals_data):
        """Remplit le Treeview des totaux avec les données calculées, incluant le coût."""
        # S'assurer que le widget Treeview existe
        if not self.totals_list:
            print("Erreur: Le Treeview des totaux n'est pas initialisé.")
            return

        # Effacer les éléments précédents
        for item in self.totals_list.get_children():
            self.totals_list.delete(item)

        if totals_data is None:
            # Afficher un message si l'échelle n'est pas définie
            self.totals_list.insert("", "end", text="Échelle non définie.", open=False, tags=("message",))
            self.totals_list.tag_configure("message", foreground="gray")
            self.total_cost_label.config(text="Coût Total: 0.00 $CAD") # Réinitialiser le coût total
            return
        if not totals_data:
            self.totals_list.insert("", "end", text="Aucun produit associé aux mesures.", open=False, tags=("message",))
            self.totals_list.tag_configure("message", foreground="gray")
            self.total_cost_label.config(text="Coût Total: 0.00 $CAD") # Réinitialiser le coût total
            return

        target_unit = self.unit_var.get()
        grand_total_cost = 0.0 # Pour calculer le coût total de tous les produits
        print(f"[DEBUG] Affichage des totaux pour {len(totals_data)} produits")

        # Trier les produits par nom pour l'affichage
        sorted_products = sorted(totals_data.keys())

        for product_name in sorted_products:
            product_data = totals_data[product_name]
            category = product_data.get("category", "")
            display_product_name = f"{product_name} ({category})" if category else product_name

            # Insérer le produit comme parent
            product_iid = self.totals_list.insert("", "end", text=display_product_name, open=True) # Ouvrir par défaut
            
            product_total_cost = 0.0 # Pour calculer le coût total par produit

            # Trier les types d'agrégation (e.g., distance avant surface)
            agg_types_sorted = sorted(key for key in product_data if key != "category")
            print(f"[DEBUG] Produit '{product_name}' - Types d'agrégation: {agg_types_sorted}")

            for agg_type in agg_types_sorted:
                agg_data = product_data[agg_type]
                total_base = agg_data["total_base"]
                total_imperial = agg_data.get("total_imperial", 0.0)
                count = agg_data["count"]
                cost = agg_data.get("cost", 0.0)  # Récupérer le coût, 0.0 par défaut
                price_unit = agg_data.get("price_unit", "metric")
                
                print(f"[DEBUG] Pour '{product_name}', type {agg_type} - Total base: {total_base:.2f}m/m², Total imp: {total_imperial:.2f}ft/ft², Unité prix: {price_unit}, Coût: {cost:.2f}, Nb mesures: {count}")
                
                product_total_cost += cost  # Additionner au total du produit
                grand_total_cost += cost    # Additionner au grand total

                display_value = 0.0
                display_unit_symbol = ""
                type_text = "" # Texte pour la colonne Type Mesure

                if agg_type == "distance":
                    if price_unit == "imperial":
                        # Afficher en unités impériales
                        display_value = total_imperial
                        display_unit_symbol = "ft"
                    else:
                        # Afficher en unités métriques selon préférence utilisateur
                        display_value, display_unit_symbol = self.convert_units(total_base, target_unit)
                    type_text = "Longueur totale"
                elif agg_type == "surface":
                    if price_unit == "imperial":
                        # Afficher en unités impériales
                        display_value = total_imperial
                        display_unit_symbol = "ft²"
                    else:
                        # Afficher en unités métriques selon préférence utilisateur
                        display_value, display_unit_symbol = self.convert_area_units(total_base, target_unit)
                        if display_unit_symbol != "ft":  # Ajouter le carré sauf si déjà en ft²
                            display_unit_symbol += "²"
                    type_text = "Surface totale"

                # Formater la valeur et le coût
                formatted_value = f"{display_value:.2f}"
                formatted_cost = f"{cost:.2f}"

                # Insérer la ligne de total pour ce type avec le coût
                values_tuple = (type_text, formatted_value, display_unit_symbol, count, formatted_cost)
                self.totals_list.insert(product_iid, "end", values=values_tuple)
                print(f"[DEBUG] Ligne ajoutée: {values_tuple}")
            
            # Optionnel: Ajouter une ligne de total pour le produit
            if len(agg_types_sorted) > 1:  # Seulement si le produit a plusieurs types de mesures
                self.totals_list.insert(product_iid, "end", values=("TOTAL PRODUIT", "", "", "", f"{product_total_cost:.2f}"), 
                                      tags=("product_total",))
                self.totals_list.tag_configure("product_total", background="#f0f0f0", font=("Arial", 9, "bold"))
                print(f"[DEBUG] Total produit '{product_name}': {product_total_cost:.2f}")

        # Mettre à jour le label du coût total
        self.total_cost_label.config(text=f"Coût Total: {grand_total_cost:.2f} $CAD")
        print(f"[DEBUG] Grand total calculé: {grand_total_cost:.2f} $CAD")

    def update_product_totals_display(self):
        """Calcule et met à jour l'affichage des totaux par produit."""
        print("[DEBUG] Mise à jour de l'affichage des totaux produits...") # Debug
        calculated_totals = self.calculate_product_totals()
        self.populate_totals_tree(calculated_totals)
    # --- FIN DES NOUVELLES MÉTHODES POUR LES TOTAUX ---


    def select_product_dialog(self):
        """Affiche une boîte de dialogue pour sélectionner un produit du catalogue."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Sélectionner Produit")
        dialog.geometry("450x350")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.colors["bg_light"])

        tk.Label(dialog, text="Sélectionnez un produit à associer:",
                 font=("Arial", 12, "bold"), bg=self.colors["bg_light"]).pack(pady=(15, 10))

        select_frame = ttk.Frame(dialog)
        select_frame.pack(pady=5, fill=tk.X, padx=20)

        # Category Selector
        ttk.Label(select_frame, text="Catégorie:").grid(row=0, column=0, sticky=tk.W, pady=5, padx=5)
        category_var = tk.StringVar()
        category_combo = ttk.Combobox(select_frame, textvariable=category_var, width=35, state="readonly")
        category_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=5)
        categories = self.product_catalog.get_categories()
        categories.sort()
        category_combo['values'] = categories

        # Product Selector
        ttk.Label(select_frame, text="Produit:").grid(row=1, column=0, sticky=tk.W, pady=5, padx=5)
        product_var = tk.StringVar()
        product_combo = ttk.Combobox(select_frame, textvariable=product_var, width=35, state="readonly")
        product_combo.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=5)

        select_frame.columnconfigure(1, weight=1) # Allow comboboxes to expand

        # Info Display
        info_frame = ttk.LabelFrame(dialog, text="Détails Produit", style="TLabelframe")
        info_frame.pack(pady=10, fill=tk.X, padx=20)
        product_info_label = ttk.Label(info_frame, text="Sélectionnez un produit...", justify=tk.LEFT, wraplength=380)
        product_info_label.pack(pady=5, padx=10, anchor=tk.W)


        # --- Dialog Logic ---
        result = [None] # Store selection (category, product)

        def update_products(*args):
            sel_category = category_var.get()
            products = self.product_catalog.get_products(sel_category)
            products.sort()
            product_combo['values'] = products
            if products:
                product_var.set(products[0]) # Auto-select first product
            else:
                product_var.set("")
            update_product_info() # Update details display

        def update_product_info(*args):
            category = category_var.get()
            product = product_var.get()
            if category and product:
                attrs = self.product_catalog.get_product_attributes(category, product)
                if attrs:
                    dims = attrs.get('dimensions', 'N/A')
                    price_val = attrs.get('prix')
                    price_str = f"{price_val:.2f} $CAD" if isinstance(price_val, (int, float)) else "N/A"
                    color_str = attrs.get('color', 'N/A') # Get color info too
                    info_text = f"Dimensions: {dims}\nPrix: {price_str}\nCouleur: {color_str}"
                    product_info_label.config(text=info_text)
                else:
                    product_info_label.config(text="Attributs non trouvés.")
            else:
                product_info_label.config(text="Sélectionnez un produit...")

        category_var.trace_add("write", update_products)
        product_var.trace_add("write", update_product_info)

        # Initialize with first category if available
        if categories:
            category_var.set(categories[0])


        def on_ok():
            if category_var.get() and product_var.get():
                result[0] = (category_var.get(), product_var.get())
            dialog.destroy()

        def on_cancel():
            result[0] = None
            dialog.destroy()

        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=15)
        ttk.Button(button_frame, text="OK", command=on_ok, style="Action.TButton").pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="Annuler", command=on_cancel).pack(side=tk.LEFT, padx=10)

        # Bind Enter/Esc
        dialog.bind('<Return>', lambda event=None: on_ok())
        dialog.bind('<Escape>', lambda event=None: on_cancel())


        # Center and wait
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 3) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        self.root.wait_window(dialog)
        return result[0]


    # --- UI Updates ---

    def update_document_info(self):
        """Met à jour les informations du document dans le panneau latéral."""
        if not self.pdf_document:
            self.doc_info.config(text="Aucun document ouvert")
            return

        try:
            metadata = self.pdf_document.metadata or {} # Ensure metadata is a dict
            info_lines = [
                 f"Fichier: {os.path.basename(self.pdf_path or 'N/A')}",
                 f"Pages: {self.pdf_document.page_count}",
            ]
            # Page dimensions
            page = self.pdf_document[self.current_page]
            width_pt, height_pt = page.rect.width, page.rect.height
            info_lines.append(f"Dim Page: {width_pt:.1f} x {height_pt:.1f} pt")

            self.doc_info.config(text="\n".join(info_lines))
        except Exception as e:
            print(f"Erreur lors de la mise à jour des infos document: {e}")
            self.doc_info.config(text="Erreur lecture infos")

    def toggle_line_display(self):
        """Active ou désactive l'affichage des lignes détectées."""
        if self.show_detected_lines.get():
            self.display_detected_lines()
        else:
            self.canvas.delete("detected_lines")

    def display_detected_lines(self):
        """Affiche les lignes détectées sur le canvas pour la page courante."""
        if not self.pdf_document or not self.show_detected_lines.get():
            return

        self.canvas.delete("detected_lines") # Clear previous lines

        lines_to_draw = self.lines_by_page.get(self.current_page, [])
        if not lines_to_draw:
             return

        # Use same factor as page display
        display_resolution_factor = max(self.zoom_factor, 1.0) * 1.5
        line_color = "#ADD8E6" # Light blue for detected lines

        for line in lines_to_draw:
            (x0_pdf, y0_pdf), (x1_pdf, y1_pdf) = line
            # Convert PDF points to display coords
            x0_disp, y0_disp = x0_pdf * display_resolution_factor, y0_pdf * display_resolution_factor
            x1_disp, y1_disp = x1_pdf * display_resolution_factor, y1_pdf * display_resolution_factor

            self.canvas.create_line(x0_disp, y0_disp, x1_disp, y1_disp,
                                  fill=line_color, width=1, dash=(1, 3), # Dotted line
                                  tags="detected_lines")
        # Ensure lines are drawn below measurements
        self.canvas.tag_lower("detected_lines", "measurement")


    # --- Navigation & Zoom ---

    def prev_page(self):
        """Va à la page précédente du PDF."""
        if self.pdf_document and self.current_page > 0:
            self.current_page -= 1
            self.points = [] # Clear points when changing page
            self.cancel_current_measurement() # Clear visuals too
            self.display_page()
            self.update_document_info() # Update info for new page dimensions etc.

    def next_page(self):
        """Va à la page suivante du PDF."""
        if self.pdf_document and self.current_page < self.pdf_document.page_count - 1:
            self.current_page += 1
            self.points = []
            self.cancel_current_measurement()
            self.display_page()
            self.update_document_info()

    def zoom_in(self, factor=1.2):
        """Augmente le zoom."""
        if not self.pdf_document: return
        self.zoom_factor *= factor
        self.zoom_level.config(text=f"{int(self.zoom_factor * 100)}%")
        # Scale info display doesn't change with zoom (it shows absolute scale)
        # self.update_scale_info_display() # No need to update scale label on zoom
        self.display_page() # Redraw page and measurements at new zoom

    def zoom_out(self, factor=1.2):
        """Diminue le zoom."""
        if not self.pdf_document: return
        new_zoom = self.zoom_factor / factor
        # Add a minimum zoom level to prevent issues
        min_zoom = 0.05
        if new_zoom < min_zoom:
             new_zoom = min_zoom
        if abs(self.zoom_factor - new_zoom) > 1e-6: # Avoid redraw if no change
             self.zoom_factor = new_zoom
             self.zoom_level.config(text=f"{int(self.zoom_factor * 100)}%")
             # self.update_scale_info_display() # No need here either
             self.display_page()

    def zoom_fit(self):
        """Ajuste le zoom pour adapter la page à la fenêtre."""
        if not self.pdf_document: return

        # Ensure canvas dimensions are available
        self.root.update_idletasks()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            print("Avertissement: Dimensions du Canvas invalides pour Zoom Fit.")
            return

        page = self.pdf_document[self.current_page]
        page_rect = page.rect
        if not page_rect or page_rect.is_empty or page_rect.width == 0 or page_rect.height == 0:
            print("Avertissement: Dimensions de la page invalides pour Zoom Fit.")
            return

        # Calculate zoom needed based on PDF points per display pixel
        # display_resolution_factor = zoom * base_factor (1.5)
        # zoom = (page_points / canvas_pixels) / base_factor

        try:
            base_factor = 1.5
            zoom_w = (canvas_width / (page_rect.width * base_factor)) if page_rect.width > 0 else 1.0
            zoom_h = (canvas_height / (page_rect.height * base_factor)) if page_rect.height > 0 else 1.0

        except ZeroDivisionError:
             return

        # Use the smaller ratio to fit the whole page, apply padding
        new_zoom_factor = min(zoom_w, zoom_h) * 0.95 # 5% padding

        # Apply minimum zoom limit
        min_zoom = 0.05
        if new_zoom_factor < min_zoom: new_zoom_factor = min_zoom

        if abs(self.zoom_factor - new_zoom_factor) > 1e-6:
             self.zoom_factor = new_zoom_factor
             self.zoom_level.config(text=f"{int(self.zoom_factor * 100)}%")
             # self.update_scale_info_display()
             self.display_page()


    def on_mousewheel(self, event, delta_override=None):
        """Gestion du zoom avec la molette."""
        if not self.pdf_document: return

        # Determine scroll direction (platform differences)
        delta = 0
        if delta_override is not None: # Linux Button-4 / Button-5
             delta = delta_override
        elif os.name == 'nt' or sys.platform == 'darwin': # Windows or macOS
             # Tentez d'utiliser une valeur brute si event.delta est parfois 0 mais que l'événement se produit
             delta = event.delta if event.delta != 0 else (1 if event.num == 4 else (-1 if event.num == 5 else 0)) # Fallback pour delta 0
             # Normalisation habituelle si delta n'est pas 0
             if event.delta != 0: delta //= 120
        elif event.num == 5: # Linux scroll down
             delta = -1
        elif event.num == 4: # Linux scroll up
             delta = 1

        if delta == 0: return # No scroll detected

        # --- Zoom Centered on Cursor ---
        # 1. Get canvas coordinates under cursor BEFORE zoom
        x_canvas_before, y_canvas_before = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

        # 2. Apply zoom
        zoom_amount = 1.15 # Smaller zoom step for mouse wheel
        old_zoom_factor = self.zoom_factor # Store old zoom factor
        if delta > 0:
             self.zoom_factor *= zoom_amount
        elif delta < 0:
             new_zoom = self.zoom_factor / zoom_amount
             min_zoom = 0.05
             self.zoom_factor = max(new_zoom, min_zoom)

        # Only proceed if zoom actually changed
        if abs(self.zoom_factor - old_zoom_factor) > 1e-6:
            self.zoom_level.config(text=f"{int(self.zoom_factor * 100)}%")
            self.display_page() # Redraw page and measurements at new zoom

            # ---> AJOUT CRUCIAL <---
            # Force Tkinter à traiter les mises à jour d'affichage/géométrie
            # avant de recalculer les coordonnées.
            self.root.update_idletasks()
            # ----------------------

            # 3. Get canvas coordinates under cursor AFTER redraw AND update
            x_canvas_after, y_canvas_after = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)

            # 4. Calculate scroll amount needed
            scroll_x = x_canvas_after - x_canvas_before
            scroll_y = y_canvas_after - y_canvas_before

            # 5. Apply scroll (only if the scroll amount is significant)
            # Convertir en entier est nécessaire pour view_scroll, mais vérifions si c'est >= 1
            scroll_x_int = int(scroll_x)
            scroll_y_int = int(scroll_y)

            if abs(scroll_x_int) >= 1:
                self.canvas.xview_scroll(scroll_x_int, "units")
            if abs(scroll_y_int) >= 1:
                self.canvas.yview_scroll(scroll_y_int, "units")

        # Optionnel: Mettre à jour la barre de statut ou autre feedback
        # self.status_bar.config(text=f"Zoom: {int(self.zoom_factor*100)}%")


    # --- Mode Setting ---

    def set_mode(self, mode):
        """Change le mode de mesure et met à jour l'interface."""
        if self.mode == mode: return # No change

        print(f"Changement de mode vers: {mode}")
        self.mode = mode
        self.cancel_current_measurement() # Clear points and temporary visuals

        # Update button states to visually indicate the active mode
        buttons = {
            "distance": self.distance_btn,
            "surface": self.surface_btn,
            "perimeter": self.perimeter_btn,
            "angle": self.angle_btn,
            "calibration": self.calibrate_btn
        }
        # Use a dedicated style for pressed state? Or rely on ttk internal state visuals?
        # Changing relief might be the simplest cross-platform visual cue
        active_relief = "sunken"
        inactive_relief = "flat" # Or 'raised' which is default for some themes

        for btn_mode, button_widget in buttons.items():
             if button_widget: # Check if button exists
                 try:
                     if btn_mode == mode:
                         button_widget.config(relief=active_relief)
                     else:
                         # Ensure default relief for the theme is restored correctly.
                         # 'flat' might not be the default for all themes/buttons.
                         # Getting default might be complex. Let's stick with 'flat' for now.
                         button_widget.config(relief=inactive_relief)
                 except tk.TclError as e:
                     print(f"Warning: Could not set relief for button {btn_mode}: {e}")


        # Update mode label and status bar message
        mode_texts = {
            "distance": "Mode: Mesure de distance",
            "surface": "Mode: Mesure de surface",
            "perimeter": "Mode: Mesure de périmètre",
            "angle": "Mode: Mesure d'angle",
            "calibration": "Mode: Calibration d'échelle"
        }
        base_text = mode_texts.get(mode, f'Mode: {mode}')

        # Add specific instructions for first click
        instruction = "Prêt."
        if mode == "distance": instruction = "Cliquez le premier point."
        elif mode == "surface": instruction = "Cliquez le premier point (Double-clic ou Entrée pour finir)."
        elif mode == "perimeter": instruction = "Cliquez le premier point (Double-clic ou Entrée pour finir)."
        elif mode == "angle": instruction = "Cliquez le premier point (bras 1)."
        elif mode == "calibration": instruction = "Cliquez le premier point connu."

        self.status_bar.config(text=f"{base_text}. {instruction}")


    # --- Menu & Project Handling ---

    def create_menu(self):
        """Crée la barre de menu principale."""
        self.menu_bar = tk.Menu(self.root)
        self.root.config(menu=self.menu_bar)

        # --- Menu Fichier ---
        file_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Fichier", menu=file_menu)
        file_menu.add_command(label="Ouvrir PDF...", command=self.open_pdf, accelerator="Ctrl+O")
        file_menu.add_separator()
        file_menu.add_command(label="Ouvrir Projet...", command=self.load_project, accelerator="Ctrl+P")
        file_menu.add_command(label="Enregistrer Projet...", command=self.save_project, accelerator="Ctrl+S")

        # Submenu for recent projects
        self.recent_menu = tk.Menu(file_menu, tearoff=0)
        file_menu.add_cascade(label="Projets Récents", menu=self.recent_menu)

        file_menu.add_separator()
        file_menu.add_command(label="Exporter Mesures...", command=self.export_measurements, accelerator="Ctrl+E")
        file_menu.add_separator()
        file_menu.add_command(label="Quitter", command=self.on_closing) # Use on_closing for clean exit


        # --- Menu Edition ---
        edit_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Edition", menu=edit_menu)
        edit_menu.add_command(label="Annuler Mesure en Cours", command=self.cancel_current_measurement, accelerator="Esc")
        edit_menu.add_separator()
        edit_menu.add_command(label="Supprimer Mesure(s) Sélectionnée(s)", command=self.delete_selected_measure, accelerator="Suppr")
        edit_menu.add_command(label="Effacer Toutes Mesures", command=self.clear_all_measures)


        # --- Menu Affichage ---
        view_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Affichage", menu=view_menu)
        view_menu.add_command(label="Zoom Avant", command=self.zoom_in, accelerator="Ctrl++")
        view_menu.add_command(label="Zoom Arrière", command=self.zoom_out, accelerator="Ctrl+-")
        view_menu.add_command(label="Ajuster à la Page", command=self.zoom_fit, accelerator="Ctrl+0")
        view_menu.add_separator()
        view_menu.add_checkbutton(label="Afficher Lignes Détectées", variable=self.show_detected_lines, command=self.toggle_line_display)


        # --- Menu Outils ---
        tools_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Outils", menu=tools_menu)
        tools_menu.add_command(label="Distance", command=lambda: self.set_mode("distance"), accelerator="F2")
        tools_menu.add_command(label="Surface (Aire)", command=lambda: self.set_mode("surface"), accelerator="F3")
        tools_menu.add_command(label="Périmètre", command=lambda: self.set_mode("perimeter"), accelerator="F6")
        tools_menu.add_command(label="Angle", command=lambda: self.set_mode("angle"), accelerator="F7")
        tools_menu.add_separator()
        tools_menu.add_command(label="Calibrer Échelle", command=lambda: self.set_mode("calibration"), accelerator="F4")
        tools_menu.add_separator()
        tools_menu.add_command(label="Terminer Mesure Surface/Périmètre", command=self.finalize_shape_if_possible, accelerator="Entrée") # Maybe Enter?
        tools_menu.add_separator()
        tools_menu.add_command(label="Extraire Lignes PDF", command=self.extract_lines_from_pdf)
        tools_menu.add_separator()
        tools_menu.add_command(label="Analyser PDF avec IA", command=self.analyze_with_ai, accelerator="F5")
        tools_menu.add_command(label="Gérer Profils Experts IA", command=self.manage_profiles)


        # --- Menu Aide ---
        help_menu = tk.Menu(self.menu_bar, tearoff=0)
        self.menu_bar.add_cascade(label="Aide", menu=help_menu)
        help_menu.add_command(label="Afficher l'Aide...", command=self.show_help, accelerator="F1")
        help_menu.add_command(label="À Propos...", command=self.show_about)


        # --- Bind Keyboard Shortcuts ---
        self.root.bind("<Control-o>", lambda e: self.open_pdf())
        self.root.bind("<Control-O>", lambda e: self.open_pdf()) # Uppercase too
        self.root.bind("<Control-s>", lambda e: self.save_project())
        self.root.bind("<Control-S>", lambda e: self.save_project())
        self.root.bind("<Control-p>", lambda e: self.load_project()) # For loading Project
        self.root.bind("<Control-P>", lambda e: self.load_project())
        self.root.bind("<Control-e>", lambda e: self.export_measurements())
        self.root.bind("<Control-E>", lambda e: self.export_measurements())
        self.root.bind("<Control-0>", lambda e: self.zoom_fit())
        self.root.bind("<Control-equal>", lambda e: self.zoom_in()) # Ctrl +
        self.root.bind("<Control-plus>", lambda e: self.zoom_in()) # Ctrl + (Numpad)
        self.root.bind("<Control-minus>", lambda e: self.zoom_out()) # Ctrl -

        self.root.bind("<F1>", lambda e: self.show_help())
        self.root.bind("<F2>", lambda e: self.set_mode("distance"))
        self.root.bind("<F3>", lambda e: self.set_mode("surface"))
        self.root.bind("<F4>", lambda e: self.set_mode("calibration"))
        self.root.bind("<F5>", lambda e: self.analyze_with_ai())
        self.root.bind("<F6>", lambda e: self.set_mode("perimeter"))
        self.root.bind("<F7>", lambda e: self.set_mode("angle"))

        self.root.bind("<Delete>", lambda e: self.delete_selected_measure())
        self.root.bind("<Escape>", self.cancel_current_measurement)
        self.root.bind("<Return>", lambda e: self.finalize_shape_if_possible()) # Enter to finalize shape


    def cancel_current_measurement(self, event=None):
         """Annule la mesure en cours (efface les points temporaires et les visuels)."""
         if self.points: # If a measurement is in progress
              print("Annulation de la mesure en cours...")
              self.points = []
              # Clear all temporary visuals
              self.canvas.delete("measurement_temp_poly", "measurement_temp_dist", "measurement_temp_angle", "temp_line", "temp_angle", "calibration_visual", "snap_indicator", "ortho_indicator")
              # Reset status bar prompt for the current mode
              self.set_mode(self.mode) # Call set_mode to reset status text
         # else: print("Aucune mesure en cours à annuler.")


    def save_project(self):
        """Sauvegarde l'état actuel du projet (PDF, mesures, échelle, etc.)."""
        if not self.pdf_path: # Check if a PDF was ever loaded
            messagebox.showinfo("Information", "Aucun document PDF n'est associé à ce projet.", parent=self.root)
            return

        # Suggest a filename based on PDF name
        pdf_basename = os.path.basename(self.pdf_path)
        project_filename_suggestion = os.path.splitext(pdf_basename)[0] + ".tak" # Custom extension

        file_path = filedialog.asksaveasfilename(
            title="Enregistrer le Projet TakeOff AI",
            defaultextension=".tak",
            filetypes=[("Projets TakeOff AI", "*.tak"), ("Tous les fichiers", "*.*")],
            initialfile=project_filename_suggestion,
            parent=self.root
        )

        if not file_path:
            return # User cancelled

        try:
            # Ensure catalog is saved before saving the project that embeds it
            if self.product_catalog.is_dirty:
                 print("[DEBUG] Sauvegarde du catalogue avant sauvegarde du projet...")
                 if not self.product_catalog.save_catalog_to_appdata():
                      messagebox.showwarning("Erreur Sauvegarde Catalogue", "Le catalogue n'a pas pu être sauvegardé.\nLe projet sera sauvegardé avec la version en mémoire du catalogue.", parent=self.root)


            # --- REVISED: Store PDF points directly ---
            # Measures already contain PDF points if logic was updated correctly
            measures_to_save = self.measures

            # Gather project data
            project_data = {
                "version": "1.2", # Incremented version due to PDF point storage change
                "pdf_path_relative": os.path.relpath(self.pdf_path, os.path.dirname(file_path)), # Store relative path
                "pdf_path_absolute": self.pdf_path, # Store absolute as fallback
                "absolute_scale": self.absolute_scale, # meters per PDF point
                "unit": self.unit_var.get(),
                "measures": measures_to_save, # Should contain PDF points and potentially color
                "current_page": self.current_page,
                # Save config settings
                "config": {
                    "colors": {
                        "distance": self.distance_color.get(),
                        "surface_outline": self.surface_color.get(),
                        "surface_fill": self.surface_fill_color.get(),
                        "angle": self.angle_color.get(),
                        "point": self.point_color.get()
                    },
                    "transparency": self.fill_transparency.get(),
                    "snapping": {
                        "enabled": self.enable_snapping.get(),
                        "threshold": self.snap_threshold.get(),
                        "endpoints": self.snap_to_endpoints.get(),
                        "midpoints": self.snap_to_midpoints.get(),
                        "intersections": self.snap_to_intersections.get()
                    }
                },
                "product_catalog": self.product_catalog.categories # Embed catalog
                # Could also save view state (zoom/scroll)? More complex.
            }

            # Save to JSON file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2)

            self.status_bar.config(text=f"Projet enregistré: {os.path.basename(file_path)}")
            self.add_recent_project(file_path) # Add saved project to recent list
            self.display_ai_message("system", f"Projet sauvegardé sous {os.path.basename(file_path)}")

        except Exception as e:
            messagebox.showerror("Erreur Sauvegarde", f"Impossible d'enregistrer le projet:\n{str(e)}", parent=self.root)


    def load_project(self, file_path=None):
        """Charge un projet sauvegardé."""
        if not file_path:
            file_path = filedialog.askopenfilename(
                title="Ouvrir un Projet TakeOff AI",
                filetypes=[("Projets TakeOff AI", "*.tak"), ("Tous les fichiers", "*.*")],
                parent=self.root
            )

        if not file_path:
            return # User cancelled

        # --- MODIFICATION: Save current catalog if dirty? ---
        if self.product_catalog.is_dirty:
             if messagebox.askyesno("Catalogue Modifié", "Le catalogue actuel a des modifications non enregistrées.\nVoulez-vous les enregistrer avant d'ouvrir le projet?", parent=self.root):
                  if not self.product_catalog.save_catalog_to_appdata():
                       messagebox.showerror("Erreur Sauvegarde", "Impossible d'enregistrer les modifications du catalogue.", parent=self.root)
                       # Ask if user wants to continue loading despite save failure?
                       if not messagebox.askyesno("Continuer?", "Le catalogue n'a pas pu être sauvegardé.\nContinuer à charger le projet (les modifications du catalogue seront perdues)?", icon='warning', parent=self.root):
                            return # Abort loading


        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)

            # --- Find and Validate PDF Path ---
            pdf_found = False
            pdf_to_load = None
            # 1. Try relative path first
            pdf_path_relative = project_data.get("pdf_path_relative")
            if pdf_path_relative:
                potential_path = os.path.abspath(os.path.join(os.path.dirname(file_path), pdf_path_relative))
                if os.path.exists(potential_path):
                    pdf_to_load = potential_path
                    pdf_found = True

            # 2. If relative failed, try absolute path
            if not pdf_found:
                pdf_path_absolute = project_data.get("pdf_path_absolute")
                if pdf_path_absolute and os.path.exists(pdf_path_absolute):
                     pdf_to_load = pdf_path_absolute
                     pdf_found = True

            # 3. If both failed, ask user to locate the PDF
            if not pdf_found:
                 pdf_original_name = os.path.basename(project_data.get("pdf_path_absolute", "document.pdf"))
                 messagebox.showwarning("PDF Manquant", f"Le fichier PDF d'origine '{pdf_original_name}' est introuvable aux emplacements enregistrés.\n\nVeuillez localiser ce fichier.", parent=self.root)
                 pdf_to_load = filedialog.askopenfilename(
                      title=f"Localiser '{pdf_original_name}'",
                      filetypes=[("Fichiers PDF", "*.pdf"), ("Tous les fichiers", "*.*")],
                      parent=self.root
                 )
                 if not pdf_to_load:
                      messagebox.showerror("Chargement Annulé", "Impossible de charger le projet sans le fichier PDF associé.", parent=self.root)
                      return
                 pdf_found = True # Assume user selected correctly


            # --- Load PDF ---
            # open_pdf handles closing old, clearing state, extracting lines
            # Important : Reset selected_measure_id before loading PDF which calls redraw
            self.selected_measure_id = None
            self.open_pdf(pdf_to_load)
            if not self.pdf_document: # Check if PDF opening failed inside open_pdf
                 raise RuntimeError("Échec de l'ouverture du PDF associé au projet.")

            # --- Restore Project State (after open_pdf clears things) ---
            # Version check (optional)
            project_version = project_data.get("version", "1.0")
            print(f"Chargement projet version {project_version}")

            self.absolute_scale = project_data.get("absolute_scale") # meters per PDF point
            self.unit_var.set(project_data.get("unit", "m"))
            self.current_page = project_data.get("current_page", 0)
            # Ensure current_page is valid
            if not (0 <= self.current_page < self.pdf_document.page_count):
                 self.current_page = 0

            # Restore config
            config = project_data.get("config", {})
            colors_cfg = config.get("colors", {})
            self.distance_color.set(colors_cfg.get("distance", "#0000FF"))
            self.surface_color.set(colors_cfg.get("surface_outline", "#00FF00"))
            self.surface_fill_color.set(colors_cfg.get("surface_fill", "#3498DB"))
            self.angle_color.set(colors_cfg.get("angle", "#FF00FF"))
            self.point_color.set(colors_cfg.get("point", "#FF0000"))
            self.fill_transparency.set(config.get("transparency", 50))

            snapping = config.get("snapping", {})
            self.enable_snapping.set(snapping.get("enabled", True))
            self.snap_threshold.set(snapping.get("threshold", 10))
            self.snap_to_endpoints.set(snapping.get("endpoints", True))
            self.snap_to_midpoints.set(snapping.get("midpoints", True))
            self.snap_to_intersections.set(snapping.get("intersections", True))

            # Restore product catalog embedded in the project
            catalog_data = project_data.get("product_catalog")
            if catalog_data is not None:
                self.product_catalog.categories = catalog_data
                # Mark as dirty because it came from project, not default AppData file
                self.product_catalog.mark_dirty()
                # Ask user if they want to save this loaded catalog to AppData?
                # Or just save automatically on close? Let's save on close via on_closing.
                self.populate_catalog_tree()
                self.update_category_dropdown()

            # Restore measures
            # --- Ensure measures contain PDF points ---
            loaded_measures = project_data.get("measures", [])
            # Add validation if needed, e.g., check if 'points' exist and are lists of tuples/lists
            # Also ensure 'color' key exists (add if missing from older projects)
            for measure in loaded_measures:
                if 'color' not in measure:
                    measure['color'] = None # Add default None if missing
            self.measures = loaded_measures


            # Reset selected measure ID after loading measures
            self.selected_measure_id = None

            # Update scale display and recalculate measure display text
            self.update_scale_info_display()
            self.update_measurements_display_units() # Recalculates and updates list/canvas


            # --- Final UI Updates ---
            self.display_page() # Display the correct page (calls redraw_measurements)
            self.update_document_info()
            self.status_bar.config(text=f"Projet chargé: {os.path.basename(file_path)}")
            self.root.title(f"TakeOff AI - {os.path.basename(file_path)}") # Update window title
            self.add_recent_project(file_path) # Add loaded project to recent list

            self.update_product_totals_display() # <--- AJOUTER CET APPEL (déplacé de la fin du bloc try)
            self.display_ai_message("system", f"Projet '{os.path.basename(file_path)}' chargé.")
            if self.absolute_scale:
                 self.display_ai_message("system", f"Échelle restaurée: {self.scale_info.cget('text')}. Unité: {self.unit_var.get()}.")
            else:
                 self.display_ai_message("system", "Aucune échelle n'était définie dans ce projet.")


        except FileNotFoundError:
             messagebox.showerror("Erreur Chargement", f"Le fichier projet '{os.path.basename(file_path)}' est introuvable.", parent=self.root)
        except json.JSONDecodeError:
             messagebox.showerror("Erreur Chargement", f"Le fichier projet '{os.path.basename(file_path)}' est corrompu ou n'est pas un fichier projet valide.", parent=self.root)
        except Exception as e:
            messagebox.showerror("Erreur Chargement", f"Impossible de charger le projet:\n{str(e)}", parent=self.root)
            # Reset state after failed load?
            if self.pdf_document: self.pdf_document.close()
            self.pdf_document = None
            self.pdf_path = None
            self.measures = []
            self.lines_by_page = {}
            self.absolute_scale = None
            self.selected_measure_id = None
            self.canvas.delete("all")
            self.update_measures_list()
            self.update_document_info()
            self.update_scale_info_display()
            self.update_product_totals_display() # Reset totals on failed load
            self.status_bar.config(text="Échec du chargement du projet. Prêt.")
            self.root.title("TakeOff AI")

    def load_recent_projects(self):
        """Charge la liste des chemins de projets récents depuis AppData."""
        recent_file = os.path.join(get_app_data_path(), "recent.json")
        try:
            if os.path.exists(recent_file):
                with open(recent_file, 'r', encoding='utf-8') as f:
                    # Filter out paths that no longer exist
                    recent_paths = json.load(f)
                    # --- AJOUT IMPORTANT : Filtrer les chemins non valides ou inexistants ---
                    valid_paths = []
                    if isinstance(recent_paths, list): # Assurer que c'est une liste
                        for p in recent_paths:
                            if isinstance(p, str) and os.path.exists(p): # Vérifier type et existence
                                valid_paths.append(p)
                    return valid_paths
            return []
        except (json.JSONDecodeError, OSError, TypeError) as e:
            print(f"Erreur lecture projets récents ({recent_file}): {e}")
            # If file is corrupted, try deleting it? Or just return empty.
            # try: os.remove(recent_file) except: pass
            return []

    def save_recent_projects(self):
        """Sauvegarde la liste actuelle des projets récents dans AppData."""
        recent_file = os.path.join(get_app_data_path(), "recent.json")
        try:
            # Ensure the list contains only valid strings
            valid_recent = [p for p in self.recent_projects if isinstance(p, str)]
            with open(recent_file, 'w', encoding='utf-8') as f:
                json.dump(valid_recent, f, indent=2) # Add indent for readability
        except Exception as e:
            print(f"Erreur sauvegarde projets récents ({recent_file}): {e}")


    def add_recent_project(self, file_path):
        """Ajoute un chemin de fichier à la liste des projets récents."""
        if not file_path or not isinstance(file_path, str): return

        abs_path = os.path.abspath(file_path)

        # Remove if already exists to move it to the top
        self.recent_projects = [p for p in self.recent_projects if p != abs_path]

        # Add to the beginning
        self.recent_projects.insert(0, abs_path)

        # Limit the list size
        max_recent = 10
        self.recent_projects = self.recent_projects[:max_recent]

        # Update menu and save the list
        self.update_recent_projects_menu()
        self.save_recent_projects()


    def update_recent_projects_menu(self):
        """Met à jour le sous-menu Fichier > Projets Récents."""
        self.recent_menu.delete(0, tk.END) # Clear existing items

        if not self.recent_projects:
            self.recent_menu.add_command(label="(Vide)", state=tk.DISABLED)
        else:
            for i, path in enumerate(self.recent_projects):
                 filename = os.path.basename(path)
                 label_text = f"{i+1}. {filename}"
                 # Use lambda with default argument to capture correct path
                 self.recent_menu.add_command(label=label_text, command=lambda p=path: self.load_project(p))
            self.recent_menu.add_separator()
            self.recent_menu.add_command(label="Effacer Liste", command=self.clear_recent_projects)


    def clear_recent_projects(self):
         """Efface la liste des projets récents."""
         if messagebox.askyesno("Effacer Récents", "Voulez-vous effacer la liste des projets récents?", parent=self.root):
              self.recent_projects = []
              self.update_recent_projects_menu()
              self.save_recent_projects()
              self.status_bar.config(text="Liste des projets récents effacée.")

    # --- Export ---

    def export_measurements(self):
        """Exporte les mesures dans un format choisi par l'utilisateur."""
        if not self.measures:
            messagebox.showinfo("Export", "Aucune mesure à exporter.", parent=self.root)
            return

        export_type = self.ask_export_type()
        if not export_type:
            return # User cancelled type selection

        # Suggest filename based on PDF/Project name
        initial_filename = "mesures"
        if self.pdf_path:
             base = os.path.splitext(os.path.basename(self.pdf_path))[0]
             initial_filename = f"{base}_mesures"

        # File dialog based on type
        file_path = filedialog.asksaveasfilename(
            title=f"Exporter Mesures en {export_type.upper()}",
            defaultextension=f".{export_type}",
            filetypes=[(f"Fichiers {export_type.upper()}", f"*.{export_type}"), ("Tous les fichiers", "*.*")],
            initialfile=f"{initial_filename}.{export_type}",
            parent=self.root
        )

        if not file_path:
            return # User cancelled save dialog

        try:
            if export_type == "csv":
                self.export_to_csv(file_path)
            elif export_type == "txt":
                self.export_to_txt(file_path)
            elif export_type == "pdf":
                if REPORTLAB_AVAILABLE:
                     self.export_to_pdf_report(file_path)
                else:
                     messagebox.showerror("Dépendance Manquante", "La librairie 'reportlab' est nécessaire pour l'export PDF.\n\nVeuillez l'installer (pip install reportlab) et réessayer.", parent=self.root)
                     return # Stop export if library missing


            self.status_bar.config(text=f"Mesures exportées vers {os.path.basename(file_path)}")
            self.display_ai_message("system", f"Mesures exportées vers {os.path.basename(file_path)} au format {export_type.upper()}.")

        except Exception as e:
            messagebox.showerror("Erreur Export", f"Une erreur est survenue lors de l'exportation:\n{str(e)}", parent=self.root)


    def ask_export_type(self):
        """Demande le format d'export via une petite fenêtre."""
        dialog = tk.Toplevel(self.root)
        dialog.title("Format d'Export")
        dialog.geometry("250x220") # Adjusted height
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.configure(bg=self.colors["bg_light"])

        tk.Label(dialog, text="Choisissez le format:", font=("Arial", 11, "bold"), bg=self.colors["bg_light"]).pack(pady=(15, 10))

        choice = tk.StringVar(value=None) # Store result

        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10, fill=tk.X, padx=20)

        options = [("CSV (Tableur)", "csv"), ("TXT (Texte Simple)", "txt")]
        # Only offer PDF if reportlab is available
        if REPORTLAB_AVAILABLE:
             options.append(("PDF (Rapport)", "pdf"))

        for text, value in options:
            ttk.Button(button_frame, text=text, width=20,
                      command=lambda v=value: (choice.set(v), dialog.destroy())).pack(pady=4)

        ttk.Button(button_frame, text="Annuler", width=20, command=dialog.destroy).pack(pady=(10,4))

        # Bind Esc
        dialog.bind('<Escape>', lambda event=None: dialog.destroy())

        # Center and wait
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() // 2) - (dialog.winfo_width() // 2)
        y = self.root.winfo_y() + (self.root.winfo_height() // 3) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        self.root.wait_window(dialog)
        return choice.get()


    def export_to_csv(self, file_path):
        """Exporte les mesures vers un fichier CSV."""
        with open(file_path, 'w', newline='', encoding='utf-8-sig') as f: # utf-8-sig for Excel compatibility
            writer = csv.writer(f, delimiter=';') # Use semicolon for French Excel? Or comma? Let's use semicolon.

            # Header row
            headers = ["ID", "Type", "Valeur", "Unité/Symbole", "Page", "Catégorie Produit", "Nom Produit", "Dims Produit", "Prix Produit", "Couleur Produit"] # Added Color
            writer.writerow(headers)

            for i, measure in enumerate(self.measures, 1):
                m_type = measure.get("type", "").capitalize()
                m_display = measure.get("display_text", "")
                m_page = measure.get("page", -1) + 1

                # Separate value and unit/symbol from display_text
                value_str = m_display.split(' [')[0] # Remove product part first
                unit_symbol = ""
                numeric_part = value_str
                # Try to extract unit symbol
                parts = value_str.split()
                if len(parts) > 1:
                     last_part = parts[-1]
                     # Basic check for common units/symbols
                     if any(u in last_part for u in ['m²', 'cm²', 'mm²', 'ft²', 'in²', 'm', 'cm', 'mm', 'ft', 'in', '°', 'pt²', 'pt']):
                          unit_symbol = last_part
                          numeric_part = " ".join(parts[:-1])
                     # Handle P: prefix for perimeter
                     if numeric_part.startswith("P: "):
                          numeric_part = numeric_part[3:]

                # Ensure numeric part doesn't contain unit again
                if unit_symbol and numeric_part.endswith(unit_symbol):
                     numeric_part = numeric_part[:-len(unit_symbol)].strip()

                # Product info
                prod_cat = measure.get("product_category", "")
                prod_name = measure.get("product_name", "")
                prod_dims = ""
                prod_price = ""
                prod_color = measure.get("color", "") # Get measure color (from product)
                if prod_color is None: prod_color = "" # Ensure empty string if None

                if "product_attributes" in measure:
                    attrs = measure.get("product_attributes",{})
                    if attrs: # Check if attrs is not None
                        prod_dims = attrs.get("dimensions", "")
                        price_val = attrs.get("prix")
                        # Format price consistently for CSV, handle None
                        prod_price = f"{price_val:.2f}" if isinstance(price_val, (int, float)) else ""


                row_data = [
                    i, # Simple row number
                    m_type,
                    numeric_part.strip(),
                    unit_symbol,
                    m_page,
                    prod_cat,
                    prod_name,
                    prod_dims,
                    prod_price,
                    prod_color # Added color
                ]
                writer.writerow(row_data)


    def export_to_txt(self, file_path):
        """Exporte les mesures vers un fichier texte simple."""
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("="*60 + "\n")
            f.write(" RAPPORT DE MESURES - TakeOff AI\n")
            f.write("="*60 + "\n\n")
            f.write(f"Date Généré: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            if self.pdf_path:
                f.write(f"Document Source: {os.path.basename(self.pdf_path)}\n")
            if self.absolute_scale:
                 # Use the scale info display text
                 f.write(f"Échelle Utilisée: {self.scale_info.cget('text')}\n")
            else:
                 f.write("Échelle: Non définie (valeurs en points ou degrés)\n")
            f.write("\n" + "-"*60 + "\n\n")
            f.write("DÉTAIL DES MESURES:\n\n")

            for i, measure in enumerate(self.measures, 1):
                f.write(f"Mesure #{i}:\n")
                f.write(f"  Type        : {measure.get('type', 'N/A').capitalize()}\n")
                # Show value + unit/symbol (without product info here)
                value_part = measure.get('display_text', '').split(' [')[0]
                f.write(f"  Valeur      : {value_part}\n")
                f.write(f"  Page        : {measure.get('page', -1) + 1}\n")

                # Product info
                if measure.get("product_name"):
                    prod_color = measure.get("color", "")
                    if prod_color is None: prod_color = "N/A"
                    f.write(f"  Produit     : {measure['product_name']}\n")
                    f.write(f"  Catégorie   : {measure.get('product_category', 'N/A')}\n")
                    f.write(f"  Couleur     : {prod_color}\n") # Added color
                    attrs = measure.get("product_attributes",{})
                    if attrs: # Check if attrs is not None
                        f.write(f"  Dimensions  : {attrs.get('dimensions', 'N/A')}\n")
                        price_val = attrs.get('prix')
                        price_str = f"{price_val:.2f} $CAD" if isinstance(price_val, (int, float)) else "N/A"
                        f.write(f"  Prix Unit.  : {price_str}\n")
                f.write("-" * 20 + "\n") # Separator

            f.write("\n" + "="*60 + "\n")
            f.write(f"TOTAL MESURES: {len(self.measures)}\n")
            f.write("="*60 + "\n")


    def export_to_pdf_report(self, file_path):
        """Exporte un rapport PDF résumé des mesures."""
        # This function relies on REPORTLAB_AVAILABLE check in export_measurements

        doc = SimpleDocTemplate(file_path, pagesize=landscape(letter),
                                leftMargin=0.5*inch, rightMargin=0.5*inch,
                                topMargin=0.75*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        story = []

        # --- Title ---
        title_style = styles['h1']
        title_style.alignment = 1 # Center
        title_style.textColor = colors.HexColor(self.colors["primary"])
        story.append(Paragraph("Rapport de Mesures - TakeOff AI", title_style))
        story.append(Spacer(1, 0.2*inch))

        # --- Document Info ---
        info_style = styles['Normal']
        info_lines = [
            f"<b>Date Généré:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        ]
        if self.pdf_path:
             info_lines.append(f"<b>Document Source:</b> {os.path.basename(self.pdf_path)}")
        if self.absolute_scale:
             info_lines.append(f"<b>Échelle Utilisée:</b> {self.scale_info.cget('text')}")
        else:
             info_lines.append("<b>Échelle:</b> Non définie")

        for line in info_lines:
            story.append(Paragraph(line, info_style))
        story.append(Spacer(1, 0.25*inch))


        # --- Table Data ---
        # Header
        header = ["#", "Type", "Valeur", "Unité/Symbole", "Page", "Produit", "Catégorie", "Dims", "Prix ($)", "Couleur"] # Added Color
        data = [header]

        # Rows
        for i, measure in enumerate(self.measures, 1):
            m_type = measure.get("type", "").capitalize()
            m_display = measure.get("display_text", "")
            m_page = measure.get("page", -1) + 1

            value_str = m_display.split(' [')[0]
            unit_symbol = ""
            numeric_part = value_str
            parts = value_str.split()
            if len(parts) > 1:
                 last_part = parts[-1]
                 # Ajustement pour m²/ft²/etc.
                 if any(u in last_part for u in ['m²', 'cm²', 'mm²', 'ft²', 'in²', 'm', 'cm', 'mm', 'ft', 'in', '°', 'pt²', 'pt']):
                      unit_symbol = last_part
                      numeric_part = " ".join(parts[:-1])
                 if numeric_part.startswith("P: "):
                      numeric_part = numeric_part[3:]

            # Ensure numeric part doesn't contain unit again
            if unit_symbol and numeric_part.endswith(unit_symbol):
                 numeric_part = numeric_part[:-len(unit_symbol)].strip()


            prod_cat = measure.get("product_category", "")
            prod_name = measure.get("product_name", "")
            prod_dims = ""
            prod_price = ""
            prod_color = measure.get("color", "") # Get color
            if prod_color is None: prod_color = "" # Ensure empty string

            attrs = measure.get("product_attributes",{})
            if attrs: # Check if attrs is not None
                prod_dims = attrs.get("dimensions", "")
                price_val = attrs.get("prix")
                prod_price = f"{price_val:.2f}" if isinstance(price_val, (int, float)) else ""

            row = [
                str(i), m_type, numeric_part.strip(), unit_symbol, str(m_page),
                prod_name, prod_cat, prod_dims, prod_price, prod_color # Added color
            ]
            data.append(row)

        # --- Create Table ---
        if len(data) > 1: # Only create table if there are measures
             # Adjusted colWidths to make space for Color column
             table = Table(data, colWidths=[0.4*inch, 0.7*inch, 1.0*inch, 0.7*inch, 0.4*inch, 1.3*inch, 1.0*inch, 0.9*inch, 0.7*inch, 0.7*inch])

             # --- Table Style ---
             style = TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#D0D0D0")), # Header background
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'), # Default center
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('ALIGN', (2, 1), (2, -1), 'RIGHT'), # Value right align
                ('ALIGN', (3, 1), (3, -1), 'LEFT'), # Unit left align
                ('ALIGN', (5, 1), (7, -1), 'LEFT'), # Product info left align
                ('ALIGN', (8, 1), (8, -1), 'RIGHT'), # Price right align
                ('ALIGN', (9, 1), (9, -1), 'LEFT'), # Color left align
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('TOPPADDING', (0, 1), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
                ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
             ])
             # Apply alternating row colors
             for i in range(1, len(data)):
                  if i % 2 == 0:
                       style.add('BACKGROUND', (0, i), (-1, i), colors.HexColor("#EFEFEF"))

             table.setStyle(style)
             story.append(table)
        else:
            story.append(Paragraph("Aucune mesure à afficher.", styles['Normal']))


        # --- Build PDF ---
        # Add page numbers (using a canvasmaker)
        def add_page_number(canvas, doc):
            page_num = canvas.getPageNumber()
            text = f"Page {page_num}"
            canvas.saveState()
            canvas.setFont('Helvetica', 8)
            canvas.setFillColor(colors.grey)
            canvas.drawRightString(doc.pagesize[0] - doc.rightMargin, 0.3*inch, text) # Position at bottom right
            canvas.restoreState()

        doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)


    # --- Help & About ---

    def show_help(self):
        """Affiche une fenêtre d'aide simple."""
        help_content = """
GUIDE RAPIDE - TakeOff AI (v1.1 - Totaux Produits)

1.  **Ouvrir**: Fichier > Ouvrir PDF (Ctrl+O) / Ouvrir Projet (Ctrl+P).
2.  **Naviguer**: Boutons Préc/Suiv, Molette/Ctrl+/- (Zoom), Ctrl+0 (Ajuster). Bouton Milieu/Droit + Glisser (Panoramique).
3.  **Calibrer (Important!)**: Outils > Calibrer Échelle (F4). Cliquez 2 pts connus, entrez la distance réelle.
4.  **Mesurer**:
    *   Sélectionnez le mode (Distance F2, Surface F3, Périmètre F6, Angle F7).
    *   Cliquez les points sur le plan.
    *   **Snapping**: Activé par défaut (Config > Accrochage). Pointe vers lignes/points proches.
    *   **Ortho**: Maintenir [Shift] pour contraindre horizontal/vertical.
    *   **Finaliser Surface/Périmètre**: Double-clic ou touche [Entrée] ou bouton '✓ Terminer'.
    *   **Annuler Mesure en Cours**: Touche [Échap].
5.  **Mesures**: Onglet 'Mesures'. Liste des mesures individuelles. Sélectionnez pour surligner sur le plan. Sélectionnez + [Suppr] pour effacer.
6.  **Catalogue**: Onglet 'Catalogue Produits'. Gérez vos produits/prix/couleurs. Associez-les aux mesures après création (si demandé). La couleur du produit sera appliquée à la mesure. Sauvegarde automatique à la fermeture.
7.  **Résumé Produits**: Nouvel onglet 'Résumé Produits'. Affiche les totaux de longueurs et surfaces cumulées pour chaque produit associé aux mesures (nécessite une échelle calibrée).
8.  **Sauvegarder**: Fichier > Enregistrer Projet (Ctrl+S). Sauvegarde PDF lié, mesures, échelle, catalogue actuel, config.
9.  **Exporter**: Fichier > Exporter Mesures (Ctrl+E). Choix CSV, TXT, PDF (si ReportLab installé). Exporte la liste détaillée des mesures.
10. **IA**: Panneau à droite. Posez des questions. Bouton 'Analyser' (F5) pour résumé du PDF et suggestions. Gérez les profils experts via Outils.
11. **Config**: Changez unités, couleurs par défaut, options d'accrochage.

**Conseil**: Calibrez l'échelle avant de faire des mesures significatives pour voir les totaux corrects !
        """
        messagebox.showinfo("Aide - TakeOff AI", help_content, parent=self.root)

    def show_about(self):
        """Affiche la fenêtre À Propos."""
        about_text = f"""
        TakeOff AI - Version 1.1 (Totaux Produits)

        Logiciel de métré sur PDF avec assistance IA.

        Fonctionnalités :
        - Visualisation PDF et navigation
        - Mesures: Distance, Surface, Périmètre, Angle
        - Calibration d'échelle (unités/point PDF)
        - Accrochage aux lignes (Snapping) & Mode Ortho
        - Catalogue produits (avec couleurs) & Association
        - **Nouveau**: Résumé des totaux par produit
        - Export CSV, TXT, PDF
        - Assistant IA
        - Gestion de projets (.tak)
        - Surlignage de la mesure sélectionnée
        - Coloration des mesures par produit

        Développé par: Sylvain Leduc

        © {datetime.now().year}
        """
        messagebox.showinfo("À Propos de TakeOff AI", about_text, parent=self.root)

    # --- Closing Handler ---
    def on_closing(self):
        """Actions à effectuer avant de fermer."""
        print("[DEBUG] Fermeture de l'application...")

        # --- MODIFICATION: Sauvegarde Catalogue si modifié ---
        if hasattr(self, 'product_catalog') and self.product_catalog.is_dirty:
             print("[DEBUG] Sauvegarde du catalogue avant fermeture...")
             if not self.product_catalog.save_catalog_to_appdata():
                  # Error already printed in save function, maybe inform user?
                  messagebox.showwarning("Erreur Catalogue", "Le catalogue modifié n'a pas pu être sauvegardé automatiquement.", parent=self.root)


        # Sauvegarder les projets récents
        if hasattr(self, 'recent_projects'):
             print("[DEBUG] Sauvegarde des projets récents...")
             self.save_recent_projects()

        # Add confirmation for unsaved project maybe?
        # This would require tracking project state (e.g., self.project_is_dirty flag)
        # if self.is_project_dirty():
        #    if not messagebox.askyesno("Quitter", "Projet non enregistré. Quitter quand même?"):
        #         return # Abort closing

        print("[DEBUG] Destruction de la fenêtre principale.")
        # Close PDF document gracefully if open
        if self.pdf_document:
             try:
                  self.pdf_document.close()
                  self.pdf_document = None
             except Exception as e:
                  print(f"Erreur lors de la fermeture du document PDF: {e}")

        self.root.destroy()


# --- Main Execution ---

def main():
    # Force high DPI awareness on Windows (optional, might improve scaling)
    if os.name == 'nt':
        try:
            from ctypes import windll
            windll.shcore.SetProcessDpiAwareness(1) # Needs Windows 8.1+
        except Exception as e:
            print(f"Could not set DPI awareness: {e}")

    root = tk.Tk()

    app = MetrePDFApp(root)

    root.mainloop()


if __name__ == "__main__":
    # Ensure AppData path exists early (might be needed by initializers)
    app_data_dir = get_app_data_path()
    print(f"Dossier de données de l'application: {app_data_dir}")
    main()

# --- END OF FILE takeoff_with_totals.py ---