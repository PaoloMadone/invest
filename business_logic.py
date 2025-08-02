"""
Logique métier de l'application d'investissement
"""
import math
from datetime import date
from typing import Dict, List, Tuple

def calculer_investissements_automatiques(revenu_net: float) -> Tuple[float, float]:
    """
    Calcule automatiquement les montants d'investissement bourse et crypto
    
    Args:
        revenu_net: Montant du revenu net mensuel
        
    Returns:
        Tuple (investissement_bourse, investissement_crypto)
    """
    montant_investissement_bourse = round(revenu_net * 0.10, 2)
    montant_investissement_crypto = round(revenu_net * 0.10, 2)
    return montant_investissement_bourse, montant_investissement_crypto

def verifier_periode_existante(revenus: List[Dict], periode: str) -> bool:
    """
    Vérifie si une période existe déjà dans les revenus
    
    Args:
        revenus: Liste des revenus existants
        periode: Période à vérifier (format "YYYY-MM")
        
    Returns:
        True si la période existe déjà, False sinon
    """
    return any(r["periode"] == periode for r in revenus)

def creer_periode(annee: int, mois: int) -> str:
    """
    Crée une chaîne de période au format YYYY-MM
    
    Args:
        annee: Année
        mois: Mois (1-12)
        
    Returns:
        Période formatée
    """
    return f"{annee}-{mois:02d}"

def calculer_quantite_investissement(montant: float, prix_unitaire: float) -> float:
    """
    Calcule la quantité d'un investissement
    
    Args:
        montant: Montant investi
        prix_unitaire: Prix unitaire de l'actif
        
    Returns:
        Quantité calculée
    """
    if prix_unitaire <= 0:
        raise ValueError("Le prix unitaire doit être supérieur à 0")
    return montant / prix_unitaire

def calculer_budget_disponible(revenus: List[Dict]) -> Tuple[int, int, int]:
    """
    Calcule les budgets disponibles pour les investissements
    
    Args:
        revenus: Liste des revenus
        
    Returns:
        Tuple (budget_bourse, budget_crypto, budget_total)
    """
    budget_bourse_brut = sum([r["investissement_disponible_bourse"] for r in revenus])
    budget_crypto_brut = sum([r["investissement_disponible_crypto"] for r in revenus])
    
    budget_bourse = math.ceil(budget_bourse_brut)
    budget_crypto = math.ceil(budget_crypto_brut)
    budget_total = budget_bourse + budget_crypto
    
    return budget_bourse, budget_crypto, budget_total

def calculer_budget_utilise(investissements: List[Dict]) -> Tuple[float, float]:
    """
    Calcule le budget utilisé (hors investissements hors budget)
    
    Args:
        investissements: Liste des investissements
        
    Returns:
        Tuple (budget_utilise, total_investi)
    """
    budget_utilise = sum([i["montant"] for i in investissements if not i.get("hors_budget", False)])
    total_investi = sum([i["montant"] for i in investissements])
    
    return budget_utilise, total_investi

def calculer_budget_restant(budget_disponible: float, budget_utilise: float) -> float:
    """
    Calcule le budget restant
    
    Args:
        budget_disponible: Budget total disponible
        budget_utilise: Budget déjà utilisé
        
    Returns:
        Budget restant
    """
    return budget_disponible - budget_utilise

def valider_donnees_revenu(revenu_net: float, mois: int, annee: int) -> List[str]:
    """
    Valide les données d'un revenu
    
    Args:
        revenu_net: Montant du revenu net
        mois: Mois (1-12)
        annee: Année
        
    Returns:
        Liste des erreurs de validation (vide si valide)
    """
    erreurs = []
    
    if revenu_net <= 0:
        erreurs.append("Le revenu net doit être supérieur à 0")
    
    if mois < 1 or mois > 12:
        erreurs.append("Le mois doit être entre 1 et 12")
    
    if annee < 2020 or annee > 2030:
        erreurs.append("L'année doit être entre 2020 et 2030")
    
    return erreurs

def valider_donnees_investissement(montant: float, prix_unitaire: float, symbole: str) -> List[str]:
    """
    Valide les données d'un investissement
    
    Args:
        montant: Montant de l'investissement
        prix_unitaire: Prix unitaire
        symbole: Symbole de l'actif
        
    Returns:
        Liste des erreurs de validation (vide si valide)
    """
    erreurs = []
    
    if montant <= 0:
        erreurs.append("Le montant doit être supérieur à 0")
    
    if prix_unitaire <= 0:
        erreurs.append("Le prix unitaire doit être supérieur à 0")
    
    if not symbole or not symbole.strip():
        erreurs.append("Le symbole est obligatoire")
    
    return erreurs

def creer_donnees_revenu(mois: int, annee: int, montant: float) -> Dict:
    """
    Crée un dictionnaire de données pour un revenu
    
    Args:
        mois: Mois
        annee: Année  
        montant: Montant du revenu
        
    Returns:
        Dictionnaire des données du revenu
    """
    periode = creer_periode(annee, mois)
    inv_bourse, inv_crypto = calculer_investissements_automatiques(montant)
    
    return {
        "mois": mois,
        "annee": int(annee),
        "periode": periode,
        "montant": montant,
        "investissement_disponible_bourse": inv_bourse,
        "investissement_disponible_crypto": inv_crypto
    }

def creer_donnees_investissement(date_achat: str, symbole: str, montant: float, 
                                prix_unitaire: float, hors_budget: bool = False) -> Dict:
    """
    Crée un dictionnaire de données pour un investissement
    
    Args:
        date_achat: Date d'achat (format ISO)
        symbole: Symbole de l'actif
        montant: Montant investi
        prix_unitaire: Prix unitaire
        hors_budget: Si l'investissement est hors budget
        
    Returns:
        Dictionnaire des données de l'investissement
    """
    quantite = calculer_quantite_investissement(montant, prix_unitaire)
    
    return {
        "date": date_achat,
        "symbole": symbole.upper(),
        "montant": montant,
        "prix_unitaire": prix_unitaire,
        "quantite": quantite,
        "hors_budget": hors_budget
    }