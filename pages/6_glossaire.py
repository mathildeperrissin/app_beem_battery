import streamlit as st

st.set_page_config(page_title="Glossaire Data", layout="wide")
st.title("📚 Glossaire des pages et sources de données")

markdown_text = """
### 🧭 **Page : Data explo**

### 🔗 **Sources de données**

1. **Informations batteries et utilisateurs**
    - **Source** : BOB (base PostgreSQL transférée vers BigQuery via Airbyte)
    - **fréquence de mise à jour :** tous les jours à 04:00
    - **Tables utilisées** :
        - `battery_device`
        - `battery_live_data`
        - `house_user`
        - `user`
        - `house`
    - **Méthode de traitement** :
        - Jointures multiples pour enrichir les informations liées à un `device_id`
        - Filtres appliqués :
            - `deleted_at IS NULL`, `replaced_by_id IS NULL`, `warranty_status = 'activated'`
            - Exclusion de certains `serial_number`
            - Exclusion des emails internes Beem (`@beemenergy`)
            - En cas de doublons sur le `serial_number`, seuls les emails clients sont conservés
    - **Champs clés utilisés** :
        - `serial_number`, `lastname`, `device_id`, `hardware_version`, `nb_modules`, `nb_cycles`, `global_soh`, `created_at`

2. **Mesures énergétiques**
    - **Source** : MongoDB (chargée dans BigQuery via connecteur interne de l’équipe dev)
    - **fréquence de mise à jour :**
    - **Tables utilisées** :
        - `battery_active_energy_measure` : **Consommation infra-journalière** (Wh par batterie)
        - `battery_active_returned_energy_meter_measure` : **Réinjection infra-journalière** (Wh par batterie)
        - `battery_active_returned_energy_measure` : **Production solaire (somme MPPT)** (Wh total)
        - `battery_energy_charged_measure` : **Énergie stockée** (Wh)
        - `battery_energy_discharged_measure` : **Énergie déstockée** (Wh)
    - **Méthode de traitement** :
        - Requête filtrée par `deviceId` et plage temporelle sélectionnée par l’utilisateur
        - Agrégation sur `device_id` et `device_sub_id` uniquement pour la production solaire
    - **Unité** : Wattheure (**Wh**)

3. **Logs techniques (faults et warnings)**
    - **Source** : BOB (base PostgreSQL transférée vers BigQuery via Airbyte)
    - **fréquence de mise à jour :** tous les jours à 04:00
    - **Table utilisée** : `battery_device_log`
    - **Champs exploités** :
        - `date`, `type`, `message`, `cleared`, `cleared_at`, `cleared_by`
    - **Méthode de traitement** :
        - Filtrage par `battery_id` et période temporelle
        - Visualisation en :
            - Graphique temporel avec repères
            - Tableau filtrable par type de log
            - Histogramme récapitulatif des types/messages les plus fréquents

---

### 🧭 **Page : Data comparaison**

### 🔗 **Sources de données**

1. **Informations batteries et utilisateurs**
    - **Source** : BOB (base PostgreSQL transférée vers BigQuery via Airbyte)
    - **fréquence de mise à jour :** tous les jours à 04:00
    - **Tables utilisées** :
        - `battery_device`
        - `battery_live_data`
        - `house_user`
        - `user`
        - `house`
    - **Méthode de traitement** :
        - Jointures pour enrichir chaque batterie avec ses données techniques et son utilisateur
        - Filtres appliqués :
            - `deleted_at IS NULL`, `replaced_by_id IS NULL`, `warranty_status = 'activated'`
            - Exclusion de certains `serial_number` et des comptes internes Beem (`@beemenergy`)
            - En cas de `serial_number` dupliqué, conservation uniquement des clients finaux
    - **Champs affichés** :
        - `hardware_version`, `created_at`, `nb_cycles`, `nb_modules`, `global_soh`

2. **Mesures énergétiques**
    - **Source** : MongoDB (chargée dans BigQuery via connecteur interne de l’équipe dev)
    - **fréquence de mise à jour :**
    - **Tables utilisées** :
        - `battery_active_energy_measure` → **Consommation infra-journalière** (Wh)
        - `battery_active_returned_energy_measure` → **Production solaire** (Wh)
        - `battery_active_returned_energy_meter_measure` → **Réinjection infra-journalière** (Wh)
        - `battery_energy_charged_measure` → **Énergie stockée** (Wh)
        - `battery_energy_discharged_measure` → **Énergie déstockée** (Wh)
    - **Méthode de traitement** :
        - Chargement pour chaque `device_id` sur la période choisie
        - Visualisation comparative (courbe combinée et détails séparés)
    - **Unité** : Wattheure (**Wh**)

---

### 📊 **Fonctionnalités affichées**

- Sélection de **deux batteries** à comparer, via le `serial_number`
- Affichage des **caractéristiques techniques** : version HW, mise en service, SOH, etc.
- **Filtrage temporel commun** aux deux batteries
- Graphique combiné de toutes les mesures sélectionnées
- Graphiques séparés par mesure pour chaque batterie

---

### 🧭 **Page : Performance battery**

### 🔗 **Sources de données**

1. **Informations batteries et utilisateurs**
    - **Source** : BOB (base PostgreSQL transférée vers BigQuery via Airbyte)
    - **fréquence de mise à jour :** tous les jours à 04:00
    - **Tables utilisées** :
        - `battery_device`
        - `battery_live_data`
        - `house_user`
        - `user`
        - `house`
    - **Méthode** :
        - Jointures pour enrichir les métadonnées batterie/utilisateur
        - Filtres : batteries actives, non remplacées, email client uniquement
    - **Champs utilisés** :
        - `serial_number`, `device_id`, `created_at`, `hardware_version`, `nb_modules`, `nb_cycles`, `global_soh`

2. **Données énergétiques journalières**
    - **Sources** :
        - **Avant mai 2025** : `mongo_beem` (MongoDB transféré via fivetran)
        - **Depuis mai 2025** : `mongodb` (chargée dans BigQuery via connecteur interne de l’équipe dev)
    - **fréquence de mise à jour :**
    - **Tables utilisées** :
        - `battery_active_energy_measure` → **Consommation** (Wh)
        - `battery_active_returned_energy_meter_measure` → **Réinjection** (Wh)
        - `battery_active_returned_energy_measure` → **Production** (Wh)
        - `battery_energy_charged_measure` → **Énergie stockée** (Wh)
        - `battery_energy_discharged_measure` → **Énergie déstockée** (Wh)
    - **Méthode** :
        - Agrégation journalière puis mensuelle via `SUM(value)`
        - Jointures FULL OUTER pour combiner toutes les sources
    - **Unité** : Wattheure (**Wh**)

---

### 📐 **Calculs & Méthodes**

- **Taux d'autonomie (%)** :
    `(production - injection) / (production + consommation - injection) * 100`
    
- **Taux d'autoconsommation (%)** :
    `(production - injection) / production * 100`

---

### 📊 **Fonctionnalités proposées**

- Sélection batterie par nom / numéro de série
- Affichage des caractéristiques techniques
- Comparaison **objectif vs production réelle**
- Visualisation **mensuelle** et **quotidienne** de :
    - Production
    - Consommation
    - Injection
- Tableau des **taux mensuels**
- Calcul dynamique des taux **sur une période personnalisée**

---

### 🧭 **Page : Débug data**

### 🔗 **Sources de données**

1. **Liste des numéros de série**
    - **Source** : BOB (base PostgreSQL transférée vers BigQuery via Airbyte)
    - **fréquence de mise à jour :** tous les jours à 04:00
    - **Table utilisée** : `battery_device`
    - **Méthode** :
        - Filtrage sur batteries actives, non remplacées et sous garantie
        - Exclusion manuelle de certains numéros de série

2. **Fichiers JSON techniques (logs horodatés)**
    - **Source** : Google Cloud Storage (GCS)
        - Bucket principal : `beem-backend-battery-warranty`
        - Index GCS complémentaire : `beem-battery-indexes`
    - **fréquence de mise à jour :**
    - **Méthode d'accès** :
        - Si date < **21/07/2025** → accès via **index JSON**
        - Si date > **23/07/2025** → accès via **arborescence GCS**
        - Si date entre le **21 et 23/07/2025** → essai d’arborescence puis fallback index
    - **Contenu des fichiers** :
        - Chaque fichier est un snapshot des debug data horodatées
        - Les données sont stockées sous une clé `"data"` dans un format JSON
        - Le nombre et les noms d’index peuvent varier selon la version de la batterie
        - Pour les batteries V1 les fichiers contiennent **350 données dont on connait partiellement les intitulés**

---

### 📐 **Traitement et affichage**

- Fichiers filtrés selon une plage horaire :
    - Plage **automatique** (−15 min / +5 min autour du bug)
    - Ou **plage manuelle**
- Conversion en DataFrame avec colonne `date` + colonnes dynamiques
- Si **350 colonnes** → renommage avec la liste d’index connue (batteries V1)
- Sinon → noms par défaut : `Index 0`, `Index 1`, etc.

---

### 📊 **Fonctionnalités**

- Sélection d’un numéro de série
- Choix de date et heure du bug
- Chargement automatique ou manuel
- Visualisation :
    - Tableau des données
    - Graphiques individuels (ligne rouge = heure du bug)
"""

st.markdown(markdown_text)
